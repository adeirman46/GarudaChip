#!/usr/bin/env bash
# =====================================================================
# GarudaChip — one-shot installer
# Digital & SoC RTL-to-GDSII automation with local LLMs (Ollama) + LibreLane.
#
# Installs, in order:
#   1. System deps (Icarus Verilog)
#   2. uv (Python package/venv manager) + the Python environment
#   3. Ollama + the default local model (qwen3.5:9b)
#   4. Nix (multi-user) + LibreLane 3.x (brings yosys/openroad/klayout/magic/netgen)
#   5. (optional) crawl4ai / Playwright for the web-research agent
#
# Re-running is safe: every step is skipped if already satisfied.
# Usage:
#   ./scripts/install.sh            # full install
#   SKIP_NIX=1 ./scripts/install.sh # skip Nix/LibreLane (RTL+sim only)
#   SKIP_WEB=1 ./scripts/install.sh # skip crawl4ai web agent
# =====================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

OLLAMA_MODEL_DEFAULT="qwen3.5:9b"
say()  { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }
ok()   { printf "\033[1;32m   ✓ %s\033[0m\n" "$*"; }
warn() { printf "\033[1;33m   ! %s\033[0m\n" "$*"; }

# ---------------------------------------------------------------------
say "1/5  System dependencies (Icarus Verilog)"
if command -v iverilog >/dev/null 2>&1; then
  ok "iverilog already installed ($(iverilog -V 2>/dev/null | head -1))"
else
  warn "iverilog not found — installing via apt (needs sudo)"
  sudo apt-get update -y && sudo apt-get install -y iverilog
  ok "iverilog installed"
fi

# ---------------------------------------------------------------------
say "2/5  uv + Python environment"
if ! command -v uv >/dev/null 2>&1; then
  warn "uv not found — installing"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
ok "uv $(uv --version)"
say "    Creating venv + installing dependencies (this pulls torch, may take a while)"
uv sync
ok "Python environment ready (.venv)"

if [ ! -f .env ]; then
  cp .env.example .env
  ok "Created .env from .env.example (defaults to local Ollama qwen3.5:9b)"
else
  ok ".env already exists — leaving it untouched"
fi

# ---------------------------------------------------------------------
say "3/5  Ollama + local model"
if ! command -v ollama >/dev/null 2>&1; then
  warn "ollama not found — installing"
  curl -fsSL https://ollama.com/install.sh | sh
fi
ok "ollama present"
# Start the server if it is not already listening.
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
  warn "ollama server not responding — starting it in the background"
  nohup ollama serve >/tmp/ollama.log 2>&1 &
  sleep 3
fi
MODEL="${OLLAMA_MODEL:-$OLLAMA_MODEL_DEFAULT}"
if ollama list 2>/dev/null | grep -q "${MODEL%%:*}"; then
  ok "Model present: $(ollama list | grep "${MODEL%%:*}" | head -1 | awk '{print $1}')"
else
  warn "Pulling $MODEL (large download)…"
  ollama pull "$MODEL"
fi

# ---------------------------------------------------------------------
say "4/5  Nix + LibreLane (EDA backend)"
if [ "${SKIP_NIX:-0}" = "1" ]; then
  warn "SKIP_NIX=1 — skipping LibreLane install (RTL generation + simulation only)"
else
  # Make nix visible in this shell if already installed.
  if [ -e /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh ]; then
    . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
  fi
  if ! command -v nix >/dev/null 2>&1; then
    warn "Nix not found — installing (multi-user, needs sudo). Flakes will be enabled."
    sh <(curl -L https://nixos.org/nix/install) --daemon --yes
    . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
    # Enable flakes if not already enabled.
    if ! grep -q "experimental-features" /etc/nix/nix.conf 2>/dev/null; then
      echo "experimental-features = nix-command flakes" | sudo tee -a /etc/nix/nix.conf >/dev/null
    fi
    if ! grep -q "trusted-users.*$(whoami)" /etc/nix/nix.conf 2>/dev/null; then
      echo "trusted-users = root $(whoami)" | sudo tee -a /etc/nix/nix.conf >/dev/null
    fi
    sudo systemctl restart nix-daemon 2>/dev/null || true
  fi
  ok "nix $(nix --version | awk '{print $3}')"
  if command -v librelane >/dev/null 2>&1; then
    ok "LibreLane already installed ($(librelane --version 2>/dev/null | head -1))"
  else
    warn "Installing LibreLane via Nix flake (downloads yosys/openroad/klayout/magic/netgen)…"
    nix profile add github:librelane/librelane --accept-flake-config
    ok "LibreLane installed: $(librelane --version 2>/dev/null | head -1)"
  fi

  # LibreLane does NOT auto-download the PDK — enable the exact gf180 open_pdks
  # revision this LibreLane release pins, using its bundled Ciel.
  export PDK_ROOT="${PDK_ROOT:-$HOME/.ciel}"
  if [ -d "$PDK_ROOT/gf180mcuC" ]; then
    ok "gf180 PDK already enabled at $PDK_ROOT/gf180mcuC"
  else
    warn "Enabling gf180 PDK via Ciel (a few hundred MB)…"
    PDK_HASHES=$(find /nix/store -maxdepth 6 -path '*librelane*/pdk_hashes.yaml' 2>/dev/null | head -1)
    PDK_HASH=$(awk '/^gf180mcu:/{print $2}' "$PDK_HASHES" 2>/dev/null)
    CIEL=$(find /nix/store -maxdepth 4 -path '*ciel*/bin/ciel' 2>/dev/null | head -1)
    if [ -n "$CIEL" ] && [ -n "$PDK_HASH" ]; then
      "$CIEL" enable --pdk-family gf180mcu "$PDK_HASH" \
        && ok "gf180 PDK enabled ($PDK_HASH)" \
        || warn "Ciel enable failed — run manually: $CIEL enable --pdk-family gf180mcu $PDK_HASH"
    else
      warn "Could not auto-locate Ciel/PDK hash. Enable manually with:"
      warn "  ciel enable --pdk-family gf180mcu <hash from librelane/pdk_hashes.yaml>"
    fi
  fi
fi

# ---------------------------------------------------------------------
say "5/5  Web-research agent (optional)"
if [ "${SKIP_WEB:-0}" = "1" ]; then
  warn "SKIP_WEB=1 — skipping crawl4ai/Playwright"
else
  warn "Installing crawl4ai extra + Playwright browser"
  uv sync --extra web
  uv run crawl4ai-setup || warn "crawl4ai-setup reported issues (web agent optional)"
fi

say "Done!"
cat <<EOF

  GarudaChip is ready.

  Launch the unified flow with:
      ./scripts/run.sh

  Configuration lives in .env (chat model defaults to local Ollama: $OLLAMA_MODEL_DEFAULT).
EOF
