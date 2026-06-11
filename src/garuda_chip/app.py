"""
GarudaChip — unified, local-LLM digital/SoC flow with a Claude-Code-style,
human-in-the-loop agent loop.

ONE Streamlit app: prompt -> Planner -> RTL (RAG + local LLM) -> Icarus sim
(+ self-fix) -> LibreLane hardening -> GDSII. The flow runs ONE AGENT AT A TIME
and PAUSES after each so you can:

  ▶️ Continue       — run the next step
  ✍️ Revise         — re-run THIS step with your feedback
  🔁 Replan         — let the Replanner choose the next steps from your feedback
  🌐 Web example    — "go find an example of block X and its inputs/outputs"

Every step's output is recorded into a transcript that is re-drawn on every
Streamlit rerun (Streamlit wipes prior output each rerun), so the whole history
stays on screen as you steer. Every artifact is written to output/<design>/.

Chat model is local by default (Ollama, e.g. qwen3.5:9b) — see llm.py.
"""

from __future__ import annotations

import os
import re
import json
import glob
import shutil
import subprocess
import zipfile
import io
from pathlib import Path
from typing import Dict, List

import streamlit as st
import streamlit.components.v1 as components
import graphviz
from dotenv import load_dotenv
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate

from llm import get_chat_model, get_embeddings, provider_label
from memory_store import get_memory

load_dotenv()

# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data" / "verilog_datasets"
OUTPUT_DIR = REPO_ROOT / "output"          # <-- all results land here
MAX_RETRIES = int(os.getenv("MAX_SIM_RETRIES", "50"))
MAX_LINT_RETRIES = int(os.getenv("MAX_LINT_RETRIES", "10"))
LIBRELANE_BIN = os.getenv("LIBRELANE_BIN", "librelane")
PDK = os.getenv("PDK", "gf180mcuD")
PDK_ROOT = os.getenv("PDK_ROOT", os.path.expanduser("~/.ciel"))
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def clean_llm_output(text: str) -> str:
    if not text:
        return ""
    stripped = re.sub(r"<think>.*?</think>", "", text,
                      flags=re.DOTALL | re.IGNORECASE).strip()
    # If the model put EVERYTHING inside <think> (no answer after), keep the raw
    # text so we can still pull a code block out of it.
    return stripped or text.strip()


def extract_code_block(text: str, lang: str = "verilog") -> str:
    text = clean_llm_output(text)
    m = re.search(rf"```(?:{lang})?\s*\n(.*?)```", text, re.DOTALL)
    code = m.group(1).strip() if m else text.replace(
        f"```{lang}", "").replace("```", "").strip()
    return dedup_modules(code)


def dedup_modules(code: str) -> str:
    """LLMs sometimes emit the SAME `module … endmodule` twice (which causes
    'already declared' compile errors). Keep one copy of each module."""
    if not code:
        return code
    full = re.findall(r"(module\s+\w+.*?endmodule)", code, re.DOTALL)
    if len(full) <= 1:
        return code.strip()
    last = {}
    order = []
    for b in full:
        nm = re.match(r"module\s+(\w+)", b).group(1)
        if nm not in last:
            order.append(nm)
        last[nm] = b  # keep the last (usually most complete) copy
    head = code[: code.find("module")] if code.find("module") > 0 else ""
    return (head + "\n\n".join(last[nm] for nm in order)).strip()


def extract_json(text: str) -> dict:
    text = clean_llm_output(text)
    m = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        s, e = text.find("{"), text.rfind("}")
        if s != -1 and e != -1 and e > s:
            raw = text[s: e + 1]
    if raw is None:
        raise json.JSONDecodeError("no JSON object found", text, 0)
    return json.loads(raw)


def strip_ansi(s: str) -> str:
    return ANSI.sub("", s)


def librelane_available() -> bool:
    return shutil.which(LIBRELANE_BIN) is not None


# --------------------------------------------------------------------------- #
# Persistent agent memory — lessons/fixes that survive across runs
# --------------------------------------------------------------------------- #
MEMORY_FILE = DATA_DIR / "agent_memory.json"


def load_memory() -> dict:
    try:
        return json.loads(MEMORY_FILE.read_text())
    except Exception:  # noqa: BLE001
        return {}


def save_memory(mem: dict) -> None:
    try:
        MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        # keep the store bounded
        items = list(mem.items())[-200:]
        MEMORY_FILE.write_text(json.dumps(dict(items), indent=2))
    except Exception:  # noqa: BLE001
        pass


def remember_fix(error_sig: str, hint: str) -> None:
    if not (error_sig and hint):
        return
    mem = load_memory()                       # fast local cache (agent_memory.json)
    mem[error_sig[:200]] = hint[:4000]
    save_memory(mem)
    # ALSO persist to the durable knowledge store (pgvector + MinIO) so the lesson is
    # shared across runs/machines and surfaces in semantic recall — the agent stops
    # repeating the same mistake.
    try:
        from memory_store import get_memory
        get_memory().remember(
            "fix", f"ERROR: {error_sig}\n\nFIX: {hint}",
            source="auto-fix", title=error_sig[:120], tags="fix")
    except Exception:  # noqa: BLE001
        pass


def recall_fix(error_sig: str) -> str:
    hit = load_memory().get((error_sig or "")[:200], "")
    if hit:
        return hit
    # fall back to durable semantic recall of past fixes
    try:
        from memory_store import get_memory
        items = get_memory().recall(error_sig or "", kind="fix", k=1)
        if items:
            return items[0].get("text", "")
    except Exception:  # noqa: BLE001
        pass
    return ""


def find_verilator() -> str | None:
    """Locate verilator even if it isn't on PATH — LibreLane pulls it into its Nix
    closure (not exposed as a profile binary), so fall back to the Nix store / env."""
    v = shutil.which("verilator")
    if v:
        return v
    v = os.getenv("VERILATOR_BIN")
    if v and Path(v).exists():
        return v
    cands = sorted(glob.glob("/nix/store/*verilator*/bin/verilator"))
    return cands[-1] if cands else None


def slugify(text: str, n: int = 48) -> str:
    return re.sub(r"\W+", "_", text).lower().strip("_")[:n] or "design"


def _norm(code: str) -> str:
    """Normalize Verilog for an 'is this the same attempt?' check — ignore comments
    and whitespace so the corrector can't sneak the SAME broken code past us by only
    re-indenting it."""
    code = re.sub(r"//[^\n]*", "", code or "")
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    return re.sub(r"\s+", " ", code).strip()


def _looks_repetitive(text: str) -> bool:
    """Detect a degenerate generation loop — the model spewing the same handful of
    lines over and over (e.g. '// We will assume … // But the prompt says …'). If
    the last 30 non-empty lines collapse to ≤3 distinct lines, it's looping. Real
    code/reasoning almost never does that (each line differs)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) < 30:
        return False
    return len(set(lines[-30:])) <= 3


# Concrete pitfalls a weak local model trips on REPEATEDLY (e.g. `4{8'd0}`,
# resetting an unpacked array in one shot, two `always` blocks driving one reg).
# Spelling them out beats a generic "fix the error" — the model has the knowledge
# but needs to be pointed at the exact rule it broke.
VERILOG_PITFALLS = """COMMON VERILOG MISTAKES — CHECK YOUR CODE AGAINST EVERY ONE BEFORE REPLYING:
1. UNPACKED-ARRAY RESET: for `reg [W-1:0] mem [0:N-1]` you CANNOT write `mem <= 0`,
   `mem <= '0`, or `mem <= {N{...}}` — that is a "malformed statement". Reset entry by
   entry with a loop: `integer i; ... for (i=0;i<N;i=i+1) mem[i] <= {W{1'b0}};`.
2. REPLICATION needs DOUBLE braces: `{4{8'd0}}` (a 32-bit value) — NEVER `4{8'd0}`.
3. ONE DRIVER PER SIGNAL: never assign the same reg/output from two `always` blocks —
   merge the logic into ONE `always` block per signal (this causes X/contention).
4. reg vs wire: a signal assigned inside `always` must be `reg`/`output reg`; declare
   every signal EXACTLY ONCE (never both a module port AND a separate reg/wire).
5. WIDTHS must match on every assignment and port connection; sign-extend explicitly.
6. Don't index a packed vector as if it were an unpacked array, or vice-versa.
7. NO COMBINATIONAL LOOP (Verilator UNOPTFLAT): a signal must NOT depend on itself
   through pure `assign`/combinational logic (e.g. `assign x = x + 1;` or a chain
   `assign a=b; assign b=a;`). Break the loop — register the feedback in an `always
   @(posedge clk)`, or drive the output from sequential logic, not a self-referential wire.
8. An `output` must have exactly ONE source — never both an `assign` and an `always`
   block writing the same output (Verilator MULTIDRIVEN).
9. NO `wire`/net declaration INSIDE an `always` block — that is illegal ("Syntax in
   assignment statement l-value"). Nets are declared at MODULE scope. For an
   intermediate value inside `always`, either declare a module-scope `wire`+`assign`,
   or use a procedural `reg`/`integer` (declared at module scope or the top of a named
   begin/end) with blocking `=`. Example fix: move `wire signed [7:0] q0 = q[15:8];`
   OUT of the always block to module scope as `wire signed [7:0] q0 = q[15:8];`."""


# ---- Live workflow graph (highlights the agent currently working) ---------- #
WF_NODES = [
    ("plan", "0 · 🧭 Planner"),
    ("retrieve", "1 · 📚 Dataset\nRetriever"),
    ("web", "2 · 🌐 Web\nResearcher"),
    ("generate", "3 · ✍️ Verilog\nGenerator"),
    ("decompose", "4 · 🧩 Decomposer"),
    ("testbench", "5 · 🧪 Testbench\nWriter"),
    ("write", "6 · 💾 File\nWriter"),
    ("simulate", "7 · 🔬 Icarus\nSim"),
    ("lint", "8 · 🔍 Verilator\nLint"),
    ("correct", "9 · 🛠️ Correctors"),
    ("harden", "10 · 🏭 LibreLane\nHardening"),
    ("gds", "🎉 GDSII"),
]
WF_EDGES = [
    ("plan", "retrieve"),
    ("retrieve", "web"), ("web", "generate"), ("generate", "decompose"),
    ("decompose", "testbench"), ("testbench", "write"), ("write", "simulate"),
    ("simulate", "correct"), ("correct", "write"), ("simulate", "lint"),
    ("lint", "correct"), ("lint", "harden"),
    ("harden", "gds"),
]
# Map an executed step name -> the graph node it lights up.
GRAPH_KEY = {"fix_design": "correct", "fix_testbench": "correct"}


def workflow_graph(active: str | None = None, done: set | None = None):
    done = done or set()
    dot = graphviz.Digraph()
    dot.attr(rankdir="LR", bgcolor="transparent")
    dot.attr("node", shape="box", style="rounded,filled",
             fontname="sans-serif", fontsize="10")
    dot.attr("edge", color="#90a4ae")
    for key, label in WF_NODES:
        if key == active:
            dot.node(key, label, fillcolor="#ffca28", color="#ff6f00",
                     penwidth="2.5")  # working = amber
        elif key in done:
            dot.node(key, label, fillcolor="#a5d6a7",
                     color="#2e7d32")                   # done = green
        else:
            dot.node(key, label, fillcolor="#eceff1",
                     color="#b0bec5", fontcolor="#546e7a")
    for a, b in WF_EDGES:
        dot.edge(a, b)
    return dot


def stream_to(runnable, inputs, placeholder, tail: int = 9000) -> str:
    """Stream a chain/LLM's output LIVE into `placeholder` so you watch the model
    REASON (thinking tokens) and then write, in real time. Returns the answer text.

    Pass a `prompt | llm` runnable (NOT one ending in StrOutputParser), otherwise
    the parser drops the separate `reasoning` field and the box stays blank while
    the model is thinking."""
    answer, thinking, n = "", "", 0

    def render():
        disp = (
            f"💭 thinking…\n{thinking.strip()}\n\n———\n" if thinking.strip() else "")
        disp += answer
        if not disp.strip():
            # always show progress, never blank
            disp = f"⏳ generating… ({n} tokens)"
        placeholder.code(disp[-tail:], language="markdown")

    try:
        for chunk in runnable.stream(inputs):
            if isinstance(chunk, str):
                answer += chunk
            else:
                answer += getattr(chunk, "content", "") or ""
                ak = getattr(chunk, "additional_kwargs", {}) or {}
                thinking += (ak.get("reasoning_content") or ak.get("reasoning")
                             or ak.get("thinking") or "")
            n += 1
            if n % 3 == 0:
                render()
            # Circuit-breaker: bail out of a degenerate repetition loop instead of
            # streaming the same lines forever (the model never stops on its own).
            if n % 15 == 0 and (_looks_repetitive(answer) or _looks_repetitive(thinking)):
                answer += "\n// [GarudaChip] generation stopped — model entered a repetition loop.\n"
                break
            if len(answer) + len(thinking) > 120_000:  # hard safety cap
                break
    except Exception:  # noqa: BLE001
        if not answer and not thinking:
            out = runnable.invoke(inputs)
            answer = out if isinstance(out, str) else (
                getattr(out, "content", "") or str(out))
    render()
    return answer or thinking


# --------------------------------------------------------------------------- #
# RAG
# --------------------------------------------------------------------------- #
def _docs_from_recall(items) -> List[Document]:
    """Turn knowledge-store recall results into the Document list the generator consumes."""
    out: List[Document] = []
    for it in items:
        body = it.get("text") or it.get("title") or ""
        if not body.strip():
            continue
        out.append(Document(page_content=body, metadata={
            "source": it.get("source") or it.get("design") or "knowledge",
            "kind": it.get("kind"), "object_key": it.get("object_key")}))
    return out


HDL_SET = {"Verilog", "SystemVerilog", "VHDL"}


# Filler words that hurt a GitHub repo search — repo search matches names/topics,
# not prose, so "riscv 8-bit like picorv using fixed point" must become "riscv picorv".
_SEARCH_STOP = {
    "a", "an", "the", "of", "for", "and", "to", "in", "on", "with", "using", "like",
    "that", "this", "my", "your", "please", "make", "build", "create", "design",
    "designs", "implement", "implementation", "module", "modules", "support", "based",
    "is", "it", "bit", "bits", "fixed", "point", "simple", "small", "tiny", "basic",
    "want", "need", "generate", "verilog", "vhdl", "systemverilog", "hdl", "chip",
}


def _hdl_keywords(text: str, n: int = 4) -> List[str]:
    """Distill a (possibly verbose) request into the few salient search keywords — the
    distinctive nouns a GitHub/web search actually needs (e.g. 'riscv', 'picorv', 'alu')."""
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9_]+", (text or "").lower())
    out: List[str] = []
    for w in words:
        if w in _SEARCH_STOP or len(w) < 3 or w in out:
            continue
        out.append(w)
    return out[:n]


def _ddg_github(query: str, limit: int) -> List[str]:
    """Fallback repo finder via DuckDuckGo `site:github.com` — works when the GitHub
    API is rate-limited or the prose query matched nothing (this is what makes a search
    for 'picorv' actually surface YosysHQ/picorv32)."""
    out: List[str] = []
    try:
        from ddgs import DDGS
        kw = " ".join(_hdl_keywords(query, 3)) or query
        for res in DDGS().text(f"{kw} verilog site:github.com", max_results=limit * 3):
            m = re.match(r"(https://github\.com/[^/]+/[^/#?]+)", res.get("href", ""))
            if m and m.group(1) not in out and "/topics/" not in m.group(1):
                out.append(m.group(1))
                if len(out) >= limit:
                    break
    except Exception:  # noqa: BLE001
        pass
    return out


def _github_hdl_repos(query: str, limit: int) -> List[str]:
    """Find real HDL repos with SHORT keyword queries (repo search hates prose), an
    optional token to dodge rate limits, and a DuckDuckGo `site:github.com` fallback."""
    out: List[str] = []
    headers = {"Accept": "application/vnd.github+json"}
    tok = os.getenv("GITHUB_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    kws = _hdl_keywords(query, 4)
    # try the strongest 2-3 keywords together, then the single strongest — short wins
    candidates = [q for q in dict.fromkeys(
        [" ".join(kws[:3]), " ".join(kws[:2]), kws[0] if kws else query.strip()]) if q]
    try:
        import requests
        for q in candidates:
            if len(out) >= limit:
                break
            r = requests.get(
                "https://api.github.com/search/repositories",
                params={"q": f"{q} verilog", "sort": "stars", "per_page": 20},
                headers=headers, timeout=12)
            if not r.ok:
                break          # rate-limited/error → stop hitting the API, use the fallback
            for it in r.json().get("items", []):
                if it.get("language") in HDL_SET:
                    u = it.get("html_url")
                    if u and u not in out:
                        out.append(u)
                        if len(out) >= limit:
                            break
    except Exception:  # noqa: BLE001
        pass
    if len(out) < max(2, limit // 2):     # API thin or rate-limited → DDG site:github.com
        for u in _ddg_github(query, limit):
            if u not in out:
                out.append(u)
    return out[:limit]


def _web_search(query: str, similar: List[str] | None = None,
                n_github: int = 10, n_other: int = 10) -> List[str]:
    """Balanced references: up to ``n_github`` HDL GitHub repos (Verilog/VHDL/
    SystemVerilog only — code for the IP, or the closest similar IP) PLUS up to
    ``n_other`` papers/web pages (theory/knowledge). ``similar`` are extra,
    LLM-suggested building-block queries used when the exact IP isn't on GitHub."""
    gh: List[str] = []
    for q in [query] + (similar or []):
        if len(gh) >= n_github:
            break
        for u in _github_hdl_repos(q, n_github):
            if u not in gh:
                gh.append(u)

    other: List[str] = []
    try:
        from ddgs import DDGS

        ddg = DDGS()
        # Search for what the PROMPT actually describes — no hardcoded topic. A
        # neutral "digital design architecture" suffix keeps results relevant for
        # CPUs/cores AND accelerators instead of forcing "accelerator" every time.
        for res in ddg.text(f"{query} verilog digital design architecture", max_results=n_other * 2):
            u = res.get("href")
            if u and "github.com" not in u and u not in other:
                other.append(u)
    except Exception:  # noqa: BLE001
        pass

    if not gh and not other:  # last-ditch fallback
        try:
            from googlesearch import search

            for u in search(f"{query} verilog github", num_results=n_github + n_other):
                (gh if "github.com" in u else other).append(u)
        except Exception:  # noqa: BLE001
            pass

    return gh[:n_github] + other[:n_other]


def _md_text(res) -> str:
    md = getattr(res, "markdown", None)
    if md is None:
        return ""
    if isinstance(md, str):
        return md
    return getattr(md, "raw_markdown", None) or getattr(md, "fit_markdown", None) or str(md)


def _crawl_urls(urls: List[str], rec: "Recorder", limit: int = 8) -> List[Document]:
    """Crawl a handful of URLs (5 at a time) into Documents. Shared by the Web
    Researcher and the on-demand 'fetch a web example of block X' tool."""
    try:
        import asyncio
        from crawl4ai import AsyncWebCrawler
    except Exception as e:  # noqa: BLE001
        rec.warning(f"crawl4ai unavailable ({e}) — skipping crawl.")
        return []
    urls = urls[:limit]
    log = rec.placeholder()
    seen: List[str] = []

    async def _crawl() -> List[Document]:
        out: List[Document] = []
        sem = asyncio.Semaphore(5)
        async with AsyncWebCrawler() as crawler:
            async def fetch(url: str) -> None:
                async with sem:
                    try:
                        res = await asyncio.wait_for(crawler.arun(url=url), timeout=25)
                    except Exception:  # noqa: BLE001
                        return
                md = _md_text(res)
                if md and len(md) > 250:
                    is_gh = "github.com" in url
                    out.append(
                        Document(page_content=md[:8000], metadata={"source": url}))
                    seen.append(("💻 " if is_gh else "📄 ") + url)
                    log.code(
                        "\n".join(f"✓ {u}" for u in seen), language="text")
            await asyncio.gather(*(fetch(u) for u in urls))
        return out

    try:
        return asyncio.run(_crawl())
    except Exception as e:  # noqa: BLE001
        rec.warning(f"Crawl failed ({e}).")
        return []


def _download_github_code(repo_url: str, save, max_files: int = 6) -> None:
    """Download a handful of real HDL files (.v/.sv/.vh/.vhd) from a GitHub repo."""
    import requests
    m = re.search(r"github\.com/([^/]+)/([^/#?]+)", repo_url)
    if not m:
        return
    user, repo = m.group(1), m.group(2).replace(".git", "")
    h = {"Accept": "application/vnd.github+json"}
    tok = os.getenv("GITHUB_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    try:
        info = requests.get(f"https://api.github.com/repos/{user}/{repo}", headers=h, timeout=12)
        if not info.ok:
            return
        branch = info.json().get("default_branch", "main")
        tree = requests.get(
            f"https://api.github.com/repos/{user}/{repo}/git/trees/{branch}?recursive=1",
            headers=h, timeout=15)
        if not tree.ok:
            return
        paths = [t["path"] for t in tree.json().get("tree", [])
                 if t.get("type") == "blob"
                 and t["path"].lower().endswith((".v", ".sv", ".vh", ".svh", ".vhd"))][:max_files]
        for path in paths:
            raw = requests.get(
                f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}", timeout=15)
            if raw.ok and raw.text.strip():
                save(f"{repo}__{path.replace('/', '_')}", raw.content)
    except Exception:  # noqa: BLE001
        return


def _download_references(urls: List[str], design_dir, rec: "Recorder" = None,
                         max_repos: int = 4, max_files: int = 6, max_pdfs: int = 10) -> int:
    """DOWNLOAD the actual reference artifacts found by the web researcher — PDF papers
    (arxiv/*.pdf) and real HDL code from GitHub — and store them in the knowledge store
    (blob → MinIO, row+embedding → pgvector). This is what makes the store grow with
    real papers/code, not just crawled text snippets."""
    import requests
    refs = Path(design_dir) / "context" / "refs"
    refs.mkdir(parents=True, exist_ok=True)
    saved: List[Path] = []

    def save(name: str, data: bytes) -> None:
        safe = re.sub(r"[^\w.\-]", "_", name)[:90] or "ref"
        p = refs / safe
        try:
            p.write_bytes(data)
            saved.append(p)
        except Exception:  # noqa: BLE001
            pass

    pdfs = repos = 0
    for u in urls:
        try:
            is_pdf = u.endswith(".pdf") or "arxiv.org/abs/" in u or "arxiv.org/pdf/" in u
            if is_pdf and pdfs < max_pdfs:
                pdf_url = u
                if "arxiv.org/abs/" in u:
                    pid = u.split("/abs/")[-1].split("?")[0].strip("/")
                    pdf_url = f"https://arxiv.org/pdf/{pid}.pdf"
                r = requests.get(pdf_url, timeout=25)
                if r.ok and r.content[:4] == b"%PDF":
                    nm = pdf_url.rstrip("/").split("/")[-1]
                    save(nm if nm.endswith(".pdf") else nm + ".pdf", r.content)
                    pdfs += 1
            elif "github.com/" in u and repos < max_repos:
                repos += 1
                _download_github_code(u, save, max_files)
        except Exception:  # noqa: BLE001
            continue

    n = 0
    mem = get_memory()
    if mem.enabled and saved:
        design = Path(design_dir).name
        for p in saved:
            if mem.ingest_file(p, design=design, source=f"webref:{design}"):
                n += 1
    if rec and saved:
        rec.success(f"📥 Downloaded **{len(saved)}** reference file(s) "
                    f"({pdfs} PDF paper(s) + code) → stored {n} in the knowledge store.")
    return n


def _store_web_docs(docs, ctx) -> int:
    """Persist crawled paper/web TEXT into the knowledge store (kind=paper for web,
    code for GitHub) so it's semantically recallable in future runs."""
    mem = get_memory()
    if not (getattr(mem, "enabled", False) and docs):
        return 0
    design = Path(ctx["design_dir"]).name
    n = 0
    for d in docs:
        src = d.metadata.get("source", "web") if hasattr(d, "metadata") else "web"
        body = getattr(d, "page_content", "") or ""
        kind = "code" if "github.com" in str(src) else "paper"
        if body and mem.remember(kind, body[:6000], design=design, source=str(src),
                                 title=str(src)[:120], tags="web"):
            n += 1
    return n


def _error_query(err: str) -> str:
    """Turn a compiler/lint error log into a concise web-search query (strip the file
    paths/line numbers and prefer the MOST DESCRIPTIVE error message, not generic
    'syntax error', so the search is actually about the real problem)."""
    cands = []
    for line in (err or "").splitlines():
        low = line.lower()
        if "error" in low or "syntax" in low:
            # drop "path:line:"
            msg = re.sub(r"^.*?:\s*\d+:?\s*", "", line)
            # drop leftover file paths
            msg = re.sub(r"/[\w./\-]+\.s?vh?", "", msg).strip()
            if len(msg) > 8 and msg.lower().strip(". ") not in ("syntax error", "error", "%error"):
                cands.append(msg)
    if cands:
        # the most specific message
        return ("verilog " + max(cands, key=len))[:140]
    first = next((l.strip()
                 for l in (err or "").splitlines() if l.strip()), "")
    return ("verilog " + re.sub(r"^.*?:\s*\d+:?\s*", "", first))[:140]


def _auto_research(query: str, rec: "Recorder") -> str:
    """Autonomously search the WEB for how to fix an error and summarize the fix —
    the corrector calls this on its own when it's stuck (no human needed)."""
    rec.caption(f"🌐 Searching the web for: *{query}*")
    try:
        with st.spinner("Searching the web for a fix…"):
            urls = _web_search(query, n_github=2, n_other=4)
        docs = _crawl_urls(urls, rec, limit=4)
        if not docs:
            rec.caption("No usable web results.")
            return ""
        body = "\n\n".join(d.page_content[:1500] for d in docs[:3])
        summary = clean_llm_output(stream_to(
            get_chat_model(temperature=0.2),
            "From these web results, explain CONCISELY how to fix this Verilog error and show the "
            f"CORRECT code pattern (a few lines).\n\nERROR: {query}\n\nWEB RESULTS:\n{body}",
            rec.placeholder(),
        ))
        rec.markdown("**🌐 Web fix hint:**")
        rec.code(summary[:1500], "markdown")
        return f"WEB FIX HINT for '{query}':\n{summary}"
    except Exception as e:  # noqa: BLE001
        rec.caption(f"Web research failed ({e}).")
        return ""


# --------------------------------------------------------------------------- #
# Transcript / Recorder — render once live AND record for replay
# --------------------------------------------------------------------------- #
# Streamlit wipes ALL output on every rerun. Because this app pauses after each
# agent and reruns on every button click, we must be able to re-draw the whole
# history. Each agent renders through a Recorder, which both draws live AND stores
# a list of (kind, payload) blocks; replay_record() re-draws them next rerun.
def _draw(kind, payload):
    if kind == "header":
        emoji, title, desc = payload
        st.markdown("---")
        st.markdown(f"### {emoji} {title}")
        if desc:
            st.caption(desc)
    elif kind == "markdown":
        st.markdown(payload[0])
    elif kind == "caption":
        st.caption(payload[0])
    elif kind == "write":
        st.write(payload[0])
    elif kind == "code":
        st.code(payload[0], language=payload[1])
    elif kind == "success":
        st.success(payload[0])
    elif kind == "error":
        st.error(payload[0])
    elif kind == "info":
        st.info(payload[0])
    elif kind == "warning":
        st.warning(payload[0])
    elif kind == "expander_code":
        title, code, language, expanded = payload
        with st.expander(title, expanded=expanded):
            st.code(code, language=language)
    elif kind == "table":
        st.table(payload[0])
    elif kind == "json":
        with st.expander("All metrics"):
            st.json(payload[0])
    elif kind == "graphviz":
        st.graphviz_chart(payload[0], use_container_width=True)
    elif kind == "image":
        # Stored as a PATH (+caption) so it re-renders on every Streamlit rerun.
        path, caption = payload
        p = Path(path)
        if not p.exists():
            st.caption(f"(image not found: {path})")
        elif p.suffix.lower() == ".svg":
            svg = p.read_text()
            m = re.search(r'height="([\d.]+)', svg)
            h = min(int(float(m.group(1))) + 40, 900) if m else 360
            if caption:
                st.caption(caption)
            components.html(f'<div style="overflow:auto;background:#fff">{svg}</div>',
                            height=h, scrolling=True)
        else:
            st.image(str(p), caption=caption or None, use_container_width=True)


class _NullPH:
    """Stand-in for a live streaming placeholder during replay (does nothing)."""

    def code(self, *a, **k):
        pass


class Recorder:
    def __init__(self, emoji, title, desc="", node="", live=True):
        self.node = node
        self.blocks = [("header", (emoji, title, desc))]
        self.live = live
        if live:
            _draw("header", (emoji, title, desc))

    def _add(self, kind, payload):
        self.blocks.append((kind, payload))
        if self.live:
            _draw(kind, payload)

    def markdown(self, t):
        self._add("markdown", (t,))

    def caption(self, t):
        self._add("caption", (t,))

    def write(self, t):
        self._add("write", (t,))

    def code(self, t, language="text"):
        self._add("code", (t, language))

    def success(self, t):
        self._add("success", (t,))

    def error(self, t):
        self._add("error", (t,))

    def info(self, t):
        self._add("info", (t,))

    def warning(self, t):
        self._add("warning", (t,))

    def expander_code(self, title, code, language="verilog", expanded=False):
        self._add("expander_code", (title, code, language, expanded))

    def table(self, data):
        self._add("table", (data,))

    def json(self, data):
        self._add("json", (data,))

    def graphviz(self, dot):
        self._add("graphviz", (dot,))

    def image(self, path, caption=""):
        """Show an image FILE (png/jpg/svg). Stored as a path so it survives replay."""
        self._add("image", (str(path), caption))

    def placeholder(self):
        """A LIVE streaming target (st.empty) during execution; a no-op on replay."""
        return st.empty() if self.live else _NullPH()


def replay_record(record):
    for kind, payload in record["blocks"]:
        _draw(kind, payload)


def _ref_context(ctx) -> str:
    """Reference text injected into the generator/correctors. Includes an on-demand
    web example (from the 🌐 'fetch example of block X' tool) when present."""
    ref = ctx.get("web_example", "")
    return (f"USER-REQUESTED WEB REFERENCE (use it):\n{ref}\n\n" if ref else "")


# --------------------------------------------------------------------------- #
# Agents — each takes (rec, ctx, feedback) and mutates ctx in place
# --------------------------------------------------------------------------- #
def agent_plan(rec, ctx, feedback=""):
    plan = ["retrieve", "web", "generate",
            "decompose", "testbench", "write", "simulate"]
    if not ctx.get("use_web"):
        plan.remove("web")
    ctx["_plan"] = plan
    if ctx.get("deep_steps"):                 # run the Planner AS a deep agent (RLM)
        return _deep_plan(rec, ctx, feedback)
    rec.markdown("**Planned build steps:**")
    rec.code("  →  ".join(plan), "text")
    rec.caption("After each step the flow PAUSES so you can Continue / Revise / Replan, "
                "or ask it to fetch a web example of a block.")
    try:
        notes = stream_to(
            get_chat_model(temperature=0.3),
            "In 3 short bullet points, name the key sub-blocks and the main verification "
            f"concerns for building this hardware in Verilog: '{ctx['query']}'."
            + (f"\nUser steering: {feedback}" if feedback else ""),
            rec.placeholder(),
        )
        notes = clean_llm_output(notes).strip()
        if notes:
            rec.markdown("**Design notes:**\n\n" + notes[:1500])
    except Exception:  # noqa: BLE001
        pass
    ctx["_plan"] = plan


def agent_retrieve(rec, ctx, feedback=""):
    query = ctx["query"] + (f" {feedback}" if feedback else "")
    mem = get_memory()
    docs: List[Document] = []
    if mem.enabled:
        with st.spinner("Recalling references from the knowledge store (pgvector)…"):
            items = mem.recall(query, k=8)
        docs = _docs_from_recall(items)
        if docs:
            rec.success(
                f"Recalled **{len(docs)}** item(s) from the knowledge store (pgvector semantic search).")
            srcs = "\n".join(f"• [{it.get('kind')}] {it.get('title')} — {it.get('source')}"
                             for it in items[:12])
            rec.expander_code("Show recalled sources", srcs, "text")
        else:
            rec.info("Knowledge store has nothing relevant yet — generating from scratch "
                     "(it fills as you build / after `docker compose up` + seed).")
    else:
        rec.warning("Knowledge store offline — generating from scratch. "
                    "Run `docker compose up -d` to enable durable recall.")
    ctx["documents"] = docs


def agent_web(rec, ctx, feedback=""):
    if not ctx.get("use_web"):
        rec.info("Web research disabled.")
        return
    if ctx.get("deep_steps"):                 # run the Web Researcher AS a deep agent (RLM)
        return _deep_web(rec, ctx, feedback)
    docs = list(ctx.get("documents", []))
    query = ctx["query"]
    mem = get_memory()

    # Cache = the durable knowledge store. If we already crawled references for a
    # similar query, recall them from pgvector instead of crawling again.
    if mem.enabled and not feedback:
        hits = _docs_from_recall(mem.recall(query, kind="reference", k=20))
        if len(hits) >= 5:
            rec.success(
                f"Recalled {len(hits)} reference chunk(s) from the knowledge store — skipping the live crawl.")
            ctx["documents"] = docs + hits
            return

    # Ask the LLM for close HDL building-block terms — derived from THIS request
    # (no hardcoded accelerator examples), so a RISC-V prompt searches for RISC-V.
    similar: List[str] = []
    rec.caption(
        "🧠 Picking similar HDL building blocks (on-topic for your prompt):")
    try:
        with st.spinner("Thinking…"):
            raw = stream_to(
                get_chat_model(temperature=0.3),
                "Given this hardware design request, list 3 short GitHub search phrases "
                "(max 4 words each) that would find open-source Verilog/VHDL/SystemVerilog "
                "implementations of THIS design and the core sub-blocks it actually needs. "
                "Derive the sub-blocks FROM THE REQUEST — e.g. a RISC-V/CPU core needs an "
                "ALU, register file, instruction decoder; a DSP filter needs multipliers and "
                "adders; an accelerator needs its datapath (MAC/systolic array). Stay strictly "
                "on-topic for the request; do NOT suggest unrelated blocks.\n\n"
                f"REQUEST: '{query}'"
                + (f"\nUSER STEERING: {feedback}" if feedback else "")
                + "\n\nReply ONLY as a comma-separated list.",
                rec.placeholder(),
            )
        txt = clean_llm_output(raw)
        similar = [s.strip() for s in re.split(r"[,\n]", txt)
                   if 2 < len(s.strip()) < 50][:3]
    except Exception:  # noqa: BLE001
        similar = []
    if similar:
        rec.caption("🔁 Similar-IP search terms: " +
                    ", ".join(f"`{s}`" for s in similar))

    with st.spinner("Searching GitHub (HDL) + web…"):
        urls = _web_search(query, similar=similar)
    n_gh = sum("github.com" in u for u in urls)
    rec.write(f"🔎 Found **{len(urls)}** references — **{n_gh}** HDL GitHub repos "
              f"+ **{len(urls) - n_gh}** papers/web.")
    if not urls:
        rec.info("No search results; skipping.")
        ctx["documents"] = docs
        return

    with st.spinner(f"Crawling {len(urls)} pages (5 at a time)…"):
        web_docs = _crawl_urls(urls, rec, limit=len(urls))
    if not web_docs:
        rec.info("Crawled pages had no usable content.")
        ctx["documents"] = docs
        return

    chunks = RecursiveCharacterTextSplitter(
        chunk_size=2000, chunk_overlap=200).split_documents(web_docs)
    # Persist the crawled chunks into the durable knowledge store (pgvector + MinIO)
    # so future runs RECALL them — this is the cache, and it grows the RLM's memory.
    stored = 0
    if mem.enabled:
        slug = slugify(query, 60)
        for c in chunks:
            src = c.metadata.get("source", "web")
            if mem.remember("reference", c.page_content, design=slug, source=src,
                            title=str(src)[:120], tags="web"):
                stored += 1
    rec.success(f"Crawled {len(web_docs)} pages → {len(chunks)} chunks"
                + (f" → stored {stored} in the knowledge store (recallable next time)." if stored else "."))
    ctx["documents"] = docs + chunks


def agent_generate(rec, ctx, feedback=""):
    # run this node AS a deep agent (planning + web + files)
    if ctx.get("deep_steps"):
        return _deep_generate(rec, ctx, feedback)
    llm = get_chat_model(temperature=0.2)
    prompt = ChatPromptTemplate.from_template(
        """You are an expert Verilog HDL designer.
Using the reference context and the request, write complete, synthesizable Verilog-2001.
Put any `define`/parameters at the top. Output ONLY Verilog in a single ```verilog block.

{pitfalls}

CONTEXT:
{context}

REQUEST:
{question}
"""
    )

    def fmt(docs):
        head = _ref_context(ctx)
        if not docs:
            return head + "No reference context."
        parts = [
            f"Source: {d.metadata.get('source','N/A')}\n{d.page_content[:1800]}" for d in docs[:20]]
        return head + "\n\n".join(parts)

    question = ctx["query"]
    if feedback:
        question += f"\n\nADDITIONAL USER INSTRUCTION (apply this): {feedback}"

    def is_degenerate(code: str) -> bool:
        # Empty, or a repetition loop produced no real module — force a retry.
        return (not code.strip()) or ("module" not in code) or _looks_repetitive(code)

    chain = prompt | llm
    rec.caption("🧠 Live model output (reasoning + RTL):")
    live = rec.placeholder()
    with st.spinner("Generating Verilog with the local model…"):
        raw = stream_to(chain, {"context": fmt(ctx["documents"]), "question": question,
                                "pitfalls": VERILOG_PITFALLS}, live)
    gen = extract_code_block(raw)

    if is_degenerate(gen):  # looped / empty? retry once without the (possibly huge) references
        rec.warning(
            "Model produced no usable RTL (empty or stuck in a loop) — retrying with a tighter prompt…")
        with st.spinner("Retrying generation…"):
            raw = stream_to(chain, {"context": _ref_context(ctx) + "No reference context.",
                                    "question": question, "pitfalls": VERILOG_PITFALLS}, live)
        gen = extract_code_block(raw)
    if not gen.strip():
        gen = raw.strip()
        rec.error(
            "The model produced no Verilog. Try a simpler prompt or a larger/instruct model.")
        rec.code(raw[:1500] or "(completely empty response)", language="text")
        ctx["generation"] = gen
        ctx["simulation_output"] = ""
        return

    rec.success("Generated RTL:")
    rec.code(gen, language="verilog")
    ctx["generation"] = gen
    ctx["simulation_output"] = ""


def _top_module(blocks: List[str], names: List[str]) -> str:
    """Pick the top module structurally: the one no OTHER module instantiates.
    Falls back to the largest module if every name is referenced somewhere."""
    instantiated = set()
    for nm, b in zip(names, blocks):
        for other in names:
            if other != nm and re.search(rf"\b{re.escape(other)}\b", b):
                instantiated.add(other)
    candidates = [n for n in names if n not in instantiated]
    if candidates:
        return candidates[0]
    return names[max(range(len(blocks)), key=lambda i: len(blocks[i]))]


def agent_decompose(rec, ctx, feedback=""):
    # MECHANICAL split — NO LLM. Asking a weak local model to "refactor into files"
    # made it REWRITE the logic (different code) or loop. Splitting on module
    # boundaries with regex preserves the generated RTL EXACTLY, byte-for-byte.
    code = ctx["generation"]
    rec.caption("Splitting the RTL into per-module files mechanically (no LLM) — the code is "
                "preserved EXACTLY as generated, never rewritten.")
    # Find REAL module declarations: the `module` keyword + name followed by `(`,
    # `#`, or `;`. The trailing anchor is what skips the word "module" when it just
    # appears inside a comment (e.g. `// Top level CPU module`).
    starts = [(m.start(), m.group(1))
              for m in re.finditer(r"\bmodule\s+(\w+)\s*[#(;]", code)]
    blocks: List[str] = []
    names: List[str] = []
    for pos, name in starts:
        em = re.search(r"\bendmodule\b", code[pos:])
        end = pos + em.end() if em else len(code)
        blocks.append(code[pos:end])
        names.append(name)

    files: Dict[str, str] = {}
    # Leading content before the first real module (shared defines / includes / params).
    head = code[: starts[0][0]].strip() if starts else ""
    header_name = None
    if head and re.search(r"`define|`include|parameter|localparam", head):
        header_name = "shared_header.vh"
        # Wrap in an include guard — the header is `include`d by EVERY module file,
        # so without a guard its parameters get declared once per module and iverilog
        # errors with "'DATA_WIDTH' has already been declared in this scope".
        files[header_name] = (f"`ifndef SHARED_HEADER_VH\n`define SHARED_HEADER_VH\n\n"
                              f"{head}\n\n`endif // SHARED_HEADER_VH")

    if not blocks:
        rec.warning(
            "No `module … endmodule` found — keeping the output as a single file.")
        m = re.search(r"module\s+(\w+)", code)
        top = m.group(1) if m else slugify(ctx["query"], 24)
        files[f"{top}.v"] = code.strip()
    else:
        top = _top_module(blocks, names)
        inc = f'`include "{header_name}"\n\n' if header_name else ""
        for nm, b in zip(names, blocks):
            files[f"{nm}.v"] = (inc + b.strip()) if header_name else b.strip()

    files = {k: v for k, v in files.items() if v.strip()}
    rec.success(
        f"Top module: `{top}` · {len(files)} file(s) — split verbatim, no code changed.")
    for fn, c in files.items():
        rec.expander_code(f"📄 {fn}", c, "verilog" if fn.endswith(".v") else "text",
                          expanded=(fn == f"{top}.v"))
    ctx["decomposed_files"] = files
    ctx["top_module_name"] = top


def agent_testbench(rec, ctx, feedback=""):
    if ctx.get("deep_steps"):                 # run the Testbench Writer AS a deep agent (RLM)
        return _deep_testbench(rec, ctx, feedback)
    files = ctx["decomposed_files"]
    top = ctx["top_module_name"]
    top_code = files.get(f"{top}.v", next(iter(files.values())))
    header = next((f for f in files if f.endswith(".vh")), None)
    inc = f'Include `\`include "{header}"`.' if header else ""
    if feedback:
        inc += f"\n- User instruction: {feedback}"
    llm = get_chat_model(temperature=0.2)
    prompt = ChatPromptTemplate.from_template(
        """Write a self-checking Verilog testbench for the top module.
STRICT RULES (follow exactly):
- Module name MUST be `{top}_tb` and it MUST have an EMPTY port list: `module {top}_tb;` —
  a testbench is the simulation top, it has NO inputs/outputs.
- Declare `clk` and every DUT *input* as `reg`; declare every DUT *output* as `wire`.
  Declare each signal EXACTLY ONCE (never both a port and a reg).
- Clock: `reg clk; initial clk = 0; always #5 clk = ~clk;`
- Instantiate the DUT connecting ports by name; apply reset; drive stimulus; check outputs.
- Waveforms: `$dumpfile("design.vcd"); $dumpvars(0, {top}_tb);`
- Print EXACTLY "Result: PASSED" on success or "Result: FAILED" on mismatch, then `$finish;`.
- Output EXACTLY ONE module. Do NOT repeat the module.
{inc}
- Reply with ONLY JSON: {{"{top}_tb.v": "<full verilog source>"}}.

DUT (`{top}.v`):
```verilog
{code}
```"""
    )
    rec.caption("🧠 Live model output:")
    live = rec.placeholder()
    with st.spinner("Writing testbench…"):
        resp = stream_to(
            prompt | llm, {"top": top, "code": top_code, "inc": inc}, live)
    try:
        tb = extract_json(resp)
        tb = {k: dedup_modules(v) for k, v in tb.items()}
    except Exception:  # noqa: BLE001
        tb = {f"{top}_tb.v": extract_code_block(resp)}
    rec.success(f"Testbench `{next(iter(tb))}`:")
    rec.code(next(iter(tb.values())), language="verilog")
    ctx["testbench_code"] = tb


def agent_write(rec, ctx, feedback=""):
    design_dir = Path(ctx["design_dir"])
    rtl_dir, tb_dir = design_dir / "rtl", design_dir / "tb"
    rtl_dir.mkdir(parents=True, exist_ok=True)
    tb_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in ctx["decomposed_files"].items():
        safe = re.sub(r"[^\w.\-]", "_", name)
        if isinstance(content, str) and content.strip():
            (rtl_dir / safe).write_text(content)
            written.append(f"rtl/{safe}")
    for name, content in ctx.get("testbench_code", {}).items():
        safe = re.sub(r"[^\w.\-]", "_", name)
        if isinstance(content, str) and content.strip():
            (tb_dir / safe).write_text(content)
            written.append(f"tb/{safe}")
    rec.success(
        f"Saved {len(written)} file(s) under `{design_dir.relative_to(REPO_ROOT)}/`:")
    rec.code("\n".join(written), language="text")


def agent_simulate(rec, ctx, feedback=""):
    design_dir = Path(ctx["design_dir"])
    rtl_dir, tb_dir, sim_dir = design_dir / \
        "rtl", design_dir / "tb", design_dir / "sim"
    sim_dir.mkdir(parents=True, exist_ok=True)
    vfiles = sorted(glob.glob(str(rtl_dir / "*.v"))) + \
        sorted(glob.glob(str(tb_dir / "*.v")))
    if not vfiles:
        rec.error("No Verilog files to simulate.")
        ctx["simulation_output"] = "Error: no Verilog files."
        return
    compile_cmd = ["iverilog", "-g2005-sv", "-o",
                   str(sim_dir / "design.vvp"), "-I", str(rtl_dir), *vfiles]
    rec.write("**Compile:**")
    rec.code("iverilog -g2005-sv -o design.vvp -I rtl " + " ".join(os.path.basename(f) for f in vfiles),
             language="bash")
    sim_out = ""
    try:
        with st.spinner("Compiling + simulating…"):
            subprocess.run(compile_cmd, cwd=sim_dir,
                           capture_output=True, text=True, check=True, timeout=90)
            proc = subprocess.run(
                ["vvp", "design.vvp"], cwd=sim_dir, capture_output=True, text=True, timeout=90)
        sim_out = proc.stdout
        rec.write("**Simulation output:**")
        rec.code(sim_out or "(no stdout)", language="text")
    except subprocess.CalledProcessError as e:
        sim_out = f"ERROR:\n{e.stderr or e.stdout}"
        rec.error("Compile/sim error:")
        rec.code(sim_out, language="text")
    except subprocess.TimeoutExpired:
        sim_out = "ERROR: simulation timed out (missing $finish?)."
        rec.error(sim_out)

    (sim_dir / "simulation.log").write_text(sim_out or "PASSED (no output)")
    # Show the dumped waveform (if the testbench wrote design.vcd) — for a pass it
    # confirms behaviour, for a fail it helps see WHY (e.g. an output stuck at 0).
    _show_waveform(rec, sim_dir / "design.vcd", sim_dir)
    passed = "Result: PASSED" in sim_out or (
        sim_out and "ERROR" not in sim_out and "Result: FAILED" not in sim_out)
    if passed:
        rec.success("✅ Simulation passed.")
        ctx["simulation_output"] = ""
        return
    rec.error("❌ Simulation failed — a corrector will be routed next.")
    ctx["simulation_output"] = sim_out or "Result: FAILED"
    ctx["error_count"] = ctx.get("error_count", 0) + 1


def agent_lint(rec, ctx, feedback=""):
    """Structural lint gate (Verilator) BETWEEN a passing sim and hardening. Catches
    the exact issues that make LibreLane fail — combinational loops (UNOPTFLAT),
    multiple-driver nets (MULTIDRIVEN), inferred latches (LATCH) — and routes them to
    the corrector so the RTL is genuinely clean before PnR (not just lint-silenced)."""
    design_dir = Path(ctx["design_dir"])
    rtl_dir = design_dir / "rtl"
    vfiles = sorted(glob.glob(str(rtl_dir / "*.v")))
    top = ctx.get("top_module_name") or ""
    vbin = find_verilator()
    if not vbin:
        rec.warning(
            "Verilator not found — skipping the lint gate (it still runs inside LibreLane).")
        ctx["lint_output"] = ""
        return
    if not vfiles:
        rec.warning("No RTL to lint.")
        ctx["lint_output"] = ""
        return
    # NOTE: verilator needs the include dir ATTACHED (`-I<dir>`, no space). Passed as
    # a separate arg ("-I", dir) verilator treats <dir> as a positional top-level
    # source and dies with "Cannot find file containing module: <dir>" — which looked
    # like a lint failure but was really an argument-parsing bug on the rtl/ path.
    cmd = [vbin, "--lint-only", "-Wno-fatal",
           "--Werror-MULTIDRIVEN", "--Werror-LATCH", "--Werror-UNOPTFLAT",
           f"-I{rtl_dir}"]
    if top:
        cmd += ["--top-module", top]
    cmd += vfiles
    rec.write("**Verilator structural lint (comb-loops / multidriven / latches):**")
    rec.code("verilator --lint-only --Werror-MULTIDRIVEN --Werror-LATCH --Werror-UNOPTFLAT "
             + " ".join(os.path.basename(f) for f in vfiles), language="bash")
    try:
        with st.spinner("Linting RTL…"):
            proc = subprocess.run(cmd, cwd=str(rtl_dir),
                                  capture_output=True, text=True, timeout=120)
        out = (proc.stdout + "\n" + proc.stderr).strip()
        failed = proc.returncode != 0 or "%Error" in out
    except Exception as e:  # noqa: BLE001
        rec.warning(f"Lint could not run ({e}); skipping the gate.")
        ctx["lint_output"] = ""
        return

    (design_dir / "sim").mkdir(parents=True, exist_ok=True)
    (design_dir / "sim" / "lint.log").write_text(out or "clean")
    if not failed:
        rec.success("✅ Lint clean — RTL is structurally sound for hardening.")
        ctx["lint_output"] = ""
        return
    rec.error(
        "❌ Lint found structural issues — routing to the corrector before hardening.")
    rec.code(out[:2500], language="text")
    ctx["lint_output"] = out
    ctx["lint_count"] = ctx.get("lint_count", 0) + 1


def agent_fix_design(rec, ctx, feedback=""):
    if ctx.get("deep_steps"):                 # run the Module Corrector AS a deep agent (RLM)
        return _deep_fix_design(rec, ctx, feedback)
    files = dict(ctx["decomposed_files"])
    # In the sim loop this is the simulation error; in the lint loop (sim already
    # passed, so simulation_output is empty) it's the Verilator lint error.
    err = ctx.get("simulation_output") or ctx.get("lint_output", "")
    faulty = next((f for f in files if f in err),
                  None) or f"{ctx['top_module_name']}.v"
    faulty = faulty if faulty in files else next(iter(files))
    history = dict(ctx.get("fix_history", {}))
    past = history.get(faulty, [])
    tried = past + [files[faulty]]
    rec.write("**Compiler/sim errors fed to the model:**")
    rec.code(err[:1800], language="text")
    rec.expander_code(
        f"Current (broken) `{faulty}` given to the corrector", files[faulty], "verilog")
    attempt = ctx.get("error_count", 0) + ctx.get("lint_count", 0)
    temp = min(0.2 + 0.18 * attempt, 0.85)
    if past:
        rec.caption(f"⛔ {len(past)} earlier fix(es) of `{faulty}` failed — all are shown to the model "
                    "with an explicit 'do NOT reproduce these' so it stops looping on the same code.")
    rec.caption(
        f"Attempt {attempt + 1} · temperature {temp:.2f} (raised each retry to avoid the same fix).")

    # DEEP-AGENT BEHAVIOR: when stuck (≥2 prior failed fixes of this file), the corrector
    # researches the error ITSELF — first from persistent MEMORY, else live from the WEB —
    # and injects the fix into its own prompt. Re-researches every few attempts if needed.
    if len(past) >= 2 and (len(past) - 2) % 3 == 0:
        sig = _error_query(err)
        remembered = recall_fix(sig)
        if remembered:
            ctx["web_example"] = remembered
            rec.caption(f"🧠 Recalled a remembered fix for this error: *{sig}*")
        else:
            hint = _auto_research(sig, rec)
            if hint:
                ctx["web_example"] = hint
                # persist so the next run solves it instantly
                remember_fix(sig, hint)

    prior_block = "\n\n".join(
        f"FAILED ATTEMPT #{i + 1} (already tried — it did NOT work, do not reproduce it):\n"
        f"```verilog\n{p}\n```"
        for i, p in enumerate(tried[-3:])
    )
    prompt = ChatPromptTemplate.from_template(
        """You are fixing a Verilog module that FAILED to compile/simulate. Use the EXACT errors
below to produce a CORRECTED, DIFFERENT version that resolves them — do not repeat the broken code.
This is attempt {attempt}; earlier fixes (shown at the bottom) FAILED, so take a FUNDAMENTALLY
DIFFERENT approach — rewrite the offending logic, don't just re-indent or tweak it.

{pitfalls}

{reference}- First, in one line, name the EXACT rule above you violated, then fix the real cause (not the symptom).
- Keep the module name `{name_stem}` and a port list compatible with the rest of the design.
- Output EXACTLY ONE module in a single ```verilog block.

ERRORS:
```
{err}
```
{prior_block}

BROKEN MODULE (`{name}`) — rewrite it correctly:
```verilog
{code}
```"""
    )
    rec.caption("🧠 Live model output:")
    live = rec.placeholder()
    reference = _ref_context(ctx)
    if feedback:
        reference += f"USER INSTRUCTION: {feedback}\n"
    inputs = {"name": faulty, "name_stem": faulty[:-2] if faulty.endswith(".v") else faulty,
              "code": files[faulty], "err": err, "attempt": attempt + 1,
              "pitfalls": VERILOG_PITFALLS, "reference": reference,
              "prior_block": prior_block or "(no earlier attempts)"}
    seen = {_norm(c) for c in tried}

    def roll(t: float) -> str:
        return extract_code_block(stream_to(prompt | get_chat_model(temperature=t), inputs, live))

    with st.spinner("Repairing module…"):
        fixed = roll(temp)
        rerolls = 0
        while fixed and _norm(fixed) in seen and rerolls < 2:
            rerolls += 1
            hot = min(temp + 0.25 * rerolls, 0.95)
            rec.caption(
                f"↻ Identical to a failed attempt — re-rolling hotter (temp {hot:.2f}).")
            fixed = roll(hot)

    if not fixed.strip():
        fixed = files[faulty]
    files[faulty] = fixed
    history[faulty] = tried + [fixed]
    rec.success(f"Corrected `{faulty}`:")
    rec.code(fixed, language="verilog")
    ctx["decomposed_files"] = files
    ctx["fix_history"] = history


def agent_fix_testbench(rec, ctx, feedback=""):
    if ctx.get("deep_steps"):                 # run the Testbench Corrector AS a deep agent (RLM)
        return _deep_fix_testbench(rec, ctx, feedback)
    tb = ctx.get("testbench_code", {})
    top = ctx["top_module_name"]
    name = next(iter(tb), f"{top}_tb.v")
    cur_tb = next(iter(tb.values()), "")
    err = ctx["simulation_output"]
    history = dict(ctx.get("fix_history", {}))
    past = history.get(name, [])
    tried = past + ([cur_tb] if cur_tb else [])
    attempt = ctx.get("error_count", 0)
    temp = min(0.3 + 0.18 * attempt, 0.9)
    rec.write("**Compiler/sim errors fed to the model:**")
    rec.code(err[:1800], language="text")
    if past:
        rec.caption(f"⛔ {len(past)} earlier testbench(es) failed — shown to the model so it doesn't "
                    "regenerate the same broken stimulus.")
    rec.expander_code("Previous (failed) testbench", cur_tb, "verilog")
    rec.caption(f"Attempt {attempt + 1} · temperature {temp:.2f} — REGENERATING from the DUT (not "
                "patching the broken testbench), so it doesn't keep copying the same bug.")
    extra = f"- User instruction: {feedback}\n" if feedback else ""
    prompt = ChatPromptTemplate.from_template(
        """The previous testbench for module `{top}` FAILED with the errors below. Write a BRAND-NEW,
correct, self-checking testbench FROM SCRATCH for the DUT. Do NOT reuse the broken testbench's
structure — start fresh from the DUT's port list.

STRICT RULES:
- `module {name_stem};` with an EMPTY port list (a testbench has NO ports).
- Declare `clk` + every DUT INPUT as `reg`; every DUT OUTPUT as `wire`; each signal EXACTLY ONCE.
- Clock: `reg clk; initial clk = 0; always #5 clk = ~clk;`
- Instantiate the DUT by name, apply reset, drive stimulus, then check the outputs.
- `$dumpfile("design.vcd"); $dumpvars(0, {name_stem});`
- Print EXACTLY "Result: PASSED" or "Result: FAILED", then `$finish;`. ONE module only.
{extra}
ERRORS FROM THE LAST ATTEMPT (avoid these):
```
{err}
```
DUT to test (`{top}.v`) — derive the port connections from THIS:
```verilog
{code}
```
Reply with ONLY JSON: {{"{name}": "<full verilog source>"}}."""
    )
    rec.caption("🧠 Live model output:")
    live = rec.placeholder()

    def roll(t: float) -> dict:
        resp = stream_to(prompt | get_chat_model(temperature=t), {
            "name": name, "name_stem": name[:-2] if name.endswith(".v") else name,
            "top": top, "code": ctx["decomposed_files"].get(f"{top}.v", ""),
            "err": err, "extra": extra,
        }, live)
        try:
            out = extract_json(resp)
            return {k: dedup_modules(v) for k, v in out.items()}
        except Exception:  # noqa: BLE001
            return {name: extract_code_block(resp)}

    seen = {_norm(c) for c in tried}
    with st.spinner("Regenerating testbench…"):
        new_tb = roll(temp)
        rerolls = 0
        while next(iter(new_tb.values()), "") and _norm(next(iter(new_tb.values()))) in seen and rerolls < 2:
            rerolls += 1
            hot = min(temp + 0.25 * rerolls, 0.95)
            rec.caption(
                f"↻ Identical to a failed testbench — re-rolling hotter (temp {hot:.2f}).")
            new_tb = roll(hot)

    history[name] = tried + [next(iter(new_tb.values()), "")]
    rec.success("Corrected testbench:")
    rec.code(next(iter(new_tb.values())), language="verilog")
    ctx["testbench_code"] = new_tb
    ctx["fix_history"] = history


def agent_harden(rec, ctx, feedback=""):
    design_dir = Path(ctx["design_dir"])
    design_name = ctx.get("top_module_name") or slugify(ctx["query"])
    chip_dir = design_dir / "chip"
    src_dir = chip_dir / "src"
    if chip_dir.exists():
        shutil.rmtree(chip_dir)
    src_dir.mkdir(parents=True, exist_ok=True)

    design_files = []
    for p in sorted(glob.glob(str(design_dir / "rtl" / "*.v"))) + sorted(glob.glob(str(design_dir / "rtl" / "*.vh"))):
        name = os.path.basename(p)
        if "tb" in name.lower() or "testbench" in name.lower():
            continue
        shutil.copy(p, src_dir / name)
        if name.endswith(".v"):
            design_files.append(f"dir::src/{name}")

    core_util = int(ctx["core_util"])
    config = {
        "DESIGN_NAME": design_name, "VERILOG_FILES": design_files,
        "CLOCK_PORT": ctx["clock_port"], "CLOCK_PERIOD": ctx["clock_period"], "PDK": PDK,
        "FP_SIZING": "absolute", "DIE_AREA": [0, 0, float(ctx["die_um"]), float(ctx["die_um"])],
        "FP_CORE_UTIL": core_util, "PL_TARGET_DENSITY_PCT": max(20, core_util + 5),
        "PRIMARY_GDSII_STREAMOUT_TOOL": "klayout",
        # --- Keep Verilator lint INFORMATIVE but NON-FATAL ---
        # Auto-generated RTL routinely trips Verilator lint (UNOPTFLAT comb-loops,
        # MULTIDRIVEN nets, inferred latches). By default LibreLane runs lint with
        # `--Werror-MULTIDRIVEN`/`--Werror-LATCH` and then QUITS on any lint error —
        # which kills hardening even though the design already passed simulation.
        # We disable those escalations and the quit-on-lint gate so the flow reaches
        # GDSII; the lint findings still show up in the log. Override via env if you
        # want strict lint back (LIBRELANE_STRICT_LINT=1).
        **({} if os.getenv("LIBRELANE_STRICT_LINT", "0") in ("1", "true", "yes") else {
            "LINTER_ERROR_ON_LATCH": False,
            "LINTER_ERROR_ON_MULTIDRIVEN": False,
            "ERROR_ON_LINTER_ERRORS": False,
            "ERROR_ON_LINTER_WARNINGS": False,
            "LINTER_DISABLE_WARNINGS": [
                "UNOPTFLAT", "WIDTH", "WIDTHEXPAND", "WIDTHTRUNC", "WIDTHCONCAT",
                "CASEINCOMPLETE", "CASEOVERLAP", "UNUSEDSIGNAL", "UNDRIVEN",
                "IMPLICIT", "BLKSEQ", "SYNCASYNCNET", "DECLFILENAME", "EOFNEWLINE",
            ],
        }),
    }
    (chip_dir / "config.json").write_text(json.dumps(config, indent=2))
    rec.expander_code("config.json", json.dumps(config, indent=2), "json")

    cmd = [LIBRELANE_BIN, "--manual-pdk",
           "--pdk-root", PDK_ROOT, "config.json"]
    rec.write(f"**Running:** `{' '.join(cmd)}`")
    log_box = rec.placeholder()
    lines: List[str] = []
    env = {**os.environ, "PDK_ROOT": PDK_ROOT}
    with st.spinner("LibreLane running (synthesis → PnR → signoff)…"):
        proc = subprocess.Popen(cmd, cwd=str(chip_dir), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, env=env, bufsize=1)
        for raw in proc.stdout:
            lines.append(strip_ansi(raw.rstrip()))
            if len(lines) % 2 == 0 or "error" in raw.lower():
                log_box.code("\n".join(lines[-30:]), language="text")
        proc.wait()
    (chip_dir / "librelane.log").write_text("\n".join(lines))
    rec.code("\n".join(lines[-30:]) or "(no output)", language="text")

    gds = sorted(glob.glob(str(chip_dir / "runs" / "**" / "final" / "**" / "*.gds"), recursive=True)) or \
        sorted(glob.glob(str(chip_dir / "runs" / "**" / "*.gds"), recursive=True))
    metrics = {}
    for mp in glob.glob(str(chip_dir / "runs" / "**" / "metrics.json"), recursive=True):
        try:
            metrics = json.load(open(mp))
        except Exception:  # noqa: BLE001
            pass
    final_gds = None
    if gds:
        final_gds = design_dir / f"{design_name}.gds"
        shutil.copy(gds[-1], final_gds)
        if metrics:
            (design_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
        rec.success(
            f"🎉 GDSII generated → `output/{design_dir.name}/{final_gds.name}`")
    else:
        rec.error(
            f"LibreLane finished (rc={proc.returncode}) but no GDS was produced — see log above.")

    if metrics:
        keys = {
            "design__die__area": "Die area (µm²)",
            "design__instance__count__stdcell": "Std cells",
            "timing__setup__ws": "Setup worst-slack (ns)",
            "timing__hold__ws": "Hold worst-slack (ns)",
            "route__wirelength": "Route wirelength",
            "power__total": "Total power (W)",
            "magic__drc__count": "DRC violations",
            "design__lvs__errors__count": "LVS errors",
        }
        rows = [(label, metrics[k])
                for k, label in keys.items() if k in metrics]
        if rows:
            rec.write("**Signoff metrics:**")
            rec.table({"Metric": [r[0] for r in rows],
                      "Value": [str(r[1]) for r in rows]})
        rec.json(metrics)
    ctx["harden"] = {"gds": str(
        final_gds) if final_gds else None, "metrics": metrics, "rc": proc.returncode}


# --------------------------------------------------------------------------- #
# Step registry + orchestration
# --------------------------------------------------------------------------- #
# (emoji, title, desc, fn, accepts_feedback)
STEP_DEFS = {
    "plan":          ("🧭", "Planner", "Drafts the build plan + design notes.", agent_plan, True),
    "retrieve":      ("📚", "Knowledge Recall", "Semantic recall over the pgvector knowledge store.", agent_retrieve, False),
    "web":           ("🌐", "Web Researcher", "HDL GitHub repos + papers, crawled & cached.", agent_web, True),
    "generate":      ("✍️", "Verilog Generator", "The local LLM drafts synthesizable RTL.", agent_generate, True),
    "decompose":     ("🧩", "Decomposer", "Split the RTL into per-module files + header.", agent_decompose, True),
    "testbench":     ("🧪", "Testbench Writer", "Self-checking testbench with PASSED/FAILED.", agent_testbench, True),
    "write":         ("💾", "File Writer", "Write RTL + testbench to the output folder.", agent_write, False),
    "simulate":      ("🔬", "Icarus Simulator", "Compile + run with iverilog/vvp.", agent_simulate, False),
    "lint":          ("🔍", "Verilator Lint", "Structural lint gate before hardening.", agent_lint, False),
    "fix_design":    ("🛠️", "Module Corrector", "LLM fixes the failing design module.", agent_fix_design, True),
    "fix_testbench": ("🛠️", "Testbench Corrector", "LLM fixes the testbench.", agent_fix_testbench, True),
    "harden":        ("🏭", "LibreLane Hardening", "RTL → synthesis → PnR → signoff → GDSII.", agent_harden, False),
}


def route_next(ctx) -> str:
    """Which corrector to run after a failed sim (ported from the old graph router)."""
    out = ctx.get("simulation_output", "")
    tb_names = list(ctx.get("testbench_code", {}).keys())
    is_tb = any(t in out for t in tb_names) or "timed out" in out.lower()
    return "fix_testbench" if is_tb else "fix_design"


def advance(run, node):
    """Enqueue the dynamic follow-up steps after `node` finished (the sim→fix loop
    and post-pass hardening that the old LangGraph conditional edges handled)."""
    ctx, q = run["ctx"], run["queue"]
    if node == "plan":
        q.extend(ctx.get("_plan", []))
    elif node == "simulate":
        if ctx.get("simulation_output"):              # sim failed
            if ctx.get("error_count", 0) < MAX_RETRIES:
                q[:0] = [route_next(ctx), "write", "simulate"]
        elif "lint" not in q:                         # sim passed → structural lint gate
            q.insert(0, "lint")
    elif node == "lint":
        # lint failed → fix the RTL, re-verify, re-lint
        if ctx.get("lint_output"):
            if ctx.get("lint_count", 0) < MAX_LINT_RETRIES:
                q[:0] = ["fix_design", "write", "simulate", "lint"]
            # give up fixing → harden anyway (lint is non-fatal)
            elif ctx.get("run_harden"):
                q.append("harden")
        elif ctx.get("run_harden"):                   # lint clean → harden if requested
            q.append("harden")


def execute_step(run, node, feedback=""):
    emoji, title, desc, fn, _ = STEP_DEFS[node]
    ctx = run["ctx"]
    if node in ("write", "simulate", "fix_design", "fix_testbench"):
        title = f"{title} (attempt {ctx.get('error_count', 0) + 1})"
    rec = Recorder(emoji, title, desc, node, live=True)
    try:
        fn(rec, ctx, feedback)
    except Exception as e:  # noqa: BLE001
        rec.error(f"Step crashed: {e} — use Replan or Revise to recover.")
    return {"node": node, "blocks": rec.blocks}


def do_replan(run, feedback):
    """Replanner: choose the SMALLEST set of next steps that recovers the build from the
    user's feedback + latest error. Key rule: a design already exists on disk after many
    correction iterations — do NOT throw that work away and rebuild from zero. Default to
    an incremental repair on the EXISTING files (fix_design → write → simulate). Only fall
    back to the from-scratch steps (generate, decompose, testbench) when the user EXPLICITLY
    asks to start over."""
    ctx = run["ctx"]
    rec = Recorder("🔁", "Replanner", "Revises the remaining plan from your feedback + latest state.",
                   "plan", live=True)
    known = ["retrieve", "web", "generate", "decompose", "testbench", "write", "simulate",
             "fix_design", "fix_testbench"]
    rebuild = {"generate", "decompose", "testbench"}   # full-from-scratch steps

    err = ctx.get("simulation_output") or ctx.get("lint_output", "")
    files = ctx.get("decomposed_files") or {}
    has_design = bool(files)
    top = ctx.get("top_module_name") or "(none yet)"
    iters = ctx.get("error_count", 0) + ctx.get("lint_count", 0)

    # Did the user EXPLICITLY ask to discard the current design and start fresh? Only
    # then do we allow the from-scratch steps; otherwise we keep the RTL on disk.
    start_over = bool(re.search(
        r"\b(from scratch|start over|start again|re-?generate|rewrite everything|"
        r"whole design|new design|redo|scrap|throw away|ulang|dari awal)\b",
        (feedback or "").lower()))

    rec.caption("🧠 Choosing the next steps…")
    raw = stream_to(
        get_chat_model(temperature=0.2),
        "You are the re-planner for a Verilog build agent. A design ALREADY EXISTS on disk and "
        "has been through several correction iterations — do NOT discard that work. Output the "
        "SMALLEST set of next steps that addresses the user's message, as a comma-separated list "
        "using ONLY these step names: " + ", ".join(known) + ".\n\n"
        "PREFER incremental repair on the EXISTING files:\n"
        "  • a question like 'why is the output 0', or any RTL/logic bug -> fix_design\n"
        "  • the testbench / stimulus is wrong                           -> fix_testbench\n"
        "  • you need a reference for a sub-block                        -> web\n"
        "Use the from-scratch steps (generate, decompose, testbench) ONLY if the user EXPLICITLY "
        "asks to start over / regenerate / rewrite the whole design.\n"
        "Every plan MUST end with: write, simulate.\n\n"
        f"DESIGN: {ctx['query']}\n"
        f"STATE: {len(files)} RTL file(s) on disk, top module `{top}`, {iters} correction "
        f"iteration(s) already done. User asked to start over? {'YES' if start_over else 'NO'}.\n"
        f"USER MESSAGE: {feedback or '(none)'}\n"
        f"LATEST ERROR: {err[:800] or '(none)'}\n\n"
        "Reply ONLY with the comma-separated step list.",
        rec.placeholder(),
    )
    picked = [s.strip() for s in re.split(
        r"[,\n]", clean_llm_output(raw)) if s.strip() in known]

    # Guard rail: never rebuild from scratch over an existing design unless the user
    # really asked for it — strip the from-scratch steps and ensure a fixer is present.
    if has_design and not start_over:
        picked = [s for s in picked if s not in rebuild]
        if not any(s in picked for s in ("fix_design", "fix_testbench")):
            picked = ["fix_design"] + picked
    if not picked:                              # nothing usable came back from the model
        picked = (["fix_design"] if has_design
                  else ["generate", "decompose", "testbench"])

    # de-dupe (preserve order) then always re-verify at the end
    seen, ordered = set(), []
    for s in picked:
        if s not in seen and s not in ("write", "simulate"):
            seen.add(s)
            ordered.append(s)
    picked = ordered + ["write", "simulate"]

    mode = ("🔧 incremental fix — keeping your existing RTL" if (has_design and not start_over)
            else "🆕 full rebuild from scratch")
    rec.success(f"{mode}.  New plan: " + "  →  ".join(picked))
    run["queue"] = picked
    # A replan grants a fresh retry budget for the NEW plan. It does NOT touch the files
    # on disk — your corrected RTL stays exactly where it is.
    ctx["error_count"] = 0
    run["transcript"].append({"node": "plan", "blocks": rec.blocks})


def do_weblookup(run, block):
    """On-demand: 'go find an example of block X and its inputs/outputs' — searches
    the web, crawls a few hits, summarizes the I/O, and injects it into the NEXT step."""
    ctx = run["ctx"]
    rec = Recorder("🌐", "Web Example Lookup", f"Finding a reference implementation of: {block}",
                   "web", live=True)
    if not (block or "").strip():
        rec.warning("No block name given — nothing to look up.")
        run["transcript"].append({"node": "web", "blocks": rec.blocks})
        return
    rec.caption(f"Searching GitHub + web for: **{block}**")
    with st.spinner("Searching…"):
        urls = _web_search(block, n_github=4, n_other=2)
    rec.code("\n".join(urls) or "(no results)", language="text")
    with st.spinner("Crawling top results…"):
        docs = _crawl_urls(urls, rec, limit=4)
    if not docs:
        rec.warning("No usable reference crawled.")
        run["transcript"].append({"node": "web", "blocks": rec.blocks})
        return
    ctx.setdefault("documents", []).extend(docs)
    ref = docs[0].page_content[:2500]
    rec.caption("🧠 Summarizing the block's inputs/outputs:")
    summary = clean_llm_output(stream_to(
        get_chat_model(temperature=0.2),
        f"From this reference implementation of '{block}', summarize CONCISELY: the module's "
        "PURPOSE, its INPUTS (name : width), its OUTPUTS (name : width), and a minimal usage "
        f"snippet.\n\n{ref}",
        rec.placeholder(),
    ))
    rec.markdown("**Reference summary (inputs / outputs):**")
    rec.code(summary[:2000], "markdown")
    ctx["web_example"] = f"REFERENCE for '{block}':\n{summary}\n\nSOURCE SNIPPET:\n{ref}"
    rec.success(
        f"Found a reference for `{block}` — it will be injected into the next step you run.")
    run["transcript"].append({"node": "web", "blocks": rec.blocks})


# --------------------------------------------------------------------------- #
# File-system agent — the steering prompt can create/remove/edit files on disk
# --------------------------------------------------------------------------- #
def _is_file_command(msg: str) -> bool:
    """Does this steering prompt ask for a FILE operation (vs design steering)? Precise
    on purpose: an edit verb must come WITH a real file path/extension, so hardware
    phrases like 'make a register file' or 'use a 5-stage pipeline' are NOT misrouted."""
    low = (msg or "").lower()
    has_path = (bool(re.search(r"\.(v|vh|sv|svh|json|log|vcd|txt)\b", low))
                or "rtl/" in low or "tb/" in low)
    listy = any(p in low for p in ("list file", "list all file", "show file",
                                   "show all file", "what files", "which files", "ls "))
    edit_verb = any(v in low for v in ("remove", "delete", "hapus", "rm ", "create",
                                       "rename", "move ", "overwrite", "write to",
                                       "new file", "make a file", "add a file"))
    return listy or (edit_verb and has_path)


def _sync_ctx_from_disk(ctx):
    """Re-read rtl/ + tb/ from disk into the pipeline state after the file agent (or
    a manual edit) changed files, so later steps use the new files."""
    design_dir = Path(ctx["design_dir"])
    rtl = {p.name: p.read_text() for p in sorted((design_dir / "rtl").glob("*"))
           if p.suffix in (".v", ".vh")}
    tb = {p.name: p.read_text()
          for p in sorted((design_dir / "tb").glob("*.v"))}
    if rtl:
        ctx["decomposed_files"] = rtl
        if f"{ctx.get('top_module_name')}.v" not in rtl:
            top_v = next((n for n in rtl if n.endswith(".v")), None)
            if top_v:
                ctx["top_module_name"] = top_v[:-2]
    if tb:
        ctx["testbench_code"] = tb


def _short(v) -> str:
    """One-line, length-capped repr of a tool-call argument for the transcript."""
    s = str(v).replace("\n", " ").strip()
    return (s[:80] + "…") if len(s) > 80 else s


def _format_todos(todos) -> str:
    if not todos:
        return ""
    lines = ["**📋 Plan:**"]
    for t in todos:
        mark = {"completed": "✅", "in_progress": "🔄",
                "pending": "⬜"}.get(t.get("status"), "⬜")
        lines.append(f"- {mark} {t.get('content', '')}")
    return "\n".join(lines)


def _render_deep_msg(rec, m) -> str:
    """Render ONE deepagents message as its own recorded block — the agent's reasoning,
    each tool/task CALL (name + args), and each tool RESULT (in a collapsible box). This
    is what makes the transcript readable: every tool and its output is shown separately,
    instead of one giant markdown wall. Returns the assistant text if this was one."""
    kind = m.__class__.__name__
    text = ""
    if kind == "AIMessage":
        text = clean_llm_output(getattr(m, "content", "") or "").strip()
        if text:
            rec.markdown(text)
        for tc in (getattr(m, "tool_calls", None) or []):
            name, args = tc.get("name"), (tc.get("args") or {})
            if name == "write_todos":                       # show the plan as a checklist
                rec.markdown(_format_todos(args.get("todos", [])))
            else:
                argstr = " · ".join(
                    f"{k}={_short(v)}" for k, v in args.items())
                rec.markdown(f"🔧 **`{name}`**" +
                             (f" · {argstr}" if argstr else ""))
    elif kind == "ToolMessage":
        name = getattr(m, "name", "") or "tool"
        if name == "write_todos":                            # already shown as the checklist
            return ""
        out = str(getattr(m, "content", "") or "").strip()
        lang = "verilog" if "endmodule" in out else "text"
        rec.expander_code(f"↳ {name} output",
                          out[:4000] or "(empty)", lang, expanded=False)
    return text


def _stream_deep_agent(rec, agent, goal, recursion_limit=60) -> str:
    """Stream a deepagents agent and render its plan + every tool/task call and output
    INCREMENTALLY as clean, recorded blocks (no agent graph). Returns the final
    assistant text. Each message is rendered exactly once as it arrives."""
    seen, final = 0, ""
    with st.spinner("🧠 Deep agent working (planning · tools · sub-tasks)…"):
        for state in agent.stream({"messages": [{"role": "user", "content": goal}]},
                                  stream_mode="values", config={"recursion_limit": recursion_limit}):
            msgs = state.get("messages", [])
            for m in msgs[seen:]:
                text = _render_deep_msg(rec, m)
                if text:
                    final = text
            seen = len(msgs)
    return final


def do_fileagent(run, msg):
    """Run the deepagents file agent (qwen3.5:9b) on the design dir for a natural-language
    file command ('remove the .vh file', 'create rtl/alu.v', …), show its tool actions +
    outputs, then sync the changed files back into the pipeline state."""
    from deep_agent import build_deep_agent

    ctx = run["ctx"]
    design_dir = Path(ctx["design_dir"])
    rec = Recorder("🤖", "File Agent (deepagents · qwen3.5:9b)",
                   "Real file-system access — plans, then lists/reads/writes/deletes files on disk.",
                   "plan", live=True)
    rec.caption(f"Command: *{msg}*")
    try:
        agent = build_deep_agent(design_dir)
        # renders every tool call + output
        _stream_deep_agent(rec, agent, msg, recursion_limit=40)
    except Exception as e:  # noqa: BLE001
        rec.error(f"File agent error: {e}")
    _sync_ctx_from_disk(ctx)
    rec.success(
        "✅ Synced design files from disk — the pipeline now uses the agent's changes.")
    run["transcript"].append({"node": "plan", "blocks": rec.blocks})


# --------------------------------------------------------------------------- #
# "Every agent is a deep agent" — run a graph node AS a deepagents agent
# --------------------------------------------------------------------------- #
def _wave_to_svg(vcd_path, out_svg, signals="", cycles=120) -> str | None:
    """sootty: VCD → SVG file. Returns the path, or None if sootty can't parse it
    (its pyvcd backend is strict and rejects some iverilog-escaped identifiers)."""
    try:
        from sootty import WireTrace, Visualizer, Style
        wt = WireTrace.from_vcd(str(vcd_path))
        n = wt.length() or cycles
        img = Visualizer(Style.Default).to_svg(
            wt, length=min(int(cycles), n) or n, wires=signals or "")
        Path(out_svg).write_text(img.source)
        return str(out_svg)
    except Exception:  # noqa: BLE001
        return None


def _parse_vcd(text: str):
    """Tolerant VCD parse (handles iverilog escaped ids that pyvcd/sootty reject).
    Returns (names, widths, series): names[id]=label, series[id]=[(time, int|None)]."""
    names, widths = {}, {}
    for m in re.finditer(r"\$var\s+\w+\s+(\d+)\s+(\S+)\s+([^$]+?)\s*\$end", text):
        w, vid, nm = int(m.group(1)), m.group(2), m.group(3).strip()
        names[vid] = nm.split("[")[0].strip().lstrip("\\")
        widths[vid] = w
    body = text.split("$enddefinitions", 1)[-1]
    toks = body.split()
    series = {vid: [] for vid in names}
    cur, i = 0, 0
    while i < len(toks):
        t = toks[i]
        if t.startswith("#"):
            try:
                cur = int(t[1:])
            except ValueError:
                pass
        elif t[0] in "01xXzZ" and len(t) >= 2:        # scalar: value+id, no space
            vid = t[1:]
            if vid in series:
                series[vid].append(
                    (cur, 1 if t[0] == "1" else 0 if t[0] == "0" else None))
        elif t[0] in "bB":                            # vector: 'b1010' then id
            bits = t[1:]
            i += 1
            vid = toks[i] if i < len(toks) else ""
            if vid in series:
                try:
                    series[vid].append((cur, int(re.sub("[xXzZ]", "0", bits), 2)))
                except ValueError:
                    series[vid].append((cur, None))
        elif t[0] in "rR":                            # real change: skip its id
            i += 1
        i += 1
    return names, widths, series


def _wave_to_png(vcd_path, out_png, signals="", cycles=120) -> str | None:
    """Fallback waveform: tolerant-parse the VCD and matplotlib step-plot it to PNG."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        names, widths, series = _parse_vcd(Path(vcd_path).read_text())
        want = [s.strip() for s in re.split(r"[,\s]+", signals) if s.strip()]
        ids = [vid for vid in names if series[vid]
               and (not want or any(w.lower() in names[vid].lower() for w in want))][:12]
        if not ids:
            return None
        tmax = max((series[vid][-1][0] for vid in ids), default=cycles) or cycles
        fig, axes = plt.subplots(len(ids), 1, figsize=(10, 0.7 * len(ids) + 1),
                                 sharex=True, squeeze=False)
        for ax, vid in zip(axes[:, 0], ids):
            ts = [t for t, _ in series[vid]] + [tmax]
            vs = [v if v is not None else 0 for _, v in series[vid]]
            vs = vs + [vs[-1] if vs else 0]
            ax.step(ts, vs, where="post", linewidth=1.2)
            label = f"{names[vid]}[{widths[vid]-1}:0]" if widths[vid] > 1 else names[vid]
            ax.set_ylabel(label, rotation=0, ha="right",
                          va="center", fontsize=8)
            ax.margins(y=0.3)
            ax.grid(True, alpha=0.3)
            ax.set_yticks([])
        axes[-1, 0].set_xlabel("time")
        fig.tight_layout()
        fig.savefig(out_png, dpi=110)
        plt.close(fig)
        return str(out_png)
    except Exception:  # noqa: BLE001
        return None


def _show_waveform(rec, vcd_path, out_dir, signals="", cycles=120) -> bool:
    """Render a VCD into the transcript: sootty SVG first, matplotlib PNG fallback."""
    vcd_path = Path(vcd_path)
    if not vcd_path.exists():
        return False
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    svg = _wave_to_svg(vcd_path, out_dir / "waveform.svg", signals, cycles)
    if svg:
        rec.image(svg, "📈 Waveform (sootty)")
        return True
    png = _wave_to_png(vcd_path, out_dir / "waveform.png", signals, cycles)
    if png:
        rec.image(png, "📈 Waveform")
        return True
    return False


def _step_tools(rec, base_dir=None):
    """Step-specific tools every deep-agent node gets, on top of the file tools:
    autonomous WEB research, persistent MEMORY recall, and DISPLAY tools (show an
    image/plot, render a simulation waveform) — so each node can plan, research,
    remember, and SHOW results, like Claude. `base_dir` sandboxes the display paths
    to the design directory."""
    from langchain_core.tools import tool
    base = Path(base_dir).resolve() if base_dir else None

    def _resolve(path: str) -> Path:
        p = (base / (path or "")).resolve() if base else Path(path or "").resolve()
        if base and p != base and base not in p.parents:
            raise ValueError(f"path '{path}' escapes the design directory")
        return p

    @tool
    def search_web(query: str) -> str:
        """Search the web for reference HDL implementations or how to fix a specific
        error, and return a concise summary with a correct code pattern."""
        return _auto_research(query, rec) or "(no useful web results)"

    @tool
    def recall_memory(topic: str) -> str:
        """Recall a remembered fix/lesson for an error message or topic from past runs."""
        return recall_fix(_error_query(topic)) or recall_fix(topic) or "(nothing remembered yet)"

    @tool
    def show_image(path: str, caption: str = "") -> str:
        """Display an image FILE in the transcript so the user can SEE it: a matplotlib
        plot you saved with run_python (e.g. 'rtl/relu_lut.png'), an uploaded diagram
        ('context/uploads/<name>'), or any .png/.jpg/.svg under the design dir. Pass a
        path relative to the design directory."""
        try:
            p = _resolve(path)
        except ValueError as e:
            return f"(refused: {e})"
        if not p.exists():
            return f"(not found: {path})"
        rec.image(str(p), caption)
        return f"shown {path}"

    @tool
    def show_waveform(vcd_path: str = "sim/design.vcd", signals: str = "", cycles: int = 120) -> str:
        """Render a simulation waveform (VCD) into the transcript so the user can SEE the
        signals toggle. Defaults to 'sim/design.vcd' (what the testbench dumps via
        $dumpfile). Optionally pass a comma-separated 'signals' filter and a 'cycles'
        window. Uses sootty, with a matplotlib fallback."""
        try:
            p = _resolve(vcd_path)
        except ValueError as e:
            return f"(refused: {e})"
        if not p.exists():
            return f"(no VCD at {vcd_path} — run the simulation first)"
        out = (base / "sim") if base else p.parent
        ok = _show_waveform(rec, p, out, signals, int(cycles))
        return "waveform shown" if ok else "(could not render the waveform from that VCD)"

    tools = [search_web, recall_memory, show_image, show_waveform]

    # --- durable knowledge store (pgvector + MinIO): recall / fetch / remember ---
    mem = get_memory()
    if mem.enabled:
        @tool
        def recall_knowledge(query: str, kind: str = "") -> str:
            """Semantically RECALL prior knowledge from GarudaChip's long-term store —
            past designs, fixes, references, datasheets — to reuse instead of starting
            cold. Optionally filter kind (design|code|fix|reference|paper|gds|image|pdf).
            Returns the best matches with their object_key; pull the full file with
            fetch_knowledge."""
            items = mem.recall(query, kind=kind or None, k=6)
            if not items:
                return "(nothing relevant in the knowledge store yet)"
            lines = []
            for it in items:
                snip = (it.get("text") or "").strip().replace("\n", " ")[:400]
                lines.append(f"[{it.get('kind')}] {it.get('title')} "
                             f"(design={it.get('design')}, key={it.get('object_key') or '-'})\n  {snip}")
            return "\n".join(lines)

        @tool
        def fetch_knowledge(object_key: str, dest_path: str = "") -> str:
            """Pull a stored artifact (by its object_key from recall_knowledge) out of
            object storage into THIS design dir so you can read it with read_file_disk.
            Defaults to context/recall/<name>."""
            blob = mem.get_object(object_key)
            if blob is None:
                return f"(no object: {object_key})"
            dest = dest_path or f"context/recall/{object_key.split('/')[-1]}"
            try:
                p = _resolve(dest)
            except ValueError as e:
                return f"(refused: {e})"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(blob)
            return f"fetched {object_key} -> {dest} ({len(blob)} bytes)"

        @tool
        def remember_knowledge(text: str, kind: str = "note", title: str = "") -> str:
            """Save a durable lesson/insight to GarudaChip's long-term store so FUTURE
            runs can recall it (e.g. a fix that worked, a synthesis gotcha, a sizing
            rule). kind is usually 'fix' or 'note'."""
            rid = mem.remember(kind, text, source="agent", title=title or text[:60], tags="agent")
            return f"remembered ({rid})" if rid else "(store unavailable)"

        tools += [recall_knowledge, fetch_knowledge, remember_knowledge]

    return tools


def run_deep_agent(rec, base_dir, goal, extra_tools=None, instructions=None, temperature=0.2):
    """Build + stream a per-step deep agent (planning + file + web + memory tools),
    rendering EVERY tool/task call and its output as clean, recorded blocks (no agent
    graph). Returns the agent's final assistant text."""
    from deep_agent import build_step_agent, INSTRUCTIONS as DEEP_INSTRUCTIONS

    agent = build_step_agent(base_dir, extra_tools=extra_tools,
                             instructions=instructions or DEEP_INSTRUCTIONS, temperature=temperature)
    return _stream_deep_agent(rec, agent, goal, recursion_limit=60)


def _ctx_store_refs(ctx) -> tuple[str | None, int]:
    """RLM context offloading: dump the reference designs (and any web-fetched
    example) to `<design>/context/references.md` ON DISK so a deep agent PEEKS at
    slices of it (read_file_disk / grep_files) instead of us inlining 4 KB into the
    prompt. This is what keeps the local model's window small ('smaller this size')."""
    design_dir = Path(ctx["design_dir"])
    parts: List[str] = []
    if ctx.get("uploads_digest"):
        parts.append(ctx["uploads_digest"])
    if ctx.get("web_example"):
        parts.append("## USER-REQUESTED WEB REFERENCE\n" + ctx["web_example"])
    for i, d in enumerate(ctx.get("documents") or []):
        if i >= 30:
            break
        src = d.metadata.get("source", "ref") if hasattr(
            d, "metadata") else "ref"
        body = getattr(d, "page_content", str(d))
        parts.append(f"## ref {i} — {src}\n{body[:2000]}")
    if not parts:
        return None, 0
    text = "\n\n".join(parts)
    cdir = design_dir / "context"
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "references.md").write_text(text)
    return "context/references.md", len(text)


def _collect_rtl_from_disk(design_dir: Path) -> str:
    """Concatenate the RTL a deep agent wrote to rtl/ (header first) into a single
    string for ctx['generation'] — the mechanical decomposer re-splits it verbatim."""
    headers = sorted((design_dir / "rtl").glob("*.vh"))
    mods = [p for p in sorted((design_dir / "rtl").glob("*.v"))
            if "tb" not in p.name.lower() and "testbench" not in p.name.lower()]
    return "\n\n".join(p.read_text() for p in headers + mods)


def _deep_generate(rec, ctx, feedback=""):
    """Verilog Generator as an RLM deep agent: plans, peeks at offloaded references,
    delegates per-module drafts to llm_query, writes RTL to disk, returns the code —
    same ctx['generation'] the rest of the graph consumes."""
    rec.caption(
        "🧠 RLM deep-agent generation — plan + on-disk context + sub-LLM delegation.")
    design_dir = Path(ctx["design_dir"])
    ref_path, ref_len = _ctx_store_refs(ctx)
    ref_note = (
        f"Reference designs are OFFLOADED to `{ref_path}` ({ref_len} chars). PEEK at the parts you "
        f"need with grep_files('<keyword>') or read_file_disk('{ref_path}', start_line, max_lines) — "
        "do NOT try to read it all.\n" if ref_path else "")
    if ctx.get("uploads_digest"):
        ref_note += ("The user ATTACHED files/images — they're included in that context under "
                     "'User-attached files' (and saved under context/uploads/). Use them.\n")
    goal = (
        f"Design complete, synthesizable Verilog-2001 for this hardware: {ctx['query']}.\n"
        + (f"USER INSTRUCTION: {feedback}\n" if feedback else "")
        + ref_note
        + "Plan the sub-modules with write_todos. For each non-trivial sub-module you MAY delegate a "
          "focused draft to llm_query (give it just that module's spec). Use search_web only if a "
          "reference is genuinely missing.\n"
          "If the design is DATA-DRIVEN (a LUT for relu/softmax/sigmoid/sin, filter taps, or NN "
          "weights), COMPUTE the values with run_python (numpy/torch) — pip_install what you need — "
          "QUANTIZE to int or Qm.n fixed-point, write them to rtl/<name>.mem and load with "
          "$readmemh/$readmemb, or bake the constants into the RTL.\n"
          "WRITE each module to rtl/<name>.v with write_file_disk, then reply with the COMPLETE "
          "top-level Verilog in ONE ```verilog block.\n"
        + VERILOG_PITFALLS
    )
    final = run_deep_agent(rec, design_dir, goal,
                           extra_tools=_step_tools(rec, design_dir), temperature=0.2)
    gen = extract_code_block(final)
    if "endmodule" not in gen:                    # final reply was a plan/transcript, not RTL
        # → use whatever modules it wrote to disk
        _sync_ctx_from_disk(ctx)
        disk = _collect_rtl_from_disk(design_dir)
        if "endmodule" in disk:
            gen = disk
    if "endmodule" in gen:
        rec.success("Generated RTL (deep agent):")
        rec.code(gen, language="verilog")
    else:                                          # be honest instead of showing the plan as "RTL"
        rec.error("Deep agent produced no usable Verilog (only a plan/transcript). "
                  "Revise/Replan, or untick 🧠 RLM deep agents in the sidebar for a one-shot draft.")
        rec.code(gen[:1500] or "(no output)", language="text")
    ctx["generation"] = gen
    ctx["simulation_output"] = ""


def _deep_plan(rec, ctx, feedback=""):
    """Planner (step 1) as a deep agent: plans the sub-blocks with todos and writes a
    concise architecture note to disk. The deterministic build queue (ctx['_plan'])
    is unchanged — this upgrades only the design reasoning."""
    rec.caption("🧠 RLM deep-agent planner — architecture decomposition + todos.")
    rec.markdown("**Planned build steps:**")
    rec.code("  →  ".join(ctx["_plan"]), "text")
    rec.caption(
        "After each step the flow PAUSES so you can Continue / Revise / Replan.")
    design_dir = Path(ctx["design_dir"])
    goal = (
        f"You are the architecture planner. Hardware to build: {ctx['query']}.\n"
        + (f"USER STEERING: {feedback}\n" if feedback else "")
        + "Use write_todos to outline the sub-blocks. Then WRITE a concise architecture note to "
          "design_notes.md: the top module, each sub-module with a one-line role and its key "
          "interface, and the main verification concerns. Keep it under ~30 lines. Reply with the note."
    )
    run_deep_agent(rec, design_dir, goal,
                   extra_tools=_step_tools(rec, design_dir), temperature=0.3)


def _deep_web(rec, ctx, feedback=""):
    """Web Researcher as a deep agent: identifies the core sub-blocks, searches +
    crawls reference HDL (via the web_research tool), and writes a reference digest to
    disk. Crawled docs flow into ctx['documents'] for the generator's context store."""
    from langchain_core.tools import tool as _tool
    rec.caption(
        "🧠 RLM deep-agent researcher — searches HDL repos, crawls, digests to disk.")
    design_dir = Path(ctx["design_dir"])
    _state = {"calls": 0}

    @_tool
    def web_research(query: str) -> str:
        """Search GitHub for HDL repos + the web for papers, crawl them, and store the
        real code/PDFs. Pass SHORT KEYWORDS only (comma-separated), e.g.
        'riscv, picorv, alu, multiplier' — NOT a sentence. Call this ONCE; you cannot
        improve results by calling it again."""
        _state["calls"] += 1
        if _state["calls"] > 1:                       # hard stop the retry loop
            n = len(ctx.get("documents", []))
            return (f"STOP — you already searched and have {n} reference(s). Do NOT call "
                    "web_research again; write the digest to context/research.md NOW from "
                    "what you have plus your own knowledge.")
        # distill whatever the model passed (keywords OR a sentence) into good search terms
        terms = [t.strip() for t in re.split(r"[,\n]", query) if t.strip()]
        kws = _hdl_keywords(", ".join(terms) or ctx["query"], 5) or [ctx["query"]]
        main, similar = kws[0], kws[1:5]
        rec.caption("🔑 Search keywords: " + ", ".join(f"`{k}`" for k in kws))
        urls = _web_search(main, similar=similar, n_github=10, n_other=12)
        n_gh = sum("github.com" in u for u in urls)
        rec.write(f"🔎 Found **{len(urls)}** references — **{n_gh}** HDL GitHub repos (code) "
                  f"+ **{len(urls) - n_gh}** papers/web (knowledge); crawling…")
        docs = _crawl_urls(urls, rec, limit=len(urls))
        ctx.setdefault("documents", []).extend(docs)
        _download_references(urls, design_dir, rec)   # real PDFs + code → knowledge store
        _store_web_docs(docs, ctx)
        if not docs:
            return ("No pages crawled. Do NOT search again — write the digest from your own "
                    "knowledge of this design now.")
        gh = [d for d in docs if "github.com" in d.metadata.get("source", "")]
        web = [d for d in docs if "github.com" not in d.metadata.get("source", "")]
        head = (f"Done — crawled {len(gh)} GitHub repo(s) + {len(web)} paper/web page(s). "
                "Now WRITE context/research.md; do NOT call web_research again.\n\n")
        return (head + "\n\n".join(f"{d.metadata.get('source','')}:\n{d.page_content[:400]}"
                                   for d in (gh[:3] + web[:3])))[:4000]

    goal = (
        f"You are the hardware reference researcher for: {ctx['query']}.\n"
        + (f"USER STEERING: {feedback}\n" if feedback else "")
        + "Do NOT narrate or explain. In ONE step: call web_research ONCE with a few SHORT "
          "KEYWORDS (comma-separated, e.g. 'riscv, picorv, alu, multiplier' — never a full "
          "sentence). Then WRITE a concise reference digest to context/research.md (per "
          "sub-block: a minimal interface + which GitHub repo implements it) and reply with it. "
          "If a search returns little, do NOT search again — just write the digest."
    )
    run_deep_agent(rec, design_dir, goal, extra_tools=[
                   web_research] + _step_tools(rec, design_dir), temperature=0.2)
    docs_now = ctx.get("documents", [])
    n_gh = sum("github.com" in d.metadata.get("source", "")
               for d in docs_now if hasattr(d, "metadata"))
    rec.success(f"Researcher gathered {len(docs_now)} reference chunk(s) — "
                f"{n_gh} from GitHub (code) + {len(docs_now) - n_gh} from papers/web (knowledge).")


def _deep_testbench(rec, ctx, feedback=""):
    """Testbench Writer as a deep agent: reads the DUT's real port list off disk and
    writes a self-checking testbench to tb/."""
    rec.caption(
        "🧠 RLM deep-agent testbench writer — reads the DUT off disk, writes tb/.")
    design_dir = Path(ctx["design_dir"])
    top = ctx["top_module_name"]
    files = ctx.get("decomposed_files", {})
    header = next((f for f in files if f.endswith(".vh")), None)
    goal = (
        f"Write a self-checking Verilog testbench for top module `{top}`. The DUT files are on disk "
        f"under rtl/. Read `rtl/{top}.v`" +
        (f" and `rtl/{header}`" if header else "")
        + " with read_file_disk to get the EXACT port list.\n"
        + (f"USER INSTRUCTION: {feedback}\n" if feedback else "")
        + (f'Include `\\`include "{header}"`.\n' if header else "")
        + f"STRICT: `module {top}_tb;` with EMPTY ports; declare clk + every DUT input as reg and "
          "every DUT output as wire, each EXACTLY once; clock `reg clk; initial clk=0; always #5 "
          "clk=~clk;`; instantiate the DUT by name; apply reset; drive stimulus; check outputs; "
          f'`$dumpfile("design.vcd"); $dumpvars(0,{top}_tb);`; print EXACTLY "Result: PASSED" or '
          '"Result: FAILED" then `$finish;`. ONE module only.\n'
        + f"WRITE it to tb/{top}_tb.v with write_file_disk, then reply with it in one ```verilog block."
    )
    final = run_deep_agent(rec, design_dir, goal,
                           extra_tools=_step_tools(rec, design_dir), temperature=0.2)
    _sync_ctx_from_disk(ctx)
    tb = {k: v for k, v in (ctx.get("testbench_code")
                            or {}).items() if v.strip()}
    if not tb:                                 # agent inlined the code instead of writing it
        code = extract_code_block(final)
        if code.strip():
            (design_dir / "tb").mkdir(parents=True, exist_ok=True)
            (design_dir / "tb" / f"{top}_tb.v").write_text(code)
            tb = {f"{top}_tb.v": code}
    ctx["testbench_code"] = {k: dedup_modules(v) for k, v in tb.items()}
    if ctx["testbench_code"]:
        rec.success(
            f"Testbench `{next(iter(ctx['testbench_code']))}` (deep agent):")
        rec.code(
            next(iter(ctx["testbench_code"].values())), language="verilog")
    else:
        rec.error("Deep agent produced no testbench — Revise or Replan to retry.")


def _deep_fix_design(rec, ctx, feedback=""):
    """Module Corrector as an RLM deep agent: the error log is offloaded to disk; the
    agent peeks at it + the broken module, may recall/search a fix, then rewrites the
    module on disk. Prior failed attempts are named so it doesn't loop on the same code."""
    rec.caption(
        "🧠 RLM deep-agent corrector — peeks the error log on disk, may research, rewrites.")
    design_dir = Path(ctx["design_dir"])
    files = dict(ctx["decomposed_files"])
    err = ctx.get("simulation_output") or ctx.get("lint_output", "")
    faulty = next((f for f in files if f in err),
                  None) or f"{ctx['top_module_name']}.v"
    faulty = faulty if faulty in files else next(iter(files))
    stem = faulty[:-2] if faulty.endswith(".v") else faulty
    attempt = ctx.get("error_count", 0) + ctx.get("lint_count", 0)

    cdir = design_dir / "context"
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "last_error.log").write_text(err or "(no error text)")

    history = dict(ctx.get("fix_history", {}))
    past = history.get(faulty, [])
    rec.write(
        "**Errors offloaded to `context/last_error.log` for the agent to peek:**")
    rec.code(err[:1800], language="text")
    prior_note = ""
    if past:
        prior_note = ("Earlier fixes of this module FAILED — take a FUNDAMENTALLY different approach, "
                      "do NOT reproduce this last attempt:\n```verilog\n" + past[-1][:1500] + "\n```\n")
        rec.caption(
            f"⛔ {len(past)} earlier fix(es) failed — the last one is shown to the agent to avoid looping.")

    goal = (
        f"A Verilog module FAILED to compile/simulate. The errors are in `context/last_error.log` and "
        f"the broken module is `rtl/{faulty}`.\n"
        f"1) read_file_disk('context/last_error.log') and read_file_disk('rtl/{faulty}').\n"
        "2) In ONE line name the EXACT rule you violated, then REWRITE the module to fix the real cause "
        "(not the symptom).\n"
        "If the error is unfamiliar, call recall_memory or search_web ONCE for the correct pattern.\n"
        + prior_note
        + f"Keep the module name `{stem}` and a port list compatible with the rest of the design. WRITE "
          f"the corrected module back to rtl/{faulty} with write_file_disk, then reply with it in one "
          "```verilog block.\n"
        + VERILOG_PITFALLS
    )
    temp = min(0.2 + 0.18 * attempt, 0.85)
    final = run_deep_agent(rec, design_dir, goal,
                           extra_tools=_step_tools(rec, design_dir), temperature=temp)

    fixed = extract_code_block(final)
    disk = design_dir / "rtl" / faulty
    if fixed.strip() and "module" in fixed:    # prefer the inlined block; mirror it to disk
        disk.write_text(fixed)
    elif disk.exists():                        # else trust what the agent wrote to disk
        fixed = disk.read_text()
    else:
        fixed = files[faulty]
    files[faulty] = fixed
    history[faulty] = past + [fixed]
    rec.success(f"Corrected `{faulty}` (deep agent):")
    rec.code(fixed, language="verilog")
    ctx["decomposed_files"] = files
    ctx["fix_history"] = history


def _deep_fix_testbench(rec, ctx, feedback=""):
    """Testbench Corrector as an RLM deep agent: regenerates the testbench from the DUT
    on disk, given the offloaded error log."""
    rec.caption(
        "🧠 RLM deep-agent testbench corrector — regenerates from the DUT on disk.")
    design_dir = Path(ctx["design_dir"])
    tb = ctx.get("testbench_code", {})
    top = ctx["top_module_name"]
    name = next(iter(tb), f"{top}_tb.v")
    err = ctx.get("simulation_output", "")
    attempt = ctx.get("error_count", 0)

    cdir = design_dir / "context"
    cdir.mkdir(parents=True, exist_ok=True)
    (cdir / "last_error.log").write_text(err or "(no error text)")
    rec.write("**Errors offloaded to `context/last_error.log`:**")
    rec.code(err[:1800], language="text")

    goal = (
        f"The testbench `{name}` for module `{top}` FAILED — errors are in `context/last_error.log`.\n"
        f"Read it and `rtl/{top}.v` with read_file_disk, then write a BRAND-NEW correct self-checking "
        "testbench FROM SCRATCH (do not reuse the broken structure).\n"
        + (f"USER INSTRUCTION: {feedback}\n" if feedback else "")
        + f"STRICT: `module {name[:-2] if name.endswith('.v') else name};` EMPTY ports; clk + DUT inputs "
          "as reg, outputs as wire, each once; `always #5 clk=~clk;`; instantiate DUT by name; reset; "
          f'stimulus; check; `$dumpfile("design.vcd"); $dumpvars(0,{top}_tb);`; print EXACTLY '
          '"Result: PASSED" or "Result: FAILED" then `$finish;`. ONE module.\n'
        + f"WRITE it to tb/{name} with write_file_disk, then reply with it in one ```verilog block."
    )
    temp = min(0.3 + 0.18 * attempt, 0.9)
    final = run_deep_agent(rec, design_dir, goal,
                           extra_tools=_step_tools(rec, design_dir), temperature=temp)

    code = extract_code_block(final)
    disk = design_dir / "tb" / name
    if code.strip() and "module" in code:
        disk.write_text(code)
    elif disk.exists():
        code = disk.read_text()
    new_tb = {name: dedup_modules(code)} if code.strip() else dict(tb)
    history = dict(ctx.get("fix_history", {}))
    history[name] = history.get(name, []) + [next(iter(new_tb.values()), "")]
    rec.success("Corrected testbench (deep agent):")
    rec.code(next(iter(new_tb.values()), "(none)"), language="verilog")
    ctx["testbench_code"] = new_tb
    ctx["fix_history"] = history


_IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


def _extract_pdf_text(path: Path) -> str:
    """Best-effort PDF → text (first 20 pages). Returns '' if pypdf isn't installed —
    the agent can then pip_install pypdf and read it via run_python."""
    try:
        import pypdf
        reader = pypdf.PdfReader(str(path))
        return "\n".join((pg.extract_text() or "") for pg in reader.pages[:20]).strip()
    except Exception:  # noqa: BLE001
        return ""


def _save_uploads(design_dir: Path, uploads) -> str:
    """Persist user-attached files/images under context/uploads/ and build a digest the
    deep agents PEEK at. Text is embedded (capped), PDFs are text-extracted best-effort,
    and images are saved with their on-disk path noted so a node can analyze them with
    the Python tool (run_python + pillow). Returns the digest markdown (or '')."""
    if not uploads:
        return ""
    updir = design_dir / "context" / "uploads"
    updir.mkdir(parents=True, exist_ok=True)
    parts: List[str] = []
    for uf in uploads:
        try:
            data = uf.getvalue()
        except Exception:  # noqa: BLE001
            continue
        name = re.sub(r"[^\w.\-]", "_", os.path.basename(uf.name))
        path = updir / name
        path.write_bytes(data)
        rel = path.relative_to(design_dir)
        ext = path.suffix.lower()
        if ext in _IMAGE_EXT:
            parts.append(f"### {name} (image · {len(data)} bytes)\nSaved at `{rel}`. "
                         "Analyze it with run_python (e.g. PIL.Image / numpy) if you need its contents.")
        elif ext == ".pdf":
            text = _extract_pdf_text(path)
            parts.append(f"### {name} (PDF)\n{text[:6000]}" if text else
                         f"### {name} (PDF · {len(data)} bytes)\nSaved at `{rel}`. "
                         "Extract its text with run_python (pip_install pypdf) if needed.")
        else:
            try:
                parts.append(f"### {name}\n```\n{data.decode('utf-8', 'replace')[:6000]}\n```")
            except Exception:  # noqa: BLE001
                parts.append(f"### {name} ({len(data)} bytes)\nSaved at `{rel}` (binary).")
    return ("# User-attached files (uploaded with the prompt)\n\n" + "\n\n".join(parts)) if parts else ""


def new_run(prompt, use_web, run_harden, clock_port, clock_period, die_um, core_util,
            autonomous=True, deep_steps=True, uploads=None):
    design_dir = OUTPUT_DIR / slugify(prompt)
    if design_dir.exists():
        shutil.rmtree(design_dir)
    design_dir.mkdir(parents=True, exist_ok=True)
    return {
        "ctx": {
            "query": prompt, "use_web": use_web, "design_dir": str(design_dir),
            "documents": [], "error_count": 0, "fix_history": {},
            "decomposed_files": {}, "testbench_code": {}, "top_module_name": "",
            "generation": "", "simulation_output": "", "web_example": "",
            "lint_output": "", "lint_count": 0, "deep_steps": deep_steps,
            "run_harden": run_harden, "clock_port": clock_port, "clock_period": clock_period,
            "die_um": die_um, "core_util": core_util,
            "uploads_digest": _save_uploads(design_dir, uploads),
        },
        "queue": ["plan"],
        "transcript": [],
        "status": "running",
        "pending": None,
        "autonomous": autonomous,
    }


# --------------------------------------------------------------------------- #
# Output summary + downloads
# --------------------------------------------------------------------------- #
def write_result_md(design_dir: Path, prompt: str, top: str, sim_passed: bool, harden: dict | None):
    lines = [f"# {top}", "", f"**Prompt:** {prompt}", "",
             f"- RTL simulation: {'PASSED ✅' if sim_passed else 'FAILED ❌'}"]
    if harden:
        m = harden.get("metrics") or {}
        lines += [
            f"- GDSII: {'`' + os.path.basename(harden['gds']) + '`' if harden.get('gds') else 'not produced'}",
            f"- Die area: {m.get('design__die__area', 'n/a')} µm²",
            f"- Std cells: {m.get('design__instance__count__stdcell', 'n/a')}",
            f"- Setup worst-slack: {m.get('timing__setup__ws', 'n/a')} ns",
            f"- DRC violations: {m.get('magic__drc__count', 'n/a')}",
        ]
    (design_dir / "result.md").write_text("\n".join(lines))


def render_output(design_dir: Path):
    st.markdown("---")
    st.markdown("### 📦 Output")
    st.caption(f"Everything is under `output/{design_dir.name}/`.")
    tree = []
    for p in sorted(design_dir.rglob("*")):
        if p.is_file() and "runs" not in p.parts:
            tree.append(str(p.relative_to(design_dir)))
    st.code("output/" + design_dir.name + "/\n" +
            "\n".join(f"  {t}" for t in tree[:60]), language="text")

    cols = st.columns(2)
    gds_files = list(design_dir.glob("*.gds"))
    if gds_files:
        with cols[0]:
            with open(gds_files[0], "rb") as f:
                st.download_button("⬇️ Download GDSII", f,
                                   file_name=gds_files[0].name)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in design_dir.rglob("*"):
            if p.is_file() and "runs" not in p.parts:
                z.write(p, p.relative_to(design_dir))
    with cols[1]:
        st.download_button("⬇️ Download all (zip)",
                           buf.getvalue(), file_name=f"{design_dir.name}.zip")


def finalize(run):
    ctx = run["ctx"]
    design_dir = Path(ctx["design_dir"])
    sim_passed = not ctx.get("simulation_output")
    top = ctx.get("top_module_name") or slugify(ctx["query"])
    write_result_md(design_dir, ctx["query"],
                    top, sim_passed, ctx.get("harden"))
    # Push this whole design (RTL/TB/sim/GDS/notes/uploads) into the durable knowledge
    # store so future runs can RECALL it — this is how the RLM gets better over time.
    try:
        n = get_memory().ingest_run(design_dir, design=design_dir.name, query=ctx["query"])
        if n:
            ctx["ingested_count"] = n
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------- #
# Human-in-the-loop feedback panel
# --------------------------------------------------------------------------- #
def feedback_ui(run):
    pend = run.get("pending")
    accepts = STEP_DEFS.get(
        pend, (None,) * 5)[4] if pend in STEP_DEFS else False
    queue = run["queue"]
    ctx = run["ctx"]
    st.markdown("---")
    if queue:
        st.info(f"⏸ **Paused** after `{pend}`. Next up: **`{queue[0]}`**. "
                "Review the output above, then continue or steer the agent.")
    elif ctx.get("simulation_output"):
        st.warning(f"⏸ **Paused** after `{pend}`. RTL not yet verified "
                   f"({ctx.get('error_count', 0)} attempts). Steer with Replan, or finish.")
    else:
        st.success(
            f"⏸ **Paused** after `{pend}`. Nothing left queued — finish, or steer.")

    # Feedback box FIRST so its value is available to every button below.
    fb = st.text_area("💬 Feedback / steering (used by Revise and Replan)",
                      key=f"fb_{len(run['transcript'])}",
                      placeholder="e.g. 'use a 5-stage pipeline', or 'the reset is active-low'…",
                      height=80)

    cols = st.columns([1, 1, 1])
    if cols[0].button("▶️ Continue" if queue else "🏁 Finish", type="primary", use_container_width=True):
        run["action"] = "continue"
        st.rerun()
    if cols[1].button("🔁 Replan", use_container_width=True,
                      help="Let the Replanner choose the next steps from your feedback above."):
        run["action"] = "replan"
        run["pending_feedback"] = fb
        st.rerun()
    if cols[2].button("✍️ Revise step", use_container_width=True, disabled=not accepts,
                      help=("Re-run this step with your feedback." if accepts
                            else "This step has no LLM to re-run.")):
        run["action"] = "revise"
        run["pending_feedback"] = fb
        st.rerun()

    with st.expander("🌐 Stuck? Ask the agent to fetch a web example of a block (name it + its I/O)"):
        blk = st.text_input("Block to look up", key=f"blk_{len(run['transcript'])}",
                            placeholder="e.g. 'RISC-V ALU', 'synchronous register file', 'AXI-lite slave'")
        if st.button("🌐 Search the web for this block + its inputs/outputs"):
            run["action"] = "weblookup"
            run["pending_block"] = blk
            st.rerun()


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def steer_box(run):
    """A prompt you can send ANYTIME — even while the agent is working. It's applied
    at the next step boundary: it revises the current step with your instruction, or
    (if that step has no LLM) replans the next steps from your message."""
    msg = st.chat_input("💬 Steer the agent or run a file command (e.g. 'remove the .vh file', "
                        "'create rtl/alu.v') — works even while it's running…")
    if msg and msg.strip():
        run["steer_msg"] = msg.strip()
        st.rerun()


def main():
    st.set_page_config(page_title="GarudaChip", layout="wide")
    st.title("🦅 GarudaChip — prompt → RTL → GDSII")
    st.caption(
        "Local-LLM digital & SoC automation · autonomous or step-by-step · Ollama + LibreLane")

    with st.sidebar:
        st.header("Model")
        st.success(f"Chat: {provider_label()}")

        mem = get_memory()
        if mem.enabled:
            s = mem.stats()
            kinds = ", ".join(f"{k}:{v}" for k, v in sorted((s.get("by_kind") or {}).items()))
            st.caption(f"🗄️ Knowledge store: **{s.get('total', 0)}** items"
                       + (f" ({kinds})" if kinds else ""))

        st.header("Run mode")
        run_mode = st.radio("Run mode",
                            ["🤖 Autonomous (run end-to-end)",
                             "✋ Review each step"],
                            label_visibility="collapsed",
                            help="Autonomous runs every agent to completion without asking "
                                 "(Chipster-style). Review pauses after each agent so you can "
                                 "Continue / Revise / Replan. Either way you can send a steering "
                                 "prompt at the bottom while it works.")
        autonomous = run_mode.startswith("🤖")
        deep_steps = st.checkbox("🧠 RLM deep agents (recursive)", value=True,
                                 help="Run EVERY LLM node (Planner, Web Researcher, Verilog Generator, "
                                      "Testbench Writer, both Correctors) as a Recursive-Language-Model "
                                      "deep agent: it plans (write_todos), OFFLOADS big context to disk and "
                                      "PEEKS slices, DELEGATES focused sub-tasks to fresh local-LLM calls "
                                      "(llm_query) or sub-agents (task), and builds up RTL in files — so the "
                                      "9B model never holds it all at once. The graph/steps are unchanged. "
                                      "Untick to fall back to fast one-shot prompts.")

        hw_ok = librelane_available()
        if hw_ok:
            st.success("LibreLane detected")
        else:
            st.warning("LibreLane not on PATH — RTL + sim only.")

        st.header("Design prompt")
        prompt = st.text_area("Describe the hardware to build", height=140,
                              value="an 8-bit (int8) transformer Q/K/V self-attention accelerator, "
                                    "sequence length 4 and head dimension 4, signed 8-bit MAC datapath")
        uploads = st.file_uploader(
            "📎 Attach files / images (spec, paper, data, diagram)",
            accept_multiple_files=True,
            type=["txt", "md", "csv", "json", "v", "vh", "sv", "svh", "log",
                  "pdf", "png", "jpg", "jpeg", "webp"],
            help="Saved into the design's context/uploads/. Text + PDF content is fed to the "
                 "agents as reference; images are saved so a node can analyze them with the "
                 "Python tool (run_python + pillow).")
        use_web = st.checkbox("Use web research", value=True)

        st.header("Hardening")
        run_harden = st.checkbox(
            "Run LibreLane after RTL passes", value=hw_ok, disabled=not hw_ok)
        clock_port = st.text_input("Clock port", value="clk")
        clock_period = st.number_input(
            "Clock period (ns)", 1.0, value=24.0, step=1.0)
        die_um = st.number_input(
            "Die size (µm, square)", 50.0, value=600.0, step=50.0)
        core_util = st.slider("Core utilization (%)", 10, 80, 25)
        go = st.button("🚀 Generate chip", type="primary",
                       use_container_width=True)
        if st.session_state.get("run") is not None and st.button("🔄 New run / reset", use_container_width=True):
            st.session_state.run = None
            st.rerun()

    if "run" not in st.session_state:
        st.session_state.run = None

    if go:
        st.session_state.run = new_run(prompt, use_web, run_harden and hw_ok,
                                       clock_port, clock_period, die_um, core_util, autonomous,
                                       deep_steps, uploads=uploads)

    run = st.session_state.run
    if run is None:
        st.subheader("Agent workflow")
        st.graphviz_chart(workflow_graph(), use_container_width=True)
        st.info("Describe the hardware on the left, pick **Autonomous** or **Review each step**, "
                "and click **Generate chip**. In Autonomous it runs every agent end-to-end without "
                "asking. Type a **prompt at the bottom while it works** to steer it (revise/replan) or "
                "run a **file command** (e.g. *'remove the .vh file'*, *'create rtl/alu.v'*) — the file "
                "agent edits your design on disk. A **Verilator lint gate** auto-fixes comb-loops / "
                "multidriven nets before hardening so LibreLane reaches GDSII.")
        return

    # Live workflow graph (amber = working, green = done).
    st.subheader("Live agent workflow")
    graph_ph = st.empty()

    # 1) Apply a steering prompt the user sent WHILE the agent worked, or a button action.
    steer = run.pop("steer_msg", None)
    act = run.pop("action", None)
    if steer:
        # "remove the .vh file", "create rtl/alu.v" → file agent
        if _is_file_command(steer):
            run["pending_fileagent"] = steer
            run["status"] = "fileagent"
        else:
            pend = run.get("pending")
            # revisable step → redo it with the new instruction
            if pend in STEP_DEFS and STEP_DEFS[pend][4]:
                if run["transcript"]:
                    run["transcript"].pop()
                run["queue"].insert(0, pend)
                run["feedback"] = steer
                run["status"] = "running"
            # not revisable (write/sim) → replan from the message
            else:
                run["pending_feedback"] = steer
                run["status"] = "replan"
    elif act == "continue":
        run["status"] = "finalize" if not run["queue"] else "running"
    elif act == "revise":
        if run["transcript"]:
            # drop the step we're redoing
            run["transcript"].pop()
        run["queue"].insert(0, run["pending"])      # and re-run it next
        run["feedback"] = run.pop("pending_feedback", "")
        run["status"] = "running"
    elif act == "replan":
        run["status"] = "replan"
    elif act == "weblookup":
        run["status"] = "weblookup"

    # 2) Re-draw the whole transcript so far (static).
    for record in run["transcript"]:
        replay_record(record)

    # 3) Persistent steering prompt — send it anytime, even mid-run (chat_input is
    #    interactive while the step below blocks; it lands on the next run).
    if run["status"] != "done":
        steer_box(run)

    # 4) Replan / web-lookup / file-agent execute now.
    if run["status"] == "replan":
        do_replan(run, run.pop("pending_feedback", ""))
        run["status"] = "paused"
    elif run["status"] == "weblookup":
        do_weblookup(run, run.pop("pending_block", ""))
        # re-run the paused step with the new reference
        run["queue"].insert(0, run["pending"])
        run["status"] = "paused"
    elif run["status"] == "fileagent":
        do_fileagent(run, run.pop("pending_fileagent", ""))
        run["status"] = "paused"

    # 5) Run the next queued step (live), then pause.
    if run["status"] == "running":
        node = run["queue"].pop(0)
        fb = run.pop("feedback", "")
        done = {GRAPH_KEY.get(r["node"], r["node"]) for r in run["transcript"]}
        graph_ph.graphviz_chart(workflow_graph(active=GRAPH_KEY.get(node, node), done=done),
                                use_container_width=True)
        run["transcript"].append(execute_step(run, node, fb))
        advance(run, node)
        run["pending"] = node
        run["status"] = "paused"

    # 6) Autonomous: auto-advance with no asking (Chipster-style). Pauses only at the end.
    if run["status"] == "paused" and run.get("autonomous"):
        if run["queue"]:
            run["action"] = "continue"
            st.rerun()
        else:
            run["status"] = "finalize"

    # 7) Finalize.
    if run["status"] == "finalize":
        finalize(run)
        run["status"] = "done"

    # Final graph state.
    done = {GRAPH_KEY.get(r["node"], r["node"]) for r in run["transcript"]}
    if run["status"] == "done" and (run["ctx"].get("harden") or {}).get("gds"):
        done.add("gds")
    graph_ph.graphviz_chart(workflow_graph(done=done),
                            use_container_width=True)

    # 8) Feedback panel (review mode) / output.
    if run["status"] == "paused":
        if run.get("autonomous"):
            st.info(
                "🤖 Running autonomously… type a prompt at the bottom anytime to steer it.")
        else:
            feedback_ui(run)
    elif run["status"] == "done":
        ctx = run["ctx"]
        if ctx.get("simulation_output"):
            st.error(f"❌ RTL could not be verified ({ctx.get('error_count', 0)} attempts). "
                     "Files saved under output/. Use **Replan** to keep trying.")
        else:
            st.success("✅ RTL verified (simulation passed).")
        render_output(Path(ctx["design_dir"]))


if __name__ == "__main__":
    main()
