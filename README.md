# GarudaChip

**Toward the independence of chip design.**

GarudaChip is a local-first, agentic flow that turns a **plain-language prompt into a
manufacturable digital chip layout (GDSII)** — RTL generation, functional verification,
and full RTL-to-GDSII hardening, all driven by a **local LLM** running on your own
machine.

It is a focused, digital/SoC-only evolution of
[Chipster](https://github.com/adeirman46/Chipster), re-architected to:

- 🧠 **Run on local models** via [Ollama](https://ollama.com) (default: `qwen3.5:9b`) —
  no API keys, no cloud, fully offline. Google Gemini remains an optional fallback.
- 📦 **Use [uv](https://docs.astral.sh/uv/)** for the Python environment (no conda).
- 🏭 **Harden with [LibreLane 3](https://github.com/librelane/librelane)** (the
  open-source successor to OpenLane 2) installed via Nix — bringing Yosys, OpenROAD,
  KLayout, Magic and Netgen.
- 🔗 **One unified flow** — Verilog generation and chip hardening are a single
  Streamlit app, not two separate tools.

---

## The unified flow

```
 Prompt ("a 4-bit pipelined multiplier")
   │
   ▼
 ┌─────────────────────────── RTL stage (local LLM) ───────────────────────────┐
 │  RAG retrieve  →  web research*  →  generate Verilog  →  decompose           │
 │  →  write testbench  →  Icarus simulation  ⇄  self-correct (module / TB)     │
 └──────────────────────────────────────────────────────────────────────────────┘
   │  (verified RTL)
   ▼
 ┌──────────────────────── Hardening stage (LibreLane) ─────────────────────────┐
 │  synthesis → floorplan → PnR → CTS → routing → STA → GDSII → DRC → LVS        │
 │  ⇄ self-correct: shrink area / relax clock / serialize I/O to meet limits     │
 └──────────────────────────────────────────────────────────────────────────────┘
   │
   ▼
 GDSII + reports (area, timing, DRC, LVS, pin count)
```

\* Web research is optional (uses `crawl4ai`).

---

## Requirements

- Linux x86_64 (tested on Ubuntu)
- `git`, `curl`, `sudo` (Nix needs root to install once)
- An NVIDIA GPU is used automatically for embeddings if present (CPU works too)
- ~20 GB free disk for the LibreLane tool closure + Python env

Everything else (uv, Ollama, Nix, LibreLane, Icarus Verilog) is installed by the script.

---

## Quick start

```bash
git clone <your-fork-url> GarudaChip && cd GarudaChip

# One-shot install: system deps, uv env, Ollama + qwen3.5:9b, Nix + LibreLane
./scripts/install.sh

# Launch the unified app
./scripts/run.sh
```

Then open the Streamlit URL it prints (default <http://localhost:8501>).

> First run downloads the model (~6 GB) and the LibreLane tools. Subsequent runs are fast.

---

## Manual setup

If you prefer to do it step by step:

```bash
# 1. System dependency
sudo apt install -y iverilog

# 2. Python environment (uv)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync                       # core deps
uv sync --extra web           # + crawl4ai web-research agent (optional)
uv run crawl4ai-setup         # one-time Playwright browser setup (optional)

# 3. Local model (Ollama)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3.5:9b

# 4. LibreLane via Nix (RTL → GDSII backend)
sh <(curl -L https://nixos.org/nix/install) --daemon --yes
echo "experimental-features = nix-command flakes" | sudo tee -a /etc/nix/nix.conf
echo "trusted-users = root $(whoami)"             | sudo tee -a /etc/nix/nix.conf
sudo systemctl restart nix-daemon
nix profile add github:librelane/librelane --accept-flake-config

# 5. Config
cp .env.example .env
```

---

## Configuration

All configuration is in `.env` (copied from `.env.example`). Highlights:

| Variable | Default | Notes |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` (local) or `google` (cloud) |
| `OLLAMA_MODEL` | `qwen3.5:9b` | any tag from `ollama list` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | |
| `GOOGLE_API_KEY` | _(empty)_ | only needed when `LLM_PROVIDER=google` |
| `EMBEDDINGS_PROVIDER` | `huggingface` | local `all-MiniLM-L6-v2` — matches the prebuilt FAISS indexes |
| `LIBRELANE_BIN` | `librelane` | path to the LibreLane CLI |
| `PDK` | `gf180mcuD` | open-source PDK for hardening |

**Switch to cloud Gemini** (optional): set `LLM_PROVIDER=google` and `GOOGLE_API_KEY=...`.

**Use a different local model**: `ollama pull <model>` then set `OLLAMA_MODEL=<model>`.

> Keep `EMBEDDINGS_PROVIDER=huggingface` unless you rebuild `data/verilog_datasets`,
> because the shipped vector indexes are 384-dim (`all-MiniLM-L6-v2`).

---

## Project structure

```
GarudaChip/
├── scripts/
│   ├── install.sh           # one-shot installer
│   └── run.sh               # launch the unified app
├── src/
│   └── garuda_chip/
│       ├── app.py           # the unified Streamlit RTL→GDSII flow
│       └── llm.py           # model/embeddings factory (Ollama ⇄ Google)
├── data/verilog_datasets/   # FAISS RAG indexes (index.* are git-ignored)
├── examples/                # generated designs & chips
├── pyproject.toml           # uv-managed dependencies
└── .env.example             # configuration template
```

---

## How it works

**RTL stage** — A LangGraph agent retrieves reference designs from local FAISS indexes
(and, optionally, the web), asks the local LLM to write synthesizable Verilog, splits it
into per-module files plus a shared header, generates a self-checking testbench, and runs
it through **Icarus Verilog**. On failure it routes to a module-fixer or testbench-fixer
and retries until the simulation passes.

**Hardening stage** — The verified RTL is handed to **LibreLane**, which runs the full
synthesis → place-and-route → signoff flow against an open-source PDK and emits the GDSII
plus area/timing/DRC/LVS reports. Agentic feedback loops shrink area, relax the clock to
fix timing, or serialize I/O to fit pin-count limits.

---

## Credits

GarudaChip is built on top of [Chipster](https://github.com/adeirman46/Chipster) by
Ade Irman, focused down to the digital/SoC flow and re-targeted at local models and
LibreLane. EDA backend by [LibreLane](https://github.com/librelane/librelane) /
[OpenROAD](https://theopenroadproject.org/).

## License

MIT — see [LICENSE](LICENSE).
