#!/usr/bin/env bash
# =====================================================================
# GarudaChip — launch the web app: FastAPI backend + Vite frontend.
#
# Brings LibreLane (Nix) onto PATH, ensures Ollama + the Postgres/MinIO
# knowledge stack are up, starts the FastAPI backend (uvicorn, :8011) and,
# if the frontend is installed, the Vite dev server (:5173).
#
# Usage:
#   ./scripts/run.sh                 # backend + frontend
#   ./scripts/run.sh --backend-only  # just the API
# =====================================================================
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# --- Put the Nix profile (librelane + EDA tools) on PATH ---
if [ -e /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh ]; then
  . /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh
fi
export PATH="$HOME/.nix-profile/bin:$PATH"

command -v librelane >/dev/null 2>&1 \
  && echo "✓ LibreLane: $(librelane --version 2>/dev/null | head -1)" \
  || echo "! LibreLane not on PATH — hardening (RTL→GDSII) disabled. Run ./scripts/install.sh"

# --- Ollama (local model) ---
if ! curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "! Ollama not on :11434 — starting it"
  nohup ollama serve >/tmp/ollama.log 2>&1 &
  sleep 3
fi

# --- Knowledge stack (Postgres pgvector + MinIO) ---
if command -v docker >/dev/null 2>&1; then
  docker compose up -d >/dev/null 2>&1 \
    && echo "✓ Knowledge stack up (Postgres :5433 · MinIO :9100)" \
    || echo "! Could not start docker compose — recall will be disabled."
fi

# --- Use the cached embeddings model offline (avoids HuggingFace name-resolution
#     hangs that silently skip knowledge ingest). Only if a HF cache already exists. ---
if [ -d "$HOME/.cache/huggingface" ]; then
  export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
fi

# --- Backend (FastAPI) ---
echo "→ Starting FastAPI backend on http://localhost:8011"
( cd "$REPO_ROOT/backend" && exec uv run uvicorn garuda_api.main:app --port 8011 ) &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT

if [ "${1:-}" = "--backend-only" ]; then
  wait $BACKEND_PID
  exit 0
fi

# --- Frontend (Vite) ---
if [ -d "$REPO_ROOT/frontend/node_modules" ]; then
  echo "→ Starting Vite frontend on http://localhost:5173"
  cd "$REPO_ROOT/frontend" && exec npm run dev
else
  echo "! Frontend deps not installed. In another terminal:"
  echo "    cd frontend && npm install && npm run dev"
  echo "  Backend is running; press Ctrl-C to stop."
  wait $BACKEND_PID
fi
