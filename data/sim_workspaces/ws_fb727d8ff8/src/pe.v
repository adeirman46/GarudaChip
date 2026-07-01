`include "shared_header.vh"

module pe (
    input  wire                    clk,
    input  wire                    rst_n,

    // ---- configuration (per-PE control word, 8 bits) -----------------------
    input  wire [`CFG_W-1:0]       cfg,        // [7:6]op [5]cin [4:3]muxA [2:1]muxB [0]route

    // ---- neighbor data inputs (registered outputs of adjacent PEs) -------
    input  wire [`DATA_W-1:0]      n_in,       // from north neighbor
    input  wire [`DATA_W-1:0]      s_in,       // from south neighbor
    input  wire [`DATA_W-1:0]      e_in,       // from east  neighbor
    input  wire [`DATA_W-1:0]      w_in,       // from west  neighbor

    // ---- neighbor data outputs (registered) ------------------------------
    output reg  [`DATA_W-1:0]      n_out,
    output reg  [`DATA_W-1:0]      s_out,
    output reg  [`DATA_W-1:0]      e_out,
    output reg  [`DATA_W-1:0]      w_out,

    // ---- local observation port (ALU result, registered) -----------------
    output reg  [`DATA_W-1:0]      pe_out
);

    // ------------------------------------------------------------------------
    // Decode configuration word
    // ------------------------------------------------------------------------
    wire [`ALU_OP_W-1:0]  alu_op  = cfg[`ALU_OP_MSB : `ALU_OP_LSB];
    wire                  cin     = cfg[`CIN_BIT];
    wire [`MUX_SEL_W-1:0] muxA_sel= cfg[`MUXA_MSB : `MUXA_LSB];
    wire [`MUX_SEL_W-1:0] muxB_sel= cfg[`MUXB_MSB : `MUXB_LSB];
    wire                  route   = cfg[`ROUTE_BIT];

    // ------------------------------------------------------------------------
    // General-purpose register file  (4 x 32-bit, FF-based)
    //   GPR[0] is the default write target and also the "local" operand.
    // ------------------------------------------------------------------------
    reg [`DATA_W-1:0] gpr [0:`NUM_GPR-1];
    integer i;

    // ------------------------------------------------------------------------
    // Operand-A mux: select among local GPR[0] and the four neighbor inputs.
    // ------------------------------------------------------------------------
    reg [`DATA_W-1:0] op_a;
    always @(*) begin
        case (muxA_sel)
            `MUX_LOCAL: op_a = gpr[0];
            `MUX_NORTH: op_a = n_in;
            `MUX_EAST:  op_a = e_in;
            `MUX_WEST:  op_a = w_in;
            default:    op_a = gpr[0];
        endcase
    end

    // ------------------------------------------------------------------------
    // Operand-B mux: select among local GPR[1] and the four neighbor inputs.
    //   (MuxB uses the south input in the WEST slot so all four neighbors are
    //    reachable across the two muxes.)
    // ------------------------------------------------------------------------
    reg [`DATA_W-1:0] op_b;
    always @(*) begin
        case (muxB_sel)
            `MUX_LOCAL: op_b = gpr[1];
            `MUX_NORTH: op_b = n_in;
            `MUX_EAST:  op_b = e_in;
            `MUX_WEST:  op_b = s_in;   // south reachable via MuxB slot 3
            default:    op_b = gpr[1];
        endcase
    end

    // ------------------------------------------------------------------------
    // ALU  (combinational)
    //   ADD : op_a + op_b + cin
    //   SUB : op_a - op_b - cin   (op_a + ~op_b + ~cin)
    //   AND : op_a & op_b
    //   OR  : op_a | op_b
    // ------------------------------------------------------------------------
    wire [`DATA_W:0] add_res = {1'b0, op_a} + {1'b0, op_b} + cin;            // ADD
    wire [`DATA_W:0] sub_res = {1'b0, op_a} + {1'b0, ~op_b} + ~cin;         // SUB
    reg  [`DATA_W-1:0] alu_res;

    always @(*) begin
        case (alu_op)
            `ALU_ADD: alu_res = add_res[`DATA_W-1:0];
            `ALU_SUB: alu_res = sub_res[`DATA_W-1:0];
            `ALU_AND: alu_res = op_a & op_b;
            `ALU_OR:  alu_res = op_a | op_b;
            default:  alu_res = {`DATA_W{1'b0}};
        endcase
    end

    // ------------------------------------------------------------------------
    // Sequential update: register file + registered outputs.
    //   * GPR[0] always captures the ALU result (write-back).
    //   * The ALU result is registered into pe_out every cycle.
    //   * The route bit selects which neighbor output carries the result.
    //     route=0 → drive east;  route=1 → drive south.
    //     (The 2x2 mesh only needs E/S routing for the systolic flow
    //      PE0→PE1→PE3→PE2→PE0; N/W are driven to 0 to avoid contention.)
    // ------------------------------------------------------------------------
    integer k;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // reset GPRs entry-by-entry (unpacked array)
            for (i = 0; i < `NUM_GPR; i = i + 1)
                gpr[i] <= {`DATA_W{1'b0}};
            n_out  <= {`DATA_W{1'b0}};
            s_out  <= {`DATA_W{1'b0}};
            e_out  <= {`DATA_W{1'b0}};
            w_out  <= {`DATA_W{1'b0}};
            pe_out <= {`DATA_W{1'b0}};
        end else begin
            // write-back to GPR[0]
            gpr[0] <= alu_res;
            // registered observation
            pe_out <= alu_res;
            // routed neighbor output (registered → no combinational loop)
            // route=0 : east,  route=1 : south
            e_out <= (route == 1'b0) ? alu_res : {`DATA_W{1'b0}};
            s_out <= (route == 1'b1) ? alu_res : {`DATA_W{1'b0}};
            // north/west held at 0 (unused in the 2x2 systolic flow)
            n_out <= {`DATA_W{1'b0}};
            w_out <= {`DATA_W{1'b0}};
        end
    end

endmodule