`include "shared_header.vh"

module config_controller (
    input  wire        clk,          // system clock
    input  wire        rst_n,       // async active-low reset
    input  wire        start,       // pulse high to begin a run
    input  wire [`CFG_AW-1:0] exec_len,  // number of execution cycles to run

    // ---- Config shift chain (shared to all PE config memories) ----
    output wire        cfg_shift_en, // shift enable during CONFIG
    output wire        exec_en,      // execution enable during EXECUTE
    output wire [`CFG_AW-1:0] cfg_addr, // active config slot address
    output wire        done          // pulse high when run finishes
);

    //---- FSM state ----
    reg [1:0]  state;
    reg [7:0]  cfg_cnt;        // counts config shift cycles (0..127)
    reg [`CFG_AW-1:0] exec_cnt;     // counts execution cycles
    reg [`CFG_AW-1:0] addr_r;       // registered config address pointer

    // total config bits = CFG_W * NUM_PES = 32 * 4 = 128
    localparam CFG_TOTAL = `CFG_W * `NUM_PES;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state    <= `ST_IDLE;
            cfg_cnt  <= 8'd0;
            exec_cnt <= {`CFG_AW{1'b0}};
            addr_r   <= {`CFG_AW{1'b0}};
        end else begin
            case (state)
                `ST_IDLE: begin
                    cfg_cnt  <= 8'd0;
                    exec_cnt <= {`CFG_AW{1'b0}};
                    addr_r   <= {`CFG_AW{1'b0}};
                    if (start)
                        state <= `ST_CONFIG;
                end

                `ST_CONFIG: begin
                    if (cfg_cnt == CFG_TOTAL - 1) begin
                        state   <= `ST_EXEC;
                        cfg_cnt <= 8'd0;
                    end else begin
                        cfg_cnt <= cfg_cnt + 8'd1;
                    end
                end

                `ST_EXEC: begin
                    if (exec_cnt == exec_len) begin
                        state    <= `ST_DONE;
                        exec_cnt <= {`CFG_AW{1'b0}};
                    end else begin
                        exec_cnt <= exec_cnt + 1'b1;
                        // Hold the config address at slot 0 during
                        // execution.  The design loads a single
                        // configuration word into slot 0 of every PE's
                        // config memory; all execution cycles reuse
                        // that same configuration.  (Time-multiplexed
                        // multi-slot scheduling would require an
                        // initiation-interval input; left for a future
                        // enhancement.)
                    end
                end

                `ST_DONE: begin
                    state <= `ST_IDLE;
                end

                default: state <= `ST_IDLE;
            endcase
        end
    end

    //---- Outputs ----
    assign cfg_shift_en = (state == `ST_CONFIG);
    assign exec_en      = (state == `ST_EXEC);
    assign cfg_addr     = addr_r;
    assign done         = (state == `ST_DONE);

endmodule