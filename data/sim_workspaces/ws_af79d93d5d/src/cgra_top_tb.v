`include "shared_header.vh"

//============================================================================
// cgra_top_tb.v — self-checking testbench for cgra_top (CGRA 2x2)
//
// Written from scratch. The previous TB failed because it referenced an
// undefined `CFG_LENGTH macro (see context/research.md). This design has no
// such macro: the config-controller computes the total shift count internally
// as CFG_W*NUM_PES = 32*4 = 128 bits. We therefore drive exactly 128 serial
// config bits here, derived only from macros that actually exist in
// cgra_pkg.vh (CFG_W, NUM_PES).
//
// Checks performed:
//   1. dmem scratchpad write/read round-trip (host 32-bit interface).
//   2. Serial configuration load + execution run produces the expected PE
//      ALU result on io_out, and the `done` status pulse fires.
//============================================================================
module cgra_top_tb;

    // ---- Clock ----
    reg clk;
    always #5 clk = ~clk;

    // ---- DUT inputs (reg) ----
    reg                  cfg_en;
    reg                  cfg_data;
    reg                  start;
    reg  [`CFG_AW-1:0]   exec_len;
    reg                  dmem_wr_en;
    reg  [`ADDR_W-1:0]   dmem_wr_addr;
    reg  [`DATA_W-1:0]   dmem_wr_data;
    reg  [`ADDR_W-1:0]   dmem_rd_addr;
    reg                  rst_n;

    // ---- DUT outputs (wire) ----
    wire [`DATA_W-1:0]   dmem_rd_data;
    wire [15:0]          io_in;
    wire [15:0]          io_out;
    wire                 done;

    // ---- Test bookkeeping ----
    integer errors;
    integer i;
    integer cfg_total;          // total serial config bits = CFG_W * NUM_PES

    // Expected config word for slot 0 of every PE (broadcast):
    //   opcode  = OP_ADD  (4'd1)  -> bits [31:28]
    //   waddr   = 4'd0             -> bits [27:24]
    //   raddr_a = 4'd0             -> bits [23:20]
    //   raddr_b = 4'd0             -> bits [19:16]
    //   muxa_sel= SEL_IO (4'd7)    -> bits [15:12]
    //   muxb_sel= SEL_IMM(4'd5)    -> bits [11:8]
    //   route   = 5'b10000 (bit4=IO)-> bits [7:4]  (route[4]=1 drives io_out)
    //   imm     = 4'd3             -> bits [3:0]  (sign-extended to 16'sd3)
    // Result = io_in + 16'sd3.
    reg [`CFG_W-1:0] cfg_word_0;
    reg [15:0]       io_in_val;
    reg [15:0]       expected_io_out;

    // ---- DUT instance (by name) ----
    cgra_top dut (
        .clk          (clk),
        .rst_n        (rst_n),
        .cfg_en       (cfg_en),
        .cfg_data     (cfg_data),
        .start        (start),
        .exec_len     (exec_len),
        .dmem_wr_en   (dmem_wr_en),
        .dmem_wr_addr (dmem_wr_addr),
        .dmem_wr_data (dmem_wr_data),
        .dmem_rd_addr (dmem_rd_addr),
        .dmem_rd_data (dmem_rd_data),
        .io_in        (io_in),
        .io_out       (io_out),
        .done         (done)
    );

    // ---- VCD dump ----
    initial begin
        $dumpfile("design.vcd");
        $dumpvars(0, cgra_top_tb);
    end

    // ---- Helper task: check equality ----
    task check_equal;
        input [127:0] got;
        input [127:0] exp;
        input [255:0] name;
        begin
            if (got !== exp) begin
                $display("FAIL: %0s — got %0h, expected %0h", name, got, exp);
                errors = errors + 1;
            end else begin
                $display("OK:   %0s = %0h", name, got);
            end
        end
    endtask

    // ---- Main stimulus ----
    initial begin
        // initialize
        errors       = 0;
        clk          = 1'b0;
        rst_n        = 1'b0;
        cfg_en       = 1'b0;
        cfg_data     = 1'b0;
        start        = 1'b0;
        exec_len     = {`CFG_AW{1'b0}};
        dmem_wr_en   = 1'b0;
        dmem_wr_addr = {`ADDR_W{1'b0}};
        dmem_wr_data = {`DATA_W{1'b0}};
        dmem_rd_addr = {`ADDR_W{1'b0}};
        io_in_val    = 16'h0010;          // external input = 16
        cfg_total    = `CFG_W * `NUM_PES; // 32 * 4 = 128

        // build the config word (slot 0) broadcast to all PEs
        cfg_word_0 = {4'd1, 4'd0, 4'd0, 4'd0, 4'd7, 4'd5, 4'b1000, 4'd3};
        // expected PE result = io_in_val + sign-extended imm(3)
        expected_io_out = io_in_val + 16'sd3;   // 16 + 3 = 19 = 0x0013

        // ---- Reset ----
        @(negedge clk);
        rst_n = 1'b0;
        @(negedge clk);
        @(negedge clk);
        rst_n = 1'b1;
        @(negedge clk);

        //==============================================================
        // TEST 1: dmem scratchpad write/read round-trip
        //==============================================================
        @(negedge clk);
        dmem_wr_en   = 1'b1;
        dmem_wr_addr = 5'd5;
        dmem_wr_data = 32'hDEADBEEF;
        @(negedge clk);
        dmem_wr_en   = 1'b0;
        dmem_wr_addr = 5'd0;
        dmem_wr_data = 32'h0;
        dmem_rd_addr = 5'd5;
        @(negedge clk);            // registered read: data available next edge
        @(negedge clk);
        check_equal(dmem_rd_data, 32'hDEADBEEF, "dmem readback addr5");

        //==============================================================
        // TEST 2: serial config load + execution run
        //==============================================================
        // Drive io_in (host-driven external input broadcast to all PEs).
        // io_in is a wire driven from the TB; assign via force/release.
        force io_in = io_in_val;

        // Hold cfg_en high and shift cfg_total bits of cfg_word_0 (LSB first)
        // into the serial config chain. All four ctrl_mems receive the same
        // broadcast stream, so every PE ends up with cfg_word_0 in slot 0.
        @(negedge clk);
        cfg_en   = 1'b1;
        for (i = 0; i < cfg_total; i = i + 1) begin
            cfg_data = cfg_word_0[i];   // LSB first
            @(negedge clk);
        end
        cfg_en   = 1'b0;
        cfg_data = 1'b0;

        // Start a run: exec_len = 5 execution cycles.
        @(negedge clk);
        exec_len = 5;
        start    = 1'b1;
        @(negedge clk);
        start    = 1'b0;

        // Wait for the done pulse (controller: CONFIG -> EXEC -> DONE).
        // Guard with a timeout so a stuck FSM fails rather than hangs.
        i = 0;
        while (done !== 1'b1 && i < 200) begin
            @(negedge clk);
            i = i + 1;
        end
        check_equal(done, 1'b1, "done pulse");

        // After done, sample io_out. The PE's io_out is combinational from the
        // active config (ALU result = io_in + imm). Allow a couple of cycles
        // for the controller to settle back to IDLE (exec_en deasserts).
        @(negedge clk);
        @(negedge clk);
        check_equal(io_out, expected_io_out, "io_out (io_in + imm)");

        release io_in;

        //==============================================================
        // Report
        //==============================================================
        if (errors == 0)
            $display("Result: PASSED");
        else
            $display("Result: FAILED");
        $finish;
    end

endmodule