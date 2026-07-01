`include "shared_header.vh"

module ctrl_mem (
    input  wire        clk,          // system clock
    input  wire        rst_n,       // async active-low reset

    // ---- Serial shift-load interface ----
    input  wire        shift_en,    // shift enable (config load mode)
    input  wire        shift_in,    // serial config bit in

    // ---- Execution read interface ----
    input  wire        exec_en,     // execution mode (stepped by controller)
    input  wire [`CFG_AW-1:0] cfg_addr,  // external config slot address

    // ---- Output ----
    output wire [`CFG_W-1:0] cfg_out     // active 32-bit config word
);

    //------------------------------------------------------------------
    // Storage: CFG_DEPTH words of CFG_W bits
    //------------------------------------------------------------------
    reg [`CFG_W-1:0] mem [0:`CFG_DEPTH-1];

    //------------------------------------------------------------------
    // Serial shift register (assembles one word from the bit stream)
    //
    // The host/testbench streams config bits LSB-first: cfg_word[0] is
    // sent on the first shift cycle, cfg_word[31] on the last.  To
    // reassemble the original word, the register must shift RIGHT and
    // insert each new bit at the MSB:
    //     shift_reg <= {shift_in, shift_reg[W-1:1]};
    // After W shifts the first bit (cfg_word[0]) lands at bit 0 and the
    // last bit (cfg_word[W-1]) at bit W-1 — exactly the original word.
    //
    // The earlier implementation shifted LEFT
    // ({shift_reg[W-2:0], shift_in}) which placed the first bit at the
    // MSB and the last bit at the LSB, producing a bit-reversed word.
    // That made every PE decode the wrong opcode / mux selects / route
    // field (e.g. opcode came out as OP_MIN instead of OP_ADD and the
    // route field was 0, so io_out never latched and stayed 0).
    //------------------------------------------------------------------
    reg [`CFG_W-1:0] shift_reg;
    reg [`CFG_AW-1:0] wr_ptr;        // write pointer into mem
    reg [`CFG_AW-1:0] bit_cnt;       // counts bits shifted into current word

    integer ci;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (ci = 0; ci < `CFG_DEPTH; ci = ci + 1)
                mem[ci]   <= {`CFG_W{1'b0}};
            shift_reg <= {`CFG_W{1'b0}};
            wr_ptr    <= {`CFG_AW{1'b0}};
            bit_cnt   <= {`CFG_AW{1'b0}};
        end else if (shift_en) begin
            // shift RIGHT: new bit enters at the MSB
            shift_reg <= {shift_in, shift_reg[`CFG_W-1:1]};
            // count bits; when a full word is assembled, commit it
            if (bit_cnt == `CFG_W - 1) begin
                mem[wr_ptr] <= {shift_in, shift_reg[`CFG_W-1:1]};
                wr_ptr  <= (wr_ptr == `CFG_DEPTH - 1) ? {`CFG_AW{1'b0}} : wr_ptr + 1'b1;
                bit_cnt <= {`CFG_AW{1'b0}};
            end else begin
                bit_cnt <= bit_cnt + 1'b1;
            end
        end
        // Note: rd_ptr removed — the active config slot is selected
        // exclusively by the controller's cfg_addr.  This avoids the
        // internal read pointer running ahead of the controller and
        // landing on uninitialised (x) schedule slots during execution.
    end

    //------------------------------------------------------------------
    // Combinational read of the active config slot.
    // The controller drives cfg_addr; during execution it steps through
    // the schedule, and when idle it holds the last address (or 0 after
    // reset).  This gives a single, consistent config-pointer source.
    //------------------------------------------------------------------
    assign cfg_out = mem[cfg_addr];

endmodule