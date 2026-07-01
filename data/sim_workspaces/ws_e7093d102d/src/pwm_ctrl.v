`include "shared_header.vh"

module pwm_ctrl (
    input  logic          clk,
    input  logic          rst_n,
    input  logic          start,
    output logic          start_ack
);

    // Start acknowledgment: pulse on first clock after start is asserted
    reg start_reg;
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            start_reg <= 0;
            start_ack <= 0;
        end else begin
            start_reg <= start;
            if (start && !start_reg) begin
                start_ack <= 1;
            end else begin
                start_ack <= 0;
            end
        end
    end

endmodule