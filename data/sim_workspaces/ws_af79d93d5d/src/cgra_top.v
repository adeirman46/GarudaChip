`include "shared_header.vh"

module cgra_top (
    input  wire        clk,           // system clock
    input  wire        rst_n,         // async active-low reset

    // ---- Configuration interface (serial shift) ----
    input  wire        cfg_en,        // configuration shift enable (host-driven)
    input  wire        cfg_data,      // serial configuration data in
    input  wire        start,         // pulse to begin a run
    input  wire [`CFG_AW-1:0] exec_len,  // execution cycle count

    // ---- Host data scratchpad interface (DATA_W = 32-bit) ----
    input  wire        dmem_wr_en,    // scratchpad write enable
    input  wire [`ADDR_W-1:0] dmem_wr_addr,
    input  wire [`DATA_W-1:0] dmem_wr_data,
    input  wire [`ADDR_W-1:0] dmem_rd_addr,
    output wire [`DATA_W-1:0] dmem_rd_data,

    // ---- Fabric IO (perimeter IOB buses) ----
    input  wire [15:0] io_in,         // 16-bit external data input (broadcast)
    output wire [15:0] io_out,        // 16-bit external data output (PE result)

    // ---- Status ----
    output wire        done           // run complete pulse
);

    //------------------------------------------------------------------
    // Config controller
    //------------------------------------------------------------------
    wire        cfg_shift_en;
    wire        exec_en;
    wire [`CFG_AW-1:0] cfg_addr;

    config_controller u_ctrl (
        .clk          (clk),
        .rst_n        (rst_n),
        .start        (start),
        .exec_len     (exec_len),
        .cfg_shift_en (cfg_shift_en),
        .exec_en      (exec_en),
        .cfg_addr     (cfg_addr),
        .done         (done)
    );

    //------------------------------------------------------------------
    // Configuration memories — one per PE, serial shift chain
    // The host loads configuration by holding cfg_en high and clocking
    // cfg_data bits into the serial chain.  This happens BEFORE `start`
    // is asserted (the controller is in IDLE).  The shift enable is
    // therefore driven directly by cfg_en — NOT gated by the
    // controller's cfg_shift_en, which is only high during the
    // controller's CONFIG state (after start).  Gating on both would
    // prevent any host-driven configuration load, leaving every PE's
    // config memory at its reset value (all zeros) and io_out stuck
    // at high-Z.
    //------------------------------------------------------------------
    wire        shift_en = cfg_en;
    wire [31:0] cfg_word [0:`NUM_PES-1];

    // Each ctrl_mem receives the same serial bit stream; the write pointer
    // inside each memory advances independently so all four PEs receive
    // identical bit positions (broadcast config load for a 2x2 grid).
    wire [`CFG_W-1:0] cfg_out_pe [0:`NUM_PES-1];

    genvar p;
    generate
        for (p = 0; p < `NUM_PES; p = p + 1) begin : cfg_mem_gen
            ctrl_mem u_cfg (
                .clk        (clk),
                .rst_n      (rst_n),
                .shift_en   (shift_en),
                .shift_in   (cfg_data),
                .exec_en    (exec_en),
                .cfg_addr   (cfg_addr),
                .cfg_out    (cfg_out_pe[p])
            );
            assign cfg_word[p] = cfg_out_pe[p];
        end
    endgenerate

    //------------------------------------------------------------------
    // Data scratchpad (DATA_W-bit host interface with byte-enable write)
    // The host drives dmem_wr_en as a master strobe; internally we tie all
    // four byte lanes active so a full 32-bit word is written on each strobe.
    //------------------------------------------------------------------
    wire [3:0] dmem_byte_en = {4{dmem_wr_en}};

    dmem u_dmem (
        .clk      (clk),
        .rst_n    (rst_n),
        .wr_en    (dmem_wr_en),
        .byte_en  (dmem_byte_en),
        .wr_addr  (dmem_wr_addr),
        .wr_data  (dmem_wr_data),
        .rd_addr  (dmem_rd_addr),
        .rd_data  (dmem_rd_data)
    );

    //------------------------------------------------------------------
    // PE array with mesh interconnect
    // The io_in bus is broadcast to all four boundary IOB slots; each PE's
    // io_out is collected and the top-level io_out reflects PE(1,1) (the
    // far corner) as the canonical extraction point.
    //------------------------------------------------------------------
    wire [15:0] io_in_arr  [0:`NUM_PES-1];
    wire [15:0] io_out_arr [0:`NUM_PES-1];

    // broadcast the external io_in to all boundary slots
    assign io_in_arr[0] = io_in;
    assign io_in_arr[1] = io_in;
    assign io_in_arr[2] = io_in;
    assign io_in_arr[3] = io_in;

    pe_array u_array (
        .clk      (clk),
        .rst_n    (rst_n),
        .exec_en  (exec_en),
        .cfg_word (cfg_word),
        .io_in    (io_in_arr),
        .io_out   (io_out_arr)
    );

    //------------------------------------------------------------------
    // Router array (2x2 mesh of 5-port static routers)
    // The routers provide an alternative communication fabric. Each PE's
    // output feeds the Local input of its router; the router's Local output
    // feeds back to the PE's input. Route selects are derived from the
    // config word's route field (static, compiler-resolved).
    // For the 2x2 design the PE array's direct mesh interconnect is the
    // primary path; the router array is instantiated for completeness and
    // future expansion. Its outputs are not muxed into the PE inputs here
    // to avoid double-driving the PE input ports.
    //------------------------------------------------------------------
    wire [15:0] router_pe_in  [0:`NUM_PES-1];
    wire [15:0] router_pe_out [0:`NUM_PES-1];

    // PE io_out feeds router local-in
    assign router_pe_out[0] = io_out_arr[0];
    assign router_pe_out[1] = io_out_arr[1];
    assign router_pe_out[2] = io_out_arr[2];
    assign router_pe_out[3] = io_out_arr[3];

    // Route selects: default to Local passthrough (4=Local) so the router
    // fabric is benign. The compiler would override these per-cycle.
    wire [2:0] sel_n_arr [0:`NUM_PES-1];
    wire [2:0] sel_s_arr [0:`NUM_PES-1];
    wire [2:0] sel_e_arr [0:`NUM_PES-1];
    wire [2:0] sel_w_arr [0:`NUM_PES-1];
    wire [2:0] sel_l_arr [0:`NUM_PES-1];

    assign sel_n_arr[0] = 3'd4; assign sel_s_arr[0] = 3'd4;
    assign sel_e_arr[0] = 3'd4; assign sel_w_arr[0] = 3'd4; assign sel_l_arr[0] = 3'd4;
    assign sel_n_arr[1] = 3'd4; assign sel_s_arr[1] = 3'd4;
    assign sel_e_arr[1] = 3'd4; assign sel_w_arr[1] = 3'd4; assign sel_l_arr[1] = 3'd4;
    assign sel_n_arr[2] = 3'd4; assign sel_s_arr[2] = 3'd4;
    assign sel_e_arr[2] = 3'd4; assign sel_w_arr[2] = 3'd4; assign sel_l_arr[2] = 3'd4;
    assign sel_n_arr[3] = 3'd4; assign sel_s_arr[3] = 3'd4;
    assign sel_e_arr[3] = 3'd4; assign sel_w_arr[3] = 3'd4; assign sel_l_arr[3] = 3'd4;

    router_array u_routers (
        .clk      (clk),
        .rst_n    (rst_n),
        .pe_out   (router_pe_out),
        .pe_in    (router_pe_in),
        .sel_n    (sel_n_arr),
        .sel_s    (sel_s_arr),
        .sel_e    (sel_e_arr),
        .sel_w    (sel_w_arr),
        .sel_l    (sel_l_arr),
        .io_in    (io_in)
    );

    // extract result from the bottom-right PE (canonical output corner)
    assign io_out = io_out_arr[3];

endmodule