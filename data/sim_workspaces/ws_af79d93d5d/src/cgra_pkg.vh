//============================================================================
// cgra_pkg.vh — CGRA 2x2 Accelerator
// Global parameters: grid dimensions, opcodes, and data widths.
// Include with:  `include "cgra_pkg.vh"
//============================================================================
`ifndef CGRA_PKG_VH
`define CGRA_PKG_VH

// ---- Grid dimensions ----
`define ROWS        2       // number of rows in the PE grid
`define COLS        2       // number of columns in the PE grid
`define NUM_PES     4       // ROWS * COLS

// ---- Datapath widths ----
`define DATA_W      32      // 32-bit data width (matches reference DW=32)
`define ACC_W       32      // accumulator width for MAC
`define ADDR_W      5       // data memory address width (32 entries)
`define DATA_DEPTH  32      // data scratchpad depth

// ---- Register file ----
`define RF_DEPTH    16      // 16 registers per PE
`define RF_AW       4       // 4-bit RF address (log2(16))

// ---- Configuration memory ----
`define CFG_W       32      // 32-bit config word per PE
`define CFG_DEPTH   32      // 32 config words per PE (config schedule slots)
`define CFG_AW      5       // 5-bit config address (log2(32))

// ---- ALU opcodes (4-bit) ----
`define OP_NOP      4'd0    // no operation / pass A
`define OP_ADD      4'd1    // a + b  (saturating)
`define OP_SUB      4'd2    // a - b  (saturating)
`define OP_MUL      4'd3    // a * b  (take lower 32 bits)
`define OP_MAC      4'd4    // acc + a*b  (32-bit accumulate, saturate on wb)
`define OP_SHL      4'd5    // a << b[3:0]
`define OP_SHR      4'd6    // a >> b[3:0] (arithmetic)
`define OP_AND      4'd7    // a & b
`define OP_OR       4'd8    // a | b
`define OP_XOR      4'd9    // a ^ b
`define OP_NOT      4'd10   // ~a
`define OP_ABS      4'd11   // |a| (absolute value)
`define OP_MIN      4'd12   // min(a,b)
`define OP_MAX      4'd13   // max(a,b)
`define OP_PASS_B   4'd14   // pass operand B unchanged
`define OP_ACC_CLR  4'd15   // clear accumulator

// ---- Routing mux selects (3-bit per direction) ----
// Selects which source feeds each PE input port.
`define SEL_N       3'd0    // North neighbor
`define SEL_S       3'd1    // South neighbor
`define SEL_E       3'd2    // East neighbor
`define SEL_W       3'd3    // West neighbor
`define SEL_RF      3'd4    // local register file read port
`define SEL_IMM     3'd5    // immediate from config word
`define SEL_ZERO    3'd6    // constant zero
`define SEL_IO      3'd7    // external IOB input

// ---- Config word field layout (32 bits) ----
// [31:28] opcode
// [27:24] RF write address
// [23:20] RF read addr A
// [19:16] RF read addr B
// [15:12] mux A select
// [11:8]  mux B select
// [7:4]   output route select (which neighbor gets the result)
// [3:0]   immediate/constant low nibble (sign-extended to 16b)
`define CFG_OPCODE  31:28
`define CFG_WADDR   27:24
`define CFG_RADDR_A 23:20
`define CFG_RADDR_B 19:16
`define CFG_MUXA    15:12
`define CFG_MUXB    11:8
`define CFG_ROUTE   7:4
`define CFG_IMM     3:0

// ---- Controller FSM states ----
`define ST_IDLE     2'd0
`define ST_CONFIG   2'd1
`define ST_EXEC     2'd2
`define ST_DONE     2'd3

`endif // CGRA_PKG_VH