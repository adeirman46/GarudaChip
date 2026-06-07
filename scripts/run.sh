#!/usr/bin/env bash
# =====================================================================
# GarudaChip — launch the unified RTL-to-GDSII Streamlit app.
#
# Brings LibreLane (from the Nix profile) onto PATH, makes sure Ollama is
# up, then starts Streamlit inside the uv-managed environment.
#
# Usage:
#   ./scripts/run.sh                 # launch on default port 8501
#   ./scripts/run.sh --port 8600     # extra args are passed to streamlit
# =====================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# --- Put the Nix profile (librelane + EDA tools) on PATH ---
if [ -e /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh ]; then
  . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
fi
export PATH="$HOME/.nix-profile/bin:$PATH"

if command -v librelane >/dev/null 2>&1; then
  echo "✓ LibreLane: $(librelane --version 2>/dev/null | head -1)"
else
  echo "! LibreLane not on PATH — the hardening (RTL→GDSII) stage will be disabled."
  echo "  Run ./scripts/install.sh (or: nix profile add github:librelane/librelane --accept-flake-config)"
fi

# --- Make sure Ollama is reachable (local default model) ---
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "! Ollama not responding on :11434 — starting it in the background"
  nohup ollama serve >/tmp/ollama.log 2>&1 &
  sleep 3
fi

# --- Launch ---
echo "→ Starting GarudaChip…"
exec uv run streamlit run src/garuda_chip/app.py "$@"
