"""Headless run engine.

Drives GarudaChip's existing pipeline loop (`new_run` → `execute_step`/`advance` →
`finalize` from src/garuda_chip/app.py) in a background thread, with the streamlit shim
installed so nothing draws to a UI. As each `Recorder` block is produced it is:
  • pushed to a per-run event bus (the SSE stream the web UI reads), and
  • persisted to Postgres (`run.transcript`), so a reload re-hydrates the conversation.
After every step the design's artifacts are ingested into the knowledge store, so the
RLM's memory updates LIVE during a run, not only at the end.
"""
from __future__ import annotations

import queue
import subprocess
import sys
import threading
from pathlib import Path

from . import db, headless_st

# --- import the existing pipeline headlessly (once) -------------------------
_REPO = Path(__file__).resolve().parents[2]
_PIPELINE = None


def _pipeline():
    global _PIPELINE
    if _PIPELINE is None:
        headless_st.install()
        src = str(_REPO / "src" / "garuda_chip")
        if src not in sys.path:
            sys.path.insert(0, src)
        import app as pipeline  # noqa: E402  (the streamlit app, now headless)
        _emit_patch(pipeline)
        _patch_subprocess()
        _PIPELINE = pipeline
    return _PIPELINE


# Track every subprocess (iverilog / verilator / LibreLane / crawler) per run so Stop
# can KILL it immediately instead of waiting for it to finish.
_PROCS: dict[str, set] = {}


def _patch_subprocess() -> None:
    if getattr(subprocess.Popen, "_garuda_tracked", False):
        return
    orig_init = subprocess.Popen.__init__

    def _init(self, *a, **k):
        orig_init(self, *a, **k)
        rid = getattr(_local, "run_id", None)
        if rid:
            _PROCS.setdefault(rid, set()).add(self)
    _init._garuda_tracked = True
    subprocess.Popen.__init__ = _init


class RunPaused(Exception):
    """Raised mid-step to abort a long-running step promptly when pause is requested."""


# Per-thread "current event sink" so the patched Recorder can stream blocks live.
_local = threading.local()


def _emit_patch(pipeline) -> None:
    """Wrap Recorder._add so every block it records is also streamed to the active run.
    Guarded so it can never double-wrap (which would emit every block twice)."""
    if getattr(pipeline.Recorder._add, "_garuda_wrapped", False):
        return
    orig = pipeline.Recorder._add

    def _add(self, kind, payload):
        orig(self, kind, payload)
        sink = getattr(_local, "sink", None)
        if sink is None:
            return
        safe = _safe(payload)
        # rewrite image blocks to a design-relative path the /file endpoint can serve
        if kind == "image" and safe and isinstance(safe[0], str):
            dd = getattr(_local, "design_dir", None)
            if dd:
                import os
                try:
                    safe[0] = os.path.relpath(safe[0], dd)
                except Exception:  # noqa: BLE001
                    pass
        sink({"type": "block", "node": getattr(self, "node", ""),
              "kind": kind, "payload": safe})
        # responsive pause: if a pause was requested, abort THIS step now (right after
        # emitting the current block) instead of finishing a multi-minute deep-agent step
        cancel = getattr(_local, "cancel", None)
        if cancel is not None and cancel():
            raise RunPaused()
    _add._garuda_wrapped = True
    pipeline.Recorder._add = _add


def _run_step(pipeline, run_obj, node, feedback):
    """Run one step. RunPaused (pause) and any crash both HALT the run rather than
    advancing with broken state. Returns (record, paused, crashed)."""
    emoji, title, desc, fn, _ = pipeline.STEP_DEFS[node]
    ctx = run_obj["ctx"]
    if node in ("write", "simulate", "fix_design", "fix_testbench"):
        title = f"{title} (attempt {ctx.get('error_count', 0) + 1})"
    rec = pipeline.Recorder(emoji, title, desc, node, live=True)
    paused = crashed = False
    try:
        fn(rec, ctx, feedback)
    except RunPaused:
        paused = True
        _local.cancel = None              # stop re-raising while we record the note
        rec.caption("⏸ Paused mid-step — this step will re-run when you say continue.")
    except Exception as e:  # noqa: BLE001
        crashed = True
        rec.error(f"Step crashed: {e}\nSay **continue** to retry this step (it does NOT skip "
                  "ahead), or **replan**.")
    return {"node": node, "blocks": rec.blocks}, paused, crashed


def _safe(payload):
    """Make a Recorder block JSON-serializable (tuples → lists, drop unknowns)."""
    import json
    out = []
    for v in (payload if isinstance(payload, (list, tuple)) else [payload]):
        try:
            json.dumps(v)
            out.append(v)
        except (TypeError, ValueError):
            out.append(str(v)[:4000])
    return out


# --- event bus --------------------------------------------------------------
class RunBus:
    def __init__(self):
        self.q: "queue.Queue" = queue.Queue()
        self.done = False

    def push(self, event: dict):
        self.q.put(event)

    def finish(self, status: str):
        self.done = True
        self.q.put({"type": "end", "status": status})


_BUSES: dict[str, RunBus] = {}
_PAUSE: dict[str, "threading.Event"] = {}
_STEER: dict[str, list] = {}        # steering messages sent WHILE a run is working
# steps that actually consume feedback (so steering isn't eaten by a mechanical step)
_LLM_STEPS = {"plan", "web", "generate", "testbench", "fix_design", "fix_testbench"}


def _unproductive(node: str, ctx: dict) -> str:
    """Reason a step produced nothing (so we RETRY it instead of skipping ahead). Empty
    string = the step produced its expected artifact. web/retrieve are research, so they
    never gate the build."""
    if node == "generate":
        return "" if "endmodule" in (ctx.get("generation") or "") else "produced no RTL"
    if node == "decompose":
        return "" if (ctx.get("decomposed_files") or {}) else "produced no modules"
    if node == "testbench":
        tb = ctx.get("testbench_code") or {}
        return "" if any((v or "").strip() for v in tb.values()) else "produced no testbench"
    return ""


def get_bus(run_id: str) -> RunBus | None:
    return _BUSES.get(run_id)


def request_steer(run_id: str, message: str) -> bool:
    """Queue a steering message for a LIVE run; it's applied as feedback to the next step.
    Returns True if the run is live."""
    if not (message or "").strip() or run_id not in _PAUSE:
        return False
    _STEER.setdefault(run_id, []).append(message.strip())
    return True


def request_pause(run_id: str) -> bool:
    """Stop a run fast: KILL any live subprocess it spawned (iverilog/verilator/LibreLane/
    crawler) and set the pause flag so the loop stops at the next checkpoint. State is
    saved, so 'continue' resumes. Returns True if the run was live."""
    for p in list(_PROCS.get(run_id, ())):
        try:
            if p.poll() is None:
                p.kill()
        except Exception:  # noqa: BLE001
            pass
    ev = _PAUSE.get(run_id)
    if ev is not None:
        ev.set()
        return True
    return False


# --- a tiny uploaded-file wrapper new_run()/_save_uploads understand --------
class _Upload:
    def __init__(self, name: str, data: bytes):
        self.name = name
        self._d = data

    def getvalue(self) -> bytes:
        return self._d


# --- public entry -----------------------------------------------------------
def start_run(*, chat_id: str, message_id: str, prompt: str,
              files: list[dict] | None = None, opts: dict | None = None) -> dict:
    """Create a run row + bus, launch the pipeline thread, return the run record."""
    pipeline = _pipeline()
    opts = opts or {}
    uploads = [_Upload(f["name"], f["data"]) for f in (files or []) if f.get("data")]

    run_obj = pipeline.new_run(
        prompt,
        opts.get("use_web", True),
        opts.get("run_harden", False),
        opts.get("clock_port", "clk"),
        float(opts.get("clock_period", 24.0)),
        float(opts.get("die_um", 600.0)),
        int(opts.get("core_util", 25)),
        autonomous=True,
        deep_steps=opts.get("deep_steps", True),
        uploads=uploads,
    )
    design_dir = run_obj["ctx"]["design_dir"]
    rec = db.create_run(chat_id, message_id, prompt, design_dir)
    bus = RunBus()
    _BUSES[rec["id"]] = bus
    _PAUSE[rec["id"]] = threading.Event()

    t = threading.Thread(target=_execute, args=(rec["id"], run_obj, bus), daemon=True)
    t.start()
    return rec


def _execute(run_id: str, run_obj: dict, bus: RunBus) -> None:
    pipeline = _pipeline()
    _local.sink = bus.push
    _local.run_id = run_id           # so spawned subprocesses are tracked for Stop
    ctx = run_obj["ctx"]
    design_dir = ctx["design_dir"]
    _local.design_dir = design_dir
    # lets the streamed Recorder abort the current step the moment pause is requested
    _local.cancel = (lambda: pause_ev.is_set()) if (pause_ev := _PAUSE.get(run_id)) else None
    design = Path(design_dir).name
    pause_ev = _PAUSE.get(run_id)
    status = "done"
    paused = False
    crashed = False
    try:
        from memory_store import get_memory
        mem = get_memory()
        # uploaded files → knowledge store immediately (live)
        _ingest_uploads(mem, Path(design_dir), design)
        # on a resume that re-runs the interrupted step, drop its partial card in the UI
        if run_obj.pop("_trim", False):
            bus.push({"type": "trim"})

        guard = 0
        while run_obj["queue"] and guard < 200:
            guard += 1
            node = run_obj["queue"].pop(0)
            bus.push({"type": "step", "node": node})
            # apply steering ONLY on steps that can act on it (LLM steps) — so a steer
            # isn't silently eaten by a mechanical step (retrieve/decompose/write/…).
            if node in _LLM_STEPS:
                steers = _STEER.pop(run_id, None)
                if steers:
                    steer = " · ".join(steers)
                    run_obj["feedback"] = ((run_obj.get("feedback") or "") + " " + steer).strip()
                    bus.push({"type": "block", "node": node, "kind": "info",
                              "payload": [f"💬 Steering applied: {steer}"]})
            # _run_step lets a mid-step pause (RunPaused) abort promptly; a crash halts too
            record, step_paused, step_crashed = _run_step(
                pipeline, run_obj, node, run_obj.pop("feedback", ""))
            run_obj["transcript"].append(record)
            if step_paused or step_crashed:
                # DON'T advance with broken state — halt here so the user can `continue`
                # (re-run THIS step) or replan. (Fix for "a crash jumped to decompose".)
                paused = True
                crashed = crashed or step_crashed
                run_obj["queue"].insert(0, node)        # re-run THIS step on continue
                db.update_run(run_id, status="paused", ctx=ctx,
                              transcript=_records(run_obj["transcript"]),
                              queue=run_obj["queue"], pending=node)
                break
            # NEVER SKIP a step that produced nothing. Retry that same step (bounded),
            # then HALT — do NOT fall through to the next step with empty/garbage state.
            why = _unproductive(node, ctx)
            if why:
                key = f"_retry_{node}"
                ctx[key] = ctx.get(key, 0) + 1
                run_obj["queue"].insert(0, node)          # re-run THIS step, never skip
                if ctx[key] < 3:
                    bus.push({"type": "block", "node": node, "kind": "warning",
                              "payload": [f"↻ {node}: {why} — retrying (attempt {ctx[key] + 1}); "
                                          "NOT skipping to the next step."]})
                    db.update_run(run_id, status="running", ctx=ctx,
                                  transcript=_records(run_obj["transcript"]),
                                  queue=run_obj["queue"], pending=node)
                    continue
                paused = True
                crashed = True
                bus.push({"type": "block", "node": node, "kind": "error",
                          "payload": [f"{node}: {why} after 3 tries — refine the prompt or steer, "
                                      "then **continue**. (Did NOT skip ahead.)"]})
                db.update_run(run_id, status="paused", ctx=ctx,
                              transcript=_records(run_obj["transcript"]),
                              queue=run_obj["queue"], pending=node)
                break
            pipeline.advance(run_obj, node)
            run_obj["pending"] = node
            # persist FULL resumable state after each step
            db.update_run(run_id, status="running", ctx=ctx,
                          transcript=_records(run_obj["transcript"]),
                          queue=run_obj["queue"], pending=node)
            # add to the knowledge store only at meaningful events (insight / research /
            # problem→fix), not a blind per-step file dump
            _ingest_event(mem, bus, run_obj, node, Path(design_dir), design)
            # also honor a pause that arrived during a non-streaming (subprocess) step
            if pause_ev is not None and pause_ev.is_set():
                paused = True
                break
        if not paused:
            pipeline.finalize(run_obj)
            _ingest_final(mem, bus, run_obj, Path(design_dir), design)   # keep verified designs
    except Exception as exc:  # noqa: BLE001
        status = "error"
        bus.push({"type": "block", "node": "error", "kind": "error",
                  "payload": [f"Run crashed: {exc}"]})
    finally:
        _local.sink = None
        _local.cancel = None
        status = "paused" if paused else status
        run_obj["status"] = status
        db.update_run(run_id, status=status, ctx=ctx,
                      transcript=_records(run_obj["transcript"]),
                      queue=run_obj["queue"], pending=run_obj.get("pending"))
        chat_id = db.get_run(run_id)["chat_id"]
        if crashed:
            db.add_message(chat_id, "assistant",
                           "⚠️ A step crashed (e.g. a timeout). Say **continue** to retry that "
                           "same step — it will NOT skip ahead — or **replan**.")
        elif paused:
            db.add_message(chat_id, "assistant",
                           "⏸ Paused. Say **continue** to resume from here.")
        else:
            db.add_message(chat_id, "assistant", _summary(run_obj))
        bus.finish(status)
        _PAUSE.pop(run_id, None)
        _PROCS.pop(run_id, None)
        _STEER.pop(run_id, None)
        _local.run_id = None


def _records(transcript) -> list:
    """Normalize a transcript to JSON-safe records. Handles both live records (blocks
    are (kind, payload) tuples) and re-hydrated records (blocks are {kind,payload} dicts),
    so resuming a run from the DB and appending new steps works seamlessly."""
    out = []
    for r in transcript:
        norm = []
        for b in r.get("blocks", []):
            if isinstance(b, dict):
                norm.append({"kind": b.get("kind"), "payload": _safe(b.get("payload", []))})
            else:
                k, p = b
                norm.append({"kind": k, "payload": _safe(p)})
        out.append({"node": r.get("node"), "blocks": norm})
    return out


# words that mean "pick up where you left off"
_CONTINUE = ("continue", "please continue", "keep going", "resume", "carry on",
             "lanjut", "lanjutkan", "teruskan")


def is_continue(prompt: str) -> bool:
    p = (prompt or "").strip().lower()
    return any(p == w or p.startswith(w) for w in _CONTINUE)


def resume_run(*, chat_id: str, message_id: str) -> dict | None:
    """Rebuild the latest run for a chat from its SAVED state (ctx + queue + transcript +
    files on disk) and continue the pipeline from where it stopped. Returns the run rec,
    or None if there's nothing resumable."""
    pipeline = _pipeline()
    prev = db.latest_run_for_chat(chat_id)
    if not prev:
        return None
    ctx = prev.get("ctx") or {}
    queue = prev.get("queue") or []
    design_dir = prev.get("design_dir") or ctx.get("design_dir")
    if not design_dir or not Path(design_dir).exists():
        return None
    ctx["design_dir"] = design_dir
    # if the run had already drained its queue, decide a sensible continuation
    if not queue:
        if ctx.get("simulation_output"):
            queue = ["fix_design", "write", "simulate"]   # still broken → keep fixing
        elif ctx.get("run_harden") and not (ctx.get("harden") or {}).get("gds"):
            queue = ["harden"]
        else:
            return None                                    # nothing left to do

    transcript = prev.get("transcript") or []
    # If we're re-running the step that was interrupted (its partial card is the last one),
    # drop that partial card and tell the UI to remove it — so continue shows ONE clean card
    # for the step, not the aborted one + the redo.
    trim = bool(transcript and queue and transcript[-1].get("node") == queue[0])
    if trim:
        transcript = transcript[:-1]

    run_obj = {"ctx": ctx, "queue": list(queue), "transcript": transcript,
               "status": "running", "pending": prev.get("pending"), "autonomous": True,
               "_trim": trim}
    # re-read the RTL/TB the previous run wrote, so the pipeline uses the real disk state
    try:
        pipeline._sync_ctx_from_disk(ctx)
    except Exception:  # noqa: BLE001
        pass

    rec = db.create_run(chat_id, message_id, ctx.get("query", "continue"), design_dir)
    bus = RunBus()
    _BUSES[rec["id"]] = bus
    _PAUSE[rec["id"]] = threading.Event()
    threading.Thread(target=_execute, args=(rec["id"], run_obj, bus), daemon=True).start()
    return rec


def _summary(run_obj) -> str:
    ctx = run_obj["ctx"]
    top = ctx.get("top_module_name") or "design"
    if ctx.get("simulation_output"):
        return f"⚠️ `{top}` — RTL could not be fully verified ({ctx.get('error_count', 0)} attempts). Files saved under output/."
    gds = ctx.get("harden", {}).get("gds") if isinstance(ctx.get("harden"), dict) else None
    return (f"✅ `{top}` — RTL verified (simulation passed)."
            + (f" GDSII generated." if gds else ""))


# --- live knowledge ingest (only newly-written files) -----------------------
def _ingest_uploads(mem, design_dir: Path, design: str) -> None:
    if not getattr(mem, "enabled", False):
        return
    for p in (design_dir / "context" / "uploads").glob("*"):
        if p.is_file():
            try:
                mem.ingest_file(p, design=design, source=f"upload:{design}")
            except Exception:  # noqa: BLE001
                pass


def _emit_knowledge(bus, mem) -> None:
    """Tell the UI the knowledge store changed (so the badge updates on real events,
    not on a blind timer)."""
    try:
        bus.push({"type": "knowledge", "total": (mem.stats() or {}).get("total", 0)})
    except Exception:  # noqa: BLE001
        pass


def _ingest_event(mem, bus, run_obj, node: str, design_dir: Path, design: str) -> None:
    """Add to the knowledge store at MEANINGFUL moments only:
      • plan      → the architecture note (a design insight)
      • web       → the research digest (papers/code/github already stored by the pipeline)
      • simulate  → if it now PASSES after a prior error, remember the PROBLEM→FIX lesson
                    so the same mistake isn't repeated; track the error otherwise
      • lint      → track the structural error for the eventual fix lesson
    """
    if not getattr(mem, "enabled", False):
        return
    ctx = run_obj["ctx"]
    added = 0
    if node == "plan":
        f = design_dir / "design_notes.md"
        if f.exists() and mem.ingest_file(f, design=design, source=f"insight:{design}"):
            added += 1
    elif node == "web":
        f = design_dir / "context" / "research.md"
        if f.exists() and mem.ingest_file(f, design=design, source=f"research:{design}"):
            added += 1
    elif node == "lint":
        if ctx.get("lint_output"):
            run_obj["_last_error"] = ctx["lint_output"][:1500]
    elif node == "simulate":
        if ctx.get("simulation_output"):                 # still failing → remember the error
            run_obj["_last_error"] = ctx["simulation_output"][:1500]
        elif run_obj.get("_last_error"):                 # PASS after a problem → store the fix
            mem.remember(
                "fix",
                f"PROBLEM:\n{run_obj['_last_error']}\n\nRESOLVED in design '{design}' — the "
                f"corrected, simulation-passing RTL is stored as code for '{design}'.",
                design=design, source=f"fix:{design}",
                title=f"fix: {run_obj['_last_error'][:90]}", tags="fix")
            run_obj["_last_error"] = ""
            added += 1
    if added:
        _emit_knowledge(bus, mem)


def _ingest_final(mem, bus, run_obj, design_dir: Path, design: str) -> None:
    """On a VERIFIED finish, store the working design (RTL = reusable code knowledge +
    a one-line 'design' summary). Only when simulation passed — we keep good designs,
    not broken ones."""
    if not getattr(mem, "enabled", False):
        return
    ctx = run_obj["ctx"]
    if ctx.get("simulation_output"):
        return
    added = 0
    rtl = list((design_dir / "rtl").glob("*.v")) + list((design_dir / "rtl").glob("*.vh"))
    for p in rtl:
        if mem.ingest_file(p, design=design, source=f"verified:{design}"):
            added += 1
    mem.remember(
        "design",
        f"VERIFIED design: {ctx.get('query', '')}\nTop module: {ctx.get('top_module_name')}\n"
        f"Modules: " + ", ".join(p.name for p in rtl),
        design=design, source=f"verified:{design}",
        title=(ctx.get("query") or design)[:120], tags="design verified")
    if added:
        _emit_knowledge(bus, mem)
