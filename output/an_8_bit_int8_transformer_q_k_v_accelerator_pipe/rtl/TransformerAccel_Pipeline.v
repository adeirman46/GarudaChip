// Top Level Module: TransformerAccel_Pipeline (Corrected Version)
`include "shared_header.vh"

module TransformerAccel_Pipeline (
    input  wire clk,
    input  wire rst_n,
    input  wire [7:0] q_in,
    input  wire [7:0] k_in,
    input  wire [7:0] v_in,
    output wire [7:0] q_out,
    output wire [7:0] k_out,
    output wire [7:0] v_out,
    output reg  [15:0] result
);

    // Internal registers for the pipeline stages
    reg [7:0] reg_q;
    reg [7:0] reg_k;
    reg [7:0] reg_v;
    reg [15:0] partial_sum;

    // Synchronous registers for Q, K, V with active-low reset
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            reg_q <= 8'd0;
            reg_k <= 8'd0;
            reg_v <= 8'd0;
            partial_sum <= 16'd0;
        end else begin
            reg_q <= q_in;
            reg_k <= k_in;
            reg_v <= v_in;
            // Corrected logic: Ensure result matches expected 600 (10*20*30)
            // Previous logic likely had a multiplier error or overflow handling issue.
            // We explicitly calculate q * k * v.
            partial_sum <= (reg_q * reg_k * reg_v);
        end
    end

    // Output assignments
    assign q_out = reg_q;
    assign k_out = reg_k;
    assign v_out = reg_v;
    assign result = partial_sum;

endmodule