#!/usr/bin/env python3
"""Generate the canonical MEMORY IPs (SRAM, ROM, register file, FIFO) as clean, parameterized,
synthesizable RTL — each with a SELF-CHECKING testbench that proves it works.

Real SRAM on a PDK is a foundry macro, but a synthesizable register-array SRAM is the portable,
hardenable, simulatable building block every SoC needs — and the user flagged SRAM as critical.
Each IP ships a testbench that writes/reads and asserts the result (prints PASS/FAIL), so the IP
card shows a green "sim ✓" verdict and the block is verified before it's placed on a chip.

    uv run python scripts/gen_memory_ips.py            # generate + register + simulate all
    uv run python scripts/gen_memory_ips.py --no-sim   # just generate + register
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))
from garuda_api import ip_store  # noqa: E402

# Each IP: top module, category, subtitle, rtl {file:code}, tb {file:code}.
IPS: list[dict] = [
    {
        "name": "Single-Port SRAM", "id": "mem_sram_sp", "top": "sram_sp",
        "subtitle": "Synchronous single-port SRAM (parameterized width/depth)",
        "rtl": {"sram_sp.v": """// Synchronous single-port SRAM — 1 read/write port, registered output.
module sram_sp #(parameter DW = 8, parameter AW = 8) (
    input              clk,
    input              we,                 // write enable
    input  [AW-1:0]    addr,
    input  [DW-1:0]    din,
    output reg [DW-1:0] dout
);
    reg [DW-1:0] mem [0:(1<<AW)-1];
    always @(posedge clk) begin
        if (we) mem[addr] <= din;          // write
        dout <= mem[addr];                 // synchronous read
    end
endmodule
"""},
        "tb": {"sram_sp_tb.v": """`timescale 1ns/1ps
module sram_sp_tb;
    localparam DW=8, AW=4;
    reg clk=0, we=0; reg [AW-1:0] addr=0; reg [DW-1:0] din=0; wire [DW-1:0] dout;
    integer i, errors=0;
    sram_sp #(.DW(DW), .AW(AW)) dut(.clk(clk), .we(we), .addr(addr), .din(din), .dout(dout));
    always #5 clk=~clk;
    initial begin
        $dumpfile("design.vcd"); $dumpvars(0, sram_sp_tb);
        for (i=0;i<16;i=i+1) begin @(negedge clk); we=1; addr=i; din=i*3+1; end
        @(negedge clk); we=0;
        for (i=0;i<16;i=i+1) begin
            @(negedge clk); addr=i; @(posedge clk); #1;
            if (dout !== (i*3+1)) begin errors=errors+1; $display("MISMATCH addr %0d: got %0d exp %0d", i, dout, i*3+1); end
        end
        if (errors==0) $display("PASS: single-port SRAM ok"); else $display("FAIL: %0d errors", errors);
        $finish;
    end
endmodule
"""},
    },
    {
        "name": "Dual-Port SRAM", "id": "mem_sram_dp", "top": "sram_dp",
        "subtitle": "True dual-port SRAM (two independent R/W ports)",
        "rtl": {"sram_dp.v": """// True dual-port synchronous SRAM — two independent read/write ports.
module sram_dp #(parameter DW = 8, parameter AW = 8) (
    input              clk,
    input              we_a, input [AW-1:0] addr_a, input [DW-1:0] din_a, output reg [DW-1:0] dout_a,
    input              we_b, input [AW-1:0] addr_b, input [DW-1:0] din_b, output reg [DW-1:0] dout_b
);
    reg [DW-1:0] mem [0:(1<<AW)-1];
    always @(posedge clk) begin
        if (we_a) mem[addr_a] <= din_a;
        dout_a <= mem[addr_a];
    end
    always @(posedge clk) begin
        if (we_b) mem[addr_b] <= din_b;
        dout_b <= mem[addr_b];
    end
endmodule
"""},
        "tb": {"sram_dp_tb.v": """`timescale 1ns/1ps
module sram_dp_tb;
    localparam DW=8, AW=4;
    reg clk=0; reg we_a=0,we_b=0; reg [AW-1:0] aa=0,ab=0; reg [DW-1:0] da=0,db=0; wire [DW-1:0] qa,qb;
    integer i, errors=0;
    sram_dp #(.DW(DW),.AW(AW)) dut(.clk(clk),.we_a(we_a),.addr_a(aa),.din_a(da),.dout_a(qa),
                                   .we_b(we_b),.addr_b(ab),.din_b(db),.dout_b(qb));
    always #5 clk=~clk;
    initial begin
        $dumpfile("design.vcd"); $dumpvars(0, sram_dp_tb);
        for (i=0;i<8;i=i+1) begin @(negedge clk); we_a=1; aa=i; da=i+10; end
        @(negedge clk); we_a=0;
        for (i=0;i<8;i=i+1) begin @(negedge clk); ab=i; @(posedge clk); #1;
            if (qb !== (i+10)) begin errors=errors+1; $display("MISMATCH %0d",i); end end
        if (errors==0) $display("PASS: dual-port SRAM ok"); else $display("FAIL: %0d errors", errors);
        $finish;
    end
endmodule
"""},
    },
    {
        "name": "Byte-Enable SRAM", "id": "mem_sram_be", "top": "sram_be",
        "subtitle": "Single-port SRAM with per-byte write enables",
        "rtl": {"sram_be.v": """// Single-port SRAM with per-byte write strobes (NB bytes wide).
module sram_be #(parameter NB = 4, parameter AW = 8) (
    input                clk,
    input  [NB-1:0]      be,               // one strobe per byte lane
    input  [AW-1:0]      addr,
    input  [NB*8-1:0]    din,
    output reg [NB*8-1:0] dout
);
    reg [NB*8-1:0] mem [0:(1<<AW)-1];
    integer i;
    always @(posedge clk) begin
        for (i=0;i<NB;i=i+1) if (be[i]) mem[addr][i*8 +: 8] <= din[i*8 +: 8];
        dout <= mem[addr];
    end
endmodule
"""},
        "tb": {"sram_be_tb.v": """`timescale 1ns/1ps
module sram_be_tb;
    localparam NB=4, AW=4;
    reg clk=0; reg [NB-1:0] be=0; reg [AW-1:0] addr=0; reg [NB*8-1:0] din=0; wire [NB*8-1:0] dout;
    integer errors=0;
    sram_be #(.NB(NB),.AW(AW)) dut(.clk(clk),.be(be),.addr(addr),.din(din),.dout(dout));
    always #5 clk=~clk;
    initial begin
        $dumpfile("design.vcd"); $dumpvars(0, sram_be_tb);
        @(negedge clk); be=4'b1111; addr=2; din=32'hDEADBEEF;     // full write
        @(negedge clk); be=4'b0010; addr=2; din=32'h0000FF00;     // write byte 1 only
        @(negedge clk); be=0; addr=2; @(posedge clk); #1;
        if (dout !== 32'hDEADFFEF) begin errors=1; $display("MISMATCH got %h", dout); end
        if (errors==0) $display("PASS: byte-enable SRAM ok"); else $display("FAIL");
        $finish;
    end
endmodule
"""},
    },
    {
        "name": "Register File 2R1W", "id": "mem_regfile", "top": "regfile",
        "subtitle": "2-read / 1-write register file (CPU datapath)",
        "rtl": {"regfile.v": """// 2-read, 1-write register file with combinational read (x0 not special).
module regfile #(parameter DW = 32, parameter AW = 5) (
    input              clk,
    input              we,
    input  [AW-1:0]    waddr, input [DW-1:0] wdata,
    input  [AW-1:0]    raddr1, output [DW-1:0] rdata1,
    input  [AW-1:0]    raddr2, output [DW-1:0] rdata2
);
    reg [DW-1:0] regs [0:(1<<AW)-1];
    integer i; initial for (i=0;i<(1<<AW);i=i+1) regs[i]=0;
    always @(posedge clk) if (we) regs[waddr] <= wdata;
    assign rdata1 = regs[raddr1];
    assign rdata2 = regs[raddr2];
endmodule
"""},
        "tb": {"regfile_tb.v": """`timescale 1ns/1ps
module regfile_tb;
    reg clk=0, we=0; reg [4:0] wa=0,ra1=0,ra2=0; reg [31:0] wd=0; wire [31:0] rd1,rd2;
    integer i, errors=0;
    regfile dut(.clk(clk),.we(we),.waddr(wa),.wdata(wd),.raddr1(ra1),.rdata1(rd1),.raddr2(ra2),.rdata2(rd2));
    always #5 clk=~clk;
    initial begin
        $dumpfile("design.vcd"); $dumpvars(0, regfile_tb);
        for (i=1;i<8;i=i+1) begin @(negedge clk); we=1; wa=i; wd=i*32'h1111; end
        @(negedge clk); we=0;
        for (i=1;i<8;i=i+1) begin #1; ra1=i; #1;
            if (rd1 !== i*32'h1111) begin errors=errors+1; $display("MISMATCH r%0d", i); end end
        if (errors==0) $display("PASS: register file ok"); else $display("FAIL: %0d", errors);
        $finish;
    end
endmodule
"""},
    },
    {
        "name": "Synchronous FIFO", "id": "mem_fifo_sync", "top": "fifo_sync",
        "subtitle": "Single-clock FIFO with full/empty flags",
        "rtl": {"fifo_sync.v": """// Single-clock synchronous FIFO with full/empty flags.
module fifo_sync #(parameter DW = 8, parameter AW = 4) (
    input              clk, input rst,
    input              wr_en, input [DW-1:0] din,  output full,
    input              rd_en, output reg [DW-1:0] dout, output empty
);
    localparam DEPTH = (1<<AW);
    reg [DW-1:0] mem [0:DEPTH-1];
    reg [AW:0] wptr, rptr;
    wire [AW-1:0] wa = wptr[AW-1:0], ra = rptr[AW-1:0];
    assign empty = (wptr == rptr);
    assign full  = (wptr[AW] != rptr[AW]) && (wa == ra);
    always @(posedge clk) begin
        if (rst) begin wptr <= 0; rptr <= 0; end
        else begin
            if (wr_en && !full)  begin mem[wa] <= din; wptr <= wptr + 1'b1; end
            if (rd_en && !empty) begin dout <= mem[ra]; rptr <= rptr + 1'b1; end
        end
    end
endmodule
"""},
        "tb": {"fifo_sync_tb.v": """`timescale 1ns/1ps
module fifo_sync_tb;
    localparam DW=8;
    reg clk=0, rst=1, wr=0, rd=0; reg [DW-1:0] din=0; wire [DW-1:0] dout; wire full, empty;
    integer i, errors=0;
    fifo_sync #(.DW(DW),.AW(3)) dut(.clk(clk),.rst(rst),.wr_en(wr),.din(din),.full(full),
                                    .rd_en(rd),.dout(dout),.empty(empty));
    always #5 clk=~clk;
    initial begin
        $dumpfile("design.vcd"); $dumpvars(0, fifo_sync_tb);
        @(negedge clk); rst=0;
        for (i=0;i<6;i=i+1) begin @(negedge clk); wr=1; din=i*7+2; end
        @(negedge clk); wr=0;
        for (i=0;i<6;i=i+1) begin @(negedge clk); rd=1; @(posedge clk); #1;
            if (dout !== (i*7+2)) begin errors=errors+1; $display("MISMATCH %0d got %0d", i, dout); end end
        @(negedge clk); rd=0;
        if (errors==0) $display("PASS: sync FIFO ok"); else $display("FAIL: %0d", errors);
        $finish;
    end
endmodule
"""},
    },
    {
        "name": "Synchronous ROM", "id": "mem_rom_sync", "top": "rom_sync",
        "subtitle": "Synchronous ROM (initialized lookup table)",
        "rtl": {"rom_sync.v": """// Synchronous ROM — registered output, content baked into the logic.
module rom_sync #(parameter DW = 8, parameter AW = 4) (
    input              clk,
    input  [AW-1:0]    addr,
    output reg [DW-1:0] dout
);
    always @(posedge clk) begin
        case (addr)
            4'd0: dout <= 8'h0A; 4'd1: dout <= 8'h1B; 4'd2: dout <= 8'h2C; 4'd3: dout <= 8'h3D;
            4'd4: dout <= 8'h4E; 4'd5: dout <= 8'h5F; 4'd6: dout <= 8'h60; 4'd7: dout <= 8'h71;
            default: dout <= 8'hFF;
        endcase
    end
endmodule
"""},
        "tb": {"rom_sync_tb.v": """`timescale 1ns/1ps
module rom_sync_tb;
    reg clk=0; reg [3:0] addr=0; wire [7:0] dout; integer errors=0;
    reg [7:0] exp [0:7];
    rom_sync dut(.clk(clk), .addr(addr), .dout(dout));
    always #5 clk=~clk;
    initial begin
        $dumpfile("design.vcd"); $dumpvars(0, rom_sync_tb);
        exp[0]=8'h0A; exp[1]=8'h1B; exp[2]=8'h2C; exp[3]=8'h3D;
        exp[4]=8'h4E; exp[5]=8'h5F; exp[6]=8'h60; exp[7]=8'h71;
        begin : chk integer i;
            for (i=0;i<8;i=i+1) begin @(negedge clk); addr=i; @(posedge clk); #1;
                if (dout !== exp[i]) begin errors=errors+1; $display("MISMATCH %0d", i); end end
        end
        if (errors==0) $display("PASS: ROM ok"); else $display("FAIL: %0d", errors);
        $finish;
    end
endmodule
"""},
    },
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-sim", action="store_true", help="generate + register only (skip simulation)")
    args = ap.parse_args()
    print(f"generating {len(IPS)} memory IP(s) (SRAM/ROM/regfile/FIFO) with testbenches…\n")
    npass = 0
    for spec in IPS:
        mf = ip_store.create_ip(spec["name"], spec["rtl"], category="memory", source="generated",
                                subtitle=spec["subtitle"], ip_id=spec["id"], top=spec["top"],
                                tb_files=spec["tb"])
        line = f"  + {mf['id']:16s} top={mf['top']:12s} ports={len(mf['ports'])}"
        if not args.no_sim:
            res = ip_store.simulate_ip(mf["id"])
            line += f"  sim={res['status']}"
            npass += res["status"] == "pass"
        ip_store.ingest_ip(mf["id"])
        print(line)
    if not args.no_sim:
        print(f"\n✓ {npass}/{len(IPS)} memory IPs simulate PASS (self-checked) → data/ip_library/")
    else:
        print(f"\n✓ {len(IPS)} memory IPs generated.")


if __name__ == "__main__":
    main()
