`timescale 1ns/1ps
module fifo_sync_tb;
    localparam DW=8;
    reg clk=0, rst=1, wr=0, rd=0; reg [DW-1:0] din=0; wire [DW-1:0] dout; wire full, empty;
    integer i, errors=0;
    fifo_sync #(.DW(DW),.AW(3)) dut(.clk(clk),.rst(rst),.wr_en(wr),.din(din),.full(full),
                                    .rd_en(rd),.dout(dout),.empty(empty));
    always #5 clk=~clk;
    initial begin
        $dumpfile("design.vcd"); $dumpvars(0, fifo_sync_tb);
        @(negedge clk); rst=0;
        for (i=0;i<6;i=i+1) begin @(negedge clk); wr=1; din=i*7+2; end
        @(negedge clk); wr=0;
        for (i=0;i<6;i=i+1) begin @(negedge clk); rd=1; @(posedge clk); #1;
            if (dout !== (i*7+2)) begin errors=errors+1; $display("MISMATCH %0d got %0d", i, dout); end end
        @(negedge clk); rd=0;
        if (errors==0) $display("PASS: sync FIFO ok"); else $display("FAIL: %0d", errors);
        $finish;
    end
endmodule
