// 2-read, 1-write register file with combinational read (x0 not special).
module regfile #(parameter DW = 32, parameter AW = 5) (
    input              clk,
    input              we,
    input  [AW-1:0]    waddr, input [DW-1:0] wdata,
    input  [AW-1:0]    raddr1, output [DW-1:0] rdata1,
    input  [AW-1:0]    raddr2, output [DW-1:0] rdata2
);
    reg [DW-1:0] regs [0:(1<<AW)-1];
    integer i; initial for (i=0;i<(1<<AW);i=i+1) regs[i]=0;
    always @(posedge clk) if (we) regs[waddr] <= wdata;
    assign rdata1 = regs[raddr1];
    assign rdata2 = regs[raddr2];
endmodule
