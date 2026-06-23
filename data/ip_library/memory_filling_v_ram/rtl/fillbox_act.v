module fillbox_act (
	input wire [27:0] vram,
	input wire [9:0] width,
	input wire [9:0] height,
	input wire start,
	output wire done,

	// AXI4 stuff
	input wire clk,
	input wire bready,
	output reg [27:0] awaddr,
	output reg burst_start,
	output reg [7:0] awlen,
	output reg [3:0] wstrb
);

// X/Y axis state machine
parameter IDLE = 2'h0,
	START = 2'h1,
	WAIT = 2'h2;
localparam SCREEN_WIDTH = 28'd1280;

reg [27:0] vram_y = 0;
reg [10:0] offset = 0;
reg [10:0] delta = 0;
reg [9:0] width_work = 0;
reg [9:0] height_work = 0;
reg [9:0] expected_count = 0;
reg [9:0] real_count = 0;
reg [1:0] state_x = IDLE, state_y = IDLE;
reg	start_x = 0;
reg	end_x = 0;
reg	done_ff1 = 0;
reg	done_ff2 = 0;
wire [27:0] awaddr_tmp = vram_y + {17'b0, offset};
assign	done = done_ff1 && ~done_ff2;

// end of accelarator action
always @(posedge clk) begin
	done_ff2 <= done_ff1;
	done_ff1 <= (width_work == 10'd0 && height_work == 10'd0 && expected_count == real_count);
	awaddr <= {awaddr_tmp[27:2], 2'b0};
end

// real access count
always @(posedge clk) begin
  if (start_x == 'b0)
    real_count <= 10'd0;
  else if (bready)
    real_count <= real_count + 10'd1;
  else
    real_count <= real_count;
end
// real access count
always @(posedge clk) begin
  if (start_x == 'b0)
    real_count <= 10'd0;
  else if (bready)
    real_count <= real_count + 10'd1;
  else
    real_count <= real_count;
end

// Y axis action
always @(posedge clk) begin
  case (state_y)
    IDLE:
      begin
        if (start) begin
          state_y <= START;
          height_work <= height;
          vram_y <= vram;
        end
        else begin
          state_y <= state_y;
          height_work <= height_work;
          vram_y <= vram_y;
        end
        start_x <= 'b0;
      end
    START:
      begin
        if (height_work == 10'd0) begin
          state_y <= IDLE;
          height_work <= 10'd0;
          vram_y <= vram_y;
          start_x <= 'b0;
        end
        else begin
          state_y <= WAIT;
          height_work <= height_work;
          vram_y <= vram_y;
          start_x <= 'b1;
        end
      end
    WAIT:
      begin
        if (end_x) begin
          state_y <= START;
          height_work <= height_work - 10'd1;
          vram_y <= vram_y + SCREEN_WIDTH;
          start_x <= 'b0;
        end
        else begin
          state_y <= state_y;
          height_work <= height_work;
          vram_y <= vram_y;
          start_x <= start_x;
        end
      end
    default:
      begin
        state_y <= IDLE;
        height_work <= height_work;
        vram_y <= vram_y;
        start_x <= 'b0;
      end
  endcase
end
// X axis action
always @(posedge clk) begin
  if (start_x == 'b0) begin
    end_x <= 'b0;
    expected_count = 10'd0;
    width_work <= 10'd0;
    offset <= 11'd0;
    delta <= 11'd0;
    burst_start <= 'b0;
    awlen <= 8'd0;
    wstrb <= 4'b0000;
    state_x <= IDLE;
  end
  else begin
    case (state_x)
      IDLE:
        begin
          end_x <= 'b0;
          expected_count <= 10'd0;
          width_work <= width;
          offset <= 11'd0;
          delta <= 11'd0;
          burst_start <= 'b0;
          awlen <= 8'd0;
          wstrb <= 4'b0000;
          state_x <= START;
        end
      START:
        begin
          if (width_work == 10'd0) begin
            end_x <= 'b1;
            expected_count <= expected_count;
            width_work <= width_work;
            offset <= offset;
            delta <= delta;
            burst_start <= 'b0;
            awlen <= awlen;
            wstrb <= wstrb;
            state_x <= IDLE;
          end
          else begin
            if (awaddr_tmp[1]) begin
              // address not divisable by 4
              // width_work greater than 0
              width_work <= width_work - 10'd1;
              delta <= 11'd2;
              wstrb <= 4'b1100;
              awlen <= 8'd0;
            end
            else if (width_work == 10'd1) begin
              // address divisable by 4
              // width_work equal to 1
              width_work <= width_work - 10'd1;
              delta <= 11'd2;
// address divisable by 4
              // width_work equal to 1
              width_work <= width_work - 10'd1;
              delta <= 11'd2;
              wstrb <= 4'b0011;
              awlen <= 8'd0;
            end
            else if (awaddr_tmp[2] || width_work <= 10'd3) begin
              // address not divisable by 8
              // width_work greater than 1, less than 4
              width_work <= width_work - 10'd2;
              delta <= 11'd4;
              wstrb <= 4'b1111;
              awlen <= 8'd0;
            end
            else if (awaddr_tmp[3] || width_work <= 10'd7) begin
              // address not divisable by 16
              // width_work greater than 3, less than 8
              width_work <= width_work - 10'd4;
              delta <= 11'd8;
              wstrb <= 4'b1111;
              awlen <= 8'd1;
            end
            else if (awaddr_tmp[4] || width_work <= 10'd15) begin
              // address not divisable by 32
              // width_work greater than 7, less than 16
              width_work <= width_work - 10'd8;
              delta <= 11'd16;
              wstrb <= 4'b1111;
              awlen <= 8'd3;
            end
            else if (awaddr_tmp[5] || width_work <= 10'd31) begin
              // address not divisable by 64
              // width_work greater thean 15, less than 32
              width_work <= width_work - 10'd16;
              delta <= 11'd32;
              wstrb <= 4'b1111;
// width_work greater thean 15, less than 32
              width_work <= width_work - 10'd16;
              delta <= 11'd32;
              wstrb <= 4'b1111;
              awlen <= 8'd7;
            end
            else begin
              // address divisable by 64
              // width_work greater than 31
              width_work <= width_work - 10'd32;
              delta <= 11'd64;
              wstrb <= 4'b1111;
              awlen <= 8'd15;
            end
            end_x <= 'b0;
            expected_count <= expected_count + 10'd1;
            offset <= offset;
            burst_start <= 'b1;
            state_x <= WAIT;
          end
        end
      WAIT:
        begin
          if (bready) begin
            offset <= offset + delta;
            delta <= 11'd0;
            state_x <= START;
          end
          else begin
            offset <= offset;
            delta <= delta;
            state_x <= state_x;
          end
          awlen <= awlen;
          wstrb <= wstrb;
          burst_start <= 'b0;
          end_x <= 'b0;
          expected_count <= expected_count;
          width_work <= width_work;
        end
      default:
        begin
          end_x <= 'b0;
          expected_count <= expected_count;
          width_work <= width_work;
          offset <= offset;
          delta <= delta;
          burst_start <= 'b0;
          awlen <= awlen;
          wstrb <= wstrb;
          state_x <= IDLE;
        end
    endcase
  end
end
endmodule
