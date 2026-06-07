// V Register Stage
module V_Reg (
    input  wire clk,
    input  wire rst_n,
    input  wire [7:0] v_in,
    output reg  [7:0] reg_v
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            reg_v <= 8'b0;
        else
            reg_v <= v_in;
    end

endmodule