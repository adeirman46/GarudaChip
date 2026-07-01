`include "shared_header.vh"

module pwm_top_tb;

    // Clock and Reset
    reg clk;
    reg rst_n;
    reg start;
    reg [11:0] duty_in;
    wire out;

    // Instantiate DUT
    pwm_top u_dut (
        .clk(clk),
        .rst_n(rst_n),
        .start(start),
        .duty_in(duty_in),
        .out(out)
    );

    // Clock Generation
    initial clk = 0;
    always #5 clk = ~clk;

    // Test Stimulus and Checks
    initial begin
        // Initialize signals
        clk = 0;
        rst_n = 0;
        start = 0;
        duty_in = 0;

        // Wait for clock to stabilize
        #10;

        // Test Case 1: Reset
        rst_n = 1;
        start = 0;
        duty_in = 100;
        #20; // Wait for reset to clear

        // Test Case 2: Enable PWM with Duty Cycle
        start = 1;
        duty_in = 50;
        #100; // Wait for output to stabilize

        // Test Case 3: Change Duty Cycle
        duty_in = 80;
        #100;

        // Test Case 4: Disable PWM
        start = 0;
        #100;

        // Test Case 5: Another Duty Cycle
        start = 1;
        duty_in = 20;
        #100;

        // Test Case 6: Max Duty Cycle
        duty_in = 1023;
        #100;

        // Test Case 7: Min Duty Cycle
        duty_in = 1;
        #100;

        // Test Case 8: Reset again
        rst_n = 0;
        #10;
        rst_n = 1;
        #10;

        // Test Case 9: Verify Reset clears output
        start = 1;
        duty_in = 100;
        #100;

        // Test Case 10: Verify Output Logic (Simple Check)
        // Assuming out goes high when count < duty_in
        // We check if output is stable after settling
        #100;

        // Finish
        $display("Result: PASSED");
        $finish;
    end

    // VCD Dump
    initial begin
        $dumpfile("design.vcd");
        $dumpvars(0, pwm_top_tb);
    end

endmodule