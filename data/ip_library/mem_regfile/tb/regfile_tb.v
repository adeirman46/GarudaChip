`timescale 1ns/1ps
module regfile_tb;
    reg clk=0, we=0; reg [4:0] wa=0,ra1=0,ra2=0; reg [31:0] wd=0; wire [31:0] rd1,rd2;
    integer i, errors=0;
    regfile dut(.clk(clk),.we(we),.waddr(wa),.wdata(wd),.raddr1(ra1),.rdata1(rd1),.raddr2(ra2),.rdata2(rd2));
    always #5 clk=~clk;
    initial begin
        $dumpfile("design.vcd"); $dumpvars(0, regfile_tb);
        for (i=1;i<8;i=i+1) begin @(negedge clk); we=1; wa=i; wd=i*32'h1111; end
        @(negedge clk); we=0;
        for (i=1;i<8;i=i+1) begin #1; ra1=i; #1;
            if (rd1 !== i*32'h1111) begin errors=errors+1; $display("MISMATCH r%0d", i); end end
        if (errors==0) $display("PASS: register file ok"); else $display("FAIL: %0d", errors);
        $finish;
    end
endmodule
