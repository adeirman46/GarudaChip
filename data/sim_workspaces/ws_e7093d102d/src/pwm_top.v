`include "shared_header.vh"

module pwm_top (
    input  logic          clk,
    input  logic          rst_n,
    input  logic          start,
    input  logic [11:0]   duty_in,
    output logic          out
);

    // Internal wires for module connections
    wire [15:0] count;
    wire [11:0] duty_reg;
    wire start_ack;

    // Instantiate LUT (identity function) - drives duty_reg
    pwm_lut u_pwm_lut (
        .duty_in(duty_in),
        .duty_out(duty_reg)
    );

    // Instantiate core PWM logic - uses duty_reg from LUT
    pwm_core u_pwm_core (
        .clk(clk),
        .rst_n(rst_n),
        .start(start),
        .duty_in(duty_reg),      // Use duty_reg from LUT
        .duty_reg(duty_reg),    // Connect input port from top
        .count(count),
        .out(out)
    );

    // Instantiate control logic
    pwm_ctrl u_pwm_ctrl (
        .clk(clk),
        .rst_n(rst_n),
        .start(start),
        .start_ack(start_ack)
    );

endmodule