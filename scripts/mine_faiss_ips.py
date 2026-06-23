#!/usr/bin/env python3
"""Mine the FAISS verilog dataset for reusable IP modules (memory, FIFO, UART, ALU, …).

"Look at my index.pkl/faiss data — maybe there are IPs to be found, like memory etc." The
big ``data/verilog_datasets/index.pkl`` is a 130k-chunk ``instruction → output`` Verilog
dataset; each module's code is chunked across several docs that share a ``metadata.row``.
This:

  1. groups the chunks by row and reconstructs each ``module … endmodule``,
  2. keeps only rows whose description matches a target IP category (memory/fifo/ram, uart,
     spi, i2c, gpio, timer, alu, multiplier, fft/fir, …),
  3. compile-checks each candidate with iverilog (``-i``) and de-duplicates,
  4. registers the best few per category as IPs in ``data/ip_library/`` (status 'sim' if it
     compiled, else 'rtl'), so they show up in the IP tab and feed Chip Studio once hardened.

The ``faiss_github_*`` caches are scraped HTML (web chrome), not clean code, so they're
skipped for mining — use them as research anchors instead.

    uv run python scripts/mine_faiss_ips.py                       # default: a few per category
    uv run python scripts/mine_faiss_ips.py --category memory --limit 8
    uv run python scripts/mine_faiss_ips.py --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import pickle
import re
import subprocess
import sys
import tempfile
from collections import OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
sys.path.insert(0, str(REPO / "src" / "garuda_chip"))
from garuda_api import ip_store  # noqa: E402

DATA = REPO / "data" / "verilog_datasets"

CATS = {
    "accelerator": r"\b(cnn|conv\w*|systolic|gemm|matmul|mac.?array|pe.?array|neural|dnn|mlp"
                   r"|tensor|pooling|relu|softmax|sigmoid|activation|accelerator|npu|tpu"
                   r"|inference|winograd|im2col|dot.?product|vector.?engine)\b",
    "memory": r"\b(fifo|ram|rom|register file|regfile|sram|cache|memory|dual.?port|scratchpad)\b",
    "peripheral": r"\b(uart|spi|i2c|gpio|timer|pwm|interrupt controller|watchdog)\b",
    "bus": r"\b(axi|ahb|apb|wishbone|crossbar|arbiter|interconnect|bridge)\b",
    "dsp": r"\b(alu|multiplier|mac|fir|iir|fft|cordic|adder|accumulator|filter)\b",
    "crypto": r"\b(sha|aes|md5|crc|lfsr|hash|cipher)\b",
    "core": r"\b(riscv|cpu|processor|alu control|program counter|decoder)\b",
}


def _load(d: Path):
    with open(d / "index.pkl", "rb") as f:
        p = pickle.load(f)
    return p[0], p[1]   # docstore, index_to_id


def _extract_module(text: str) -> tuple[str, str] | None:
    """First complete `module NAME … endmodule` in a reconstructed row, stripped of the
    dataset's ``instruction:/output:`` framing."""
    text = re.sub(r"^\s*instruction:.*?(?:\n|$)", "", text, flags=re.S | re.I)
    text = re.sub(r"^\s*output:\s*", "", text, flags=re.I)
    m = re.search(r"\bmodule\s+([A-Za-z_]\w*)\b.*?\bendmodule\b", text, flags=re.S)
    if not m:
        return None
    return m.group(1), m.group(0).strip() + "\n"


def _compiles(code: str) -> bool:
    tmp = Path(tempfile.mkdtemp(prefix="mine_"))
    try:
        f = tmp / "m.v"
        f.write_text(code)
        p = subprocess.run(["iverilog", "-g2012", "-t", "null", "-i", str(f)],
                           capture_output=True, text=True, timeout=20)
        return p.returncode == 0
    except Exception:  # noqa: BLE001
        return False
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


# importance weight per category — AI accelerators + cores rank highest (most valuable IP)
_CAT_WEIGHT = {"accelerator": 3.0, "core": 2.5, "memory": 2.0, "bus": 2.0, "peripheral": 2.0,
               "crypto": 1.5, "dsp": 1.5}

# Vendor / part-specific blocks the dataset is full of — NOT reusable IP (Xilinx MIG DDR,
# Analog Devices AD9xxx RF, Altera/Intel PHYs, FPGA hard-IP). Reject by name or description.
_REJECT = re.compile(
    r"mig.?7series|\bad9\d|\badi_|altera|stratix|virtex|kintex|zynq|artix|spartan|cyclone"
    r"|arria|\bmax ?10|xilinx|ultrascale|\bpdp1|lpddr|\bddr[234]|\bgt[xhy]\b|pcie_?7|hard.?ip"
    r"|_v\d+_\d+_|cpuwr|cpurd|oh_|\bsm_|tlu_|jbi_|niu_|_pcs_|chipscope|ibufds|obufds", re.I)

# Recognizable, general-purpose IP terms — boost these (the user wants useful, nameable IPs).
_GENERIC = re.compile(
    r"\b(fifo|uart|spi|i2c|axi|ahb|apb|wishbone|alu|\bram\b|rom|fft|fir|iir|sha\d*|aes|crc"
    r"|lfsr|gpio|timer|pwm|register file|regfile|arbiter|crossbar|\bmux\b|decoder|encoder"
    r"|counter|multiplier|divider|accumulator|shift register|barrel shifter|priority"
    r"|round robin|dual.?port|spram|dpram|watchdog|debounce|pll|clock divider)\b", re.I)

# words to drop when synthesizing a friendly display name from the description
_STOP = {"module", "code", "verilog", "the", "a", "an", "with", "for", "of", "and", "to", "is",
         "this", "that", "following", "description", "implements", "interface", "functionality",
         "using", "based", "design", "it", "in", "on", "which", "contains", "handles", "simple",
         "generate", "defines", "data", "signals", "logic", "various", "multiple", "system"}
# tokens to render upper-case in a friendly name
_ACR = {"fifo", "spi", "uart", "axi", "ahb", "apb", "alu", "ram", "rom", "fft", "fir", "iir",
        "sha", "aes", "i2c", "gpio", "dma", "ecc", "cpu", "adc", "dac", "lvds", "crc", "lfsr",
        "pwm", "jtag", "mii", "usb", "pll", "fsm"}


def _cap(w: str) -> str:
    return w.upper() if w.lower() in _ACR else (w if w[:1].isupper() else w.capitalize())


def _friendly(desc: str, top: str) -> str:
    """A short, human-readable IP name from the dataset description (NOT the cryptic vendor
    module id). 'FIFO module with simple read and write…' → 'FIFO Read Write'."""
    first = re.split(r"[.;\n]", desc)[0]
    words = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]*", first) if w.lower() not in _STOP]
    if len(words) < 2:
        words = [t for t in re.split(r"[_\d]+", top) if t and t.lower() not in _STOP]
    words = words[:4] or [top]
    return " ".join(_cap(w) for w in words)[:42]


def _score(name: str, code: str, desc: str, cat: str) -> float:
    """Cheap importance pre-score (no compile): RECOGNIZABLE, substantial, parameterized,
    valuable-category modules rank highest. Used to pick which candidates to compile-check."""
    lines = code.count("\n")
    s = _CAT_WEIGHT.get(cat, 0.5)
    s += 2 if 15 <= lines <= 600 else (0.5 if lines > 600 else 0)
    s += min(code.count(";") / 20, 2)                       # logic substance
    if re.search(r"\bparameter\b", code):
        s += 1.5                                            # reusable / configurable
    s += min(len(re.findall(r"\b(?:input|output|inout)\b", code)) / 4, 2)  # real interface
    if re.match(r"^[a-z][a-z0-9_]{2,40}$", name, re.I):
        s += 1                                              # a real identifier, not a hash
    if _GENERIC.search(f"{name} {desc}"):
        s += 3                                              # a recognizable general-purpose IP
    s += min(len(desc) / 80, 1)                             # descriptive
    return s


def mine(categories: list[str], top: int, per_cat: int, dry_run: bool,
         allow_noncompile: bool) -> None:
    if not (DATA / "index.pkl").exists():
        print(f"no dataset at {DATA}/index.pkl"); return
    print(f"loading {DATA}/index.pkl …")
    ds, idx = _load(DATA)
    # group chunk texts by row, in docstore order (chunks of one module are consecutive)
    rows: "OrderedDict[str, dict]" = OrderedDict()
    for i in sorted(idx):
        doc = ds.search(idx[i])
        if doc is None or isinstance(doc, str):
            continue
        meta = getattr(doc, "metadata", {}) or {}
        key = f"{meta.get('source','')}|{meta.get('row','')}"
        rows.setdefault(key, {"src": meta.get("source", ""), "parts": []})
        rows[key]["parts"].append(getattr(doc, "page_content", ""))
    print(f"  {len(rows)} unique modules; extracting + scoring candidates in {categories} …")

    cands: list[dict] = []
    seen_hash: set = set()
    seen_name: set = set()
    for row in rows.values():
        desc_full = row["src"] or ""
        cat = next((c for c in categories if re.search(CATS[c], desc_full, re.I)), None)
        if not cat:
            continue
        ex = _extract_module("\n".join(row["parts"]))
        if not ex:
            continue
        name, code = ex
        if len(code) < 120:
            continue
        # drop vendor / part-specific junk (mig_7series, axi_ad9361, altera_*, …) — not reusable IP
        if _REJECT.search(name) or _REJECT.search(desc_full):
            continue
        h = hashlib.sha1(re.sub(r"\s+", "", code).encode()).hexdigest()[:16]
        if h in seen_hash:
            continue
        seen_hash.add(h)
        desc = desc_full.split("description:")[-1].strip()[:90]
        display = _friendly(desc, name)                     # human-readable IP name
        key = display.lower()
        if key in seen_name:                                # one IP per friendly name
            continue
        seen_name.add(key)
        cands.append({"name": name, "display": display, "code": code, "desc": desc, "cat": cat,
                      "score": _score(name, code, desc, cat)})
    cands.sort(key=lambda c: c["score"], reverse=True)
    print(f"  {len(cands)} unique candidate module(s). Compile-checking best first "
          f"(dropping any .v that errors)…")

    # Walk best-first; keep only modules that COMPILE (the user: don't take error .v into
    # account). Bound compile calls — stop once we have `top` keepers (and `per_cat` each).
    kept: list[dict] = []
    per_count: dict[str, int] = {c: 0 for c in categories}
    checked = 0
    for c in cands:
        if len(kept) >= top:
            break
        if per_cat and per_count[c["cat"]] >= per_cat:
            continue
        checked += 1
        ok = allow_noncompile or _compiles(c["code"])
        if not ok:
            continue
        c["compiles"] = True
        kept.append(c)
        per_count[c["cat"]] += 1
        if checked > top * 6 and len(kept) >= max(1, top // 2):
            break                                          # stop burning compile time

    total = 0
    for c in kept:
        print(f"   • {c['cat']:11s} {c['display']:26s} score={c['score']:.1f}  ({c['name']})")
        if dry_run:
            total += 1
            continue
        ip_id = ip_store.slug(f"{c['cat']}_{c['display']}")
        try:
            # friendly display name on the card; the real module stays the file/top name
            mf = ip_store.create_ip(c["display"], {f"{c['name']}.v": c["code"]}, category=c["cat"],
                                    source="faiss-dataset", subtitle=c["desc"], ip_id=ip_id)
            ip_store.update_ip(mf["id"], status="sim")     # compiled clean → simulation-ready
            ip_store.ingest_ip(mf["id"])                   # → Postgres row + MinIO blobs
            total += 1
        except Exception as e:  # noqa: BLE001
            print(f"     ⚠️  register failed: {e}")
    verb = "would register" if dry_run else "registered + saved to Postgres/MinIO"
    by_cat = {}
    for c in kept:
        by_cat[c["cat"]] = by_cat.get(c["cat"], 0) + 1
    print(f"\n═══ {verb} {total} mined IP(s): " + ", ".join(f"{k}×{v}" for k, v in by_cat.items()))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--category", nargs="*", choices=list(CATS), help="categories to mine")
    ap.add_argument("--top", type=int, default=50, help="total IPs to keep (importance-ranked)")
    ap.add_argument("--per-category", type=int, default=0, help="cap per category (0 = no cap)")
    ap.add_argument("--allow-noncompile", action="store_true",
                    help="keep modules even if they don't compile (default: drop error .v)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    mine(args.category or list(CATS), args.top, args.per_category, args.dry_run,
         args.allow_noncompile)


if __name__ == "__main__":
    main()
