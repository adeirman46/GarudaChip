#!/usr/bin/env python3
"""
One-time migration: existing FAISS reference indexes  →  the pgvector knowledge store.

GarudaChip's runtime no longer uses FAISS — recall lives in Postgres (pgvector) +
MinIO. This script moves the *content* of the old prebuilt indexes into the store so
none of that knowledge is lost. It REUSES the vectors already in the FAISS index
(faiss reconstruct) — it does NOT re-embed 130k chunks — so it's fast.

It migrates:
  • data/verilog_datasets/index.{faiss,pkl}            (the big prebuilt corpus)
  • data/verilog_datasets/faiss_github_*/index.{faiss,pkl}  (per-query web caches)

This is OPTIONAL and LOCAL — the migrated rows are large, so they are NOT part of the
committed seed (see scripts and memory_store.export_seed for the small shipped seed).

Usage:
    uv run python scripts/migrate_faiss_to_pg.py            # migrate everything
    uv run python scripts/migrate_faiss_to_pg.py --limit 5000   # cap per index
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src" / "garuda_chip"))

DATA = REPO / "data" / "verilog_datasets"


def _load_faiss(dir_path: Path):
    """Return (faiss_index, docstore, index_to_id) from a LangChain FAISS folder."""
    import faiss
    index = faiss.read_index(str(dir_path / "index.faiss"))
    with open(dir_path / "index.pkl", "rb") as fh:
        payload = pickle.load(fh)
    # LangChain stores either (docstore, index_to_docstore_id) or a 3-tuple.
    docstore, index_to_id = payload[0], payload[1]
    return index, docstore, index_to_id


def _doc_text(docstore, doc_id):
    doc = docstore.search(doc_id)
    if doc is None or isinstance(doc, str):
        return None, {}
    return getattr(doc, "page_content", ""), getattr(doc, "metadata", {}) or {}


def migrate_index(mem, dir_path: Path, *, kind: str, design: str, limit: int) -> int:
    if not (dir_path / "index.faiss").exists():
        return 0
    index, docstore, index_to_id = _load_faiss(dir_path)
    n = min(index.ntotal, limit) if limit else index.ntotal
    print(f"  {dir_path.name}: {index.ntotal} vectors (migrating {n})…")
    done = 0
    for i in range(n):
        try:
            vec = index.reconstruct(i).tolist()           # reuse the stored embedding
        except Exception:
            continue
        doc_id = index_to_id.get(i)
        text, meta = _doc_text(docstore, doc_id)
        if not text:
            continue
        src = meta.get("source") or f"{kind}:{dir_path.name}"
        mem.remember(kind, text, design=design, source=str(src),
                     title=str(src)[:120], tags="migrated", embedding=vec)
        done += 1
        if done % 1000 == 0:
            print(f"    … {done}")
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="max rows per index (0 = all)")
    args = ap.parse_args()

    from memory_store import MemoryStore
    mem = MemoryStore()
    if not mem.enabled:
        print("Knowledge store is offline — run `docker compose up -d` first.")
        return
    total = 0
    total += migrate_index(mem, DATA, kind="dataset", design="verilog-corpus", limit=args.limit)
    for cache in sorted(DATA.glob("faiss_github_*")):
        if cache.is_dir():
            total += migrate_index(mem, cache, kind="reference",
                                   design=cache.name.replace("faiss_github_", ""),
                                   limit=args.limit)
    print(f"\nMigrated {total} items. Store stats: {mem.stats()}")


if __name__ == "__main__":
    main()
