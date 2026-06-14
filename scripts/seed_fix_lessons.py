"""Seed the knowledge store's `fix` category with a comprehensive library of Verilog
problem→solution lessons — the recurring iverilog/Verilator/Yosys errors a local model
trips on, each with the EXACT compiler message (so semantic recall matches a future
error), the CAUSE, the RULE, and a WRONG→RIGHT code pair (like the alu fix).

These are recalled by the corrector on attempt 1 and injected into the generator BEFORE
it writes RTL, so the same mistake isn't repeated. Idempotent: each lesson has a stable
id, so re-running UPDATES in place instead of duplicating.

    .venv/bin/python scripts/seed_fix_lessons.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "garuda_chip"))
import hashlib
from memory_store import get_memory  # noqa: E402

# (signature, symptom, cause, fix, wrong, right)
LESSONS = [
    ("bare `define macro used without backtick",
     "iverilog: Unable to bind parameter `REG_COUNT' in `regfile' / Dimensions must be constant / "
     "Unable to bind wire/reg/memory `REG_COUNT'",
     "A name created with `define is used as a plain identifier (no leading backtick), so it is "
     "undefined at elaboration. Also the file that uses it never `include`d the header that defines it.",
     "Reference every `define macro WITH the backtick, and `include the header in each file that uses it.",
     "reg [7:0] regs [0:REG_COUNT-1];   // REG_COUNT is a `define\n"
     "for (i=0;i<REG_COUNT;i=i+1) ...",
     "`include \"params.vh\"\nreg [7:0] regs [0:`REG_COUNT-1];\n"
     "for (i=0;i<`REG_COUNT;i=i+1) ...   // backtick on every use"),

    ("instantiated port does not exist on the module",
     "iverilog: port ``pc_out'' is not a port of if_stage",
     "An instantiation connects a port by name that the target module does not declare — the "
     "parent and child port lists drifted out of sync.",
     "Open the child module, read its REAL port list, and connect only ports that exist (fix the "
     "name or add the port to the child).",
     "pipeline_reg u_if (.clk(clk), .pc_out(pc_w), ...);  // pipeline_reg has no pc_out",
     "pipeline_reg u_if (.clk(clk), .ir_out(ir_w), ...);  // only real ports of pipeline_reg"),

    ("} used to close a block instead of end",
     "iverilog: syntax error near `else' / unexpected '}'",
     "Verilog has NO curly-brace blocks. `}` was used to close a begin/if/else block. Curly braces "
     "are ONLY for concatenation/replication.",
     "Close every begin block with `end`. Use `end else`, not `} else`.",
     "if (flush) begin\n    x = 0;\n} else begin\n    x = y;\nend",
     "if (flush) begin\n    x = 0;\nend else begin\n    x = y;\nend"),

    ("wire/net declared inside an always block",
     "iverilog: Syntax in assignment statement l-value",
     "A `wire` (net) was declared inside an `always` block. Nets may only be declared at module scope.",
     "Move the wire+assign to module scope, or use a module-scope reg/integer with blocking '=' "
     "inside the always block.",
     "always @* begin\n    wire [7:0] t = a & b;   // illegal\n    y = t;\nend",
     "wire [7:0] t = a & b;     // module scope\nalways @* begin\n    y = t;\nend"),

    ("bit-select on a parenthesised expression",
     "iverilog: error near ')[' — cannot select from an expression / syntax error",
     "You can bit-select or part-select only a NET or VARIABLE, never the result of an expression "
     "like (a+b)[31].",
     "Assign the expression to a wire first, then index the wire. For a carry use one extra bit.",
     "carry = (a + b)[8];\novf   = ((a+b)[7] != (a+b)[8]);",
     "wire [8:0] sum = a + b;\nassign carry = sum[8];\nassign ovf = (sum[7] != sum[8]);"),

    ("variable / non-constant part-select width",
     "iverilog: A reference to a wire or reg (`i') is not allowed in a constant expression",
     "A part-select like mem[32*(i+1)-1 : 32*i] uses a variable `i` in the bound — part-select "
     "WIDTH must be constant.",
     "Use an unpacked word array and index it (mem[i]), or the indexed part-select bus[i*32 +: 32] "
     "(the width after +: is constant).",
     "reg [W*N-1:0] mem;\nmem[32*(i+1)-1 : 32*i] <= 0;   // illegal",
     "reg [31:0] mem [0:N-1];\nmem[i] <= 32'd0;            // unpacked array\n"
     "// or: bus[i*32 +: 32] <= 32'd0;"),

    ("reversed / out-of-bounds part-select",
     "iverilog: part select imm[11:12] is out of order / out of bounds",
     "A part-select wrote [low:high] (MSB < LSB) or indices outside the vector width.",
     "Write part-selects MSB-first [high:low] within the declared range; check the field width.",
     "wire [4:0] sh = instr[11:12];   // reversed",
     "wire [4:0] sh = instr[24:20];   // [high:low], valid range"),

    ("multiple drivers on one net (MULTIDRIVEN)",
     "iverilog: Unresolved net/uwire X cannot have multiple drivers / Verilator MULTIDRIVEN",
     "The same signal is driven from two places (two always blocks, or an assign plus an always).",
     "One driver per signal: merge the logic into a SINGLE always block (or a single assign).",
     "always @* y = a;\nalways @* y = b;   // two drivers",
     "always @* begin\n    if (sel) y = a;\n    else     y = b;\nend"),

    ("unpacked array reset in one statement",
     "iverilog: malformed statement / cannot assign to an unpacked array",
     "An unpacked array (reg [W-1:0] mem [0:N-1]) was reset with mem <= 0 or mem <= {N{...}}.",
     "Reset an unpacked array element-by-element with an integer for-loop.",
     "always @(posedge clk) if (rst) mem <= 0;   // illegal",
     "integer i;\nalways @(posedge clk)\n  if (rst) for (i=0;i<N;i=i+1) mem[i] <= {W{1'b0}};"),

    ("replication missing the inner braces",
     "iverilog: syntax error near '{' / value is the wrong width",
     "Replication needs DOUBLE braces: {N{value}}. Writing 4{8'd0} or {12{1'b0}, x} is malformed.",
     "Wrap the replicated value in its own braces, then concatenate.",
     "y = {12{1'b0}, instr[20:16]};   // malformed",
     "y = {{12{1'b0}}, instr[20:16]}; // replication then concat"),

    ("combinational loop (UNOPTFLAT)",
     "Verilator: UNOPTFLAT — signal feeds back into itself through combinational logic",
     "A signal depends on itself through pure assign/combinational logic (assign x = x + 1; or a=b,b=a).",
     "Break the loop: register the feedback in an always @(posedge clk), don't drive it from a "
     "self-referential wire.",
     "assign count = count + 1;        // comb loop",
     "always @(posedge clk) count <= count + 1;"),

    ("inferred latch (LATCH)",
     "Verilator: LATCH — latch inferred on signal X",
     "A combinational always block does not assign the signal in every path (incomplete if/case), "
     "so a latch is inferred.",
     "Assign a default value at the top of the always block, or make the case/if complete (add default/else).",
     "always @* if (en) y = d;          // y latched when !en",
     "always @* begin\n    y = 1'b0;     // default\n    if (en) y = d;\nend"),

    ("signal assigned in always not declared reg",
     "iverilog: X is not a valid l-value / cannot assign to a net in a procedural block",
     "A signal assigned inside an always block was declared as wire (or only as a module input), "
     "but procedural assignment requires reg.",
     "Declare it `reg` (or `output reg`); declare each signal EXACTLY once (never both a port and a reg).",
     "output y;\nalways @* y = a & b;   // y is a wire",
     "output reg y;\nalways @* y = a & b;"),

    ("duplicate parameter from un-guarded header include",
     "iverilog: 'DATA_WIDTH' has already been declared in this scope",
     "A header with parameters/`defines is `include`d by several files (or twice) with no include "
     "guard, so its declarations repeat.",
     "Wrap the header in an include guard (`ifndef/`define/`endif) so its contents are seen once.",
     "// params.vh\nparameter DATA_WIDTH = 8;",
     "`ifndef PARAMS_VH\n`define PARAMS_VH\nparameter DATA_WIDTH = 8;\n`endif"),

    ("duplicate module definition",
     "iverilog: module `alu' was already declared here",
     "The same module name is defined in two files (e.g. alu.v and alu_8bit.v both define alu) — "
     "often from over-decomposition.",
     "Keep ONE definition per module name; delete the duplicate file and point instantiations at "
     "the kept module.",
     "// alu.v  -> module alu(...)\n// alu_8bit.v -> module alu(...)  // duplicate",
     "// one alu.v -> module alu(...); delete the other; instantiate `alu`"),

    ("port / assignment width mismatch",
     "iverilog: warning: port expects N bits, got M / Verilator WIDTH",
     "An assignment or port connection has mismatched widths; a signed value isn't sign-extended.",
     "Match widths on every assignment and port; sign-extend signed values explicitly.",
     "wire [15:0] x; wire [7:0] b;\nassign x = b;          // zero-padded silently",
     "assign x = {{8{b[7]}}, b};   // explicit sign-extend to 16 bits"),

    ("testbench never finishes / sim timeout",
     "GarudaChip: simulation timed out (missing $finish?)",
     "The testbench has no $finish (or an infinite stimulus loop), so vvp never returns.",
     "Drive a bounded stimulus and call $finish at the end; print 'Result: PASSED'/'FAILED' first.",
     "initial begin\n  // apply stimulus, no $finish\nend",
     "initial begin\n  // apply stimulus, check\n  $display(\"Result: PASSED\");\n  $finish;\nend"),

    ("arrayed module ports break synthesis",
     "Yosys: arrayed/2-D ports not supported on module boundary",
     "A module port is a 2-D/unpacked array (e.g. output [7:0] data [0:3]) — fine for sim, but the "
     "synthesis boundary needs flat ports.",
     "Flatten arrayed ports into a single wide vector at the boundary and slice inside.",
     "output [7:0] data [0:3];        // arrayed port",
     "output [31:0] data_flat;        // {d3,d2,d1,d0}; slice inside the module"),

    ("blocking vs non-blocking in sequential logic",
     "Verilator: BLKSEQ — blocking assignment '=' in a sequential (clocked) block",
     "Sequential logic used blocking '=' inside always @(posedge clk), risking simulation/synthesis "
     "mismatch and races.",
     "Use non-blocking '<=' for all registers in a clocked block; blocking '=' only in combinational @*.",
     "always @(posedge clk) q = d;",
     "always @(posedge clk) q <= d;"),

    ("async reset not in the sensitivity list",
     "Verilator: SYNCASYNCNET / reset behaves synchronously",
     "An async reset signal is used inside the block but not in the @(posedge clk or negedge rst_n) "
     "sensitivity list.",
     "List the reset edge in the sensitivity list and branch on it first.",
     "always @(posedge clk) if (!rst_n) q<=0; else q<=d;",
     "always @(posedge clk or negedge rst_n)\n  if (!rst_n) q<=0; else q<=d;"),
]


def main():
    mem = get_memory()
    if not getattr(mem, "enabled", False):
        print("knowledge store offline — run `docker compose up -d` first.")
        return
    n = 0
    for sig, symptom, cause, fix, wrong, right in LESSONS:
        body = (
            f"ERROR SIGNATURE: {sig}\n\n"
            f"SYMPTOM (compiler/sim message): {symptom}\n\n"
            f"CAUSE: {cause}\n\n"
            f"FIX (rule): {fix}\n\n"
            f"WRONG (do NOT write this):\n```verilog\n{wrong}\n```\n\n"
            f"RIGHT:\n```verilog\n{right}\n```\n"
        )
        rid = "fix_" + hashlib.sha1(sig.lower().encode()).hexdigest()[:16]
        ok = mem.remember("fix", body, source="seed:verilog-rules",
                          title=("fix: " + sig)[:120], tags="fix lesson verilog-rule seed",
                          object_key=rid, meta={"error_sig": sig})
        if ok:
            n += 1
            print(f"  ✓ {sig}")
    print(f"\nSeeded {n}/{len(LESSONS)} Verilog fix lessons into the knowledge store (kind=fix).")
    print("stats:", mem.stats())


if __name__ == "__main__":
    main()
