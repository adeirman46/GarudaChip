`include "shared_header.vh"

//============================================================================
// pe_array.v — CGRA 2x2 PE array with mesh interconnect
//
// This file defines ONLY the pe_array module.  The pe (Processing Element)
// module is defined in pe.v and instantiated here.  Do NOT inline pe here —
// a duplicate module definition causes a compile error when both files are
// passed to the compiler.
//
// Interconnect: flat 1-D unpacked arrays (one element per PE, indexed by
// idx = r*COLS + c).  No tri-state, no packed buses, no indexed part-selects
// on port LHS — all Verilator-friendly constructs.
//============================================================================
module pe_array (
    input  wire             clk,
    input  wire             rst_n,
    input  wire             exec_en,

    // per-PE config words (one 32-bit instruction per PE)
    input  wire [31:0]      cfg_word [0:`NUM_PES-1],

    // external IOB data buses (boundary injection / extraction)
    input  wire [15:0]      io_in  [0:`NUM_PES-1],
    output wire [15:0]      io_out [0:`NUM_PES-1]
);

    //------------------------------------------------------------------
    // Flat 1-D neighbor nets (one word per PE, idx = r*COLS + c).
    // Each PE reads its neighbor's output; boundary PEs read io_in.
    //------------------------------------------------------------------
    wire [15:0] n_in_w  [0:`NUM_PES-1];
    wire [15:0] s_in_w  [0:`NUM_PES-1];
    wire [15:0] e_in_w  [0:`NUM_PES-1];
    wire [15:0] w_in_w  [0:`NUM_PES-1];

    wire [15:0] n_out_w [0:`NUM_PES-1];
    wire [15:0] s_out_w [0:`NUM_PES-1];
    wire [15:0] e_out_w [0:`NUM_PES-1];
    wire [15:0] w_out_w [0:`NUM_PES-1];

    //------------------------------------------------------------------
    // 2x2 PE grid instantiation.
    // PE ports connect to flat 1-D array elements (Verilator-safe).
    //------------------------------------------------------------------
    genvar r, c;
    generate
        for (r = 0; r < `ROWS; r = r + 1) begin : row
            for (c = 0; c < `COLS; c = c + 1) begin : col
                pe pe_inst (
                    .clk      (clk),
                    .rst_n    (rst_n),
                    .exec_en  (exec_en),
                    .cfg_word (cfg_word[r*`COLS + c]),

                    .n_in     (n_in_w [r*`COLS + c]),
                    .s_in     (s_in_w [r*`COLS + c]),
                    .e_in     (e_in_w [r*`COLS + c]),
                    .w_in     (w_in_w [r*`COLS + c]),
                    .io_in    (io_in [r*`COLS + c]),

                    .n_out    (n_out_w[r*`COLS + c]),
                    .s_out    (s_out_w[r*`COLS + c]),
                    .e_out    (e_out_w[r*`COLS + c]),
                    .w_out    (w_out_w[r*`COLS + c]),
                    .io_out   (io_out [r*`COLS + c])
                );
            end
        end
    endgenerate

    //------------------------------------------------------------------
    // Mesh interconnect.
    // In a 2x2 grid each PE input has at most ONE driver (a neighbor output
    // or the boundary io_in), so there is no contention.
    //   idx(r,c) = r*COLS + c
    //   North input of (r,c): south_out of (r-1,c), or io_in if top row
    //   South input of (r,c): north_out of (r+1,c), or io_in if bottom row
    //   West  input of (r,c): east_out  of (r,c-1), or io_in if left col
    //   East  input of (r,c): west_out  of (r,c+1), or io_in if right col
    //------------------------------------------------------------------
    generate
        for (r = 0; r < `ROWS; r = r + 1) begin : row_w
            for (c = 0; c < `COLS; c = c + 1) begin : col_w
                // North input
                if (r == 0)
                    assign n_in_w[r*`COLS + c] = io_in[r*`COLS + c];
                else
                    assign n_in_w[r*`COLS + c] = s_out_w[(r-1)*`COLS + c];

                // South input
                if (r == `ROWS-1)
                    assign s_in_w[r*`COLS + c] = io_in[r*`COLS + c];
                else
                    assign s_in_w[r*`COLS + c] = n_out_w[(r+1)*`COLS + c];

                // West input
                if (c == 0)
                    assign w_in_w[r*`COLS + c] = io_in[r*`COLS + c];
                else
                    assign w_in_w[r*`COLS + c] = e_out_w[r*`COLS + (c-1)];

                // East input
                if (c == `COLS-1)
                    assign e_in_w[r*`COLS + c] = io_in[r*`COLS + c];
                else
                    assign e_in_w[r*`COLS + c] = w_out_w[r*`COLS + (c+1)];
            end
        end
    endgenerate

endmodule