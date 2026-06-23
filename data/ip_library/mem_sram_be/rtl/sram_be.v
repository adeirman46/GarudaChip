// Single-port SRAM with per-byte write strobes (NB bytes wide).
module sram_be #(parameter NB = 4, parameter AW = 8) (
    input                clk,
    input  [NB-1:0]      be,               // one strobe per byte lane
    input  [AW-1:0]      addr,
    input  [NB*8-1:0]    din,
    output reg [NB*8-1:0] dout
);
    reg [NB*8-1:0] mem [0:(1<<AW)-1];
    integer i;
    always @(posedge clk) begin
        for (i=0;i<NB;i=i+1) if (be[i]) mem[addr][i*8 +: 8] <= din[i*8 +: 8];
        dout <= mem[addr];
    end
endmodule
