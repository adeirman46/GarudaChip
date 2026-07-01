`include "shared_header.vh"

module pwm_lut (
    input  logic [11:0]   duty_in,
    output logic [11:0]   duty_out
);

    // Identity function: duty_out = duty_in
    assign duty_out = duty_in;

endmodule