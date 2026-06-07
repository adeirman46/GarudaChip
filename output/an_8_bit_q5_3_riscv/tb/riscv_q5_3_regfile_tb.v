module riscv_q5_3_regfile_tb;

`include "shared_header.vh"

// Clock and Reset
reg clk;
reg rst_n;

// DUT Inputs (declared as reg per strict rules)
reg mem_en;
reg mem_wr;
reg mem_we;
reg [6:0] mem_addr;
reg [7:0] mem_data;
reg mem_valid;

// DUT Outputs (declared as wire per strict rules)
wire [7:0] q5_3_data;
wire [7:0] q5_3_data_out;
wire q5_3_valid;

// Instantiate DUT
riscv_q5_3_regfile dut (
    .clk(clk),
    .rst_n(rst_n),
    .mem_en(mem_en),
    .mem_wr(mem_wr),
    .mem_we(mem_we),
    .mem_addr(mem_addr),
    .mem_data(mem_data),
    .mem_valid(mem_valid),
    .q5_3_data(q5_3_data),
    .q5_3_data_out(q5_3_data_out),
    .q5_3_valid(q5_3_valid)
);

// Clock Generation
initial clk = 0;
always #5 clk = ~clk;

// Test Stimulus and Checking
initial begin
    // Initialize signals
    rst_n = 0;
    mem_en = 0;
    mem_wr = 0;
    mem_we = 0;
    mem_valid = 0;
    
    // Wait for reset to release
    @(posedge clk);
    rst_n = 1;
    @(posedge clk);
    
    // Test 1: Write data
    mem_en = 1;
    mem_wr = 1;
    mem_we = 1;
    mem_addr = 0;
    mem_data = 8'hAA;
    mem_valid = 1;
    @(posedge clk);
    
    // Test 2: Read data
    mem_en = 1;
    mem_wr = 0;
    mem_we = 0;
    mem_valid = 1;
    @(posedge clk);
    
    // Test 3: Write new data
    mem_en = 1;
    mem_wr = 1;
    mem_we = 1;
    mem_addr = 0;
    mem_data = 8'hBB;
    mem_valid = 1;
    @(posedge clk);
    
    // Test 4: Read new data
    mem_en = 1;
    mem_wr = 0;
    mem_we = 0;
    mem_valid = 1;
    @(posedge clk);
    
    // Check results
    if (q5_3_data == 8'hBB && q5_3_data_out == 8'hBB && q5_3_valid == 1) begin
        $display("Result: PASSED");
    end else begin
        $display("Result: FAILED");
    end
    
    $finish;
end

endmodule