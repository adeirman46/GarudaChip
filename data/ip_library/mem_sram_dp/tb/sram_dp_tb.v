`timescale 1ns/1ps
module sram_dp_tb;
    localparam DW=8, AW=4;
    reg clk=0; reg we_a=0,we_b=0; reg [AW-1:0] aa=0,ab=0; reg [DW-1:0] da=0,db=0; wire [DW-1:0] qa,qb;
    integer i, errors=0;
    sram_dp #(.DW(DW),.AW(AW)) dut(.clk(clk),.we_a(we_a),.addr_a(aa),.din_a(da),.dout_a(qa),
                                   .we_b(we_b),.addr_b(ab),.din_b(db),.dout_b(qb));
    always #5 clk=~clk;
    initial begin
        $dumpfile("design.vcd"); $dumpvars(0, sram_dp_tb);
        for (i=0;i<8;i=i+1) begin @(negedge clk); we_a=1; aa=i; da=i+10; end
        @(negedge clk); we_a=0;
        for (i=0;i<8;i=i+1) begin @(negedge clk); ab=i; @(posedge clk); #1;
            if (qb !== (i+10)) begin errors=errors+1; $display("MISMATCH %0d",i); end end
        if (errors==0) $display("PASS: dual-port SRAM ok"); else $display("FAIL: %0d errors", errors);
        $finish;
    end
endmodule
