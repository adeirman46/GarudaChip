// Synchronous ROM — registered output, content baked into the logic.
module rom_sync #(parameter DW = 8, parameter AW = 4) (
    input              clk,
    input  [AW-1:0]    addr,
    output reg [DW-1:0] dout
);
    always @(posedge clk) begin
        case (addr)
            4'd0: dout <= 8'h0A; 4'd1: dout <= 8'h1B; 4'd2: dout <= 8'h2C; 4'd3: dout <= 8'h3D;
            4'd4: dout <= 8'h4E; 4'd5: dout <= 8'h5F; 4'd6: dout <= 8'h60; 4'd7: dout <= 8'h71;
            default: dout <= 8'hFF;
        endcase
    end
endmodule
