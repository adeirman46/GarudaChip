`include "shared_header.vh"

module pwm_core (
    input  logic          clk,
    input  logic          rst_n,
    input  logic          start,
    input  logic [11:0]   duty_in,
    input  logic [11:0]   duty_reg,  // Changed from output to input
    output logic [15:0]   count,
    output logic          out
);

    // Counter: 16-bit up-counter
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count <= 0;
        end else if (start) begin
            count <= 0;
        end else begin
            count <= count + 1;
        end
    end

    // PWM output: combinational logic
    assign out = (count < duty_reg) ? 1'b1 : 1'b0;

endmodule