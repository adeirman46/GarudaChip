// Compute Unit Stage (Partial Product Accumulation) - Corrected Version
module Compute_Unit (
    input  wire clk,
    input  wire rst_n,
    input  wire [7:0] q_data,
    input  wire [7:0] v_data,
    output reg  [15:0] partial_sum
);

    // Use a loop-free combinational-style logic inside sequential block 
    // to avoid 'integer' type (not supported in standard Verilog) and 
    // to prevent multiple assignments to 'partial_sum' in one clock cycle.
    // We calculate the weighted sum directly without a for-loop.
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            partial_sum <= 16'b0;
        else begin
            // Calculate shift amount: v_data is shifted left by (7 - bit_index)
            // This is equivalent to: q_data[0] * v_data[7:0] + q_data[1] * v_data[6:0] ...
            // Implemented as: if q_data[i] is high, add v_data << (7-i)
            
            reg [15:0] accumulator;
            reg [7:0] shift_amount;
            reg [7:0] bit_index;
            
            // Reset accumulator for this cycle
            accumulator <= 16'b0;
            
            // Unroll the loop logic manually to avoid 'for' loops and 'integer' types
            // Bit 0 of q_data corresponds to shift 7
            if (q_data[0])
                accumulator <= accumulator + (v_data << 7);
            // Bit 1 of q_data corresponds to shift 6
            if (q_data[1])
                accumulator <= accumulator + (v_data << 6);
            // Bit 2 of q_data corresponds to shift 5
            if (q_data[2])
                accumulator <= accumulator + (v_data << 5);
            // Bit 3 of q_data corresponds to shift 4
            if (q_data[3])
                accumulator <= accumulator + (v_data << 4);
            // Bit 4 of q_data corresponds to shift 3
            if (q_data[4])
                accumulator <= accumulator + (v_data << 3);
            // Bit 5 of q_data corresponds to shift 2
            if (q_data[5])
                accumulator <= accumulator + (v_data << 2);
            // Bit 6 of q_data corresponds to shift 1
            if (q_data[6])
                accumulator <= accumulator + (v_data << 1);
            // Bit 7 of q_data corresponds to shift 0
            if (q_data[7])
                accumulator <= accumulator + (v_data << 0);
            
            partial_sum <= accumulator;
        end
    end

endmodule