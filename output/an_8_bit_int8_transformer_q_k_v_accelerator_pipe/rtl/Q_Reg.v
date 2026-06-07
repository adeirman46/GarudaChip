// Q Register Stage
module Q_Reg (
    input  wire clk,
    input  wire rst_n,
    input  wire [7:0] q_in,
    output reg  [7:0] reg_q
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            reg_q <= 8'b0;
        else
            reg_q <= q_in;
    end

endmodule