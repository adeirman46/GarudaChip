"""
GarudaChip — unified, local-LLM digital/SoC flow (Chipster-style UI).

ONE Streamlit app: prompt -> RTL (RAG + local LLM) -> Icarus sim (+ self-fix)
-> LibreLane hardening -> GDSII. Every agent renders its OWN block showing the
code/testbench/simulation it produced, and every artifact is written to
output/<design>/ (rtl, tb, sim, chip/gds, reports, result.md).

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
from typing import Dict, List, TypedDict

import streamlit as st
import graphviz
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

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


# ---- Live workflow graph (highlights the agent currently working) ---------- #
WF_NODES = [
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
    ("retrieve", "web"), ("web", "generate"), ("generate", "decompose"),
    ("decompose", "testbench"), ("testbench", "write"), ("write", "simulate"),
    ("simulate", "correct"), ("correct", "write"), ("simulate", "harden"),
    ("harden", "gds"),
]

_GRAPH_PH = None       # st.empty() placeholder, set in main()
_DONE: set = set()     # nodes already executed


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


def highlight(node_key: str) -> None:
    """Mark a graph node active in the live placeholder, then record it done."""
    if _GRAPH_PH is not None:
        _GRAPH_PH.graphviz_chart(workflow_graph(active=node_key, done=set(_DONE)),
                                 use_container_width=True)
    _DONE.add(node_key)


def agent(emoji: str, title: str, desc: str = "", node: str = "") -> None:
    if node:
        highlight(node)
    st.markdown("---")
    st.markdown(f"### {emoji} {title}")
    if desc:
        st.caption(desc)


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
        for res in ddg.text(f"{query} hardware accelerator architecture", max_results=n_other * 2):
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


# --------------------------------------------------------------------------- #
# Graph state
# --------------------------------------------------------------------------- #
class GraphState(TypedDict):
    query: str
    use_web: bool
    design_dir: str
    documents: List[Document]
    generation: str
    decomposed_files: Dict[str, str]
    testbench_code: Dict[str, str]
    top_module_name: str
    simulation_output: str
    error_count: int


# --------------------------------------------------------------------------- #
# Agents — each renders its OWN Streamlit block
# --------------------------------------------------------------------------- #
def dataset_retriever_node(state: GraphState) -> dict:
    agent("📚", "Agent 1 · Dataset Retriever", "RAG over the local FAISS reference index.", node="retrieve")
    vs = load_vectorstore()
    docs: List[Document] = []
    if vs is not None:
        with st.spinner("Retrieving reference designs…"):
            docs = vs.as_retriever(search_kwargs={"k": 8}).invoke(state["query"])
        st.success(f"Retrieved **{len(docs)}** reference chunks from the local index.")
        with st.expander("Show retrieved sources"):
            for d in docs:
                st.write("•", d.metadata.get("source", "local dataset"))
    else:
        st.warning("No local index found — generating from scratch.")
    return {"documents": docs}


def web_retriever_node(state: GraphState) -> dict:
    agent("🌐", "Agent 2 · Web Researcher",
          "HDL GitHub repos (Verilog/VHDL/SystemVerilog) + papers/theory · crawled & cached.", node="web")
    if not state.get("use_web"):
        st.info("Web research disabled.")
        return {}
    docs = list(state.get("documents", []))
    cache_dir = DATA_DIR / f"faiss_github_{slugify(state['query'], 80)}"

    if (cache_dir / "index.faiss").exists():
        try:
            vs = FAISS.load_local(str(cache_dir), _embeddings(), allow_dangerous_deserialization=True)
            hits = vs.as_retriever(search_kwargs={"k": 20}).invoke(state["query"])
            st.success(f"Loaded cached web index `{cache_dir.name}` ({len(hits)} chunks).")
            return {"documents": docs + hits}
        except Exception as e:  # noqa: BLE001
            st.warning(f"Cache load failed ({e}); crawling live.")

    try:
        import asyncio
        from crawl4ai import AsyncWebCrawler
    except Exception as e:  # noqa: BLE001
        st.warning(f"crawl4ai unavailable ({e}) — skipping web research.")
        return {"documents": docs}

    # Ask the LLM for close HDL building-block terms — used when the exact IP is
    # not on GitHub ("similar but not too different, still Verilog/VHDL/SV").
    similar: List[str] = []
    st.caption("🧠 Model reasoning — picking similar HDL building blocks:")
    think_box = st.empty()
    try:
        with st.spinner("Thinking…"):
            raw = stream_to(
                get_chat_model(temperature=0.3),
                "Give 3 short GitHub search phrases (max 4 words each) to find open-source "
                "Verilog/VHDL/SystemVerilog HDL implementations similar to this hardware: "
                f"'{state['query']}'. Focus on core building blocks (e.g. systolic array, "
                "MAC unit, matrix multiply, FIFO). Reply ONLY as a comma-separated list.",
                think_box,
            )
        txt = clean_llm_output(raw)
        similar = [s.strip() for s in re.split(r"[,\n]", txt) if 2 < len(s.strip()) < 50][:3]
    except Exception:  # noqa: BLE001
        similar = []
    if similar:
        st.caption("🔁 Similar-IP search terms: " + ", ".join(f"`{s}`" for s in similar))

    with st.spinner("Searching GitHub (HDL) + web…"):
        urls = _web_search(state["query"], similar=similar)
    n_gh = sum("github.com" in u for u in urls)
    st.write(f"🔎 Found **{len(urls)}** references — **{n_gh}** HDL GitHub repos "
             f"+ **{len(urls) - n_gh}** papers/web.")
    if not urls:
        st.info("No search results; skipping.")
        return {"documents": docs}

    crawl_log = st.empty()
    crawled: List[str] = []

    async def _crawl() -> List[Document]:
        out: List[Document] = []
        sem = asyncio.Semaphore(5)  # crawl up to 5 pages at once (fast)
        async with AsyncWebCrawler() as crawler:
            async def fetch(url: str) -> None:
                async with sem:
                    try:
                        res = await asyncio.wait_for(crawler.arun(url=url), timeout=25)
                    except Exception:  # noqa: BLE001
                        return
                md = _md_text(res)
                is_gh = "github.com" in url
                # Keep every page that actually returned content (HDL repos AND
                # papers/theory) so we use as many of the 20 references as possible.
                if md and len(md) > 250:
                    out.append(Document(page_content=md[:8000], metadata={"source": url}))
                    crawled.append(("💻 " if is_gh else "📄 ") + url)
                    crawl_log.code("\n".join(f"✓ {u}" for u in crawled), language="text")
            await asyncio.gather(*(fetch(u) for u in urls))
        return out

    with st.spinner(f"Crawling {len(urls)} pages (5 at a time)…"):
        web_docs = asyncio.run(_crawl())
    if not web_docs:
        st.info("Crawled pages had no usable code.")
        return {"documents": docs}

    chunks = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=200).split_documents(web_docs)
    try:
        vs = FAISS.from_documents(chunks, _embeddings())
        vs.save_local(str(cache_dir))
        hits = vs.as_retriever(search_kwargs={"k": 20}).invoke(state["query"])
        st.success(f"Crawled {len(web_docs)} pages → cached {len(chunks)} chunks → using {len(hits)}.")
        return {"documents": docs + hits}
    except Exception as e:  # noqa: BLE001
        st.warning(f"Crawled {len(web_docs)} pages (cache save failed: {e}).")
        return {"documents": docs + chunks}


def code_generator_node(state: GraphState) -> dict:
    agent("✍️", "Agent 3 · Verilog Generator", "The local LLM drafts synthesizable RTL from the references.", node="generate")
    llm = get_chat_model(temperature=0.2)
    prompt = ChatPromptTemplate.from_template(
        """You are an expert Verilog HDL designer.
Using the reference context and the request, write complete, synthesizable Verilog-2001.
Put any `define`/parameters at the top. Output ONLY Verilog in a single ```verilog block.

CONTEXT:
{context}

REQUEST:
{question}
"""
    )

    def fmt(docs):
        if not docs:
            return "No reference context."
        # Cap each reference so the whole prompt fits comfortably in the window.
        parts = [f"Source: {d.metadata.get('source','N/A')}\n{d.page_content[:1800]}" for d in docs[:20]]
        return "\n\n".join(parts)

    chain = prompt | llm
    st.caption("🧠 Live model output (reasoning + RTL):")
    live = st.empty()
    with st.spinner("Generating Verilog with the local model…"):
        raw = stream_to(chain, {"context": fmt(state["documents"]), "question": state["query"]}, live)
    gen = extract_code_block(raw)

    if not gen.strip():  # empty? retry once without the (possibly huge) references
        st.warning("Model returned no code — retrying with a tighter prompt…")
        with st.spinner("Retrying generation…"):
            raw = stream_to(chain, {"context": "No reference context.", "question": state["query"]}, live)
        gen = extract_code_block(raw)
    if not gen.strip():
        gen = raw.strip()  # last resort: show whatever came back
        st.error("The model produced no Verilog. Try a simpler prompt or a larger/instruct model.")
        st.code(raw[:1500] or "(completely empty response)", language="text")
        return {"generation": gen, "simulation_output": ""}

    st.success("Generated RTL:")
    st.code(gen, language="verilog")
    return {"generation": gen, "simulation_output": ""}


def decomposer_node(state: GraphState) -> dict:
    agent("🧩", "Agent 4 · Decomposer", "Split the monolithic RTL into per-module files + shared header.", node="decompose")
    llm = get_chat_model(temperature=0.0)
    prompt = ChatPromptTemplate.from_template(
        """Refactor this Verilog into separate files.
Rules:
1. Identify the top-level module.
2. One module per file ("module_name.v").
3. Move shared `define`/parameters into "shared_header.vh" and `include` it where used.
4. Reply with ONLY a JSON object: {{"top_module_name": "...", "files": {{"name.v": "code"}}}}.

REQUEST: {query}
CODE:
```verilog
{verilog_code}
```"""
    )
    st.caption("🧠 Live model output:")
    live = st.empty()
    with st.spinner("Decomposing…"):
        resp = stream_to(prompt | llm,
                         {"verilog_code": state["generation"], "query": state["query"]}, live)
    try:
        parsed = extract_json(resp)
        files = parsed.get("files", {})
        top = parsed.get("top_module_name", "")
        if not files or not top:
            raise ValueError("missing files/top_module_name")
    except Exception as e:  # noqa: BLE001
        st.warning(f"Decompose fell back to monolithic ({e}).")
        m = re.search(r"module\s+([\w]+)", state["generation"])
        top = m.group(1) if m else "top"
        files = {f"{top}.v": state["generation"]}
    files = {k: dedup_modules(v) for k, v in files.items()}
    st.success(f"Top module: `{top}` · {len(files)} file(s).")
    for fn, code in files.items():
        with st.expander(f"📄 {fn}", expanded=(fn == f"{top}.v")):
            st.code(code, language="verilog")
    return {"decomposed_files": files, "top_module_name": top}


def testbench_generator_node(state: GraphState) -> dict:
    agent("🧪", "Agent 5 · Testbench Writer", "Self-checking testbench with $dumpvars + PASSED/FAILED.", node="testbench")
    files = state["decomposed_files"]
    top = state["top_module_name"]
    top_code = files.get(f"{top}.v", next(iter(files.values())))
    header = next((f for f in files if f.endswith(".vh")), None)
    inc = f'Include `\`include "{header}"`.' if header else ""
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
    st.caption("🧠 Live model output:")
    live = st.empty()
    with st.spinner("Writing testbench…"):
        resp = stream_to(prompt | llm,
                         {"top": top, "code": top_code, "inc": inc}, live)
    try:
        tb = extract_json(resp)
        tb = {k: dedup_modules(v) for k, v in tb.items()}
    except Exception:  # noqa: BLE001
        tb = {f"{top}_tb.v": extract_code_block(resp)}
    st.success(f"Testbench `{next(iter(tb))}`:")
    st.code(next(iter(tb.values())), language="verilog")
    return {"testbench_code": tb}


def file_writer_node(state: GraphState) -> dict:
    attempt = state.get("error_count", 0)
    agent("💾", f"Agent 6 · File Writer (attempt {attempt + 1})", "Write RTL + testbench to the output folder.", node="write")
    design_dir = Path(state["design_dir"])
    rtl_dir, tb_dir = design_dir / "rtl", design_dir / "tb"
    rtl_dir.mkdir(parents=True, exist_ok=True)
    tb_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, content in state["decomposed_files"].items():
        safe = re.sub(r"[^\w.\-]", "_", name)
        if isinstance(content, str) and content.strip():
            (rtl_dir / safe).write_text(content)
            written.append(f"rtl/{safe}")
    for name, content in state.get("testbench_code", {}).items():
        safe = re.sub(r"[^\w.\-]", "_", name)
        if isinstance(content, str) and content.strip():
            (tb_dir / safe).write_text(content)
            written.append(f"tb/{safe}")
    st.success(f"Saved {len(written)} file(s) under `{design_dir.relative_to(REPO_ROOT)}/`:")
    st.code("\n".join(written), language="text")
    return {}


def simulator_node(state: GraphState) -> dict:
    attempt = state.get("error_count", 0)
    agent("🔬", f"Agent 7 · Icarus Simulator (attempt {attempt + 1})", "Compile + run with iverilog/vvp.", node="simulate")
    design_dir = Path(state["design_dir"])
    rtl_dir, tb_dir, sim_dir = design_dir / "rtl", design_dir / "tb", design_dir / "sim"
    sim_dir.mkdir(parents=True, exist_ok=True)
    vfiles = sorted(glob.glob(str(rtl_dir / "*.v"))) + sorted(glob.glob(str(tb_dir / "*.v")))
    if not vfiles:
        st.error("No Verilog files to simulate.")
        return {"simulation_output": "Error: no Verilog files."}
    compile_cmd = ["iverilog", "-g2005-sv", "-o", str(sim_dir / "design.vvp"), "-I", str(rtl_dir), *vfiles]
    st.write("**Compile:**")
    st.code("iverilog -g2005-sv -o design.vvp -I rtl " + " ".join(os.path.basename(f) for f in vfiles), language="bash")
    sim_out = ""
    try:
        with st.spinner("Compiling + simulating…"):
            subprocess.run(compile_cmd, cwd=sim_dir, capture_output=True, text=True, check=True, timeout=90)
            proc = subprocess.run(["vvp", "design.vvp"], cwd=sim_dir, capture_output=True, text=True, timeout=90)
        sim_out = proc.stdout
        st.write("**Simulation output:**")
        st.code(sim_out or "(no stdout)", language="text")
    except subprocess.CalledProcessError as e:
        sim_out = f"ERROR:\n{e.stderr or e.stdout}"
        st.error("Compile/sim error:")
        st.code(sim_out, language="text")
    except subprocess.TimeoutExpired:
        sim_out = "ERROR: simulation timed out (missing $finish?)."
        st.error(sim_out)

    (sim_dir / "simulation.log").write_text(sim_out or "PASSED (no output)")
    passed = "Result: PASSED" in sim_out or (sim_out and "ERROR" not in sim_out and "Result: FAILED" not in sim_out)
    if passed:
        st.success("✅ Simulation passed.")
        return {"simulation_output": ""}
    st.error("❌ Simulation failed — routing to a corrector.")
    return {"simulation_output": sim_out or "Result: FAILED", "error_count": attempt + 1}


def module_corrector_node(state: GraphState) -> dict:
    agent("🛠️", "Agent 8a · Module Corrector", "LLM fixes the failing design module from the error log.", node="correct")
    files = dict(state["decomposed_files"])
    err = state["simulation_output"]
    faulty = next((f for f in files if f in err), None) or f"{state['top_module_name']}.v"
    faulty = faulty if faulty in files else next(iter(files))
    st.write("**Compiler/sim errors fed to the model:**")
    st.code(err[:1800], language="text")
    with st.expander(f"Current (broken) `{faulty}` given to the corrector"):
        st.code(files[faulty], language="verilog")
    attempt = state.get("error_count", 0)
    temp = min(0.2 + 0.18 * attempt, 0.85)  # raise each retry so it stops repeating
    st.caption(f"Attempt {attempt + 1} · temperature {temp:.2f} (raised each retry to avoid the same fix).")
    llm = get_chat_model(temperature=temp)
    prompt = ChatPromptTemplate.from_template(
        """You are fixing a Verilog module that FAILED to compile/simulate. Use the EXACT errors
below to produce a CORRECTED, DIFFERENT version that resolves them — do not repeat the broken code.
This is attempt {attempt}; if earlier fixes failed, take a FUNDAMENTALLY DIFFERENT approach (rewrite
the offending logic, don't tweak it).
- Address every error specifically (undeclared signals, port/width mismatches, syntax, etc.).
- Keep the module name `{name_stem}` and a port list compatible with the rest of the design.
- Output EXACTLY ONE module in a single ```verilog block.

ERRORS:
```
{err}
```
BROKEN MODULE (`{name}`):
```verilog
{code}
```"""
    )
    st.caption("🧠 Live model output:")
    live = st.empty()
    with st.spinner("Repairing module…"):
        fixed = extract_code_block(stream_to(prompt | llm,
            {"name": faulty, "name_stem": faulty[:-2] if faulty.endswith(".v") else faulty,
             "code": files[faulty], "err": err, "attempt": attempt + 1}, live))
    files[faulty] = fixed
    st.success(f"Corrected `{faulty}`:")
    st.code(fixed, language="verilog")
    return {"decomposed_files": files}


def testbench_corrector_node(state: GraphState) -> dict:
    agent("🛠️", "Agent 8b · Testbench Corrector", "LLM fixes the testbench from the error log.", node="correct")
    tb = state.get("testbench_code", {})
    top = state["top_module_name"]
    name = next(iter(tb), f"{top}_tb.v")
    cur_tb = next(iter(tb.values()), "")
    err = state["simulation_output"]
    attempt = state.get("error_count", 0)
    temp = min(0.3 + 0.18 * attempt, 0.9)  # raise each retry so it diverges
    st.write("**Compiler/sim errors fed to the model:**")
    st.code(err[:1800], language="text")
    with st.expander("Previous (failed) testbench"):
        st.code(cur_tb, language="verilog")
    st.caption(f"Attempt {attempt + 1} · temperature {temp:.2f} — REGENERATING from the DUT (not "
               "patching the broken testbench), so it doesn't keep copying the same bug.")
    llm = get_chat_model(temperature=temp)
    # Anchor on the DUT, NOT the broken testbench — patching makes the model copy
    # the broken structure. Regenerating from scratch breaks the fixpoint loop.
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
    st.caption("🧠 Live model output:")
    live = st.empty()
    with st.spinner("Regenerating testbench…"):
        resp = stream_to(prompt | llm, {
            "name": name, "name_stem": name[:-2] if name.endswith(".v") else name,
            "top": top, "code": state["decomposed_files"].get(f"{top}.v", ""),
            "err": err,
        }, live)
    try:
        new_tb = extract_json(resp)
        new_tb = {k: dedup_modules(v) for k, v in new_tb.items()}
    except Exception:  # noqa: BLE001
        new_tb = {name: extract_code_block(resp)}
    st.success("Corrected testbench:")
    st.code(next(iter(new_tb.values())), language="verilog")
    return {"testbench_code": new_tb}


def route_after_sim(state: GraphState) -> str:
    if not state.get("simulation_output"):
        return "success"
    if state.get("error_count", 0) >= MAX_RETRIES:
        return "give_up"
    tb_names = list(state.get("testbench_code", {}).keys())
    is_tb = any(t in state["simulation_output"] for t in tb_names) or "timed out" in state["simulation_output"].lower()
    return "fix_testbench" if is_tb else "fix_design"


def build_rtl_graph():
    g = StateGraph(GraphState)
    for name, fn in [
        ("retrieve", dataset_retriever_node), ("web", web_retriever_node),
        ("generate", code_generator_node), ("decompose", decomposer_node),
        ("testbench", testbench_generator_node), ("write", file_writer_node),
        ("simulate", simulator_node), ("fix_design", module_corrector_node),
        ("fix_testbench", testbench_corrector_node),
    ]:
        g.add_node(name, fn)
    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "web")
    g.add_edge("web", "generate")
    g.add_edge("generate", "decompose")
    g.add_edge("decompose", "testbench")
    g.add_edge("testbench", "write")
    g.add_edge("write", "simulate")
    g.add_conditional_edges("simulate", route_after_sim, {
        "success": END, "give_up": END,
        "fix_design": "fix_design", "fix_testbench": "fix_testbench",
    })
    g.add_edge("fix_design", "write")
    g.add_edge("fix_testbench", "write")
    return g.compile()


# --------------------------------------------------------------------------- #
# Hardening agent (LibreLane) — own block, live log
# --------------------------------------------------------------------------- #
def harden_node(design_dir: Path, design_name: str, clock_port: str,
                clock_period: float, die_um: float, core_util: int) -> dict:
    agent("🏭", "Agent 9 · LibreLane Hardening", "RTL → synthesis → PnR → signoff → GDSII (gf180mcuD).", node="harden")
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

    config = {
        "DESIGN_NAME": design_name, "VERILOG_FILES": design_files,
        "CLOCK_PORT": clock_port, "CLOCK_PERIOD": clock_period, "PDK": PDK,
        "FP_SIZING": "absolute", "DIE_AREA": [0, 0, float(die_um), float(die_um)],
        "FP_CORE_UTIL": int(core_util), "PL_TARGET_DENSITY_PCT": max(20, int(core_util) + 5),
        "PRIMARY_GDSII_STREAMOUT_TOOL": "klayout",
    }
    (chip_dir / "config.json").write_text(json.dumps(config, indent=2))
    with st.expander("config.json"):
        st.code(json.dumps(config, indent=2), language="json")

    cmd = [LIBRELANE_BIN, "--manual-pdk", "--pdk-root", PDK_ROOT, "config.json"]
    st.write(f"**Running:** `{' '.join(cmd)}`")
    log_box = st.empty()
    lines: List[str] = []
    env = {**os.environ, "PDK_ROOT": PDK_ROOT}
    with st.spinner("LibreLane running (synthesis → PnR → signoff)…"):
        proc = subprocess.Popen(cmd, cwd=str(chip_dir), stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, env=env, bufsize=1)
        for raw in proc.stdout:  # live streaming
            lines.append(strip_ansi(raw.rstrip()))
            if len(lines) % 2 == 0 or "error" in raw.lower():
                log_box.code("\n".join(lines[-30:]), language="text")
        proc.wait()
    log_box.code("\n".join(lines[-30:]), language="text")
    (chip_dir / "librelane.log").write_text("\n".join(lines))

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
        st.success(f"🎉 GDSII generated → `output/{design_dir.name}/{final_gds.name}`")
    else:
        st.error(f"LibreLane finished (rc={proc.returncode}) but no GDS was produced — see log above.")

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
            st.write("**Signoff metrics:**")
            st.table({"Metric": [r[0] for r in rows], "Value": [r[1] for r in rows]})
        with st.expander("All metrics"):
            st.json(metrics)
    return {"gds": str(final_gds) if final_gds else None, "metrics": metrics, "rc": proc.returncode}


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
    agent("📦", "Output", f"Everything is under `output/{design_dir.name}/`.")
    tree = []
    for p in sorted(design_dir.rglob("*")):
        if p.is_file() and "runs" not in p.parts:  # hide the huge librelane run tree
            tree.append(str(p.relative_to(design_dir)))
    st.code("output/" + design_dir.name + "/\n" + "\n".join(f"  {t}" for t in tree[:60]), language="text")

    cols = st.columns(2)
    gds = design_dir / f"{design_dir.name}.gds"
    gds_files = list(design_dir.glob("*.gds"))
    if gds_files:
        with cols[0]:
            with open(gds_files[0], "rb") as f:
                st.download_button("⬇️ Download GDSII", f, file_name=gds_files[0].name)
    # zip everything (minus runs/)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for p in design_dir.rglob("*"):
            if p.is_file() and "runs" not in p.parts:
                z.write(p, p.relative_to(design_dir))
    with cols[1]:
        st.download_button("⬇️ Download all (zip)", buf.getvalue(), file_name=f"{design_dir.name}.zip")


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main():
    global _GRAPH_PH, _DONE
    st.set_page_config(page_title="GarudaChip", layout="wide")
    st.title("🦅 GarudaChip — prompt → RTL → GDSII")
    st.caption("Local-LLM digital & SoC automation · one flow · Ollama + LibreLane")

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

    if not go:
        st.subheader("Agent workflow")
        st.graphviz_chart(workflow_graph(), use_container_width=True)
        st.info("Describe the hardware on the left and click **Generate chip**. "
                "Each agent below will show the code/testbench/sim/GDS it produces. "
                "The graph above lights the agent that is currently working (amber) "
                "and turns finished ones green.")
        return

    # Live workflow graph — updates as each agent runs (amber = working, green = done).
    st.subheader("Live agent workflow")
    _DONE = set()
    _GRAPH_PH = st.empty()
    _GRAPH_PH.graphviz_chart(workflow_graph(), use_container_width=True)

    design_dir = OUTPUT_DIR / slugify(prompt)
    if design_dir.exists():
        shutil.rmtree(design_dir)
    design_dir.mkdir(parents=True, exist_ok=True)

    st.header("Stage 1 · RTL generation & verification")
    graph = build_rtl_graph()
    final: GraphState = graph.invoke(
        {"query": prompt, "use_web": use_web, "design_dir": str(design_dir),
         "documents": [], "error_count": 0},
        {"recursion_limit": 80},
    )
    sim_passed = not final.get("simulation_output")
    top = final.get("top_module_name", slugify(prompt))

    harden = None
    if not sim_passed:
        st.error(f"❌ RTL could not be verified within {MAX_RETRIES} attempts. Files saved under output/.")
    else:
        st.success("✅ RTL verified (simulation passed).")
        if run_harden and hw_ok:
            st.header("Stage 2 · Physical implementation")
            harden = harden_node(design_dir, top, clock_port, clock_period, die_um, core_util)
            if harden and harden.get("gds"):
                highlight("gds")  # turn the GDSII node green
        else:
            st.info("Hardening skipped.")

    write_result_md(design_dir, prompt, top, sim_passed, harden)
    render_output(design_dir)


if __name__ == "__main__":
    main()
