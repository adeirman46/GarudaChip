`include "shared_header.vh"

module config_mem (
    input  wire                    clk,
    input  wire                    rst_n,

    // write port
    input  wire                    cfg_we,
    input  wire [`CFG_AW-1:0]      cfg_addr,   // entry address
    input  wire [`CFG_W-1:0]       cfg_wdata,   // config word to store

    // read port (combinational)
    output wire [`CFG_W-1:0]       cfg_out
);

    // FF-based configuration memory
    reg [`CFG_W-1:0] mem [0:`CFG_DEPTH-1];
    integer i;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // reset entry-by-entry (unpacked array)
            for (i = 0; i < `CFG_DEPTH; i = i + 1)
                mem[i] <= {`CFG_W{1'b0}};
        end else if (cfg_we) begin
            mem[cfg_addr] <= cfg_wdata;
        end
    end

    // combinational read of the addressed entry
    assign cfg_out = mem[cfg_addr];

endmodule