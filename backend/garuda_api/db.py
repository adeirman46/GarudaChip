"""Chat + run persistence (Postgres) — so a prompt and its run state survive reloads
('not vanished'). Lives in the same `garudachip` database as the knowledge store, in
its own tables: `chat`, `message`, `run`. Defensive: if Postgres is down, the API still
serves with an in-memory fallback so the UI works for a single session.

The full run transcript is stored as JSONB on the `run` row, so reopening a chat
re-hydrates the entire conversation + agent transcript exactly as it was.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

_DB_URL = os.getenv("GARUDA_DATABASE_URL",
                    "postgresql+psycopg://garuda:garuda@localhost:5433/garudachip")

_engine = None
_ready = False


def _now():
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def init() -> bool:
    """Create the engine + tables. Returns True if Postgres-backed, False if it fell
    back to in-memory (DB unavailable)."""
    global _engine, _ready
    if _ready:
        return True
    try:
        from sqlalchemy import (Column, DateTime, MetaData, String, Table, Text,
                                create_engine)
        from sqlalchemy.dialects.postgresql import JSONB
        eng = create_engine(_DB_URL, pool_pre_ping=True, future=True)
        md = MetaData()
        Table("chat", md,
              Column("id", String, primary_key=True),
              Column("title", String),
              Column("created_at", DateTime(timezone=True)),
              Column("updated_at", DateTime(timezone=True)))
        Table("message", md,
              Column("id", String, primary_key=True),
              Column("chat_id", String, index=True),
              Column("role", String),                 # user | assistant | system
              Column("content", Text),
              Column("files", JSONB),                  # [{name, object_key, kind}]
              Column("created_at", DateTime(timezone=True)))
        Table("run", md,
              Column("id", String, primary_key=True),
              Column("chat_id", String, index=True),
              Column("message_id", String),
              Column("status", String),                # running | paused | done | error
              Column("query", Text),
              Column("design_dir", String),
              Column("ctx", JSONB),
              Column("transcript", JSONB),             # full step-by-step transcript
              Column("queue", JSONB),                  # remaining steps (for resume)
              Column("pending", String),               # last-run step (for resume)
              Column("created_at", DateTime(timezone=True)),
              Column("updated_at", DateTime(timezone=True)))
        md.create_all(eng)
        # add resume columns to a pre-existing run table (create_all won't ALTER)
        from sqlalchemy import text as sqltext
        with eng.begin() as conn:
            conn.execute(sqltext("ALTER TABLE run ADD COLUMN IF NOT EXISTS queue JSONB"))
            conn.execute(sqltext("ALTER TABLE run ADD COLUMN IF NOT EXISTS pending VARCHAR"))
        _engine, _ready = eng, True
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[db] Postgres unavailable ({exc}); using in-memory store.")
        _engine, _ready = None, False
        return False


# --- in-memory fallback (single-process) -----------------------------------
_mem = {"chat": {}, "message": [], "run": {}}


def _q(sql, **params):
    from sqlalchemy import text as sqltext
    with _engine.begin() as conn:
        return conn.execute(sqltext(sql), params)


# --- chats ------------------------------------------------------------------
def create_chat(title: str) -> dict:
    cid = new_id("chat")
    row = {"id": cid, "title": title[:200] or "New chat",
           "created_at": _now(), "updated_at": _now()}
    if _engine:
        _q("INSERT INTO chat (id,title,created_at,updated_at) "
           "VALUES (:id,:title,:created_at,:updated_at)", **row)
    else:
        _mem["chat"][cid] = row
    return _iso(row)


def list_chats() -> list[dict]:
    if _engine:
        rows = _q("SELECT id,title,created_at,updated_at FROM chat "
                  "ORDER BY updated_at DESC NULLS LAST").mappings().all()
        return [_iso(dict(r)) for r in rows]
    return [_iso(c) for c in sorted(_mem["chat"].values(),
                                    key=lambda c: c["updated_at"], reverse=True)]


def get_chat(chat_id: str) -> dict | None:
    if _engine:
        r = _q("SELECT id,title,created_at,updated_at FROM chat WHERE id=:id",
               id=chat_id).mappings().first()
        return _iso(dict(r)) if r else None
    return _iso(_mem["chat"].get(chat_id)) if chat_id in _mem["chat"] else None


def touch_chat(chat_id: str, title: str | None = None) -> None:
    if _engine:
        if title:
            _q("UPDATE chat SET updated_at=:t, title=:ti WHERE id=:id",
               t=_now(), ti=title[:200], id=chat_id)
        else:
            _q("UPDATE chat SET updated_at=:t WHERE id=:id", t=_now(), id=chat_id)
    elif chat_id in _mem["chat"]:
        _mem["chat"][chat_id]["updated_at"] = _now()
        if title:
            _mem["chat"][chat_id]["title"] = title[:200]


def delete_chat(chat_id: str) -> None:
    """Delete a chat AND most of what it produced: its messages/runs (Postgres), the
    design's knowledge rows + MinIO blobs (object storage), and its on-disk workspace.
    The learned error→fix LESSONS (kind='fix') are PRESERVED in the knowledge store —
    they're cross-design lessons, not chat data, so deleting the chat must not lose them."""
    designs, dirs = _chat_designs(chat_id)
    if _engine:
        _q("DELETE FROM run WHERE chat_id=:id", id=chat_id)
        _q("DELETE FROM message WHERE chat_id=:id", id=chat_id)
        _q("DELETE FROM chat WHERE id=:id", id=chat_id)
    else:
        _mem["chat"].pop(chat_id, None)
        _mem["message"] = [m for m in _mem["message"] if m["chat_id"] != chat_id]
        _mem["run"] = {k: v for k, v in _mem["run"].items() if v["chat_id"] != chat_id}
    _cleanup_designs(designs, dirs)


def _chat_designs(chat_id: str):
    """Collect the (design-name, design-dir) of every run in this chat."""
    from pathlib import Path
    designs, dirs = set(), set()
    if _engine:
        rows = _q("SELECT design_dir FROM run WHERE chat_id=:id", id=chat_id).mappings().all()
    else:
        rows = [r for r in _mem["run"].values() if r["chat_id"] == chat_id]
    for r in rows:
        dd = r.get("design_dir")
        if dd:
            dirs.add(dd)
            designs.add(Path(dd).name)
    return designs, dirs


def _cleanup_designs(designs: set, dirs: set) -> None:
    """Remove each design's knowledge rows + MinIO blobs, and its output/ workspace."""
    if designs:
        try:
            import sys
            from pathlib import Path
            src = str(Path(__file__).resolve().parents[2] / "src" / "garuda_chip")
            if src not in sys.path:
                sys.path.insert(0, src)
            from memory_store import get_memory
            mem = get_memory()
            for d in designs:
                # delete this design's rows + blobs, but KEEP kind='fix' lessons — those are
                # durable, cross-design knowledge that must survive the chat being deleted.
                mem.delete_where(design=d, exclude_kinds=["fix"])
        except Exception as exc:  # noqa: BLE001
            print(f"[db] knowledge cleanup skipped: {exc}")
    import shutil
    from pathlib import Path
    for dd in dirs:
        try:
            p = Path(dd).resolve()
            if "output" in p.parts and p.exists():    # only ever under output/
                shutil.rmtree(p)
        except Exception:  # noqa: BLE001
            pass


# --- messages ---------------------------------------------------------------
def add_message(chat_id: str, role: str, content: str, files: list | None = None) -> dict:
    mid = new_id("msg")
    row = {"id": mid, "chat_id": chat_id, "role": role, "content": content or "",
           "files": files or [], "created_at": _now()}
    if _engine:
        import json
        _q("INSERT INTO message (id,chat_id,role,content,files,created_at) "
           "VALUES (:id,:chat_id,:role,:content,CAST(:files AS JSONB),:created_at)",
           **{**row, "files": json.dumps(row["files"])})
    else:
        _mem["message"].append(row)
    touch_chat(chat_id)
    return _iso(row)


def get_messages(chat_id: str) -> list[dict]:
    if _engine:
        rows = _q("SELECT id,chat_id,role,content,files,created_at FROM message "
                  "WHERE chat_id=:id ORDER BY created_at", id=chat_id).mappings().all()
        return [_iso(dict(r)) for r in rows]
    return [_iso(m) for m in _mem["message"] if m["chat_id"] == chat_id]


# --- runs (persist live ctx + transcript) -----------------------------------
def create_run(chat_id: str, message_id: str, query: str, design_dir: str) -> dict:
    rid = new_id("run")
    row = {"id": rid, "chat_id": chat_id, "message_id": message_id, "status": "running",
           "query": query, "design_dir": design_dir, "ctx": {}, "transcript": [],
           "created_at": _now(), "updated_at": _now()}
    if _engine:
        import json
        _q("INSERT INTO run (id,chat_id,message_id,status,query,design_dir,ctx,transcript,"
           "created_at,updated_at) VALUES (:id,:chat_id,:message_id,:status,:query,"
           ":design_dir,CAST(:ctx AS JSONB),CAST(:transcript AS JSONB),:created_at,:updated_at)",
           **{**row, "ctx": json.dumps({}), "transcript": json.dumps([])})
    else:
        _mem["run"][rid] = row
    return _iso(row)


def update_run(run_id: str, *, status=None, ctx=None, transcript=None,
               queue=None, pending=None) -> None:
    if _engine:
        import json
        sets, params = ["updated_at=:t"], {"t": _now(), "id": run_id}
        if status is not None:
            sets.append("status=:s")
            params["s"] = status
        if ctx is not None:
            sets.append("ctx=CAST(:c AS JSONB)")
            params["c"] = json.dumps(_jsonable(ctx))
        if transcript is not None:
            sets.append("transcript=CAST(:tr AS JSONB)")
            params["tr"] = json.dumps(_jsonable(transcript))
        if queue is not None:
            sets.append("queue=CAST(:q AS JSONB)")
            params["q"] = json.dumps(list(queue))
        if pending is not None:
            sets.append("pending=:p")
            params["p"] = pending
        _q(f"UPDATE run SET {', '.join(sets)} WHERE id=:id", **params)
    elif run_id in _mem["run"]:
        r = _mem["run"][run_id]
        if status is not None:
            r["status"] = status
        if ctx is not None:
            r["ctx"] = _jsonable(ctx)
        if transcript is not None:
            r["transcript"] = _jsonable(transcript)
        if queue is not None:
            r["queue"] = list(queue)
        if pending is not None:
            r["pending"] = pending
        r["updated_at"] = _now()


def get_run(run_id: str) -> dict | None:
    if _engine:
        r = _q("SELECT * FROM run WHERE id=:id", id=run_id).mappings().first()
        return _iso(dict(r)) if r else None
    return _iso(_mem["run"].get(run_id)) if run_id in _mem["run"] else None


def runs_for_chat(chat_id: str) -> list[dict]:
    """All runs of a chat (id, message_id, status, transcript) in order — so the UI can
    show each user turn's own assistant response (proper chat alternation)."""
    if _engine:
        rows = _q("SELECT id, message_id, status, transcript FROM run WHERE chat_id=:id "
                  "ORDER BY created_at", id=chat_id).mappings().all()
        return [_iso(dict(r)) for r in rows]
    return [_iso(r) for r in sorted((x for x in _mem["run"].values() if x["chat_id"] == chat_id),
                                    key=lambda r: r["created_at"])]


def latest_run_for_chat(chat_id: str) -> dict | None:
    if _engine:
        r = _q("SELECT * FROM run WHERE chat_id=:id ORDER BY created_at DESC LIMIT 1",
               id=chat_id).mappings().first()
        return _iso(dict(r)) if r else None
    runs = [r for r in _mem["run"].values() if r["chat_id"] == chat_id]
    return _iso(sorted(runs, key=lambda r: r["created_at"])[-1]) if runs else None


# --- helpers ----------------------------------------------------------------
def _iso(row: dict) -> dict:
    out = dict(row)
    for k in ("created_at", "updated_at"):
        v = out.get(k)
        if isinstance(v, datetime):
            out[k] = v.isoformat()
    return out


def _jsonable(obj):
    """Drop non-serializable values (e.g. langchain Document objects in ctx)."""
    import json
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        if isinstance(obj, dict):
            return {k: _jsonable(v) for k, v in obj.items() if _safe(v)}
        if isinstance(obj, list):
            return [_jsonable(v) for v in obj if _safe(v)]
        return str(obj)[:2000]


def _safe(v) -> bool:
    import json
    try:
        json.dumps(v)
        return True
    except (TypeError, ValueError):
        return isinstance(v, (dict, list))
