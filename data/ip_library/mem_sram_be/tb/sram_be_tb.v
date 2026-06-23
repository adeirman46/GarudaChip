`timescale 1ns/1ps
module sram_be_tb;
    localparam NB=4, AW=4;
    reg clk=0; reg [NB-1:0] be=0; reg [AW-1:0] addr=0; reg [NB*8-1:0] din=0; wire [NB*8-1:0] dout;
    integer errors=0;
    sram_be #(.NB(NB),.AW(AW)) dut(.clk(clk),.be(be),.addr(addr),.din(din),.dout(dout));
    always #5 clk=~clk;
    initial begin
        $dumpfile("design.vcd"); $dumpvars(0, sram_be_tb);
        @(negedge clk); be=4'b1111; addr=2; din=32'hDEADBEEF;     // full write
        @(negedge clk); be=4'b0010; addr=2; din=32'h0000FF00;     // write byte 1 only
        @(negedge clk); be=0; addr=2; @(posedge clk); #1;
        if (dout !== 32'hDEADFFEF) begin errors=1; $display("MISMATCH got %h", dout); end
        if (errors==0) $display("PASS: byte-enable SRAM ok"); else $display("FAIL");
        $finish;
    end
endmodule
