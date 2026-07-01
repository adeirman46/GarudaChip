`include "shared_header.vh"

//============================================================================
// module pe — single Processing Element
//
// 16-bit fixed-point ALU with a 16x16 register file and a 32-bit MAC
// accumulator.  Neighbor outputs (n/s/e/w) are REGISTERED so there is NO
// combinational path from a neighbor input through the ALU back out to a
// neighbor output — that would form a combinational loop across the mesh
// (Verilator UNOPTFLAT).  The registered output holds the last computed
// alu_result that was routed in that direction; when the route bit is
// clear the register holds 0.
//
// NOTE on declaration order: Yosys's Verilog frontend does NOT support
// forward references — every net/reg must be DECLARED before it is USED.
// The register-file read ports (rdata_a/rdata_b) are consumed by the
// input-mux always blocks, so their registers AND wire aliases are
// declared at the TOP of the module body, ahead of the muxes.  The RF
// write always block (further down) only *assigns* those already-declared
// registers, which is legal.
//============================================================================
module pe (
    input  wire        clk,          // system clock
    input  wire        rst_n,        // async active-low reset
    input  wire        exec_en,      // execution enable (drives RF writeback)
    input  wire [31:0] cfg_word,     // active config word for this PE

    // ---- Neighbor data inputs (from adjacent PEs / IOBs) ----
    input  wire [15:0] n_in,         // data from North neighbor
    input  wire [15:0] s_in,         // data from South neighbor
    input  wire [15:0] e_in,         // data from East neighbor
    input  wire [15:0] w_in,         // data from West neighbor
    input  wire [15:0] io_in,        // external IOB data (boundary PEs only)

    // ---- Neighbor data outputs (registered, no comb mesh path) ----
    output wire [15:0] n_out,        // data to North neighbor
    output wire [15:0] s_out,        // data to South neighbor
    output wire [15:0] e_out,        // data to East neighbor
    output wire [15:0] w_out,        // data to West neighbor

    // ---- External IOB output (boundary PEs route result off-chip) ----
    output wire [15:0] io_out
);

    //------------------------------------------------------------------
    // Decode config word fields
    //------------------------------------------------------------------
    wire [3:0]  opcode   = cfg_word[`CFG_OPCODE];
    wire [3:0]  waddr    = cfg_word[`CFG_WADDR];
    wire [3:0]  raddr_a  = cfg_word[`CFG_RADDR_A];
    wire [3:0]  raddr_b  = cfg_word[`CFG_RADDR_B];
    wire [3:0]  muxa_sel = cfg_word[`CFG_MUXA];
    wire [3:0]  muxb_sel = cfg_word[`CFG_MUXB];
    wire [3:0]  route    = cfg_word[`CFG_ROUTE];
    wire [15:0] imm      = {{12{cfg_word[3]}}, cfg_word[`CFG_IMM]}; // sign-extend

    //------------------------------------------------------------------
    // Register file storage + read ports — DECLARED EARLY.
    // The input muxes below read rdata_a / rdata_b, so these must exist
    // before the mux always blocks.  The synchronous write of
    // rdata_a_r / rdata_b_r happens in the RF always block further down
    // (assigning an already-declared reg is legal in Verilog/Yosys).
    //------------------------------------------------------------------
    reg  [15:0] rf [0:`RF_DEPTH-1];
    reg  [15:0] rdata_a_r;
    reg  [15:0] rdata_b_r;
    wire [15:0] rdata_a = rdata_a_r;
    wire [15:0] rdata_b = rdata_b_r;

    //------------------------------------------------------------------
    // Input routing muxes — select operand A and operand B
    //------------------------------------------------------------------
    reg  [15:0] op_a;
    reg  [15:0] op_b;
    always @(*) begin
        case (muxa_sel)
            `SEL_N  : op_a = n_in;
            `SEL_S  : op_a = s_in;
            `SEL_E  : op_a = e_in;
            `SEL_W  : op_a = w_in;
            `SEL_RF : op_a = rdata_a;
            `SEL_IMM: op_a = imm;
            `SEL_ZERO: op_a = 16'h0;
            `SEL_IO : op_a = io_in;
            default : op_a = 16'h0;
        endcase
    end

    always @(*) begin
        case (muxb_sel)
            `SEL_N  : op_b = n_in;
            `SEL_S  : op_b = s_in;
            `SEL_E  : op_b = e_in;
            `SEL_W  : op_b = w_in;
            `SEL_RF : op_b = rdata_b;
            `SEL_IMM: op_b = imm;
            `SEL_ZERO: op_b = 16'h0;
            `SEL_IO : op_b = io_in;
            default : op_b = 16'h0;
        endcase
    end

    //------------------------------------------------------------------
    // ALU datapath wires
    //------------------------------------------------------------------
    wire signed [15:0] a_s = op_a;
    wire signed [15:0] b_s = op_b;

    // 32-bit accumulator (Q2.30) for MAC
    reg  signed [31:0] acc;       // current accumulator value
    wire signed [31:0] mul_ext = a_s * b_s;            // Q1.15*Q1.15 = Q2.30 (32-bit)
    wire signed [31:0] add_ext = {{16{a_s[15]}}, a_s} + {{16{b_s[15]}}, b_s};
    wire signed [31:0] sub_ext = {{16{a_s[15]}}, a_s} - {{16{b_s[15]}}, b_s};

    // combinational ALU result (16-bit) and next accumulator.
    reg  [15:0]        alu_result;
    reg  signed [31:0] acc_next;

    //------------------------------------------------------------------
    // saturation to Q1.15 range
    //------------------------------------------------------------------
    function [15:0] saturate;
        input signed [31:0] val;
        begin
            if (val > 32'sd32767)
                saturate = 16'h7FFF;
            else if (val < -32'sd32768)
                saturate = 16'h8000;
            else
                saturate = val[15:0];
        end
    endfunction

    //------------------------------------------------------------------
    // ALU — 16-bit fixed-point with 32-bit MAC accumulator
    //------------------------------------------------------------------
    always @(*) begin
        acc_next = acc;          // default: hold accumulator
        case (opcode)
            `OP_NOP:     alu_result = op_a;
            `OP_ADD:     begin alu_result = saturate(add_ext); end
            `OP_SUB:     begin alu_result = saturate(sub_ext); end
            `OP_MUL:     begin alu_result = mul_ext[30:15]; end
            `OP_MAC:     begin acc_next = acc + mul_ext; alu_result = saturate(acc_next); end
            `OP_SHL:     alu_result = op_a << b_s[3:0];
            `OP_SHR:     alu_result = a_s >>> b_s[3:0];
            `OP_AND:     alu_result = op_a & op_b;
            `OP_OR:      alu_result = op_a | op_b;
            `OP_XOR:     alu_result = op_a ^ op_b;
            `OP_NOT:     alu_result = ~op_a;
            `OP_ABS:     alu_result = (a_s[15]) ? -a_s : op_a;
            `OP_MIN:     alu_result = (a_s < b_s) ? op_a : op_b;
            `OP_MAX:     alu_result = (a_s > b_s) ? op_a : op_b;
            `OP_PASS_B:  alu_result = op_b;
            `OP_ACC_CLR: begin acc_next = 32'sd0; alu_result = 16'h0; end
            default:     alu_result = 16'h0;
        endcase
    end

    //------------------------------------------------------------------
    // Register file: 16 x 16-bit, dual-read, single-write
    // (storage + read-port regs declared at top; this block only writes.)
    //------------------------------------------------------------------
    integer ri;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (ri = 0; ri < `RF_DEPTH; ri = ri + 1)
                rf[ri] <= 16'h0;
            rdata_a_r <= 16'h0;
            rdata_b_r <= 16'h0;
        end else begin
            // synchronous read (registered) for 2-stage pipeline timing
            rdata_a_r <= rf[raddr_a];
            rdata_b_r <= rf[raddr_b];
            // writeback of ALU result
            if (exec_en && (opcode != `OP_NOP) && (opcode != `OP_ACC_CLR))
                rf[waddr] <= alu_result;
        end
    end

    // register the accumulator
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            acc <= 32'sd0;
        else if (exec_en)
            acc <= acc_next;
    end

    //------------------------------------------------------------------
    // Output routing — REGISTERED neighbor ports.
    // The route field is cfg_word[7:4], a 4-bit vector:
    //   route[0] = North output  (n_out)
    //   route[1] = South output  (s_out)
    //   route[2] = East  output  (e_out)
    //   route[3] = West  output  (w_out)
    //
    // The mesh-facing outputs are REGISTERED so there is no combinational
    // path:  neighbor_in -> op_a/op_b -> alu_result -> neighbor_out.
    // That path would form a combinational cycle across the 2x2 mesh
    // (Verilator UNOPTFLAT).  By registering n/s/e/w_out we break the
    // loop with a flip-flop: a PE reads a neighbor's *previous-cycle*
    // output, computes, and presents its own result on the NEXT cycle.
    // This matches the reference CGRA, which pipelines inter-PE data
    // through DelayPipe/RF stages.
    //
    // When a route bit is set, the register captures alu_result; when
    // clear it captures 0.  A receiving PE only reads a neighbor port
    // when its input mux selects that direction, so an unrouted zero
    // value is harmlessly ignored.
    //
    // io_out is REGISTERED (unchanged) so the host can sample the last
    // computed result after `done`.
    //------------------------------------------------------------------
    reg [15:0] n_out_r, s_out_r, e_out_r, w_out_r;
    reg [15:0] io_out_r;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            n_out_r  <= 16'h0;
            s_out_r  <= 16'h0;
            e_out_r  <= 16'h0;
            w_out_r  <= 16'h0;
            io_out_r <= 16'h0;
        end else if (exec_en) begin
            n_out_r  <= route[0] ? alu_result : 16'h0;
            s_out_r  <= route[1] ? alu_result : 16'h0;
            e_out_r  <= route[2] ? alu_result : 16'h0;
            w_out_r  <= route[3] ? alu_result : 16'h0;
            if (|route)
                io_out_r <= alu_result;
        end
    end

    assign n_out  = n_out_r;
    assign s_out  = s_out_r;
    assign e_out  = e_out_r;
    assign w_out  = w_out_r;
    assign io_out = io_out_r;

endmodule