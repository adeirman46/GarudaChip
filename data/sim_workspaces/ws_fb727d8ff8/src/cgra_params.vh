// cgra_params.vh
// ============================================================================
// Global parameter definitions for the 2x2 Coarse-Grained Reconfigurable Array.
// Included by every RTL module via `include "cgra_params.vh".
// ============================================================================

`ifndef CGRA_PARAMS_VH
`define CGRA_PARAMS_VH

// ----------------------------------------------------------------------------
// Grid dimensions
// ----------------------------------------------------------------------------
`define GRID_ROWS   2      // number of PE rows
`define GRID_COLS   2      // number of PE columns
`define NUM_PE      4      // total PEs (GRID_ROWS * GRID_COLS)

// ----------------------------------------------------------------------------
// Datapath width  (Q0.32 integer, 2's-complement, wrap-on-overflow)
// ----------------------------------------------------------------------------
`define DATA_W      32     // data / register width

// ----------------------------------------------------------------------------
// Per-PE register file
// ----------------------------------------------------------------------------
`define NUM_GPR     4      // general-purpose registers per PE
`define GPR_AW      2      // ceil(log2(NUM_GPR))

// ----------------------------------------------------------------------------
// Configuration / instruction word layout  (8-bit control word per PE)
//   [7:6] ALU opcode   (2 bits)
//   [5]   Carry-in     (1 bit)
//   [4:3] MuxA select  (2 bits)  — selects operand A source
//   [2:1] MuxB select  (2 bits)  — selects operand B source
//   [0]   Output route (1 bit)   — selects which neighbor gets the result
// ----------------------------------------------------------------------------
`define CFG_W       8      // configuration word width

`define ALU_OP_MSB  7
`define ALU_OP_LSB  6
`define CIN_BIT     5
`define MUXA_MSB    4
`define MUXA_LSB    3
`define MUXB_MSB    2
`define MUXB_LSB    1
`define ROUTE_BIT   0

`define ALU_OP_W    2      // 2-bit opcode field width
`define MUX_SEL_W   2      // 2-bit mux select field width

// ----------------------------------------------------------------------------
// ALU opcodes  (2-bit encoding)
// ----------------------------------------------------------------------------
`define ALU_ADD     2'd0   // A + B + Cin
`define ALU_SUB     2'd1   // A - B - Cin  (implemented as A + ~B + ~Cin)
`define ALU_AND     2'd2   // A & B
`define ALU_OR      2'd3   // A | B
// (XOR and right-shift are reached via the extended opcode space below when
//  a wider config word is available; the 2-bit core set covers add/sub/and/or.)

// ----------------------------------------------------------------------------
// Mux select encodings  (each 2 bits → 4 sources)
//   MuxA / MuxB select among: local GPR, North-in, East-in, West-in / South-in
// ----------------------------------------------------------------------------
`define MUX_LOCAL   2'd0   // local GPR operand
`define MUX_NORTH   2'd1   // north neighbor data
`define MUX_EAST    2'd2   // east neighbor data
`define MUX_WEST    2'd3   // west neighbor data  (MuxB uses south for variety)

// ----------------------------------------------------------------------------
// Configuration memory
// ----------------------------------------------------------------------------
`define CFG_DEPTH   16     // config entries per PE (small FF-based memory)
`define CFG_AW      4      // ceil(log2(CFG_DEPTH))

// ----------------------------------------------------------------------------
// I/O pad count (per side of the 2x2 grid)
// ----------------------------------------------------------------------------
`define IO_PER_SIDE 2      // one pad per boundary PE edge

`endif // CGRA_PARAMS_VH