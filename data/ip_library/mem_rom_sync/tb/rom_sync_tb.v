`timescale 1ns/1ps
module rom_sync_tb;
    reg clk=0; reg [3:0] addr=0; wire [7:0] dout; integer errors=0;
    reg [7:0] exp [0:7];
    rom_sync dut(.clk(clk), .addr(addr), .dout(dout));
    always #5 clk=~clk;
    initial begin
        $dumpfile("design.vcd"); $dumpvars(0, rom_sync_tb);
        exp[0]=8'h0A; exp[1]=8'h1B; exp[2]=8'h2C; exp[3]=8'h3D;
        exp[4]=8'h4E; exp[5]=8'h5F; exp[6]=8'h60; exp[7]=8'h71;
        begin : chk integer i;
            for (i=0;i<8;i=i+1) begin @(negedge clk); addr=i; @(posedge clk); #1;
                if (dout !== exp[i]) begin errors=errors+1; $display("MISMATCH %0d", i); end end
        end
        if (errors==0) $display("PASS: ROM ok"); else $display("FAIL: %0d", errors);
        $finish;
    end
endmodule
