"""GarudaChip FastAPI backend.

Endpoints the Vite frontend consumes:
  GET    /api/health
  GET    /api/chats                       list chats
  POST   /api/chats                       create a chat
  GET    /api/chats/{id}                  chat + messages + latest run transcript (re-hydrate)
  DELETE /api/chats/{id}                  delete a chat
  POST   /api/chats/{id}/messages         send a prompt (+ optional image/PDF uploads) → starts a run
  GET    /api/runs/{run_id}/stream        Server-Sent-Events live stream of the run
  GET    /api/runs/{run_id}/file?path=…   serve an artifact (e.g. a waveform/plot) from the design dir
  GET    /api/knowledge/stats             knowledge-store stats
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from . import db, runner

_REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "src" / "garuda_chip"))

app = FastAPI(title="GarudaChip API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"], allow_credentials=True,
)


@app.on_event("startup")
def _startup():
    backed = db.init()
    print(f"[garuda-api] persistence: {'Postgres' if backed else 'in-memory'}")


# --- models -----------------------------------------------------------------
class CreateChat(BaseModel):
    title: str | None = None


class RunOpts(BaseModel):
    use_web: bool = True
    run_harden: bool = False
    deep_steps: bool = True
    clock_port: str = "clk"
    clock_period: float = 24.0
    die_um: float = 600.0
    core_util: int = 25


# --- health -----------------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/knowledge/stats")
def knowledge_stats():
    try:
        from memory_store import get_memory
        return get_memory().stats() or {"total": 0, "by_kind": {}}
    except Exception:  # noqa: BLE001
        return {"total": 0, "by_kind": {}}


# --- chats ------------------------------------------------------------------
@app.get("/api/chats")
def chats():
    return db.list_chats()


@app.post("/api/chats")
def create_chat(body: CreateChat):
    return db.create_chat(body.title or "New chat")


@app.get("/api/chats/{chat_id}")
def get_chat(chat_id: str):
    chat = db.get_chat(chat_id)
    if not chat:
        raise HTTPException(404, "chat not found")
    run = db.latest_run_for_chat(chat_id)
    return {"chat": chat, "messages": db.get_messages(chat_id),
            "run": run, "transcript": (run or {}).get("transcript", [])}


@app.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str):
    db.delete_chat(chat_id)
    return {"ok": True}


# --- send a message (starts a run) ------------------------------------------
@app.post("/api/chats/{chat_id}/messages")
async def send_message(
    chat_id: str,
    prompt: str = Form(...),
    opts: str = Form("{}"),
    files: list[UploadFile] = File(default=[]),
):
    chat = db.get_chat(chat_id)
    if not chat:
        raise HTTPException(404, "chat not found")

    # read uploads (image/PDF/text) into memory for the pipeline + knowledge store
    uploads = []
    for uf in files or []:
        data = await uf.read()
        if data:
            uploads.append({"name": uf.filename or "file", "data": data})

    user_files = [{"name": u["name"], "kind": _kind(u["name"])} for u in uploads]
    msg = db.add_message(chat_id, "user", prompt, files=user_files)
    # name the chat from the first prompt
    if chat["title"] in ("New chat", "", None):
        db.touch_chat(chat_id, title=prompt[:60])

    try:
        run_opts = RunOpts(**json.loads(opts or "{}")).model_dump()
    except Exception:  # noqa: BLE001
        run_opts = RunOpts().model_dump()

    # "continue" / "resume" → pick up the chat's last run from its SAVED state
    if runner.is_continue(prompt) and not uploads:
        rec = runner.resume_run(chat_id=chat_id, message_id=msg["id"])
        if rec is not None:
            return {"message": msg, "run": rec, "resumed": True}

    rec = runner.start_run(chat_id=chat_id, message_id=msg["id"],
                           prompt=prompt, files=uploads, opts=run_opts)
    return {"message": msg, "run": rec}


# --- pause a running run (state is saved; 'continue' resumes) ---------------
@app.post("/api/runs/{run_id}/pause")
def pause_run(run_id: str):
    ok = runner.request_pause(run_id)
    return {"ok": ok, "paused": ok}


# --- SSE live stream of a run ----------------------------------------------
@app.get("/api/runs/{run_id}/stream")
async def stream_run(run_id: str, request: Request):
    bus = runner.get_bus(run_id)
    if bus is None:
        # run already finished (or server restarted) → replay persisted transcript
        run = db.get_run(run_id)
        if not run:
            raise HTTPException(404, "run not found")

        async def replay():
            for r in run.get("transcript", []):
                for b in r.get("blocks", []):
                    yield _sse({"type": "block", "node": r["node"], **b})
            yield _sse({"type": "end", "status": run.get("status", "done")})
        return StreamingResponse(replay(), media_type="text/event-stream")

    async def gen():
        loop = asyncio.get_event_loop()
        ended = False
        try:
            while True:
                # client closed the tab / reloaded / switched chat → stop the run
                if await request.is_disconnected():
                    break
                try:
                    event = await loop.run_in_executor(None, bus.q.get, True, 1.0)
                except Exception:  # queue.Empty (timeout) → heartbeat
                    yield ": keep-alive\n\n"
                    continue
                yield _sse(event)
                if event.get("type") == "end":
                    ended = True
                    break
        finally:
            if not ended:
                # the viewer went away before the run finished → pause it (state is saved,
                # so 'continue' resumes). This is the ChatGPT-like "leaving stops it".
                runner.request_pause(run_id)
    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


# --- serve an artifact from a run's design dir ------------------------------
@app.get("/api/runs/{run_id}/file")
def run_file(run_id: str, path: str):
    run = db.get_run(run_id)
    if not run or not run.get("design_dir"):
        raise HTTPException(404, "run not found")
    base = Path(run["design_dir"]).resolve()
    target = (base / path).resolve()
    if base != target and base not in target.parents:
        raise HTTPException(400, "invalid path")
    if not target.is_file():
        raise HTTPException(404, "file not found")
    return FileResponse(str(target))


# --- helpers ----------------------------------------------------------------
def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def _kind(name: str) -> str:
    ext = Path(name).suffix.lower()
    if ext == ".pdf":
        return "pdf"
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        return "image"
    return "file"
