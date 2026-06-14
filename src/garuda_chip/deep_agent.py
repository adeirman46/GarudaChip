"""
GarudaChip Deep Agents — every LLM node is a Recursive-Language-Model-style
(RLM) deep agent, driven ENTIRELY by the local Ollama model (qwen3.5:9b).

The MIT "Recursive Language Models" idea (arXiv:2512.24601) applied here:
treat the big stuff (reference designs, error logs, the existing RTL) as an
*environment on disk* — NOT as one giant prompt. The root agent keeps its own
window SMALL: it PEEKS at slices (`read_file_disk` with line ranges, `grep_files`)
and DELEGATES focused sub-tasks to fresh sub-LLM calls (`llm_query`) or full
sub-agents (the built-in `task` tool). It builds the answer up in files, then
returns it. This is why a 9B local model can handle large designs: it never has
to hold everything at once.

The model is ALWAYS get_chat_model() (Ollama). deepagents' Anthropic default
(get_default_model) is never used because we pass `model=` explicitly.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

from langchain_core.tools import tool
from deepagents import create_deep_agent

from llm import get_chat_model

PITFALLS = (
    "Write synthesizable Verilog-2001. Avoid these classic mistakes: "
    "(1) to reset an unpacked array `reg [W-1:0] mem [0:N-1]` use a for-loop, never "
    "`mem <= 0` or `mem <= {N{...}}`; (2) replication needs double braces `{4{8'd0}}`, "
    "never `4{8'd0}`; (3) one driver per signal — never assign a reg from two `always` "
    "blocks; (4) a signal assigned in `always` must be `reg`/`output reg`, declared once."
)

# RLM-style operating contract shared by every deep-agent node. Each pipeline
# node ALSO gets a specific goal (the user message); this is the standing
# behaviour: keep context small, peek, delegate, build up in files, verify.
INSTRUCTIONS = f"""You are a GarudaChip Verilog/SoC engineer agent operating as a
Recursive Language Model (RLM): you keep your OWN context small and treat large
inputs as an environment on disk.

You manage REAL files for one chip design with your file tools — `list_files`,
`read_file_disk` (reads a SLICE: pass start_line/max_lines), `write_file_disk`,
`delete_file_disk`, and `grep_files` (regex-probe across files). RTL lives under
`rtl/`, testbenches under `tb/`, offloaded context under `context/`.

How to work (RLM loop):
1. PEEK, don't swallow. For anything big (references, error logs, existing RTL),
   `grep_files` for the relevant lines or `read_file_disk` a slice — never assume
   you must read a whole file to act.
2. DELEGATE focused sub-tasks. Use `llm_query(prompt)` to summarize/extract/classify
   a slice, or to draft ONE small module — give it a self-contained prompt with just
   the slice it needs, so YOUR window stays small. Use the `task` tool for a heavier
   sub-job. Do NOT over-delegate: batch related work into one call.
3. BUILD UP in files. Write intermediate and final RTL to `rtl/<module>.v` with
   `write_file_disk` instead of holding it all in your reply.
4. Use `write_todos` to plan multi-step work and track progress.
5. PYTHON IS A LAST-RESORT DATA TOOL — NOT a deliverable. Most designs (CPU, ALU, FSM,
   regfile, datapath, controller) need NO Python at all; write them straight as RTL.
   Reach for `run_python` ONLY when the hardware is genuinely DATA-DRIVEN and the data
   needs real computation:
     • LINEARIZE/quantize a math function into a LUT (relu, softmax, sigmoid, sin/cos,
       reciprocal) — numpy;
     • TRAIN or derive NN weights/filter taps to bake into the chip — numpy/torch;
     • a C/C++/C reference KERNEL to cross-check a low-level datapath against.
   When you do, use `run_python` to EMIT the result — QUANTIZE to the right format
   (signed/unsigned int, or Qm.n fixed-point) and WRITE a `rtl/<name>.mem` loaded by
   `$readmemh`/`$readmemb`, or print constants to bake into the RTL. The Python is a
   throw-away generator: do NOT leave a `*.py` script in `rtl/` as part of the design.
   (`run_python` is also fine for reading an attached PDF/image with pypdf/pillow.)
   If the math is just arithmetic the RTL already does, skip Python entirely.
6. VERIFY before finishing — re-read what you wrote and check it against the rules.
- {PITFALLS}
- Before editing a file, read it first. After writing, confirm the file path.
"""


# Per-file last compile error during a write (path -> (error, broken_content)), so when a
# file goes broken→clean we can persist the error→fix lesson. Module-level so it survives
# across write_file_disk calls within a generation step.
_LAST_WRITE_ERR: dict = {}


def _save_gen_fix_lesson(err: str, broken: str, fixed: str, design: str) -> None:
    """Persist a fix made DURING generation to the knowledge DB (kind='fix'), with a stable
    id by error signature so it dedupes. This is what makes EVERY problem solved while
    working in chat get saved — not just corrector-stage fixes."""
    try:
        import re as _re
        import hashlib
        from memory_store import get_memory
        mem = get_memory()
        if not getattr(mem, "enabled", False):
            return
        # concise signature = the first real error message line
        sigline = next((ln for ln in (err or "").splitlines()
                        if "error" in ln.lower() or "warning" in ln.lower()), err[:80])
        sig = _re.sub(r"^.*?:\s*\d+:?\s*", "", sigline).strip()[:120] or "verilog error"
        body = (f"ERROR SIGNATURE: {sig}\n\nSYMPTOM:\n{err[:600]}\n\n"
                f"BROKEN (do NOT write this):\n```verilog\n{broken[:1200]}\n```\n\n"
                f"CORRECT FIX:\n```verilog\n{fixed[:1600]}\n```\n")
        rid = "fix_" + hashlib.sha1(sig.lower().encode()).hexdigest()[:16]
        mem.remember("fix", body, design=design, source="auto-fix:generation",
                     title=("fix: " + sig)[:120], tags="fix lesson generation",
                     object_key=rid, meta={"error_sig": sig})
    except Exception:  # noqa: BLE001
        pass


def make_fs_tools(base_dir: str | Path) -> List:
    """Real on-disk file tools, sandboxed to `base_dir` (the design directory).
    Reads are SLICED (RLM 'peek') and there is a regex `grep_files` so an agent can
    probe a large context without loading it whole — the key to keeping the local
    model's window small."""
    base = Path(base_dir).resolve()

    def _resolve(path: str) -> Path:
        p = (base / (path or "")).resolve()
        if p != base and base not in p.parents:
            raise ValueError(f"path '{path}' escapes the design directory")
        return p

    @tool
    def list_files(subdir: str = "") -> str:
        """List files under the design directory. Optionally pass a subdir like 'rtl' or 'tb'."""
        d = _resolve(subdir)
        if not d.exists():
            return f"(no such path: {subdir or '.'})"
        if d.is_file():
            return str(d.relative_to(base))
        files = [str(p.relative_to(base)) for p in sorted(d.rglob("*"))
                 if p.is_file() and "chip/runs" not in str(p.relative_to(base))]
        return "\n".join(files) or "(empty)"

    @tool
    def read_file_disk(path: str, start_line: int = 1, max_lines: int = 250) -> str:
        """Read a SLICE of a text file under the design dir, e.g. 'rtl/cpu.v'.
        Returns a header (total lines/chars) then lines [start_line, start_line+max_lines).
        PEEK at big files in slices instead of reading them whole — keeps context small."""
        p = _resolve(path)
        if not p.exists() or not p.is_file():
            return f"(not found: {path})"
        text = p.read_text()
        lines = text.splitlines()
        n = len(lines)
        start = max(1, int(start_line))
        end = min(n, start - 1 + max(1, int(max_lines)))
        body = "\n".join(lines[start - 1:end]) if n else ""
        more = "" if end >= n else f"\n… ({n - end} more lines — read from line {end + 1} to continue)"
        return (f"# {path} — {n} lines, {len(text)} chars; showing {start}-{end}\n{body}{more}")[:20000]

    @tool
    def grep_files(pattern: str, subdir: str = "") -> str:
        """Regex-search the design files (optionally within a subdir like 'rtl' or
        'context'). Returns up to 60 matching 'path:line: text' rows. Use this to
        PROBE a large context (references, error logs, RTL) instead of reading whole
        files — the fastest way to find the lines you actually need."""
        try:
            rx = re.compile(pattern, re.IGNORECASE)
        except re.error as e:
            return f"(bad regex: {e})"
        d = _resolve(subdir)
        roots = [d] if d.exists() else []
        hits: List[str] = []
        for root in roots:
            paths = [root] if root.is_file() else sorted(
                p for p in root.rglob("*")
                if p.is_file() and "chip/runs" not in str(p) and p.suffix in
                (".v", ".vh", ".sv", ".svh", ".md", ".log", ".txt", ".json"))
            for p in paths:
                try:
                    for i, line in enumerate(p.read_text().splitlines(), 1):
                        if rx.search(line):
                            hits.append(f"{p.relative_to(base)}:{i}: {line.strip()[:160]}")
                            if len(hits) >= 60:
                                return "\n".join(hits) + "\n… (truncated at 60 matches)"
                except Exception:  # noqa: BLE001
                    continue
        return "\n".join(hits) or f"(no matches for /{pattern}/)"

    @tool
    def write_file_disk(path: str, content: str) -> str:
        """Create or OVERWRITE a file under the design dir, e.g. 'rtl/alu.v'. Use this to
        save new or updated Verilog. Verilog files are AUTO-REPAIRED (obvious syntax tics)
        and COMPILE-CHECKED on write: if the result says COMPILE ERRORS, fix the file and
        write it again before moving on."""
        p = _resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        fixnote = ""
        if p.suffix in (".v", ".sv", ".vh"):
            try:
                from verilog_check import autofix_text
                content, notes = autofix_text(content)
                if notes:
                    fixnote = " · auto-repaired: " + "; ".join(notes)
            except Exception:  # noqa: BLE001
                pass
        p.write_text(content)
        note = f"wrote {path} ({len(content)} bytes){fixnote}"
        # Instant feedback loop: a syntax/elaboration error surfaces in THIS tool result,
        # so the agent fixes the file now — not 10 modules later at simulation time.
        if p.suffix in (".v", ".sv"):
            # testbenches check fine too: -i ignores the missing DUT, syntax still caught
            try:
                from verilog_check import check_file
                err = check_file(p, base / "rtl")
                if err:
                    _LAST_WRITE_ERR[str(p)] = (err, content)   # remember for the fix-lesson
                    return (f"{note}\nCOMPILE ERRORS — fix this file and write it again "
                            f"NOW (do not move to the next module):\n{err}")
                # broken→clean during GENERATION = a real fix → save the lesson to the
                # knowledge DB (pg/MinIO) so the same mistake isn't repeated next run.
                prev = _LAST_WRITE_ERR.pop(str(p), None)
                if prev:
                    _save_gen_fix_lesson(prev[0], prev[1], content, base.name)
                return f"{note} — compile check clean ✓"
            except Exception:  # noqa: BLE001
                pass
        return note

    @tool
    def delete_file_disk(path: str) -> str:
        """Delete a file under the design dir, e.g. 'rtl/shared_header.vh'."""
        p = _resolve(path)
        if p.exists() and p.is_file():
            p.unlink()
            return f"deleted {path}"
        return f"(not found: {path})"

    return [list_files, read_file_disk, grep_files, write_file_disk, delete_file_disk]


def make_rlm_tools(temperature: float = 0.2, model=None) -> List:
    """The RLM recursion primitive: `llm_query`, a single fresh local-LLM call the
    root agent uses to DELEGATE a focused sub-task (summarize/extract/classify a
    slice, or draft one small module) so its own context stays small. Pairs with the
    built-in `task` tool (heavier sub-agent delegation) that deepagents always adds."""

    @tool
    def llm_query(prompt: str) -> str:
        """Delegate a focused sub-task to a fresh local LLM call and return its answer.
        Give a SELF-CONTAINED prompt (include the exact slice of context to process):
        e.g. 'Summarize the ports of this module: <code>' or 'Write an 8-bit adder
        module named add8'. Use this to keep YOUR own context small. Batch related
        work into one call — do not call it per line."""
        m = model or get_chat_model(temperature=temperature)
        try:
            out = m.invoke(prompt)
            text = getattr(out, "content", None)
            if not text:
                text = str(out)
        except Exception as e:  # noqa: BLE001
            return f"(llm_query failed: {e})"
        return text[:6000]

    return [llm_query]


def make_python_tools(base_dir: str | Path, timeout: int = 300) -> List:
    """A real Python sandbox for the agent: `run_python` (execute a snippet, capture
    output) and `pip_install` (fetch libraries on demand). This lets a node PROTOTYPE
    in Python before writing Verilog — build/quantize LUTs (relu, softmax, sin) and
    filter/NN coefficients with numpy/torch, test a paper's algorithm, or parse an
    attached PDF/image — and drop the results (e.g. a `.mem` file) next to the RTL.
    Scripts run with the current interpreter, cwd = the design dir, with a timeout so a
    runaway can't hang the app."""
    base = Path(base_dir).resolve()

    @tool
    def run_python(code: str) -> str:
        """Run a Python snippet in the design directory and return its stdout/stderr.
        Use it to COMPUTE data for hardware before writing Verilog: build a LUT
        (relu/softmax/sigmoid/sin), filter taps, or NN weights with numpy/torch,
        QUANTIZE to int or Qm.n fixed-point, and WRITE them to a file —
        `open('rtl/relu_lut.mem','w')` of hex/bin lines that Verilog loads with
        `$readmemh`/`$readmemb` — or just print the constants to bake into the RTL.
        Also good for testing an algorithm/paper concept, or reading an attached
        PDF/image (pip_install pypdf / pillow first). The working dir is the design
        dir, so relative paths like 'rtl/...' resolve there. matplotlib is forced to
        the headless 'Agg' backend — savefig to a file, never show(). Keep prints
        SMALL: you only get back the last ~6000 characters."""
        work = base / "work"
        work.mkdir(parents=True, exist_ok=True)
        script = work / "_snippet.py"
        # Force a headless matplotlib backend IF it's installed — never crash the
        # snippet just because matplotlib is absent.
        header = ("try:\n    import matplotlib; matplotlib.use('Agg')\n"
                  "except Exception:\n    pass\n")
        script.write_text(header + (code or ""))
        try:
            proc = subprocess.run([sys.executable, str(script)], cwd=str(base),
                                  capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return f"(timed out after {timeout}s — do less work per call or split it up)"
        except Exception as e:  # noqa: BLE001
            return f"(could not run python: {e})"
        out = proc.stdout + (("\n[stderr]\n" + proc.stderr) if proc.stderr else "")
        tag = "OK" if proc.returncode == 0 else f"EXIT {proc.returncode}"
        return f"[{tag}]\n{out.strip()[-6000:] or '(no output)'}"

    @tool
    def pip_install(packages: str) -> str:
        """Install Python packages so `run_python` can import them. Pass names
        space- or comma-separated, e.g. 'numpy', 'torch', 'matplotlib scipy', 'pypdf
        pillow'. Call this BEFORE run_python when an import is missing."""
        pkgs = [p for p in re.split(r"[,\s]+", (packages or "").strip()) if p]
        if not pkgs:
            return "(no packages given)"
        attempts = []
        if shutil.which("uv"):                       # this project is uv-managed
            attempts.append(
                ["uv", "pip", "install", "--python", sys.executable, *pkgs])
        attempts.append([sys.executable, "-m", "pip", "install", *pkgs])
        last = ""
        for cmd in attempts:
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=600)
                if proc.returncode == 0:
                    return f"installed: {', '.join(pkgs)}"
                last = (proc.stdout + proc.stderr)[-1500:]
            except Exception as e:  # noqa: BLE001
                last = str(e)
        return f"(pip install failed for {', '.join(pkgs)}: {last})"

    return [run_python, pip_install]


def build_deep_agent(base_dir: str | Path, model=None, temperature: float = 0.2):
    """A deepagents agent with planning + REAL file tools + the RLM `llm_query`
    delegation primitive, driven by Ollama qwen3.5:9b. Used by the file agent."""
    return create_deep_agent(
        tools=make_fs_tools(base_dir) + make_rlm_tools(temperature),
        instructions=INSTRUCTIONS,
        model=model or get_chat_model(temperature=temperature),
        # keep the planning tool; use OUR real-disk file tools instead of the
        # built-in virtual-filesystem ones (write_file/read_file/ls/edit_file).
        builtin_tools=["write_todos"],
    )


def build_step_agent(base_dir: str | Path, extra_tools=None, instructions: str | None = None,
                     temperature: float = 0.2, model=None):
    """A deep agent for ONE pipeline step ("every agent is a deep agent"). Every node
    gets: planning (`write_todos`), real file tools (slice-read + grep), the RLM
    `llm_query` delegation primitive, the built-in `task` sub-agent tool, PLUS whatever
    step-specific tools (web research, memory, …) the caller passes. All driven by the
    local Ollama model. The fixed graph still orchestrates the steps; this upgrades a
    single node's brain into an RLM."""
    tools = (list(make_fs_tools(base_dir))
             + list(make_rlm_tools(temperature))
             + list(make_python_tools(base_dir))
             + list(extra_tools or []))
    return create_deep_agent(
        tools=tools,
        instructions=instructions or INSTRUCTIONS,
        model=model or get_chat_model(temperature=temperature),
        builtin_tools=["write_todos"],
    )
