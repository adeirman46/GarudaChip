`include "shared_header.vh"

module pwm_generator #(
    parameter COUNTER_WIDTH = 16
) (
    // System Inputs
    input  logic          clk,
    input  logic          rst,

    // Configuration Inputs
    input  logic [COUNTER_WIDTH-1:0] period,  // The counter will cycle from 0 to this value
    input  logic [COUNTER_WIDTH-1:0] compare, // The output is high while counter < compare

    // Output
    output logic          pwm_out              // The PWM output signal
);

    // Internal counter
    reg [COUNTER_WIDTH-1:0] counter_reg;

    // Main sequential logic block
    always @(posedge clk) begin
        if (rst) begin
            // Reset state
            counter_reg <= 0;
            pwm_out     <= 1'b0;
        end else begin
            // Counter logic: increments up to 'period' and then resets to 0
            if (counter_reg >= period) begin
                counter_reg <= 0;
            end else begin
                counter_reg <= counter_reg + 1;
            end

            // PWM generation logic: output is high when counter is less than the compare value
            if (counter_reg < compare) begin
                pwm_out <= 1'b1;
            end else begin
                pwm_out <= 1'b0;
            end
        end
    end

endmodule