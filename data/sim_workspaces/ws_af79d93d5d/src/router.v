`include "shared_header.vh"

module router (
    // ---- Data ports (16-bit fabric links) ----
    input  wire [15:0] data_n_in,    // from North neighbor router
    input  wire [15:0] data_s_in,    // from South neighbor router
    input  wire [15:0] data_e_in,    // from East neighbor router
    input  wire [15:0] data_w_in,    // from West neighbor router
    input  wire [15:0] data_l_in,    // from local PE (PE output)

    output wire [15:0] data_n_out,   // to North neighbor router
    output wire [15:0] data_s_out,   // to South neighbor router
    output wire [15:0] data_e_out,   // to East neighbor router
    output wire [15:0] data_w_out,   // to West neighbor router
    output wire [15:0] data_l_out,   // to local PE (PE input)

    // ---- Static route selects (one 3-bit select per output port) ----
    // Each select chooses which INPUT port drives that OUTPUT port.
    input  wire [2:0]  sel_n_out,   // source for North output
    input  wire [2:0]  sel_s_out,   // source for South output
    input  wire [2:0]  sel_e_out,   // source for East output
    input  wire [2:0]  sel_w_out,   // source for West output
    input  wire [2:0]  sel_l_out    // source for Local output
);

    //------------------------------------------------------------------
    // Crossbar: each output port muxes among the five input ports.
    // Encoding: 0=N, 1=S, 2=E, 3=W, 4=Local, 5/6/7 = zero
    //------------------------------------------------------------------
    function [15:0] xbar;
        input [2:0] sel;
        begin
            case (sel)
                3'd0: xbar = data_n_in;
                3'd1: xbar = data_s_in;
                3'd2: xbar = data_e_in;
                3'd3: xbar = data_w_in;
                3'd4: xbar = data_l_in;
                default: xbar = 16'h0;
            endcase
        end
    endfunction

    assign data_n_out = xbar(sel_n_out);
    assign data_s_out = xbar(sel_s_out);
    assign data_e_out = xbar(sel_e_out);
    assign data_w_out = xbar(sel_w_out);
    assign data_l_out = xbar(sel_l_out);

endmodule