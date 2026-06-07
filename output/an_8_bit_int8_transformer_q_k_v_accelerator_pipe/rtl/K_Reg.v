// K Register Stage
module K_Reg (
    input  wire clk,
    input  wire rst_n,
    input  wire [7:0] k_in,
    output reg  [7:0] reg_k
);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            reg_k <= 8'b0;
        else
            reg_k <= k_in;
    end

endmodule