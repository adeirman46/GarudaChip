"""
GarudaChip Deep Agent — a `deepagents` (LangChain) agent driven ENTIRELY by the
local Ollama model (qwen3.5:9b). It has planning (`write_todos`) plus REAL on-disk
file tools scoped to one design directory, so you can tell it things like
"remove the .vh file" or "create an 8-bit ALU in rtl/alu.v" and it acts on disk.

The model is ALWAYS get_chat_model() (Ollama). deepagents' Anthropic default
(get_default_model) is never used because we pass `model=` explicitly.
"""

from __future__ import annotations

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

INSTRUCTIONS = f"""You are GarudaChip's Verilog HDL engineer agent.

You manage REAL Verilog/SystemVerilog files on disk for one chip design using your
file tools: `list_files`, `read_file_disk`, `write_file_disk`, `delete_file_disk`.
RTL lives under `rtl/`, testbenches under `tb/`.

Rules:
- When the user asks to add, update, remove, or inspect code or files, actually DO IT
  with the tools — then briefly summarize what you changed.
- {PITFALLS}
- Before editing a file, read it first. After writing, confirm the file path.
- Use `write_todos` to plan multi-step work and track progress.
"""


def make_fs_tools(base_dir: str | Path) -> List:
    """Real on-disk file tools, sandboxed to `base_dir` (the design directory)."""
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
    def read_file_disk(path: str) -> str:
        """Read a text file under the design dir, e.g. 'rtl/cpu.v'."""
        p = _resolve(path)
        if not p.exists() or not p.is_file():
            return f"(not found: {path})"
        return p.read_text()[:20000]

    @tool
    def write_file_disk(path: str, content: str) -> str:
        """Create or OVERWRITE a file under the design dir, e.g. 'rtl/alu.v'. Use this to save new or updated Verilog."""
        p = _resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"wrote {path} ({len(content)} bytes)"

    @tool
    def delete_file_disk(path: str) -> str:
        """Delete a file under the design dir, e.g. 'rtl/shared_header.vh'."""
        p = _resolve(path)
        if p.exists() and p.is_file():
            p.unlink()
            return f"deleted {path}"
        return f"(not found: {path})"

    return [list_files, read_file_disk, write_file_disk, delete_file_disk]


def build_deep_agent(base_dir: str | Path, model=None, temperature: float = 0.2):
    """A deepagents agent with planning + REAL file tools, driven by Ollama qwen3.5:9b."""
    return create_deep_agent(
        tools=make_fs_tools(base_dir),
        instructions=INSTRUCTIONS,
        model=model or get_chat_model(temperature=temperature),
        # keep the planning tool; use OUR real-disk file tools instead of the
        # built-in virtual-filesystem ones (write_file/read_file/ls/edit_file).
        builtin_tools=["write_todos"],
    )


def build_step_agent(base_dir: str | Path, extra_tools=None, instructions: str | None = None,
                     temperature: float = 0.2, model=None):
    """A deep agent for ONE pipeline step ("every agent is a deep agent"). It keeps the
    planning tool + real file tools and adds whatever step-specific tools (web research,
    memory, …) the caller passes — all driven by the local Ollama model. The fixed graph
    still orchestrates the steps; this just upgrades a single node's brain."""
    tools = list(make_fs_tools(base_dir)) + list(extra_tools or [])
    return create_deep_agent(
        tools=tools,
        instructions=instructions or INSTRUCTIONS,
        model=model or get_chat_model(temperature=temperature),
        builtin_tools=["write_todos"],
    )
