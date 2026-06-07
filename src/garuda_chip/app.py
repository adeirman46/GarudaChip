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
import graphviz
from dotenv import load_dotenv
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate

from llm import get_chat_model, get_embeddings, provider_label

load_dotenv()

# --------------------------------------------------------------------------- #
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data" / "verilog_datasets"
OUTPUT_DIR = REPO_ROOT / "output"          # <-- all results land here
MAX_RETRIES = int(os.getenv("MAX_SIM_RETRIES", "20"))
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
    stripped = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
    # If the model put EVERYTHING inside <think> (no answer after), keep the raw
    # text so we can still pull a code block out of it.
    return stripped or text.strip()


def extract_code_block(text: str, lang: str = "verilog") -> str:
    text = clean_llm_output(text)
    m = re.search(rf"```(?:{lang})?\s*\n(.*?)```", text, re.DOTALL)
    code = m.group(1).strip() if m else text.replace(f"```{lang}", "").replace("```", "").strip()
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
            raw = text[s : e + 1]
    if raw is None:
        raise json.JSONDecodeError("no JSON object found", text, 0)
    return json.loads(raw)


def strip_ansi(s: str) -> str:
    return ANSI.sub("", s)


def librelane_available() -> bool:
    return shutil.which(LIBRELANE_BIN) is not None


def slugify(text: str, n: int = 48) -> str:
    return re.sub(r"\W+", "_", text).lower().strip("_")[:n] or "design"


def _norm(code: str) -> str:
    """Normalize Verilog for an 'is this the same attempt?' check — ignore comments
    and whitespace so the corrector can't sneak the SAME broken code past us by only
    re-indenting it."""
    code = re.sub(r"//[^\n]*", "", code or "")
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    return re.sub(r"\s+", " ", code).strip()


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
6. Don't index a packed vector as if it were an unpacked array, or vice-versa."""


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
    ("correct", "8 · 🛠️ Correctors"),
    ("harden", "9 · 🏭 LibreLane\nHardening"),
    ("gds", "🎉 GDSII"),
]
WF_EDGES = [
    ("plan", "retrieve"),
    ("retrieve", "web"), ("web", "generate"), ("generate", "decompose"),
    ("decompose", "testbench"), ("testbench", "write"), ("write", "simulate"),
    ("simulate", "correct"), ("correct", "write"), ("simulate", "harden"),
    ("harden", "gds"),
]
# Map an executed step name -> the graph node it lights up.
GRAPH_KEY = {"fix_design": "correct", "fix_testbench": "correct"}


def workflow_graph(active: str | None = None, done: set | None = None):
    done = done or set()
    dot = graphviz.Digraph()
    dot.attr(rankdir="LR", bgcolor="transparent")
    dot.attr("node", shape="box", style="rounded,filled", fontname="sans-serif", fontsize="10")
    dot.attr("edge", color="#90a4ae")
    for key, label in WF_NODES:
        if key == active:
            dot.node(key, label, fillcolor="#ffca28", color="#ff6f00", penwidth="2.5")  # working = amber
        elif key in done:
            dot.node(key, label, fillcolor="#a5d6a7", color="#2e7d32")                   # done = green
        else:
            dot.node(key, label, fillcolor="#eceff1", color="#b0bec5", fontcolor="#546e7a")
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
        disp = (f"💭 thinking…\n{thinking.strip()}\n\n———\n" if thinking.strip() else "")
        disp += answer
        if not disp.strip():
            disp = f"⏳ generating… ({n} tokens)"  # always show progress, never blank
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
    except Exception:  # noqa: BLE001
        if not answer and not thinking:
            out = runnable.invoke(inputs)
            answer = out if isinstance(out, str) else (getattr(out, "content", "") or str(out))
    render()
    return answer or thinking


# --------------------------------------------------------------------------- #
# RAG
# --------------------------------------------------------------------------- #
@st.cache_resource(show_spinner="Loading local embedding model…")
def _embeddings():
    return get_embeddings()


@st.cache_resource(show_spinner="Loading Verilog reference index…")
def load_vectorstore():
    if (DATA_DIR / "index.faiss").exists():
        try:
            return FAISS.load_local(
                str(DATA_DIR), _embeddings(), allow_dangerous_deserialization=True
            )
        except Exception as e:  # noqa: BLE001
            st.warning(f"Could not load reference index: {e}")
    return None


HDL_SET = {"Verilog", "SystemVerilog", "VHDL"}


def _github_hdl_repos(query: str, limit: int) -> List[str]:
    """ONE GitHub repo-search call per query, post-filtered to HDL languages by
    the repo's `language` field — keeps us under the 10-req/min unauthenticated
    rate limit while guaranteeing every hit is real Verilog/VHDL/SystemVerilog."""
    out: List[str] = []
    try:
        import requests

        r = requests.get(
            "https://api.github.com/search/repositories",
            params={"q": f"{query} verilog", "sort": "stars", "per_page": 25},
            headers={"Accept": "application/vnd.github+json"},
            timeout=12,
        )
        if r.ok:
            for it in r.json().get("items", []):
                if it.get("language") in HDL_SET:
                    u = it.get("html_url")
                    if u and u not in out:
                        out.append(u)
                        if len(out) >= limit:
                            break
    except Exception:  # noqa: BLE001
        pass
    return out


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
                    out.append(Document(page_content=md[:8000], metadata={"source": url}))
                    seen.append(("💻 " if is_gh else "📄 ") + url)
                    log.code("\n".join(f"✓ {u}" for u in seen), language="text")
            await asyncio.gather(*(fetch(u) for u in urls))
        return out

    try:
        return asyncio.run(_crawl())
    except Exception as e:  # noqa: BLE001
        rec.warning(f"Crawl failed ({e}).")
        return []


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
    plan = ["retrieve", "web", "generate", "decompose", "testbench", "write", "simulate"]
    if not ctx.get("use_web"):
        plan.remove("web")
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
    vs = load_vectorstore()
    docs: List[Document] = []
    query = ctx["query"] + (f" {feedback}" if feedback else "")
    if vs is not None:
        with st.spinner("Retrieving reference designs…"):
            docs = vs.as_retriever(search_kwargs={"k": 8}).invoke(query)
        rec.success(f"Retrieved **{len(docs)}** reference chunks from the local index.")
        srcs = "\n".join("• " + d.metadata.get("source", "local dataset") for d in docs[:12])
        if srcs:
            rec.expander_code("Show retrieved sources", srcs, "text")
    else:
        rec.warning("No local index found — generating from scratch.")
    ctx["documents"] = docs


def agent_web(rec, ctx, feedback=""):
    if not ctx.get("use_web"):
        rec.info("Web research disabled.")
        return
    docs = list(ctx.get("documents", []))
    query = ctx["query"]
    cache_dir = DATA_DIR / f"faiss_github_{slugify(query, 80)}"

    if (cache_dir / "index.faiss").exists() and not feedback:
        try:
            vs = FAISS.load_local(str(cache_dir), _embeddings(), allow_dangerous_deserialization=True)
            hits = vs.as_retriever(search_kwargs={"k": 20}).invoke(query)
            rec.success(f"Loaded cached web index `{cache_dir.name}` ({len(hits)} chunks).")
            ctx["documents"] = docs + hits
            return
        except Exception as e:  # noqa: BLE001
            rec.warning(f"Cache load failed ({e}); crawling live.")

    # Ask the LLM for close HDL building-block terms — derived from THIS request
    # (no hardcoded accelerator examples), so a RISC-V prompt searches for RISC-V.
    similar: List[str] = []
    rec.caption("🧠 Picking similar HDL building blocks (on-topic for your prompt):")
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
        similar = [s.strip() for s in re.split(r"[,\n]", txt) if 2 < len(s.strip()) < 50][:3]
    except Exception:  # noqa: BLE001
        similar = []
    if similar:
        rec.caption("🔁 Similar-IP search terms: " + ", ".join(f"`{s}`" for s in similar))

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

    chunks = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200).split_documents(web_docs)
    try:
        vs = FAISS.from_documents(chunks, _embeddings())
        vs.save_local(str(cache_dir))
        hits = vs.as_retriever(search_kwargs={"k": 20}).invoke(query)
        rec.success(f"Crawled {len(web_docs)} pages → cached {len(chunks)} chunks → using {len(hits)}.")
        ctx["documents"] = docs + hits
    except Exception as e:  # noqa: BLE001
        rec.warning(f"Crawled {len(web_docs)} pages (cache save failed: {e}).")
        ctx["documents"] = docs + chunks


def agent_generate(rec, ctx, feedback=""):
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
        parts = [f"Source: {d.metadata.get('source','N/A')}\n{d.page_content[:1800]}" for d in docs[:20]]
        return head + "\n\n".join(parts)

    question = ctx["query"]
    if feedback:
        question += f"\n\nADDITIONAL USER INSTRUCTION (apply this): {feedback}"

    chain = prompt | llm
    rec.caption("🧠 Live model output (reasoning + RTL):")
    live = rec.placeholder()
    with st.spinner("Generating Verilog with the local model…"):
        raw = stream_to(chain, {"context": fmt(ctx["documents"]), "question": question,
                                "pitfalls": VERILOG_PITFALLS}, live)
    gen = extract_code_block(raw)

    if not gen.strip():  # empty? retry once without the (possibly huge) references
        rec.warning("Model returned no code — retrying with a tighter prompt…")
        with st.spinner("Retrying generation…"):
            raw = stream_to(chain, {"context": _ref_context(ctx) + "No reference context.",
                                    "question": question, "pitfalls": VERILOG_PITFALLS}, live)
        gen = extract_code_block(raw)
    if not gen.strip():
        gen = raw.strip()
        rec.error("The model produced no Verilog. Try a simpler prompt or a larger/instruct model.")
        rec.code(raw[:1500] or "(completely empty response)", language="text")
        ctx["generation"] = gen
        ctx["simulation_output"] = ""
        return

    rec.success("Generated RTL:")
    rec.code(gen, language="verilog")
    ctx["generation"] = gen
    ctx["simulation_output"] = ""


def agent_decompose(rec, ctx, feedback=""):
    llm = get_chat_model(temperature=0.0)
    prompt = ChatPromptTemplate.from_template(
        """Refactor this Verilog into separate files.
Rules:
1. Identify the top-level module.
2. One module per file ("module_name.v").
3. Move shared `define`/parameters into "shared_header.vh" and `include` it where used.
4. Reply with ONLY a JSON object: {{"top_module_name": "...", "files": {{"name.v": "code"}}}}.
{extra}
REQUEST: {query}
CODE:
```verilog
{verilog_code}
```"""
    )
    rec.caption("🧠 Live model output:")
    live = rec.placeholder()
    extra = f"5. User instruction: {feedback}\n" if feedback else ""
    with st.spinner("Decomposing…"):
        resp = stream_to(prompt | llm,
                         {"verilog_code": ctx["generation"], "query": ctx["query"], "extra": extra}, live)
    try:
        parsed = extract_json(resp)
        files = parsed.get("files", {})
        top = parsed.get("top_module_name", "")
        if not files or not top:
            raise ValueError("missing files/top_module_name")
    except Exception as e:  # noqa: BLE001
        rec.warning(f"Decompose fell back to monolithic ({e}).")
        m = re.search(r"module\s+([\w]+)", ctx["generation"])
        top = m.group(1) if m else "top"
        files = {f"{top}.v": ctx["generation"]}
    files = {k: dedup_modules(v) for k, v in files.items()}
    rec.success(f"Top module: `{top}` · {len(files)} file(s).")
    for fn, code in files.items():
        rec.expander_code(f"📄 {fn}", code, "verilog", expanded=(fn == f"{top}.v"))
    ctx["decomposed_files"] = files
    ctx["top_module_name"] = top


def agent_testbench(rec, ctx, feedback=""):
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
        resp = stream_to(prompt | llm, {"top": top, "code": top_code, "inc": inc}, live)
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
    rec.success(f"Saved {len(written)} file(s) under `{design_dir.relative_to(REPO_ROOT)}/`:")
    rec.code("\n".join(written), language="text")


def agent_simulate(rec, ctx, feedback=""):
    design_dir = Path(ctx["design_dir"])
    rtl_dir, tb_dir, sim_dir = design_dir / "rtl", design_dir / "tb", design_dir / "sim"
    sim_dir.mkdir(parents=True, exist_ok=True)
    vfiles = sorted(glob.glob(str(rtl_dir / "*.v"))) + sorted(glob.glob(str(tb_dir / "*.v")))
    if not vfiles:
        rec.error("No Verilog files to simulate.")
        ctx["simulation_output"] = "Error: no Verilog files."
        return
    compile_cmd = ["iverilog", "-g2005-sv", "-o", str(sim_dir / "design.vvp"), "-I", str(rtl_dir), *vfiles]
    rec.write("**Compile:**")
    rec.code("iverilog -g2005-sv -o design.vvp -I rtl " + " ".join(os.path.basename(f) for f in vfiles),
             language="bash")
    sim_out = ""
    try:
        with st.spinner("Compiling + simulating…"):
            subprocess.run(compile_cmd, cwd=sim_dir, capture_output=True, text=True, check=True, timeout=90)
            proc = subprocess.run(["vvp", "design.vvp"], cwd=sim_dir, capture_output=True, text=True, timeout=90)
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
    passed = "Result: PASSED" in sim_out or (sim_out and "ERROR" not in sim_out and "Result: FAILED" not in sim_out)
    if passed:
        rec.success("✅ Simulation passed.")
        ctx["simulation_output"] = ""
        return
    rec.error("❌ Simulation failed — a corrector will be routed next.")
    ctx["simulation_output"] = sim_out or "Result: FAILED"
    ctx["error_count"] = ctx.get("error_count", 0) + 1


def agent_fix_design(rec, ctx, feedback=""):
    files = dict(ctx["decomposed_files"])
    err = ctx["simulation_output"]
    faulty = next((f for f in files if f in err), None) or f"{ctx['top_module_name']}.v"
    faulty = faulty if faulty in files else next(iter(files))
    history = dict(ctx.get("fix_history", {}))
    past = history.get(faulty, [])
    tried = past + [files[faulty]]
    rec.write("**Compiler/sim errors fed to the model:**")
    rec.code(err[:1800], language="text")
    rec.expander_code(f"Current (broken) `{faulty}` given to the corrector", files[faulty], "verilog")
    attempt = ctx.get("error_count", 0)
    temp = min(0.2 + 0.18 * attempt, 0.85)
    if past:
        rec.caption(f"⛔ {len(past)} earlier fix(es) of `{faulty}` failed — all are shown to the model "
                    "with an explicit 'do NOT reproduce these' so it stops looping on the same code.")
    rec.caption(f"Attempt {attempt + 1} · temperature {temp:.2f} (raised each retry to avoid the same fix).")

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
            rec.caption(f"↻ Identical to a failed attempt — re-rolling hotter (temp {hot:.2f}).")
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
            rec.caption(f"↻ Identical to a failed testbench — re-rolling hotter (temp {hot:.2f}).")
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
    }
    (chip_dir / "config.json").write_text(json.dumps(config, indent=2))
    rec.expander_code("config.json", json.dumps(config, indent=2), "json")

    cmd = [LIBRELANE_BIN, "--manual-pdk", "--pdk-root", PDK_ROOT, "config.json"]
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
        rec.success(f"🎉 GDSII generated → `output/{design_dir.name}/{final_gds.name}`")
    else:
        rec.error(f"LibreLane finished (rc={proc.returncode}) but no GDS was produced — see log above.")

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
        rows = [(label, metrics[k]) for k, label in keys.items() if k in metrics]
        if rows:
            rec.write("**Signoff metrics:**")
            rec.table({"Metric": [r[0] for r in rows], "Value": [str(r[1]) for r in rows]})
        rec.json(metrics)
    ctx["harden"] = {"gds": str(final_gds) if final_gds else None, "metrics": metrics, "rc": proc.returncode}


# --------------------------------------------------------------------------- #
# Step registry + orchestration
# --------------------------------------------------------------------------- #
# (emoji, title, desc, fn, accepts_feedback)
STEP_DEFS = {
    "plan":          ("🧭", "Planner", "Drafts the build plan + design notes.", agent_plan, True),
    "retrieve":      ("📚", "Dataset Retriever", "RAG over the local FAISS reference index.", agent_retrieve, False),
    "web":           ("🌐", "Web Researcher", "HDL GitHub repos + papers, crawled & cached.", agent_web, True),
    "generate":      ("✍️", "Verilog Generator", "The local LLM drafts synthesizable RTL.", agent_generate, True),
    "decompose":     ("🧩", "Decomposer", "Split the RTL into per-module files + header.", agent_decompose, True),
    "testbench":     ("🧪", "Testbench Writer", "Self-checking testbench with PASSED/FAILED.", agent_testbench, True),
    "write":         ("💾", "File Writer", "Write RTL + testbench to the output folder.", agent_write, False),
    "simulate":      ("🔬", "Icarus Simulator", "Compile + run with iverilog/vvp.", agent_simulate, False),
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
        if ctx.get("simulation_output"):  # failed
            if ctx.get("error_count", 0) < MAX_RETRIES:
                q[:0] = [route_next(ctx), "write", "simulate"]
        elif ctx.get("run_harden"):       # passed → harden if requested
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
    """Replanner: choose the next steps from the user's feedback + latest error."""
    ctx = run["ctx"]
    rec = Recorder("🔁", "Replanner", "Revises the remaining plan from your feedback + latest state.",
                   "plan", live=True)
    known = ["retrieve", "web", "generate", "decompose", "testbench", "write", "simulate",
             "fix_design", "fix_testbench"]
    err = ctx.get("simulation_output", "")
    rec.caption("🧠 Choosing the next steps…")
    raw = stream_to(
        get_chat_model(temperature=0.3),
        "You are the re-planner for a Verilog build agent. Output the next steps to run as a "
        "comma-separated list using ONLY these step names: " + ", ".join(known) + ".\n"
        "Common recoveries: regenerate from scratch = generate,decompose,testbench,write,simulate; "
        "rebuild only the testbench = fix_testbench,write,simulate; re-fetch references then "
        "regenerate = web,generate,decompose,testbench,write,simulate.\n\n"
        f"USER FEEDBACK: {feedback or '(none)'}\n"
        f"LATEST ERROR: {err[:800] or '(none)'}\n"
        f"DESIGN: {ctx['query']}\n\n"
        "Reply ONLY with the comma-separated step list.",
        rec.placeholder(),
    )
    picked = [s.strip() for s in re.split(r"[,\n]", clean_llm_output(raw)) if s.strip() in known]
    if not picked:
        picked = ["generate", "decompose", "testbench", "write", "simulate"]
    if "simulate" not in picked:           # always end by re-verifying
        picked += ["write", "simulate"]
    rec.success("New plan: " + "  →  ".join(picked))
    run["queue"] = picked
    ctx["error_count"] = 0                  # explicit replan resets the retry budget
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
    rec.success(f"Found a reference for `{block}` — it will be injected into the next step you run.")
    run["transcript"].append({"node": "web", "blocks": rec.blocks})


def new_run(prompt, use_web, run_harden, clock_port, clock_period, die_um, core_util):
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
            "run_harden": run_harden, "clock_port": clock_port, "clock_period": clock_period,
            "die_um": die_um, "core_util": core_util,
        },
        "queue": ["plan"],
        "transcript": [],
        "status": "running",
        "pending": None,
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
    st.code("output/" + design_dir.name + "/\n" + "\n".join(f"  {t}" for t in tree[:60]), language="text")

    cols = st.columns(2)
    gds_files = list(design_dir.glob("*.gds"))
    if gds_files:
        with cols[0]:
            with open(gds_files[0], "rb") as f:
                st.download_button("⬇️ Download GDSII", f, file_name=gds_files[0].name)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in design_dir.rglob("*"):
            if p.is_file() and "runs" not in p.parts:
                z.write(p, p.relative_to(design_dir))
    with cols[1]:
        st.download_button("⬇️ Download all (zip)", buf.getvalue(), file_name=f"{design_dir.name}.zip")


def finalize(run):
    ctx = run["ctx"]
    design_dir = Path(ctx["design_dir"])
    sim_passed = not ctx.get("simulation_output")
    top = ctx.get("top_module_name") or slugify(ctx["query"])
    write_result_md(design_dir, ctx["query"], top, sim_passed, ctx.get("harden"))


# --------------------------------------------------------------------------- #
# Human-in-the-loop feedback panel
# --------------------------------------------------------------------------- #
def feedback_ui(run):
    pend = run.get("pending")
    accepts = STEP_DEFS.get(pend, (None,) * 5)[4] if pend in STEP_DEFS else False
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
        st.success(f"⏸ **Paused** after `{pend}`. Nothing left queued — finish, or steer.")

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
def main():
    st.set_page_config(page_title="GarudaChip", layout="wide")
    st.title("🦅 GarudaChip — prompt → RTL → GDSII")
    st.caption("Local-LLM digital & SoC automation · step-by-step, human-in-the-loop · Ollama + LibreLane")

    with st.sidebar:
        st.header("Model")
        st.success(f"Chat: {provider_label()}")
        hw_ok = librelane_available()
        if hw_ok:
            st.success("LibreLane detected")
        else:
            st.warning("LibreLane not on PATH — RTL + sim only.")

        st.header("Design prompt")
        prompt = st.text_area("Describe the hardware to build", height=140,
                              value="an 8-bit (int8) transformer Q/K/V self-attention accelerator, "
                                    "sequence length 4 and head dimension 4, signed 8-bit MAC datapath")
        use_web = st.checkbox("Use web research", value=True)

        st.header("Hardening")
        run_harden = st.checkbox("Run LibreLane after RTL passes", value=hw_ok, disabled=not hw_ok)
        clock_port = st.text_input("Clock port", value="clk")
        clock_period = st.number_input("Clock period (ns)", 1.0, value=24.0, step=1.0)
        die_um = st.number_input("Die size (µm, square)", 50.0, value=600.0, step=50.0)
        core_util = st.slider("Core utilization (%)", 10, 80, 25)
        go = st.button("🚀 Generate chip", type="primary", use_container_width=True)
        if st.session_state.get("run") is not None and st.button("🔄 New run / reset", use_container_width=True):
            st.session_state.run = None
            st.rerun()

    if "run" not in st.session_state:
        st.session_state.run = None

    if go:
        st.session_state.run = new_run(prompt, use_web, run_harden and hw_ok,
                                       clock_port, clock_period, die_um, core_util)

    run = st.session_state.run
    if run is None:
        st.subheader("Agent workflow")
        st.graphviz_chart(workflow_graph(), use_container_width=True)
        st.info("Describe the hardware on the left and click **Generate chip**. The flow runs "
                "ONE agent at a time and PAUSES after each so you can **Continue**, **Revise** "
                "with feedback, **Replan**, or ask it to **fetch a web example** of a block — "
                "just like Claude Code.")
        return

    # Live workflow graph (amber = working, green = done).
    st.subheader("Live agent workflow")
    graph_ph = st.empty()

    # 1) Apply the action queued by a button click on the previous run.
    act = run.pop("action", None)
    if act == "continue":
        run["status"] = "finalize" if not run["queue"] else "running"
    elif act == "revise":
        if run["transcript"]:
            run["transcript"].pop()                 # drop the step we're redoing
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

    # 3) Replan / web-lookup execute now, then pause for review.
    if run["status"] == "replan":
        do_replan(run, run.pop("pending_feedback", ""))
        run["status"] = "paused"
    elif run["status"] == "weblookup":
        do_weblookup(run, run.pop("pending_block", ""))
        run["queue"].insert(0, run["pending"])      # re-run the paused step with the new reference
        run["status"] = "paused"

    # 4) Run the next queued step (live), then pause.
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

    # 5) Finalize.
    if run["status"] == "finalize":
        finalize(run)
        run["status"] = "done"

    # Final graph state.
    done = {GRAPH_KEY.get(r["node"], r["node"]) for r in run["transcript"]}
    if run["status"] == "done" and (run["ctx"].get("harden") or {}).get("gds"):
        done.add("gds")
    graph_ph.graphviz_chart(workflow_graph(done=done), use_container_width=True)

    # 6) Feedback panel / output.
    if run["status"] == "paused":
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
