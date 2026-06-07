module riscv_q5_3_regfile (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        mem_en,
    input  wire        mem_wr,
    input  wire        mem_we,
    input  wire [6:0]  mem_addr,
    input  wire [7:0]  mem_data,
    input  wire        mem_valid,
    input  wire [2:0]  waddr,
    input  wire [2:0]  raddr,
    output reg  [7:0]  q5_3_data,
    output reg  [7:0]  q5_3_data_out,
    output reg         q5_3_valid,
    output reg         q5_3_we
);

    // Internal storage for the register file data (4 entries of 8 bits)
    reg [7:0] reg_q5_3 [0:3];

    // Synchronous write logic: Update internal register array and output ports
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            reg_q5_3   <= 4{8'd0};
            q5_3_data  <= 8'd0;
            q5_3_data_out <= 8'd0;
            q5_3_valid <= 0;
            q5_3_we    <= 0;
        end else begin
            // Perform write if enabled and write signal is active
            if (mem_en && mem_wr && mem_valid) begin
                reg_q5_3[waddr] <= mem_data;
                q5_3_data      <= mem_data;
                q5_3_data_out <= mem_data;
                q5_3_valid     <= 1;
                q5_3_we        <= 1;
            end else begin
                // Reset write enable flag when not writing
                q5_3_we <= 0;
            end
        end
    end

    // Synchronous read logic: Read from internal register array based on raddr
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            q5_3_data_out <= 8'd0;
            q5_3_valid    <= 0;
        end else begin
            // Read operation depends on memory enable and validity
            if (mem_en && mem_valid) begin
                // Read from the correct internal register index
                q5_3_data_out <= reg_q5_3[raddr];
                q5_3_valid    <= 1;
            end else begin
                q5_3_data_out <= 8'd0;
                q5_3_valid    <= 0;
            end
        end
    end

endmodule