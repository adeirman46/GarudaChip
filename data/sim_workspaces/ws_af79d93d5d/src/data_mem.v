`include "shared_header.vh"

module data_mem (
    input  wire        clk,          // system clock
    input  wire        rst_n,       // async active-low reset

    // ---- Host write port ----
    input  wire        wr_en,       // write enable
    input  wire [`ADDR_W-1:0] wr_addr,  // write address
    input  wire [`DATA_W-1:0] wr_data,  // write data (32-bit host word)

    // ---- Read port (combinational) ----
    input  wire [`ADDR_W-1:0] rd_addr,  // read address
    output wire [`DATA_W-1:0] rd_data   // read data (32-bit host word)
);

    //---- Storage ----
    reg [`DATA_W-1:0] mem [0:`DATA_DEPTH-1];

    integer di;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (di = 0; di < `DATA_DEPTH; di = di + 1)
                mem[di] <= {`DATA_W{1'b0}};
        end else if (wr_en) begin
            mem[wr_addr] <= wr_data;
        end
    end

    //---- Combinational read ----
    assign rd_data = mem[rd_addr];

endmodule