`include "shared_header.vh"

module cgra_top (
    input  wire                    clk,
    input  wire                    rst_n,        // async active-low reset

    // ---- configuration / control port -------------------------------------
    input  wire                    cfg_start,    // 1 = begin RUN after load
    input  wire                    cfg_we,       // write enable for config_mem
    input  wire [1:0]              cfg_pe_sel,   // which PE config to write (0..3)
    input  wire [`CFG_AW-1:0]      cfg_addr,     // config entry address
    input  wire [`CFG_W-1:0]       cfg_wdata,    // config word to write

    // ---- external data ingress (chip I/O) -------------------------------
    input  wire [`DATA_W-1:0]      data_in_top_0,
    input  wire [`DATA_W-1:0]      data_in_top_1,
    input  wire [`DATA_W-1:0]      data_in_right_0,
    input  wire [`DATA_W-1:0]      data_in_right_1,
    input  wire [`DATA_W-1:0]      data_in_bot_0,
    input  wire [`DATA_W-1:0]      data_in_bot_1,
    input  wire [`DATA_W-1:0]      data_in_left_0,
    input  wire [`DATA_W-1:0]      data_in_left_1,

    // ---- external data egress (chip I/O) --------------------------------
    output wire [`DATA_W-1:0]      data_out_top_0,
    output wire [`DATA_W-1:0]      data_out_top_1,
    output wire [`DATA_W-1:0]      data_out_right_0,
    output wire [`DATA_W-1:0]      data_out_right_1,
    output wire [`DATA_W-1:0]      data_out_bot_0,
    output wire [`DATA_W-1:0]      data_out_bot_1,
    output wire [`DATA_W-1:0]      data_out_left_0,
    output wire [`DATA_W-1:0]      data_out_left_1,

    // ---- per-PE observation outputs --------------------------------------
    output wire [`DATA_W-1:0]      pe_out0,
    output wire [`DATA_W-1:0]      pe_out1,
    output wire [`DATA_W-1:0]      pe_out2,
    output wire [`DATA_W-1:0]      pe_out3,

    // ---- status ----------------------------------------------------------
    output wire                    run_active    // 1 when FSM is in RUN
);

    // ------------------------------------------------------------------------
    // Control FSM:  IDLE -> LOAD -> RUN
    //   IDLE : hold; wait for rst_n deassert.
    //   LOAD : accept config writes; transition to RUN on cfg_start.
    //   RUN  : broadcast config to PEs; stay until reset.
    // ------------------------------------------------------------------------
    localparam FSM_IDLE = 2'd0;
    localparam FSM_LOAD = 2'd1;
    localparam FSM_RUN  = 2'd2;

    reg [1:0] fsm_state, fsm_next;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            fsm_state <= FSM_IDLE;
        else
            fsm_state <= fsm_next;
    end

    always @(*) begin
        case (fsm_state)
            FSM_IDLE: fsm_next = FSM_LOAD;
            FSM_LOAD: fsm_next = cfg_start ? FSM_RUN : FSM_LOAD;
            FSM_RUN:  fsm_next = FSM_RUN;
            default:  fsm_next = FSM_IDLE;
        endcase
    end

    assign run_active = (fsm_state == FSM_RUN);

    // ------------------------------------------------------------------------
    // Per-PE config memory write enables.
    //   Writes are only accepted while in LOAD (or IDLE->LOAD) state.
    //   cfg_pe_sel selects which of the 4 PE config memories is targeted.
    // ------------------------------------------------------------------------
    wire cfg_we_gated = cfg_we & (fsm_state != FSM_RUN);
    wire we0 = cfg_we_gated & (cfg_pe_sel == 2'd0);
    wire we1 = cfg_we_gated & (cfg_pe_sel == 2'd1);
    wire we2 = cfg_we_gated & (cfg_pe_sel == 2'd2);
    wire we3 = cfg_we_gated & (cfg_pe_sel == 2'd3);

    // ------------------------------------------------------------------------
    // Four config memories (one per PE).  All share the same address bus;
    // only the selected PE's memory accepts a write.
    // ------------------------------------------------------------------------
    wire [`CFG_W-1:0] cfg0, cfg1, cfg2, cfg3;

    config_mem cm0 (
        .clk(clk), .rst_n(rst_n),
        .cfg_we(we0), .cfg_addr(cfg_addr), .cfg_wdata(cfg_wdata),
        .cfg_out(cfg0)
    );
    config_mem cm1 (
        .clk(clk), .rst_n(rst_n),
        .cfg_we(we1), .cfg_addr(cfg_addr), .cfg_wdata(cfg_wdata),
        .cfg_out(cfg1)
    );
    config_mem cm2 (
        .clk(clk), .rst_n(rst_n),
        .cfg_we(we2), .cfg_addr(cfg_addr), .cfg_wdata(cfg_wdata),
        .cfg_out(cfg2)
    );
    config_mem cm3 (
        .clk(clk), .rst_n(rst_n),
        .cfg_we(we3), .cfg_addr(cfg_addr), .cfg_wdata(cfg_wdata),
        .cfg_out(cfg3)
    );

    // ------------------------------------------------------------------------
    // I/O pads: register external <-> grid boundary signals.
    // ------------------------------------------------------------------------
    wire [`DATA_W-1:0] gin_top_0,  gin_top_1,  gin_right_0,  gin_right_1;
    wire [`DATA_W-1:0] gin_bot_0,  gin_bot_1,  gin_left_0,  gin_left_1;
    wire [`DATA_W-1:0] gout_top_0, gout_top_1, gout_right_0, gout_right_1;
    wire [`DATA_W-1:0] gout_bot_0, gout_bot_1, gout_left_0, gout_left_1;

    io_pad pads (
        .clk(clk), .rst_n(rst_n),
        // external ingress
        .data_in_top_0(data_in_top_0),   .data_in_top_1(data_in_top_1),
        .data_in_right_0(data_in_right_0), .data_in_right_1(data_in_right_1),
        .data_in_bot_0(data_in_bot_0),   .data_in_bot_1(data_in_bot_1),
        .data_in_left_0(data_in_left_0), .data_in_left_1(data_in_left_1),
        // external egress
        .data_out_top_0(data_out_top_0),   .data_out_top_1(data_out_top_1),
        .data_out_right_0(data_out_right_0), .data_out_right_1(data_out_right_1),
        .data_out_bot_0(data_out_bot_0),   .data_out_bot_1(data_out_bot_1),
        .data_out_left_0(data_out_left_0), .data_out_left_1(data_out_left_1),
        // grid-side ingress (to grid)
        .grid_in_top_0(gin_top_0),   .grid_in_top_1(gin_top_1),
        .grid_in_right_0(gin_right_0), .grid_in_right_1(gin_right_1),
        .grid_in_bot_0(gin_bot_0),   .grid_in_bot_1(gin_bot_1),
        .grid_in_left_0(gin_left_0), .grid_in_left_1(gin_left_1),
        // grid-side egress (from grid)
        .grid_out_top_0(gout_top_0),   .grid_out_top_1(gout_top_1),
        .grid_out_right_0(gout_right_0), .grid_out_right_1(gout_right_1),
        .grid_out_bot_0(gout_bot_0),   .grid_out_bot_1(gout_bot_1),
        .grid_out_left_0(gout_left_0), .grid_out_left_1(gout_left_1)
    );

    // ------------------------------------------------------------------------
    // 2x2 PE grid.
    // ------------------------------------------------------------------------
    pe_grid grid (
        .clk(clk), .rst_n(rst_n),
        .cfg_pe0(cfg0), .cfg_pe1(cfg1), .cfg_pe2(cfg2), .cfg_pe3(cfg3),
        // boundary inputs (from pads)
        .in_top_0(gin_top_0),   .in_top_1(gin_top_1),
        .in_right_0(gin_right_0), .in_right_1(gin_right_1),
        .in_bot_0(gin_bot_0),   .in_bot_1(gin_bot_1),
        .in_left_0(gin_left_0), .in_left_1(gin_left_1),
        // boundary outputs (to pads)
        .out_top_0(gout_top_0),   .out_top_1(gout_top_1),
        .out_right_0(gout_right_0), .out_right_1(gout_right_1),
        .out_bot_0(gout_bot_0),   .out_bot_1(gout_bot_1),
        .out_left_0(gout_left_0), .out_left_1(gout_left_1),
        // observation
        .pe_out0(pe_out0), .pe_out1(pe_out1),
        .pe_out2(pe_out2), .pe_out3(pe_out3)
    );

endmodule