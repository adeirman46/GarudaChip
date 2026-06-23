// Synchronous single-port SRAM — 1 read/write port, registered output.
module sram_sp #(parameter DW = 8, parameter AW = 8) (
    input              clk,
    input              we,                 // write enable
    input  [AW-1:0]    addr,
    input  [DW-1:0]    din,
    output reg [DW-1:0] dout
);
    reg [DW-1:0] mem [0:(1<<AW)-1];
    always @(posedge clk) begin
        if (we) mem[addr] <= din;          // write
        dout <= mem[addr];                 // synchronous read
    end
endmodule
