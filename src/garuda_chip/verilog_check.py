"""
Deterministic Verilog structure checks — the pipeline's safety net.

A small local model WILL produce incoherent multi-file designs (modules that
reference macros without `include`, top modules that instantiate ports that
don't exist, duplicate alu.v/alu_8bit.v variants). LLM retries cannot converge
against 70 cross-module elaboration errors. These checks catch every one of
those failure classes DETERMINISTICALLY, at the earliest possible moment:

  • check_file()       — compile ONE file with `iverilog -t null -i` the moment
                         it is written, so the generating agent gets the error
                         back in the same tool call and fixes it immediately.
  • static_report()    — cross-module audit before simulation: duplicate module
                         definitions, instantiations of unknown modules, named
                         port connections that don't exist on the definition,
                         bare uses of `define macros (missing backtick/include).
  • pick_top()         — structural top detection that prefers an actual
                         integration module over a leaf that nobody happens to
                         instantiate.
  • closure_files()    — the dependency cone from the top module, so simulation
                         compiles ONLY the files the design actually uses and a
                         stale/orphan file can never break the build.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Verilog keywords that look like instantiations in a naive scan.
_KEYWORDS = {
    "module", "endmodule", "begin", "end", "if", "else", "case", "casez", "casex",
    "endcase", "for", "while", "repeat", "forever", "always", "initial", "assign",
    "wire", "reg", "integer", "real", "genvar", "generate", "endgenerate", "input",
    "output", "inout", "parameter", "localparam", "function", "endfunction", "task",
    "endtask", "posedge", "negedge", "or", "and", "not", "nand", "nor", "xor",
    "xnor", "buf", "bufif0", "bufif1", "notif0", "notif1", "supply0", "supply1",
    "default", "signed", "unsigned", "specify", "endspecify", "defparam",
}

_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_MODULE_RE = re.compile(r"\bmodule\s+(\w+)\s*(#\s*\(.*?\))?\s*(\(.*?\))?\s*;",
                        re.DOTALL)
_DEFINE_RE = re.compile(r"`define\s+(\w+)")
# named instantiation:  mod_name [#(.P(v), ...)] inst_name ( .port(sig), ... );
# The param-override and port lists are matched with ONE level of nested parens balanced
# (`(?:[^()]|\([^()]*\))*`), so SystemVerilog instantiations like
#   fazyrv_core #(.CHUNKSIZE(CHUNKSIZE)) i_core (.clk_i(clk_i), ...);
# are detected (the old `[^;]*?` stopped at the first inner `)` → 0 instantiations on SV → no
# top found → the testbench tested a leaf module).
_INST_RE = re.compile(
    r"\b(\w+)\s*"
    r"(?:#\s*\((?:[^()]|\([^()]*\))*\)\s*)?"          # optional #(params), 1-level nesting
    r"(\w+)\s*"                                        # instance name
    r"\(\s*(\.(?:[^()]|\([^()]*\))*)\)\s*;",           # port list (.x(y), …), 1-level nesting
    re.DOTALL)
_NAMED_PORT_RE = re.compile(r"\.(\w+)\s*\(")


def _strip_comments(text: str) -> str:
    return _COMMENT_RE.sub(" ", text)


def autofix_text(code: str) -> Tuple[str, List[str]]:
    """Deterministically repair the UNAMBIGUOUS syntax tics a small model emits, so the
    LLM correction loop never has to spend a cycle on them. Returns (fixed, notes).

    The big one: `}` used to CLOSE A BLOCK instead of `end` (qwen does this constantly:
    `... end; } else if (...)`). We tell a block-close `}` from a concatenation `}` by
    tracking `{` depth while skipping strings/comments — a `}` seen at brace-depth 0 is a
    misused block close and becomes `end`; a `}` inside `{...}` is left alone. Conservative
    by construction: a real concatenation always has a matching earlier `{`, so it is never
    touched."""
    if not code or "}" not in code:
        return code, []
    out: List[str] = []
    depth = 0          # concatenation/replication brace depth
    i, n = 0, len(code)
    fixed_braces = 0
    while i < n:
        c = code[i]
        # skip line comment
        if c == "/" and i + 1 < n and code[i + 1] == "/":
            j = code.find("\n", i)
            j = n if j == -1 else j
            out.append(code[i:j])
            i = j
            continue
        # skip block comment
        if c == "/" and i + 1 < n and code[i + 1] == "*":
            j = code.find("*/", i + 2)
            j = n if j == -1 else j + 2
            out.append(code[i:j])
            i = j
            continue
        # skip string literal
        if c == '"':
            j = i + 1
            while j < n and code[j] != '"':
                j += 2 if code[j] == "\\" else 1
            j = min(j + 1, n)
            out.append(code[i:j])
            i = j
            continue
        if c == "{":
            depth += 1
            out.append(c)
            i += 1
            continue
        if c == "}":
            if depth > 0:                       # real concatenation close — leave it
                depth -= 1
                out.append(c)
                i += 1
                continue
            # depth 0 → misused block close → `end`
            fixed_braces += 1
            out.append("end")
            i += 1
            if i < n and code[i] == ";":        # `};` → `end`
                i += 1
            if i < n and (code[i].isalnum() or code[i] == "_"):
                out.append(" ")                 # `}else` → `end else`
            continue
        out.append(c)
        i += 1
    notes = []
    if fixed_braces:
        notes.append(f"replaced {fixed_braces} misused `}}` block-close(s) with `end`")
    return "".join(out), notes


def _port_names(header: str) -> List[str]:
    """Port names from a module's `(...)` header (ANSI or non-ANSI style)."""
    if not header:
        return []
    inner = header.strip()[1:-1]
    names: List[str] = []
    for piece in inner.split(","):
        # last identifier in the piece is the port name ("input wire [7:0] foo")
        ids = re.findall(r"\b([a-zA-Z_]\w*)\b", re.sub(r"\[[^\]]*\]", " ", piece))
        ids = [i for i in ids if i not in _KEYWORDS]
        if ids:
            names.append(ids[-1])
    return names


def parse_rtl(rtl_dir: Path) -> Dict:
    """Parse every rtl/*.v (+ .vh): module definitions (name, file, ports),
    instantiations per module, and `define names per file."""
    rtl_dir = Path(rtl_dir)
    defs: Dict[str, dict] = {}            # module -> {file, ports}
    dupes: List[str] = []
    insts: Dict[str, List[Tuple[str, str, List[str]]]] = {}  # module -> [(child, inst, ports)]
    defines: Dict[str, str] = {}          # macro -> file
    includes: Dict[str, List[str]] = {}   # file -> included names
    texts: Dict[str, str] = {}

    for p in (sorted(rtl_dir.glob("*.vh")) + sorted(rtl_dir.glob("*.svh"))
              + sorted(rtl_dir.glob("*.v")) + sorted(rtl_dir.glob("*.sv"))):
        raw = p.read_text(errors="replace")
        texts[p.name] = raw
        clean = _strip_comments(raw)
        for m in _DEFINE_RE.finditer(clean):
            defines.setdefault(m.group(1), p.name)
        includes[p.name] = re.findall(r'`include\s+"([^"]+)"', clean)
        for m in _MODULE_RE.finditer(clean):
            name = m.group(1)
            if name in defs:
                dupes.append(f"module `{name}` is defined in BOTH {defs[name]['file']} "
                             f"and {p.name} — delete one of them")
                continue
            defs[name] = {"file": p.name, "ports": _port_names(m.group(3) or "")}
            body_start = m.end()
            em = clean.find("endmodule", body_start)
            body = clean[body_start: em if em != -1 else len(clean)]
            found = []
            for im in _INST_RE.finditer(body):
                child, inst, conns = im.group(1), im.group(2), im.group(3)
                if child in _KEYWORDS or inst in _KEYWORDS:
                    continue
                found.append((child, inst, _NAMED_PORT_RE.findall(conns)))
            insts[name] = found
    return {"defs": defs, "dupes": dupes, "insts": insts,
            "defines": defines, "includes": includes, "texts": texts}


def pick_top(rtl_dir: Path) -> str:
    """Structural top: an uninstantiated module, preferring the one that
    instantiates the MOST sub-modules (an integration module), with a name
    bonus for top/soc/cpu/core. Never returns a leaf if a real top exists."""
    info = parse_rtl(rtl_dir)
    defs, insts = info["defs"], info["insts"]
    if not defs:
        return ""
    instantiated: Set[str] = set()
    for kids in insts.values():
        for child, _, _ in kids:
            if child in defs:
                instantiated.add(child)
    cands = [n for n in defs if n not in instantiated] or list(defs)

    def score(n: str) -> tuple:
        kids = sum(1 for c, _, _ in insts.get(n, []) if c in defs)
        name_bonus = 1 if re.search(r"top|soc|cpu|core|system", n, re.I) else 0
        return (kids, name_bonus)
    return max(cands, key=score)


def closure_files(rtl_dir: Path, top: str) -> Tuple[List[str], List[str]]:
    """(files needed to build `top` — module cone + their `include headers,
    orphan .v files NOT needed) — so sim never compiles stale leftovers."""
    info = parse_rtl(rtl_dir)
    defs, insts, includes = info["defs"], info["insts"], info["includes"]
    if top not in defs:
        vs = sorted(Path(rtl_dir).glob("*.v")) + sorted(Path(rtl_dir).glob("*.sv"))
        hd = sorted(Path(rtl_dir).glob("*.vh")) + sorted(Path(rtl_dir).glob("*.svh"))
        return [p.name for p in hd + vs], []
    needed_mods: Set[str] = set()
    stack = [top]
    while stack:
        m = stack.pop()
        if m in needed_mods:
            continue
        needed_mods.add(m)
        for child, _, _ in insts.get(m, []):
            if child in defs:
                stack.append(child)
    files = {defs[m]["file"] for m in needed_mods}
    # headers any needed file includes (plus all .vh — they're cheap and harmless)
    for f in list(files):
        files.update(h for h in includes.get(f, []))
    files.update(p.name for p in Path(rtl_dir).glob("*.vh"))
    files.update(p.name for p in Path(rtl_dir).glob("*.svh"))
    orphans = [p.name for p in sorted(Path(rtl_dir).glob("*.v")) + sorted(Path(rtl_dir).glob("*.sv"))
               if p.name not in files]
    ordered = ([f for f in sorted(files) if f.endswith((".vh", ".svh"))]
               + [f for f in sorted(files) if f.endswith((".v", ".sv"))])
    return [f for f in ordered if (Path(rtl_dir) / f).exists()], orphans


def audit_findings(rtl_dir: Path, top: str = "") -> List[dict]:
    """Structured cross-module audit — the single source of truth both the text report
    (static_report) and the deterministic fixer (reconcile_ports) build on. Each finding is
    a dict with a `kind`: 'dupe', 'missing_module', or 'bad_port' (a `.port(...)` connection
    that names a port the instantiated child module does not declare)."""
    info = parse_rtl(rtl_dir)
    defs, insts = info["defs"], info["insts"]
    out: List[dict] = [{"kind": "dupe", "text": d} for d in info["dupes"]]
    for parent, kids in insts.items():
        pfile = defs[parent]["file"]
        for child, inst, conns in kids:
            if child not in defs:
                out.append({"kind": "missing_module", "parent": parent,
                            "parent_file": pfile, "child": child, "inst": inst})
                continue
            ports = defs[child]["ports"]
            if not ports:
                continue
            pset = set(ports)
            for c in conns:
                if c not in pset:
                    out.append({"kind": "bad_port", "parent": parent, "parent_file": pfile,
                                "child": child, "child_file": defs[child]["file"],
                                "inst": inst, "port": c, "child_ports": ports})
    return out


_DIR_SUFFIXES = ("_io", "_in", "_out", "_i", "_o")


def _has_dir(s: str) -> bool:
    return s.endswith(_DIR_SUFFIXES)


def _best_port(bad: str, ports: List[str]) -> str:
    """The UNIQUE *safe* rename for a mis-named connection `.bad(` among a child's real
    `ports`, or '' when no rename is provably safe. A wrong deterministic rename silently
    COMPILES and escapes the audit — strictly worse than leaving it for the cross-module LLM
    corrector — so this only accepts two unambiguous cases and refuses everything else:

      1. exact match apart from letter case (`.CLK` ↔ `clk`);
      2. a DIRECTIONLESS connection that gains a direction (`.a` ↔ `a_i`, `.clk` ↔ `clk_i`) —
         and only when exactly ONE child port matches.

    It deliberately NEVER toggles a present direction (`_o`↔`_i` is a different net) and does
    NO fuzzy/difflib matching (`b` vs `ab` changes meaning). Those need semantic judgement and
    are handed to the LLM corrector, which now sees both modules."""
    low = {p.lower(): p for p in ports}
    b = bad.lower()
    if b in low:                                   # case-only difference — safe
        return low[b]
    if not _has_dir(b):                            # bare name → it may just need a direction
        cand = [p for p in ports
                if p.lower() in (b + "_i", b + "_o", b + "_in", b + "_out", b + "_io")]
        if len(cand) == 1:
            return cand[0]
    return ""


def reconcile_ports(rtl_dir: Path, top: str = "") -> List[str]:
    """Deterministically repair HIGH-CONFIDENCE cross-module port-name mismatches by renaming
    the connection in the PARENT file to the child's real port (e.g. `.a(` → `.a_i(`). This
    clears the mechanical findings for free (no LLM call) so the corrector only spends the
    model on the genuine, semantic ones. SAFETY: a name is renamed only when (1) there is a
    unique confident match on the child, and (2) that name is NOT a valid port of any OTHER
    child instantiated in the same file (so we never clobber a legitimate connection).
    Returns a human-readable list of the rewrites applied."""
    rtl_dir = Path(rtl_dir)
    info = parse_rtl(rtl_dir)
    defs, insts = info["defs"], info["insts"]
    changes: List[str] = []
    by_file: Dict[str, list] = {}
    for f in audit_findings(rtl_dir, top):
        if f["kind"] != "bad_port":
            continue
        repl = _best_port(f["port"], f["child_ports"])
        if repl and repl != f["port"]:
            by_file.setdefault(f["parent_file"], []).append(
                (f["port"], repl, f["child"], f["inst"], f["parent"]))
    for fname, edits in by_file.items():
        p = Path(rtl_dir) / fname
        if not p.exists():
            continue
        src = new = p.read_text()
        for old, repl, child, inst, parent in edits:
            # don't rename if `old` is a real port of some sibling child in this file
            sibling_ports = set()
            for ch, _, _ in insts.get(parent, []):
                if ch != child and ch in defs:
                    sibling_ports.update(defs[ch]["ports"])
            if old in sibling_ports:
                continue
            cand = re.sub(rf"\.{re.escape(old)}(\s*)\(", rf".{repl}\1(", new)
            if cand != new:
                new = cand
                changes.append(f"{fname}: `.{old}` → `.{repl}` (instance `{inst}` of `{child}`)")
        if new != src:
            p.write_text(new)
    return changes


def static_report(rtl_dir: Path, top: str = "") -> List[str]:
    """Cross-module audit. Each finding is ONE actionable line naming the file,
    the exact problem, and the fix — written for an LLM corrector to act on."""
    info = parse_rtl(rtl_dir)
    defines, includes, texts = info["defines"], info["includes"], info["texts"]
    problems: List[str] = []
    for f in audit_findings(rtl_dir, top):
        if f["kind"] == "dupe":
            problems.append(f["text"])
        elif f["kind"] == "missing_module":
            problems.append(
                f"{f['parent_file']}: `{f['parent']}` instantiates module `{f['child']}` "
                f"(instance `{f['inst']}`) but NO file defines `{f['child']}` — create "
                f"rtl/{f['child']}.v or fix the module name")
        elif f["kind"] == "bad_port":
            problems.append(
                f"{f['parent_file']}: connection `.{f['port']}(...)` on instance `{f['inst']}` "
                f"— but `{f['child']}` ({f['child_file']}) has no port `{f['port']}`; its real "
                f"ports are: {', '.join(f['child_ports'][:14])}. FIX: either rename this "
                f"connection to one of those real ports, OR add port `{f['port']}` to "
                f"`{f['child']}` ({f['child_file']}) and wire it; if it's a debug/formal-only "
                f"signal that nothing uses, delete the connection.")

    # bare macro usage: `define NAME exists in a header, file uses NAME without `
    for fname, raw in texts.items():
        if not fname.endswith(".v"):
            continue
        clean = _strip_comments(raw)
        for macro, src in defines.items():
            if re.search(rf"(?<!`)\b{re.escape(macro)}\b", clean) and src != fname:
                fix = (f"write it as `{macro}` (with the backtick)"
                       + ("" if src in includes.get(fname, [])
                          else f' and add `include "{src}" at the top of {fname}'))
                problems.append(
                    f"{fname}: uses `{macro}` as a bare identifier but it is a "
                    f"`define in {src} — {fix}")
    return problems


def check_file(path: Path, rtl_dir: Path, timeout: int = 30) -> str:
    """Compile ONE Verilog file with iverilog (-t null = no output, -i = ignore
    missing sub-modules). Returns '' when clean, else the error text. This is
    the instant feedback a generating agent gets from write_file_disk."""
    path, rtl_dir = Path(path), Path(rtl_dir)
    if path.suffix not in (".v", ".sv"):
        return ""
    cmd = ["iverilog", "-g2012", "-t", "null", "-i", f"-I{rtl_dir}", str(path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return ""                      # no iverilog — don't block writes
    except subprocess.TimeoutExpired:
        return "(compile check timed out)"
    if proc.returncode == 0:
        return ""
    out = (proc.stderr or proc.stdout or "").strip()
    # keep only error lines, relative paths, capped
    lines = [ln.replace(str(path.parent) + "/", "")
             for ln in out.splitlines() if ln.strip()]
    return "\n".join(lines[:12])[:1500]


def full_report(rtl_dir: Path, top: str = "", only: Set[str] | None = None) -> str:
    """Everything wrong with the design as one actionable digest ('' = clean):
    per-file compile errors + the cross-module static audit. `only` limits the
    report to that set of file names (e.g. the simulation closure), so stale
    orphan files can't block the build."""
    rtl_dir = Path(rtl_dir)
    parts: List[str] = []
    for p in sorted(rtl_dir.glob("*.v")) + sorted(rtl_dir.glob("*.sv")):
        if only is not None and p.name not in only:
            continue
        err = check_file(p, rtl_dir)
        if err:
            parts.append(f"--- {p.name} (single-file compile) ---\n{err}")
    audit = static_report(rtl_dir, top)
    if only is not None:
        audit = [a for a in audit if a.split(":", 1)[0] in only]
    if audit:
        parts.append("--- cross-module audit ---\n" + "\n".join(audit[:25]))
    return "\n\n".join(parts)
