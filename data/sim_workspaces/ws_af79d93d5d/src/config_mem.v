`include "shared_header.vh"

module config_mem (
    input  wire        clk,          // system clock
    input  wire        rst_n,       // async active-low reset

    // ---- Serial shift-load interface ----
    input  wire        shift_en,    // shift enable (config load mode)
    input  wire        shift_in,    // serial config bit in

    // ---- Execution read interface ----
    input  wire        exec_en,     // execution mode (steps the read pointer)
    input  wire [`CFG_AW-1:0] cfg_addr,  // active config slot address

    // ---- Output ----
    output wire [`CFG_W-1:0] cfg_out     // active 32-bit config word
);

    //---- Storage: CFG_DEPTH words of CFG_W bits ----
    reg [`CFG_W-1:0] mem [0:`CFG_DEPTH-1];

    //---- Serial shift register (assembles one word) ----
    reg [`CFG_W-1:0] shift_reg;
    reg [`CFG_AW-1:0] wr_ptr;          // write pointer into mem
    reg [`CFG_AW-1:0] bit_cnt;          // counts bits shifted into current word

    integer ci;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (ci = 0; ci < `CFG_DEPTH; ci = ci + 1)
                mem[ci]   <= {`CFG_W{1'b0}};
            shift_reg <= {`CFG_W{1'b0}};
            wr_ptr    <= {`CFG_AW{1'b0}};
            bit_cnt   <= {`CFG_AW{1'b0}};
        end else if (shift_en) begin
            // shift the incoming bit into the LSB of shift_reg
            shift_reg <= {shift_reg[`CFG_W-2:0], shift_in};
            // count bits; when a full word is assembled, commit it
            if (bit_cnt == `CFG_W - 1) begin
                mem[wr_ptr] <= {shift_reg[`CFG_W-2:0], shift_in};
                wr_ptr  <= (wr_ptr == `CFG_DEPTH - 1) ? {`CFG_AW{1'b0}} : wr_ptr + 1'b1;
                bit_cnt <= {`CFG_AW{1'b0}};
            end else begin
                bit_cnt <= bit_cnt + 1'b1;
            end
        end
    end

    //---- Combinational read of the active config slot ----
    assign cfg_out = mem[cfg_addr];

endmodule