#!/usr/bin/env python3
"""Clone open-source HDL IP repos, KEEP only the synthesizable RTL, throw the rest away,
and register each as an IP in the library.

The user asked for a *tidy* folder of cloned GitHub RISC-V cores (and the other important
IP — peripherals, buses, memory): take the important data, discard the rest. So for every
catalog entry this:

  1. shallow-clones the repo to a temp dir,
  2. extracts ONLY the RTL (rtl/src/hdl dirs, .v/.sv/.vh/.svh; skips tb/sim/fpga/sw/docs),
  3. drops it into ``data/ip_sources/<name>/rtl/`` + a small ``source.json`` (repo, commit,
     license, file count) — nothing else,
  4. deletes the clone,
  5. registers the IP in ``data/ip_library/`` (status='rtl') so it shows in the IP tab and,
     once you harden it (`scripts/build_ip_library.py --harden`), in Chip Studio.

This is TOOLING you trigger — it does network + disk work, so it's never run automatically.

    uv run python scripts/clone_ip_sources.py                 # everything in the catalog
    uv run python scripts/clone_ip_sources.py --only serv picorv32
    uv run python scripts/clone_ip_sources.py --category core  # just the RISC-V cores
    uv run python scripts/clone_ip_sources.py --list           # show the catalog, clone nothing
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
from garuda_api import ip_store  # noqa: E402

IP_SOURCES = REPO / "data" / "ip_sources"

# Curated catalog of the most important / most-used open-source digital-chip IP — the building
# blocks of a real SoC, across every category. `rtl` = subdirs to pull from (auto-detected if
# omitted); big repos are `optional` (skipped unless --include-optional or named with --only).
# Repos that don't clone (offline/moved) are skipped with a warning — the rest still import.
CATALOG: list[dict] = [
    # ── CPU cores (RISC-V + classic) ──────────────────────────────────────────
    {"name": "serv", "repo": "https://github.com/olofk/serv", "category": "core",
     "rtl": ["rtl"], "full": True, "subtitle": "World's smallest RV32I core (bit-serial, ~200 GE)"},
    {"name": "picorv32", "repo": "https://github.com/YosysHQ/picorv32", "category": "core",
     "rtl": ["."], "rtl_files": ["picorv32.v"], "subtitle": "Simple, well-proven RV32IMC core"},
    {"name": "fazyrv", "repo": "https://github.com/meiniKi/FazyRV", "category": "core",
     "rtl": ["rtl"], "full": True, "subtitle": "Scalable 1/2/4/8-bit-datapath RV32I core"},
    {"name": "darkriscv", "repo": "https://github.com/darklife/darkriscv", "category": "core",
     "rtl": ["rtl"], "subtitle": "Tiny 2/3-stage RV32E/I core"},
    {"name": "ibex", "repo": "https://github.com/lowRISC/ibex", "category": "core",
     "rtl": ["rtl"], "subtitle": "Industrial-grade 2-stage RV32IMC (silicon-proven)", "optional": True},
    {"name": "cv32e40p", "repo": "https://github.com/openhwgroup/cv32e40p", "category": "core",
     "rtl": ["rtl"], "subtitle": "4-stage RV32IMFCXpulp core with DSP extensions", "optional": True},
    {"name": "neorv32", "repo": "https://github.com/stnolting/neorv32", "category": "core",
     "rtl": ["rtl/core"], "subtitle": "Full RV32 microcontroller SoC", "optional": True},
    {"name": "zipcpu", "repo": "https://github.com/ZipCPU/zipcpu", "category": "core",
     "rtl": ["rtl"], "subtitle": "Small, pipelined 32-bit RISC CPU", "optional": True},
    {"name": "cva6", "repo": "https://github.com/openhwgroup/cva6", "category": "core",
     "rtl": ["core"], "subtitle": "Linux-capable RV64GC application core", "optional": True},

    # ── Peripherals ───────────────────────────────────────────────────────────
    {"name": "uart16550", "repo": "https://github.com/freecores/uart16550", "category": "peripheral",
     "rtl": ["rtl/verilog"], "subtitle": "16550-compatible UART"},
    {"name": "verilog_uart", "repo": "https://github.com/alexforencich/verilog-uart", "category": "peripheral",
     "rtl": ["rtl"], "subtitle": "Lightweight UART TX/RX"},
    {"name": "i2c", "repo": "https://github.com/alexforencich/verilog-i2c", "category": "peripheral",
     "rtl": ["rtl"], "subtitle": "I2C master/slave"},
    {"name": "simple_spi", "repo": "https://github.com/freecores/simple_spi", "category": "peripheral",
     "rtl": ["rtl/verilog"], "subtitle": "Simple SPI master (OpenCores)"},
    {"name": "spi", "repo": "https://github.com/freecores/spi", "category": "peripheral",
     "rtl": ["rtl/verilog"], "subtitle": "SPI master with FIFOs"},
    {"name": "gpio", "repo": "https://github.com/freecores/gpio", "category": "peripheral",
     "rtl": ["rtl/verilog"], "subtitle": "General-purpose I/O"},
    {"name": "ps2", "repo": "https://github.com/freecores/ps2", "category": "peripheral",
     "rtl": ["rtl/verilog"], "subtitle": "PS/2 keyboard/mouse controller", "optional": True},
    {"name": "vga_lcd", "repo": "https://github.com/freecores/vga_lcd", "category": "peripheral",
     "rtl": ["rtl/verilog"], "subtitle": "VGA/LCD controller", "optional": True},
    {"name": "usb_phy", "repo": "https://github.com/freecores/usb_phy", "category": "peripheral",
     "rtl": ["rtl/verilog"], "subtitle": "USB 1.1 PHY", "optional": True},
    {"name": "can", "repo": "https://github.com/freecores/can", "category": "peripheral",
     "rtl": ["rtl/verilog"], "subtitle": "CAN 2.0 controller", "optional": True},

    # ── Buses / interconnect ──────────────────────────────────────────────────
    {"name": "wishbone_interconnect", "repo": "https://github.com/freecores/wb_conmax", "category": "bus",
     "rtl": ["rtl/verilog"], "subtitle": "Wishbone conmax interconnect"},
    {"name": "wb_dma", "repo": "https://github.com/freecores/wb_dma", "category": "bus",
     "rtl": ["rtl/verilog"], "subtitle": "Wishbone DMA / bridge", "optional": True},
    {"name": "verilog_axi", "repo": "https://github.com/alexforencich/verilog-axi", "category": "bus",
     "rtl": ["rtl"], "subtitle": "AXI4 crossbar / adapters", "optional": True},
    {"name": "verilog_axis", "repo": "https://github.com/alexforencich/verilog-axis", "category": "bus",
     "rtl": ["rtl"], "subtitle": "AXI-Stream infrastructure (mux/fifo/arb)", "optional": True},

    # ── Memory ────────────────────────────────────────────────────────────────
    {"name": "async_fifo", "repo": "https://github.com/dpretet/async_fifo", "category": "memory",
     "rtl": ["rtl"], "subtitle": "Clock-domain-crossing async FIFO"},
    {"name": "sdr_ctrl", "repo": "https://github.com/freecores/sdr_ctrl", "category": "memory",
     "rtl": ["rtl/core"], "subtitle": "SDRAM controller", "optional": True},

    # ── Security / crypto (secworks suite — clean, self-contained, well-known) ──
    {"name": "aes", "repo": "https://github.com/secworks/aes", "category": "crypto",
     "rtl": ["src/rtl"], "subtitle": "AES-128/256 encrypt/decrypt"},
    {"name": "sha256", "repo": "https://github.com/secworks/sha256", "category": "crypto",
     "rtl": ["src/rtl"], "subtitle": "SHA-256 hash core"},
    {"name": "sha512", "repo": "https://github.com/secworks/sha512", "category": "crypto",
     "rtl": ["src/rtl"], "subtitle": "SHA-512 hash core"},
    {"name": "sha3", "repo": "https://github.com/secworks/sha3", "category": "crypto",
     "rtl": ["src/rtl"], "subtitle": "SHA-3 / Keccak hash core"},
    {"name": "chacha", "repo": "https://github.com/secworks/chacha", "category": "crypto",
     "rtl": ["src/rtl"], "subtitle": "ChaCha stream cipher"},
    {"name": "poly1305", "repo": "https://github.com/secworks/poly1305", "category": "crypto",
     "rtl": ["src/rtl"], "subtitle": "Poly1305 MAC"},
    {"name": "blake2s", "repo": "https://github.com/secworks/blake2s", "category": "crypto",
     "rtl": ["src/rtl"], "subtitle": "BLAKE2s hash core"},
    {"name": "trng", "repo": "https://github.com/secworks/trng", "category": "crypto",
     "rtl": ["src/rtl"], "subtitle": "True random number generator", "optional": True},
    {"name": "des", "repo": "https://github.com/secworks/des", "category": "crypto",
     "rtl": ["src/rtl"], "subtitle": "DES / 3DES cipher", "optional": True},

    # ── AI / DSP accelerators (real designs from GitHub) ──────────────────────
    {"name": "nvdla", "repo": "https://github.com/nvdla/hw", "category": "accelerator",
     "rtl": ["vmod/nvdla"], "subtitle": "NVDLA — NVIDIA open deep-learning accelerator", "optional": True},
    {"name": "redmule", "repo": "https://github.com/pulp-platform/redmule", "category": "accelerator",
     "rtl": ["rtl"], "subtitle": "PULP RedMulE matrix-multiply (GEMM) accelerator", "optional": True},
    {"name": "ne16", "repo": "https://github.com/pulp-platform/ne16", "category": "accelerator",
     "rtl": ["rtl"], "subtitle": "PULP NE16 neural-engine (conv) accelerator", "optional": True},
    {"name": "zip_dsp", "repo": "https://github.com/ZipCPU/dspfilters", "category": "dsp",
     "rtl": ["rtl"], "subtitle": "FIR / CIC / boxcar DSP filter cores"},
    {"name": "zip_fft", "repo": "https://github.com/ZipCPU/dblclockfft", "category": "dsp",
     "rtl": ["rtl"], "subtitle": "Pipelined FFT core", "optional": True},
    {"name": "cordic_core", "repo": "https://github.com/freecores/cordic", "category": "dsp",
     "rtl": ["rtl/verilog"], "subtitle": "CORDIC rotation engine"},
    {"name": "cic", "repo": "https://github.com/freecores/cic_core", "category": "dsp",
     "rtl": ["rtl/verilog"], "subtitle": "CIC decimation/interpolation filter"},
    {"name": "turbo_dsp", "repo": "https://github.com/freecores/turbocodes", "category": "dsp",
     "rtl": ["rtl/verilog"], "subtitle": "Turbo encoder/decoder", "optional": True},
    {"name": "hwpe_mac", "repo": "https://github.com/pulp-platform/hwpe-mac-engine", "category": "accelerator",
     "rtl": ["rtl"], "subtitle": "PULP HWPE multiply-accumulate engine", "optional": True},

    # ── Robotics / motor / control ────────────────────────────────────────────
    {"name": "pid_controller", "repo": "https://github.com/AngeloJacobo/FPGA_PID_Controller",
     "category": "peripheral", "rtl": ["."], "subtitle": "PID control loop (motors/robotics)"},
    {"name": "quad_decoder", "repo": "https://github.com/jamieiles/quadrature-decoder",
     "category": "peripheral", "rtl": ["."], "subtitle": "Quadrature encoder decoder", "optional": True},
    {"name": "stepper", "repo": "https://github.com/freecores/stepper_motor_drive", "category": "peripheral",
     "rtl": ["rtl/verilog"], "subtitle": "Stepper-motor driver", "optional": True},

    # ── Communications / networking / video ───────────────────────────────────
    {"name": "ethmac", "repo": "https://github.com/freecores/ethmac", "category": "peripheral",
     "rtl": ["rtl/verilog"], "subtitle": "10/100 Ethernet MAC", "optional": True},
    {"name": "verilog_pcie", "repo": "https://github.com/alexforencich/verilog-pcie", "category": "bus",
     "rtl": ["rtl"], "subtitle": "PCI Express interface", "optional": True},
    {"name": "hdmi_tx", "repo": "https://github.com/hdl-util/hdmi", "category": "peripheral",
     "rtl": ["src"], "subtitle": "HDMI 1.4 transmitter", "optional": True},
    {"name": "vga_text", "repo": "https://github.com/projf/projf-explore", "category": "peripheral",
     "rtl": ["display"], "subtitle": "Display / graphics primitives", "optional": True},
    {"name": "manchester", "repo": "https://github.com/freecores/manchester_encoder", "category": "peripheral",
     "rtl": ["rtl/verilog"], "subtitle": "Manchester encoder/decoder", "optional": True},

    # ── Memory / storage controllers ──────────────────────────────────────────
    {"name": "sdspi", "repo": "https://github.com/ZipCPU/sdspi", "category": "memory",
     "rtl": ["rtl"], "subtitle": "SD-card (SPI) controller", "optional": True},
    {"name": "wbsdram", "repo": "https://github.com/ZipCPU/wbsdram", "category": "memory",
     "rtl": ["rtl"], "subtitle": "Wishbone SDRAM controller", "optional": True},
    {"name": "qspi_flash", "repo": "https://github.com/ZipCPU/qspiflash", "category": "memory",
     "rtl": ["rtl"], "subtitle": "QSPI flash controller", "optional": True},

    # ── Bus / interconnect (more) ─────────────────────────────────────────────
    {"name": "wb2axip", "repo": "https://github.com/ZipCPU/wb2axip", "category": "bus",
     "rtl": ["rtl"], "subtitle": "Wishbone/AXI bridges + crossbars", "optional": True},

    # ── Crypto / security (more) ──────────────────────────────────────────────
    {"name": "sha1", "repo": "https://github.com/secworks/sha1", "category": "crypto",
     "rtl": ["src/rtl"], "subtitle": "SHA-1 hash core"},
    {"name": "siphash", "repo": "https://github.com/secworks/siphash", "category": "crypto",
     "rtl": ["src/rtl"], "subtitle": "SipHash keyed hash"},
    {"name": "cmac", "repo": "https://github.com/secworks/cmac", "category": "crypto",
     "rtl": ["src/rtl"], "subtitle": "AES-CMAC authentication", "optional": True},
    {"name": "gcm", "repo": "https://github.com/secworks/gcm", "category": "crypto",
     "rtl": ["src/rtl"], "subtitle": "Galois/Counter-Mode core", "optional": True},
    {"name": "fpu", "repo": "https://github.com/freecores/fpu", "category": "dsp",
     "rtl": ["."], "subtitle": "IEEE-754 single-precision FPU", "optional": True},
    {"name": "fpu_double", "repo": "https://github.com/freecores/fpu_double", "category": "dsp",
     "rtl": ["rtl/verilog"], "subtitle": "Double-precision FPU", "optional": True},

    # ── Networking / infra ────────────────────────────────────────────────────
    {"name": "verilog_ethernet", "repo": "https://github.com/alexforencich/verilog-ethernet", "category": "bus",
     "rtl": ["rtl"], "subtitle": "Ethernet MAC + infrastructure", "optional": True},
]

SKIP_DIR = re.compile(r"(^|/)(tb|test|tests|bench|sim|fpga|syn|synth|dv|sw|doc|docs|example"
                      r"|examples|scripts|fpga_|formal|tb_|vendor|deps|third_party)(/|$)", re.I)
# Clearly non-synthesis files — drop these but KEEP real design modules. Conservative on
# purpose: an earlier pass also matched `_if`/`_sim`/`monitor`, which wrongly dropped needed
# interface modules (e.g. serv_rf_if) and broke the core's elaboration cone.
SKIP_FILE = re.compile(r"(tracer|_dv\b|dv_|_tb\b|tb_|_sva\b|sva_|assertions?|_bind\b|_cov\b"
                       r"|coverage|scoreboard|_fpga\b|fpga_|_formal\b|testbench)", re.I)
RTL_EXT = (".v", ".sv", ".vh", ".svh")
MAX_FILES = 60                      # cap per source — a core needs its cone, not 300 files


def _run(cmd: list[str], cwd=None, timeout=600) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stdout + p.stderr)
    except Exception as e:  # noqa: BLE001
        return 1, str(e)


def _find_rtl(clone: Path, entry: dict, full: bool = False) -> list[Path]:
    """Collect RTL paths: from the declared subdirs if given, else auto-detect rtl/src/hdl.
    `full` keeps the ENTIRE cone (no SKIP_FILE, no cap) — needed for a real core like serv/fazyrv
    whose top elaborates every module in rtl/."""
    roots: list[Path] = []
    for sub in entry.get("rtl", []):
        d = clone / sub
        if d.is_dir():
            roots.append(d)
    if not roots:  # auto-detect
        for cand in ("rtl", "src", "hdl", "verilog", "core"):
            for d in clone.rglob(cand):
                if d.is_dir() and not SKIP_DIR.search(str(d.relative_to(clone))):
                    roots.append(d)
        if not roots:
            roots = [clone]
    only = set(entry.get("rtl_files", []))
    match = entry.get("rtl_files_match")
    out, seen = [], set()
    for root in roots:
        for p in root.rglob("*"):
            if p.suffix.lower() not in RTL_EXT or not p.is_file():
                continue
            rel = str(p.relative_to(clone))
            if SKIP_DIR.search(rel) or (not only and not full and SKIP_FILE.search(p.name)):
                continue                       # drop tb/dv/tracer/fpga/assert — keep the core
            if only and p.name not in only:
                continue
            if match and not re.search(match, p.name, re.I):
                continue
            if p.name in seen:  # de-dup by basename (flatten)
                continue
            seen.add(p.name)
            out.append(p)
    if only or match:
        return out
    # "just what we need": keep packages/headers + the core cone, capped. Rank essential first
    # (packages, then top/core/<repo-name>, then the rest) so a hard cap keeps the right files.
    name = entry["name"].lower()
    def rank(p: Path) -> tuple:
        n = p.name.lower()
        return (0 if p.suffix.lower() in (".vh", ".svh") or "pkg" in n else
                1 if any(k in n for k in ("top", "core", name)) else 2, n)
    out.sort(key=rank)
    return out if full else out[:MAX_FILES]


def clone_one(entry: dict, *, register: bool = True, full: bool = False) -> dict:
    full = full or entry.get("full", False)        # entry can force its full cone (cores)
    name = entry["name"]
    dest = IP_SOURCES / name
    print(f"\n── {name}  ({entry['category']})  {entry['repo']}")
    tmp = Path(tempfile.mkdtemp(prefix=f"clone_{name}_"))
    clone = tmp / "repo"
    rc, log = _run(["git", "clone", "--depth", "1", entry["repo"], str(clone)])
    if rc != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"   ⚠️  clone failed — skipped ({log.strip().splitlines()[-1][:120] if log.strip() else 'error'})")
        return {"name": name, "ok": False}
    _rc, commit = _run(["git", "-C", str(clone), "rev-parse", "HEAD"])
    rtl_files = _find_rtl(clone, entry, full=full)
    if not rtl_files:
        shutil.rmtree(tmp, ignore_errors=True)
        print("   ⚠️  no RTL found — skipped")
        return {"name": name, "ok": False}
    # write ONLY the RTL into the tidy folder, discard everything else
    if dest.exists():
        shutil.rmtree(dest)
    rtl_dir = dest / "rtl"
    rtl_dir.mkdir(parents=True, exist_ok=True)
    kept = 0
    for p in rtl_files:
        try:
            shutil.copy(p, rtl_dir / p.name)
            kept += 1
        except Exception:  # noqa: BLE001
            pass
    lic = next((str(f.name) for f in clone.glob("LICENSE*")), "")
    license_text = ""
    if lic:
        try:
            license_text = (clone / lic).read_text(errors="replace")[:400]
        except Exception:  # noqa: BLE001
            pass
    (dest / "source.json").write_text(json.dumps({
        "name": name, "repo": entry["repo"], "commit": commit.strip()[:12],
        "category": entry["category"], "subtitle": entry.get("subtitle", ""),
        "rtl_files": kept, "license": lic, "license_head": license_text,
    }, indent=2))
    shutil.rmtree(tmp, ignore_errors=True)
    print(f"   ✓ kept {kept} RTL file(s) → {rtl_dir.relative_to(REPO)}  (clone discarded)")

    if register:
        files = {p.name: p.read_text(errors="replace") for p in rtl_dir.glob("*")
                 if p.suffix.lower() in RTL_EXT}
        try:
            mf = ip_store.create_ip(name, files, category=entry["category"],
                                    source=f"clone:{entry['repo']}",
                                    subtitle=entry.get("subtitle", ""), ip_id=name)
            n = ip_store.ingest_ip(name)
            print(f"   ✓ registered IP '{mf['id']}'  top={mf['top']}  "
                  f"ports={len(mf['ports'])}  ({n} rows → knowledge store)")
        except Exception as e:  # noqa: BLE001
            print(f"   ⚠️  IP registration failed: {e}")
    return {"name": name, "ok": True, "rtl_files": kept}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", help="clone only these catalog names")
    ap.add_argument("--category", help="clone only this category (core/peripheral/bus/memory)")
    ap.add_argument("--list", action="store_true", help="print the catalog and exit")
    ap.add_argument("--no-register", action="store_true", help="extract RTL but don't add to the IP library")
    ap.add_argument("--include-optional", action="store_true", help="include big/optional repos (cva6, axi)")
    ap.add_argument("--full", action="store_true", help="keep the WHOLE cone (no skip-filter, no cap) — for real cores")
    args = ap.parse_args()

    catalog = CATALOG
    if args.only:
        catalog = [e for e in catalog if e["name"] in set(args.only)]
    if args.category:
        catalog = [e for e in catalog if e["category"] == args.category]
    if not args.include_optional and not args.only:
        catalog = [e for e in catalog if not e.get("optional")]

    if args.list:
        for e in catalog:
            print(f"  {e['name']:22s} {e['category']:11s} {e['repo']}"
                  + ("  (optional)" if e.get("optional") else ""))
        return

    IP_SOURCES.mkdir(parents=True, exist_ok=True)
    results = [clone_one(e, register=not args.no_register, full=args.full) for e in catalog]
    ok = [r for r in results if r.get("ok")]
    print(f"\n═══ done: {len(ok)}/{len(results)} sources imported "
          f"({sum(r.get('rtl_files', 0) for r in ok)} RTL files kept) → data/ip_sources/")


if __name__ == "__main__":
    main()
