`timescale 1ns/1ps
module sram_sp_tb;
    localparam DW=8, AW=4;
    reg clk=0, we=0; reg [AW-1:0] addr=0; reg [DW-1:0] din=0; wire [DW-1:0] dout;
    integer i, errors=0;
    sram_sp #(.DW(DW), .AW(AW)) dut(.clk(clk), .we(we), .addr(addr), .din(din), .dout(dout));
    always #5 clk=~clk;
    initial begin
        $dumpfile("design.vcd"); $dumpvars(0, sram_sp_tb);
        for (i=0;i<16;i=i+1) begin @(negedge clk); we=1; addr=i; din=i*3+1; end
        @(negedge clk); we=0;
        for (i=0;i<16;i=i+1) begin
            @(negedge clk); addr=i; @(posedge clk); #1;
            if (dout !== (i*3+1)) begin errors=errors+1; $display("MISMATCH addr %0d: got %0d exp %0d", i, dout, i*3+1); end
        end
        if (errors==0) $display("PASS: single-port SRAM ok"); else $display("FAIL: %0d errors", errors);
        $finish;
    end
endmodule
