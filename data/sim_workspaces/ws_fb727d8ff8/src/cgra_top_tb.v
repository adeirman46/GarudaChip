`include "shared_header.vh"

module cgra_top_tb;
    reg clk;
    initial clk = 0;
    always #5 clk = ~clk;

    reg rst_n;
    reg cfg_start;
    reg cfg_we;
    reg [1:0] cfg_pe_sel;
    reg [`CFG_AW-1:0] cfg_addr;
    reg [`CFG_W-1:0] cfg_wdata;
    reg [`DATA_W-1:0] data_in_top_0;
    reg [`DATA_W-1:0] data_in_top_1;
    reg [`DATA_W-1:0] data_in_right_0;
    reg [`DATA_W-1:0] data_in_right_1;
    reg [`DATA_W-1:0] data_in_bot_0;
    reg [`DATA_W-1:0] data_in_bot_1;
    reg [`DATA_W-1:0] data_in_left_0;
    reg [`DATA_W-1:0] data_in_left_1;

    wire [`DATA_W-1:0] data_out_top_0;
    wire [`DATA_W-1:0] data_out_top_1;
    wire [`DATA_W-1:0] data_out_right_0;
    wire [`DATA_W-1:0] data_out_right_1;
    wire [`DATA_W-1:0] data_out_bot_0;
    wire [`DATA_W-1:0] data_out_bot_1;
    wire [`DATA_W-1:0] data_out_left_0;
    wire [`DATA_W-1:0] data_out_left_1;
    wire [`DATA_W-1:0] pe_out0;
    wire [`DATA_W-1:0] pe_out1;
    wire [`DATA_W-1:0] pe_out2;
    wire [`DATA_W-1:0] pe_out3;
    wire run_active;

    integer pass;

    cgra_top dut (
        .clk(clk),
        .rst_n(rst_n),
        .cfg_start(cfg_start),
        .cfg_we(cfg_we),
        .cfg_pe_sel(cfg_pe_sel),
        .cfg_addr(cfg_addr),
        .cfg_wdata(cfg_wdata),
        .data_in_top_0(data_in_top_0),
        .data_in_top_1(data_in_top_1),
        .data_in_right_0(data_in_right_0),
        .data_in_right_1(data_in_right_1),
        .data_in_bot_0(data_in_bot_0),
        .data_in_bot_1(data_in_bot_1),
        .data_in_left_0(data_in_left_0),
        .data_in_left_1(data_in_left_1),
        .data_out_top_0(data_out_top_0),
        .data_out_top_1(data_out_top_1),
        .data_out_right_0(data_out_right_0),
        .data_out_right_1(data_out_right_1),
        .data_out_bot_0(data_out_bot_0),
        .data_out_bot_1(data_out_bot_1),
        .data_out_left_0(data_out_left_0),
        .data_out_left_1(data_out_left_1),
        .pe_out0(pe_out0),
        .pe_out1(pe_out1),
        .pe_out2(pe_out2),
        .pe_out3(pe_out3),
        .run_active(run_active)
    );

    initial begin
        $dumpfile("design.vcd");
        $dumpvars(0, cgra_top_tb);

        pass = 1;

        rst_n = 0;
        cfg_start = 0;
        cfg_we = 0;
        cfg_pe_sel = 0;
        cfg_addr = 0;
        cfg_wdata = 0;
        data_in_top_0 = 0;
        data_in_top_1 = 0;
        data_in_right_0 = 0;
        data_in_right_1 = 0;
        data_in_bot_0 = 0;
        data_in_bot_1 = 0;
        data_in_left_0 = 0;
        data_in_left_1 = 0;

        #15;
        rst_n = 1;

        @(posedge clk);
        #1;
        if (run_active !== 1'b0) pass = 0;

        @(posedge clk);
        #1;
        if (run_active !== 1'b0) pass = 0;

        cfg_we = 1;
        cfg_pe_sel = 2'd0;
        cfg_addr = 0;
        cfg_wdata = 32'hAAAA_AAAA;
        @(posedge clk);
        #1;
        cfg_we = 0;

        @(posedge clk);
        #1;
        if (run_active !== 1'b0) pass = 0;

        cfg_start = 1;
        @(posedge clk);
        #1;
        cfg_start = 0;

        @(posedge clk);
        #1;
        if (run_active !== 1'b1) pass = 0;

        @(posedge clk);
        #1;
        if (run_active !== 1'b1) pass = 0;

        if (pass) $display("Result: PASSED");
        else $display("Result: FAILED");

        $finish;
    end
endmodule