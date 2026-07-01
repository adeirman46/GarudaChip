`include "shared_header.vh"

module io_pad (
    input  wire                    clk,
    input  wire                    rst_n,

    // ---- external data ingress (chip-side) -------------------------------
    input  wire [`DATA_W-1:0]      data_in_top_0,
    input  wire [`DATA_W-1:0]      data_in_top_1,
    input  wire [`DATA_W-1:0]      data_in_right_0,
    input  wire [`DATA_W-1:0]      data_in_right_1,
    input  wire [`DATA_W-1:0]      data_in_bot_0,
    input  wire [`DATA_W-1:0]      data_in_bot_1,
    input  wire [`DATA_W-1:0]      data_in_left_0,
    input  wire [`DATA_W-1:0]      data_in_left_1,

    // ---- external data egress (chip-side) --------------------------------
    output reg  [`DATA_W-1:0]      data_out_top_0,
    output reg  [`DATA_W-1:0]      data_out_top_1,
    output reg  [`DATA_W-1:0]      data_out_right_0,
    output reg  [`DATA_W-1:0]      data_out_right_1,
    output reg  [`DATA_W-1:0]      data_out_bot_0,
    output reg  [`DATA_W-1:0]      data_out_bot_1,
    output reg  [`DATA_W-1:0]      data_out_left_0,
    output reg  [`DATA_W-1:0]      data_out_left_1,

    // ---- grid-side boundary inputs (driven to the grid) ------------------
    output reg  [`DATA_W-1:0]      grid_in_top_0,
    output reg  [`DATA_W-1:0]      grid_in_top_1,
    output reg  [`DATA_W-1:0]      grid_in_right_0,
    output reg  [`DATA_W-1:0]      grid_in_right_1,
    output reg  [`DATA_W-1:0]      grid_in_bot_0,
    output reg  [`DATA_W-1:0]      grid_in_bot_1,
    output reg  [`DATA_W-1:0]      grid_in_left_0,
    output reg  [`DATA_W-1:0]      grid_in_left_1,

    // ---- grid-side boundary outputs (received from the grid) -------------
    input  wire [`DATA_W-1:0]      grid_out_top_0,
    input  wire [`DATA_W-1:0]      grid_out_top_1,
    input  wire [`DATA_W-1:0]      grid_out_right_0,
    input  wire [`DATA_W-1:0]      grid_out_right_1,
    input  wire [`DATA_W-1:0]      grid_out_bot_0,
    input  wire [`DATA_W-1:0]      grid_out_bot_1,
    input  wire [`DATA_W-1:0]      grid_out_left_0,
    input  wire [`DATA_W-1:0]      grid_out_left_1
);

    // ------------------------------------------------------------------------
    // Registered ingress: external data_in_* -> grid_in_*
    // ------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            grid_in_top_0   <= {`DATA_W{1'b0}};
            grid_in_top_1   <= {`DATA_W{1'b0}};
            grid_in_right_0 <= {`DATA_W{1'b0}};
            grid_in_right_1 <= {`DATA_W{1'b0}};
            grid_in_bot_0   <= {`DATA_W{1'b0}};
            grid_in_bot_1   <= {`DATA_W{1'b0}};
            grid_in_left_0  <= {`DATA_W{1'b0}};
            grid_in_left_1  <= {`DATA_W{1'b0}};
        end else begin
            grid_in_top_0   <= data_in_top_0;
            grid_in_top_1   <= data_in_top_1;
            grid_in_right_0 <= data_in_right_0;
            grid_in_right_1 <= data_in_right_1;
            grid_in_bot_0   <= data_in_bot_0;
            grid_in_bot_1   <= data_in_bot_1;
            grid_in_left_0  <= data_in_left_0;
            grid_in_left_1  <= data_in_left_1;
        end
    end

    // ------------------------------------------------------------------------
    // Registered egress: grid_out_* -> data_out_*
    // ------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out_top_0   <= {`DATA_W{1'b0}};
            data_out_top_1   <= {`DATA_W{1'b0}};
            data_out_right_0 <= {`DATA_W{1'b0}};
            data_out_right_1 <= {`DATA_W{1'b0}};
            data_out_bot_0   <= {`DATA_W{1'b0}};
            data_out_bot_1   <= {`DATA_W{1'b0}};
            data_out_left_0  <= {`DATA_W{1'b0}};
            data_out_left_1  <= {`DATA_W{1'b0}};
        end else begin
            data_out_top_0   <= grid_out_top_0;
            data_out_top_1   <= grid_out_top_1;
            data_out_right_0 <= grid_out_right_0;
            data_out_right_1 <= grid_out_right_1;
            data_out_bot_0   <= grid_out_bot_0;
            data_out_bot_1   <= grid_out_bot_1;
            data_out_left_0  <= grid_out_left_0;
            data_out_left_1  <= grid_out_left_1;
        end
    end

endmodule