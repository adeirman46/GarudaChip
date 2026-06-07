module TransformerAccel_Pipeline_tb;

`include "shared_header.vh"

// Clock and Reset Signals
reg clk;
reg rst_n;

// DUT Inputs
reg [7:0] q_in;
reg [7:0] k_in;
reg [7:0] v_in;

// DUT Outputs
wire [7:0] q_out;
wire [7:0] k_out;
wire [7:0] v_out;
wire [15:0] result;

// Clock Generation
initial clk = 0;
always #5 clk = ~clk;

// Instantiate DUT
TransformerAccel_Pipeline dut (
    .clk(clk),
    .rst_n(rst_n),
    .q_in(q_in),
    .k_in(k_in),
    .v_in(v_in),
    .q_out(q_out),
    .k_out(k_out),
    .v_out(v_out),
    .result(result)
);

// Test Stimulus
initial begin
    // Initialize signals
    q_in = 8'd0;
    k_in = 8'd0;
    v_in = 8'd0;
    
    // Apply Reset
    rst_n = 1'b0;
    
    // Wait for reset to settle
    #20;
    
    // Release Reset
    rst_n = 1'b1;
    
    // Apply Stimulus
    @(posedge clk);
    q_in = 8'd10;
    k_in = 8'd20;
    v_in = 8'd30;
    
    // Wait for pipeline to stabilize (e.g., 10 clock cycles)
    #50;
    
    // Check Results
    if (q_out === 8'd10 && k_out === 8'd20 && v_out === 8'd30 && result === 16'd600) begin
        $display("Result: PASSED");
    end else begin
        $display("Result: FAILED");
        $display("Expected: q_out=10, k_out=20, v_out=30, result=600");
        $display("Got: q_out=%0d, k_out=%0d, v_out=%0d, result=%0d", q_out, k_out, v_out, result);
    end
    
    // Finish simulation
    $finish;
end

// VCD Dump Setup
initial begin
    $dumpfile("design.vcd");
    $dumpvars(0, TransformerAccel_Pipeline_tb);
end

endmodule