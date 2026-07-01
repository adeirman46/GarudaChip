`include "shared_header.vh"

module pe_grid (
    input  wire                    clk,
    input  wire                    rst_n,

    // per-PE configuration words (one per PE, from config_mem)
    input  wire [`CFG_W-1:0]       cfg_pe0,
    input  wire [`CFG_W-1:0]       cfg_pe1,
    input  wire [`CFG_W-1:0]       cfg_pe2,
    input  wire [`CFG_W-1:0]       cfg_pe3,

    // ---- boundary inputs (external data ingress, one per boundary edge) ---
    input  wire [`DATA_W-1:0]      in_top_0,   // -> PE0.n_in
    input  wire [`DATA_W-1:0]      in_top_1,   // -> PE1.n_in
    input  wire [`DATA_W-1:0]      in_right_0, // -> PE1.e_in
    input  wire [`DATA_W-1:0]      in_right_1, // -> PE3.e_in
    input  wire [`DATA_W-1:0]      in_bot_0,   // -> PE2.s_in
    input  wire [`DATA_W-1:0]      in_bot_1,   // -> PE3.s_in
    input  wire [`DATA_W-1:0]      in_left_0,  // -> PE0.w_in
    input  wire [`DATA_W-1:0]      in_left_1,  // -> PE2.w_in

    // ---- boundary outputs (external data egress) -------------------------
    output wire [`DATA_W-1:0]      out_top_0,  // PE0.n_out
    output wire [`DATA_W-1:0]      out_top_1,  // PE1.n_out
    output wire [`DATA_W-1:0]      out_right_0,// PE1.e_out
    output wire [`DATA_W-1:0]      out_right_1,// PE3.e_out
    output wire [`DATA_W-1:0]      out_bot_0,  // PE2.s_out
    output wire [`DATA_W-1:0]      out_bot_1,  // PE3.s_out
    output wire [`DATA_W-1:0]      out_left_0, // PE0.w_out
    output wire [`DATA_W-1:0]      out_left_1, // PE2.w_out

    // ---- per-PE observation outputs --------------------------------------
    output wire [`DATA_W-1:0]      pe_out0,
    output wire [`DATA_W-1:0]      pe_out1,
    output wire [`DATA_W-1:0]      pe_out2,
    output wire [`DATA_W-1:0]      pe_out3
);

    // ------------------------------------------------------------------------
    // Internal mesh wires — one wire per directed PE-to-PE link.
    // Naming: <src>_to_<dst>_<port-of-dst>
    // ------------------------------------------------------------------------
    // PE0 <-> PE1 (top row, horizontal)
    wire [`DATA_W-1:0] pe0_e;   // PE0.e_out  -> PE1.w_in
    wire [`DATA_W-1:0] pe1_w;   // PE1.w_out  -> PE0.e_in
    // PE0 <-> PE2 (left column, vertical)
    wire [`DATA_W-1:0] pe0_s;   // PE0.s_out  -> PE2.n_in
    wire [`DATA_W-1:0] pe2_n;   // PE2.n_out  -> PE0.s_in
    // PE1 <-> PE3 (right column, vertical)
    wire [`DATA_W-1:0] pe1_s;   // PE1.s_out  -> PE3.n_in
    wire [`DATA_W-1:0] pe3_n;   // PE3.n_out  -> PE1.s_in
    // PE2 <-> PE3 (bottom row, horizontal)
    wire [`DATA_W-1:0] pe2_e;   // PE2.e_out  -> PE3.w_in
    wire [`DATA_W-1:0] pe3_w;   // PE3.w_out  -> PE2.e_in

    // PE outputs that go only to the boundary (no neighbor in that direction)
    wire [`DATA_W-1:0] pe0_n, pe0_w;   // PE0 north, west  -> boundary
    wire [`DATA_W-1:0] pe1_n, pe1_e;   // PE1 north, east  -> boundary
    wire [`DATA_W-1:0] pe2_s, pe2_w;   // PE2 south, west  -> boundary
    wire [`DATA_W-1:0] pe3_s, pe3_e;   // PE3 south, east  -> boundary

    // ------------------------------------------------------------------------
    // PE0 — Top-Left
    //   N = boundary top_0,  W = boundary left_0
    //   E = PE1.w_out (pe1_w),  S = PE2.n_out (pe2_n)
    // ------------------------------------------------------------------------
    pe pe0 (
        .clk(clk), .rst_n(rst_n), .cfg(cfg_pe0),
        .n_in(in_top_0), .s_in(pe2_n), .e_in(pe1_w), .w_in(in_left_0),
        .n_out(pe0_n), .s_out(pe0_s), .e_out(pe0_e), .w_out(pe0_w),
        .pe_out(pe_out0)
    );

    // ------------------------------------------------------------------------
    // PE1 — Top-Right
    //   N = boundary top_1,  E = boundary right_0
    //   W = PE0.e_out (pe0_e),  S = PE3.n_out (pe3_n)
    // ------------------------------------------------------------------------
    pe pe1 (
        .clk(clk), .rst_n(rst_n), .cfg(cfg_pe1),
        .n_in(in_top_1), .s_in(pe3_n), .e_in(in_right_0), .w_in(pe0_e),
        .n_out(pe1_n), .s_out(pe1_s), .e_out(pe1_e), .w_out(pe1_w),
        .pe_out(pe_out1)
    );

    // ------------------------------------------------------------------------
    // PE2 — Bottom-Left
    //   N = PE0.s_out (pe0_s),  W = boundary left_1
    //   E = PE3.w_out (pe3_w),  S = boundary bot_0
    // ------------------------------------------------------------------------
    pe pe2 (
        .clk(clk), .rst_n(rst_n), .cfg(cfg_pe2),
        .n_in(pe0_s), .s_in(in_bot_0), .e_in(pe3_w), .w_in(in_left_1),
        .n_out(pe2_n), .s_out(pe2_s), .e_out(pe2_e), .w_out(pe2_w),
        .pe_out(pe_out2)
    );

    // ------------------------------------------------------------------------
    // PE3 — Bottom-Right
    //   N = PE1.s_out (pe1_s),  E = boundary right_1
    //   W = PE2.e_out (pe2_e),  S = boundary bot_1
    // ------------------------------------------------------------------------
    pe pe3 (
        .clk(clk), .rst_n(rst_n), .cfg(cfg_pe3),
        .n_in(pe1_s), .s_in(in_bot_1), .e_in(in_right_1), .w_in(pe2_e),
        .n_out(pe3_n), .s_out(pe3_s), .e_out(pe3_e), .w_out(pe3_w),
        .pe_out(pe_out3)
    );

    // ------------------------------------------------------------------------
    // Boundary output assignments
    // ------------------------------------------------------------------------
    assign out_top_0   = pe0_n;   // PE0 north
    assign out_top_1   = pe1_n;   // PE1 north
    assign out_right_0 = pe1_e;   // PE1 east
    assign out_right_1 = pe3_e;   // PE3 east
    assign out_bot_0   = pe2_s;   // PE2 south
    assign out_bot_1   = pe3_s;   // PE3 south
    assign out_left_0  = pe0_w;   // PE0 west
    assign out_left_1  = pe2_w;   // PE2 west

endmodule