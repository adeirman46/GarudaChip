#!/usr/bin/env python3
"""Prune the IP library — no junk.

The bar: an IP worth keeping can be hardened to a GDS *and* verified by a testbench. This
removes the rest (folder + Postgres rows + MinIO blobs).

  default       delete IPs that CANNOT make a GDS (status == harden_failed)
  --strict      delete every IP that is NOT (hardened AND testbench-passing) — leaves ONLY the
                Chip-Studio-ready set
  --dry-run     show what would be deleted, delete nothing

    uv run python scripts/prune_ips.py --dry-run
    uv run python scripts/prune_ips.py                 # drop the un-hardenable failures
    uv run python scripts/prune_ips.py --strict        # keep only GDS + TB-verified
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
from garuda_api import ip_store  # noqa: E402


def keep(m: dict, strict: bool) -> bool:
    if strict:                                   # only the pristine, tape-out-clean + verified set
        return m.get("tapeout_ready") and m.get("sim_status") == "pass"
    return bool(m.get("gds"))                     # retain anything that produced a GDS


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--strict", action="store_true", help="keep ONLY hardened + TB-verified IPs")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ips = ip_store.list_ips()
    doomed = [m for m in ips if not keep(m, args.strict)]
    kept = len(ips) - len(doomed)
    why = "not (tape-out-clean AND TB-verified)" if args.strict else "have no GDS"
    print(f"{len(ips)} IPs · removing {len(doomed)} that are {why} · keeping {kept}\n")
    for m in doomed:
        tag = f"{m['status']}/{m.get('sim_status','-')}"
        print(f"  {'would remove' if args.dry_run else 'remove'}  {m['id']:42s} [{m['category']:10s}] {tag}")
        if not args.dry_run:
            ip_store.delete_ip(m["id"])
    if not args.dry_run:
        left = ip_store.list_ips()
        ready = sum(1 for m in left if m.get("status") == "hardened" and m.get("sim_status") == "pass")
        print(f"\n✓ library now {len(left)} IPs · {ready} GDS + TB-verified (Chip-Studio-ready)")


if __name__ == "__main__":
    main()
