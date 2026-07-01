`include "shared_header.vh"

module dmem (
    input  wire        clk,          // system clock
    input  wire        rst_n,       // async active-low reset

    // ---- Host write port (byte-enable) ----
    input  wire        wr_en,       // write enable (master strobe)
    input  wire [3:0]  byte_en,     // per-byte write enable (4 bytes for 32-bit)
    input  wire [`ADDR_W-1:0] wr_addr,  // write address
    input  wire [`DATA_W-1:0] wr_data,  // write data (32-bit host word)

    // ---- Read port (registered output) ----
    input  wire [`ADDR_W-1:0] rd_addr,  // read address
    output reg  [`DATA_W-1:0] rd_data   // read data (registered, 32-bit)
);

    //------------------------------------------------------------------
    // Storage: DATA_DEPTH words of DATA_W bits
    //------------------------------------------------------------------
    reg [`DATA_W-1:0] mem [0:`DATA_DEPTH-1];

    //------------------------------------------------------------------
    // Write logic with byte-enable merge
    // When wr_en is high, each byte lane selected by byte_en takes the new
    // value from wr_data; unselected lanes keep the old mem value.
    //------------------------------------------------------------------
    integer di;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (di = 0; di < `DATA_DEPTH; di = di + 1)
                mem[di] <= {`DATA_W{1'b0}};
        end else if (wr_en) begin
            // Byte-merge: build the new word from selected/old bytes
            mem[wr_addr] <= {
                byte_en[3] ? wr_data[31:24] : mem[wr_addr][31:24],
                byte_en[2] ? wr_data[23:16] : mem[wr_addr][23:16],
                byte_en[1] ? wr_data[15:8]  : mem[wr_addr][15:8],
                byte_en[0] ? wr_data[7:0]   : mem[wr_addr][7:0]
            };
        end
    end

    //------------------------------------------------------------------
    // Registered read: latch the addressed word on the clock edge.
    // This gives a one-cycle read latency. The testbench writes, then
    // presents rd_addr and waits one clock before sampling rd_data.
    //------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            rd_data <= {`DATA_W{1'b0}};
        else
            rd_data <= mem[rd_addr];
    end

endmodule