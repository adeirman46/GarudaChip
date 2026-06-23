// True dual-port synchronous SRAM — two independent read/write ports.
module sram_dp #(parameter DW = 8, parameter AW = 8) (
    input              clk,
    input              we_a, input [AW-1:0] addr_a, input [DW-1:0] din_a, output reg [DW-1:0] dout_a,
    input              we_b, input [AW-1:0] addr_b, input [DW-1:0] din_b, output reg [DW-1:0] dout_b
);
    reg [DW-1:0] mem [0:(1<<AW)-1];
    always @(posedge clk) begin
        if (we_a) mem[addr_a] <= din_a;
        dout_a <= mem[addr_a];
    end
    always @(posedge clk) begin
        if (we_b) mem[addr_b] <= din_b;
        dout_b <= mem[addr_b];
    end
endmodule
