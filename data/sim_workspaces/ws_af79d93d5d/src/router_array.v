`include "shared_header.vh"

module router_array (
    input  wire             clk,
    input  wire             rst_n,

    // ---- Per-router local data port (to/from PE) ----
    input  wire [15:0]      pe_out  [0:`NUM_PES-1],  // PE -> router Local-in
    output wire [15:0]      pe_in   [0:`NUM_PES-1],  // router Local-out -> PE

    // ---- Per-router route selects (5 x 3-bit per router) ----
    input  wire [2:0]       sel_n   [0:`NUM_PES-1],
    input  wire [2:0]       sel_s   [0:`NUM_PES-1],
    input  wire [2:0]       sel_e   [0:`NUM_PES-1],
    input  wire [2:0]       sel_w   [0:`NUM_PES-1],
    input  wire [2:0]       sel_l   [0:`NUM_PES-1],

    // ---- Boundary IO injection (perimeter) ----
    // External data can be injected at the mesh boundary. We provide a
    // simple broadcast: io_in feeds the North input of the top-row routers
    // and the West input of the left-column routers.
    input  wire [15:0]      io_in
);

    //------------------------------------------------------------------
    // Router-to-router link nets (indexed [row][col])
    //------------------------------------------------------------------
    // data flowing OUT of router (r,c) toward a neighbor
    wire [15:0] n_out_net [0:`ROWS-1][0:`COLS-1];
    wire [15:0] s_out_net [0:`ROWS-1][0:`COLS-1];
    wire [15:0] e_out_net [0:`ROWS-1][0:`COLS-1];
    wire [15:0] w_out_net [0:`ROWS-1][0:`COLS-1];

    // data flowing INTO router (r,c) from a neighbor (or boundary)
    wire [15:0] n_in_net  [0:`ROWS-1][0:`COLS-1];
    wire [15:0] s_in_net  [0:`ROWS-1][0:`COLS-1];
    wire [15:0] e_in_net  [0:`ROWS-1][0:`COLS-1];
    wire [15:0] w_in_net  [0:`ROWS-1][0:`COLS-1];

    //------------------------------------------------------------------
    // Instantiate the 2x2 router grid
    //------------------------------------------------------------------
    genvar r, c;
    generate
        for (r = 0; r < `ROWS; r = r + 1) begin : row_g
            for (c = 0; c < `COLS; c = c + 1) begin : col_g
                router router_inst (
                    .data_n_in  (n_in_net [r][c]),
                    .data_s_in  (s_in_net [r][c]),
                    .data_e_in  (e_in_net [r][c]),
                    .data_w_in  (w_in_net [r][c]),
                    .data_l_in  (pe_out   [r*`COLS + c]),

                    .data_n_out (n_out_net[r][c]),
                    .data_s_out (s_out_net[r][c]),
                    .data_e_out (e_out_net[r][c]),
                    .data_w_out (w_out_net[r][c]),
                    .data_l_out (pe_in    [r*`COLS + c]),

                    .sel_n_out  (sel_n [r*`COLS + c]),
                    .sel_s_out  (sel_s [r*`COLS + c]),
                    .sel_e_out  (sel_e [r*`COLS + c]),
                    .sel_w_out  (sel_w [r*`COLS + c]),
                    .sel_l_out  (sel_l [r*`COLS + c])
                );
            end
        end
    endgenerate

    //------------------------------------------------------------------
    // Mesh wiring: connect adjacent routers
    //------------------------------------------------------------------
    generate
        for (r = 0; r < `ROWS; r = r + 1) begin : row_w
            for (c = 0; c < `COLS; c = c + 1) begin : col_w
                // North input: from the router above's South output;
                // top row gets boundary IO (io_in broadcast).
                if (r == 0)
                    assign n_in_net[r][c] = io_in;
                else
                    assign n_in_net[r][c] = s_out_net[r-1][c];

                // South input: from the router below's North output;
                // bottom row gets zero (no neighbor).
                if (r == `ROWS-1)
                    assign s_in_net[r][c] = 16'h0;
                else
                    assign s_in_net[r][c] = n_out_net[r+1][c];

                // West input: from the router to the left's East output;
                // left column gets boundary IO (io_in broadcast).
                if (c == 0)
                    assign w_in_net[r][c] = io_in;
                else
                    assign w_in_net[r][c] = e_out_net[r][c-1];

                // East input: from the router to the right's West output;
                // right column gets zero (no neighbor).
                if (c == `COLS-1)
                    assign e_in_net[r][c] = 16'h0;
                else
                    assign e_in_net[r][c] = w_out_net[r][c+1];
            end
        end
    endgenerate

endmodule