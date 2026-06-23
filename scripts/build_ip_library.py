#!/usr/bin/env python3
"""Build the IP library: register local RTL as IPs and (on request) harden them to GDS.

Three jobs, all triggerable (LibreLane is slow, so hardening never runs automatically):

  --register   import every design under examples/verilog_designs/ (and data/ip_sources/)
               as an IP (status 'rtl', or 'sim' if it compiles). Groups each design folder's
               RTL, drops testbenches.
  --harden     run LibreLane (gf180) on the named IPs (or all un-hardened ones) → attach the
               GDS + metrics + render, status 'hardened'. This is what makes an IP usable in
               Chip Studio (only hardened macros can be placed on the padframe).
  --ingest     mirror every IP into the durable knowledge store (Postgres + MinIO).

    uv run python scripts/build_ip_library.py --register --ingest
    uv run python scripts/build_ip_library.py --harden serv picorv32     # specific IPs
    uv run python scripts/build_ip_library.py --harden --max 5           # first 5 un-hardened
    uv run python scripts/build_ip_library.py --list
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "src" / "garuda_chip"))
from garuda_api import ip_store, harden  # noqa: E402

CORPUS = [REPO / "examples" / "verilog_designs"]
RTL_EXT = (".v", ".sv", ".vh", ".svh")


def _design_folders() -> list[Path]:
    out = []
    for root in CORPUS:
        if not root.is_dir():
            continue
        for d in sorted(root.iterdir()):
            if d.is_dir() and any(d.glob("*.v")) or any(d.glob("*.sv")):
                out.append(d)
    return out


def register_corpus() -> int:
    n = 0
    for d in _design_folders():
        files = {p.name: p.read_text(errors="replace") for p in d.glob("*")
                 if p.suffix.lower() in RTL_EXT
                 and not re.search(r"(_tb|tb_|test|bench)", p.name, re.I)}
        if not files:
            continue
        name = re.sub(r"^generated_", "", d.name)
        ip_id = ip_store.slug(name)
        if ip_store.get_ip(ip_id):
            continue                                  # already registered
        try:
            mf = ip_store.create_ip(name, files, source=f"corpus:{d.name}", ip_id=ip_id)
            print(f"  + {mf['id']:26s} {mf['category']:11s} top={mf['top']} "
                  f"({len(files)} files, {len(mf['ports'])} ports)")
            n += 1
        except Exception as e:  # noqa: BLE001
            print(f"  ⚠️  {name}: {e}")
    return n


def harden_ips(names: list[str], max_n: int, util: int, period: float) -> None:
    if not harden.available():
        print("librelane not on PATH — cannot harden."); return
    # all un-hardened, SMALLEST FIRST (quick wins land GDS sooner; big/partial cores last)
    pending = sorted((m for m in ip_store.list_ips() if m.get("status") != "hardened"),
                     key=lambda m: m.get("lines", 9999))
    targets = names or [m["id"] for m in pending][:max_n or None]
    print(f"hardening {len(targets)} IP(s): {', '.join(targets)}", flush=True)
    import shutil
    for ip_id in targets:
        # ROBUST: a crash on ONE IP must never kill the whole batch (that's why the previous
        # run stopped before the crypto/cores/accelerators at the end of the queue).
        work = None
        try:
            mf = ip_store.get_ip(ip_id)
            if not mf:
                print(f"  ⚠️  {ip_id}: not found", flush=True); continue
            print(f"\n── harden {ip_id} (top={mf['top']}) …", flush=True)
            rtl = ip_store.ip_dir(ip_id) / "rtl"
            work = Path(tempfile.mkdtemp(prefix=f"harden_{ip_id}_"))
            res = harden.harden_rtl(rtl, work, ip_id, top=mf["top"],
                                    clock_period=period, core_util=util,
                                    on_log=lambda ln: print("   " + ln, flush=True) if re.search(
                                        r"error|Step|Finished|Starting|GDS", ln, re.I) else None)
            if res["ok"]:
                ip_store.attach_harden(ip_id, gds_src=res["gds"], png_src=res["png"],
                                       metrics=res["metrics"], signoff=res.get("signoff"),
                                       tapeout_ready=res.get("tapeout_ready", False), status="hardened")
                ip_store.ingest_ip(ip_id)
                if res.get("tapeout_ready"):
                    print(f"   ✅ TAPE-OUT READY → GDS sign-off clean; metrics={res['metrics']}", flush=True)
                else:
                    fails = (res.get("signoff") or {}).get("failed", [])
                    print(f"   ⚠️  GDS produced but NOT sign-off clean (violations: {', '.join(fails)})", flush=True)
            else:
                ip_store.update_ip(ip_id, status="harden_failed")
                print(f"   ✗ harden failed (rc={res['rc']}). tail:\n   "
                      + "\n   ".join(res["log"].splitlines()[-8:]), flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"   ✗ {ip_id}: harden crashed ({e}) — skipping, batch continues", flush=True)
            try:
                ip_store.update_ip(ip_id, status="harden_failed")
            except Exception:  # noqa: BLE001
                pass
        if work:
            shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--register", action="store_true", help="import the corpus as IPs")
    ap.add_argument("--harden", nargs="*", metavar="IP", help="harden these IPs (or all un-hardened)")
    ap.add_argument("--ingest", action="store_true", help="mirror all IPs into the knowledge store")
    ap.add_argument("--list", action="store_true", help="list the IP library")
    ap.add_argument("--max", type=int, default=0, help="cap how many to harden")
    ap.add_argument("--util", type=int, default=35, help="FP_CORE_UTIL for hardening")
    ap.add_argument("--period", type=float, default=10.0, help="clock period (ns) for hardening")
    args = ap.parse_args()

    if args.register:
        print("registering corpus IPs …")
        print(f"  registered {register_corpus()} new IP(s).")
    if args.harden is not None:
        harden_ips(args.harden, args.max, args.util, args.period)
    if args.ingest:
        n = sum(ip_store.ingest_ip(m["id"]) for m in ip_store.list_ips())
        print(f"ingested IP rows into the knowledge store ({n} rows).")
    if args.list or not any([args.register, args.harden is not None, args.ingest]):
        ips = ip_store.list_ips()
        print(f"\nIP library — {len(ips)} IP(s):")
        for m in ips:
            print(f"  {m['status']:14s} {m['category']:11s} {m['id']:26s} "
                  f"top={m['top']:18s} ports={len(m.get('ports', []))}"
                  + ("  [GDS]" if m.get("gds") else ""))


if __name__ == "__main__":
    main()
