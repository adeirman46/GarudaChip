`include "cgra_defs.svh"
module DelayPipe_50(
  input         clock,
  input         reset,
  input         io_en,
  input  [1:0]  io_config,
  input  [31:0] io_in,
  output [31:0] io_out
);
`ifdef RANDOMIZE_REG_INIT
  reg [31:0] _RAND_0;
  reg [31:0] _RAND_1;
  reg [31:0] _RAND_2;
  reg [31:0] _RAND_3;
  reg [31:0] _RAND_4;
  reg [31:0] _RAND_5;
  reg [31:0] _RAND_6;
`endif // RANDOMIZE_REG_INIT
  reg [31:0] regs_0; // @[DelayPipe.scala 70:21]
  reg [31:0] regs_1; // @[DelayPipe.scala 70:21]
  reg [31:0] regs_2; // @[DelayPipe.scala 70:21]
  reg [1:0] wptr; // @[DelayPipe.scala 71:21]
  reg [1:0] rptr; // @[DelayPipe.scala 72:21]
  reg [1:0] config_temp; // @[DelayPipe.scala 74:28]
  wire  _T_1 = wptr < 2'h2; // @[DelayPipe.scala 77:23]
  wire  _T_2 = io_en & _T_1; // @[DelayPipe.scala 77:14]
  wire [1:0] _T_4 = wptr + 2'h1; // @[DelayPipe.scala 78:17]
  wire  _T_7 = _T_4 >= io_config; // @[DelayPipe.scala 83:17]
  wire [1:0] _T_11 = _T_4 - io_config; // @[DelayPipe.scala 84:24]
  wire [2:0] _GEN_16 = {{1'd0}, wptr}; // @[DelayPipe.scala 86:30]
  wire [2:0] _T_13 = 3'h4 + _GEN_16; // @[DelayPipe.scala 86:30]
  wire [2:0] _GEN_17 = {{1'd0}, io_config}; // @[DelayPipe.scala 86:37]
  wire [2:0] _T_15 = _T_13 - _GEN_17; // @[DelayPipe.scala 86:37]
  wire [2:0] _GEN_1 = _T_7 ? {{1'd0}, _T_11} : _T_15; // @[DelayPipe.scala 83:30]
  wire  _T_16 = io_config > 2'h0; // @[DelayPipe.scala 90:28]
  wire  _T_17 = io_en & _T_16; // @[DelayPipe.scala 90:14]
  reg [1:0] cnt; // @[DelayPipe.scala 94:20]
  wire  _T_18 = ~io_en; // @[DelayPipe.scala 95:8]
  wire  _T_19 = config_temp != io_config; // @[DelayPipe.scala 97:26]
  wire  _T_20 = cnt < io_config; // @[DelayPipe.scala 99:18]
  wire [1:0] _T_22 = cnt + 2'h1; // @[DelayPipe.scala 100:16]
  wire  _T_23 = 2'h0 == io_config; // @[DelayPipe.scala 103:22]
  wire  _T_24 = io_en & _T_23; // @[DelayPipe.scala 103:14]
  wire  _T_25 = cnt == io_config; // @[DelayPipe.scala 105:28]
  wire  _T_26 = io_en & _T_25; // @[DelayPipe.scala 105:20]
  wire [31:0] _GEN_12 = 2'h1 == rptr ? regs_1 : regs_0; // @[DelayPipe.scala 106:12]
  wire [31:0] _GEN_13 = 2'h2 == rptr ? regs_2 : _GEN_12; // @[DelayPipe.scala 106:12]
  wire [31:0] _GEN_14 = _T_26 ? _GEN_13 : 32'h0; // @[DelayPipe.scala 105:43]
  assign io_out = _T_24 ? io_in : _GEN_14; // @[DelayPipe.scala 104:12 DelayPipe.scala 106:12 DelayPipe.scala 108:12]
`ifdef RANDOMIZE_GARBAGE_ASSIGN
`define RANDOMIZE
`endif
`ifdef RANDOMIZE_INVALID_ASSIGN
`define RANDOMIZE
`endif
`ifdef RANDOMIZE_REG_INIT
`define RANDOMIZE
`endif
`ifdef RANDOMIZE_MEM_INIT
`define RANDOMIZE
`endif
`ifndef RANDOM
`define RANDOM $random
`endif
`ifdef RANDOMIZE_MEM_INIT
  integer initvar;
`endif
`ifndef SYNTHESIS
`ifdef FIRRTL_BEFORE_INITIAL
`FIRRTL_BEFORE_INITIAL
`endif
initial begin
  `ifdef RANDOMIZE
    `ifdef INIT_RANDOM
      `INIT_RANDOM
    `endif
    `ifndef VERILATOR
      `ifdef RANDOMIZE_DELAY
        #`RANDOMIZE_DELAY begin end
      `else
        #0.002 begin end
      `endif
    `endif
`ifdef RANDOMIZE_REG_INIT
  _RAND_0 = {1{`RANDOM}};
  regs_0 = _RAND_0[31:0];
  _RAND_1 = {1{`RANDOM}};
  regs_1 = _RAND_1[31:0];
  _RAND_2 = {1{`RANDOM}};
  regs_2 = _RAND_2[31:0];
  _RAND_3 = {1{`RANDOM}};
  wptr = _RAND_3[1:0];
  _RAND_4 = {1{`RANDOM}};
  rptr = _RAND_4[1:0];
  _RAND_5 = {1{`RANDOM}};
  config_temp = _RAND_5[1:0];
  _RAND_6 = {1{`RANDOM}};
  cnt = _RAND_6[1:0];
`endif // RANDOMIZE_REG_INIT
  `endif // RANDOMIZE
end // initial
`ifdef FIRRTL_AFTER_INITIAL
`FIRRTL_AFTER_INITIAL
`endif
`endif // SYNTHESIS
  always @(posedge clock) begin
    if (reset) begin
      regs_0 <= 32'h0;
    end else if (_T_17) begin
      if (2'h0 == wptr) begin
        regs_0 <= io_in;
      end
    end
    if (reset) begin
      regs_1 <= 32'h0;
    end else if (_T_17) begin
      if (2'h1 == wptr) begin
        regs_1 <= io_in;
      end
    end
    if (reset) begin
      regs_2 <= 32'h0;
    end else if (_T_17) begin
      if (2'h2 == wptr) begin
        regs_2 <= io_in;
      end
    end
    if (reset) begin
      wptr <= 2'h0;
    end else if (_T_2) begin
      wptr <= _T_4;
    end else begin
      wptr <= 2'h0;
    end
    if (reset) begin
      rptr <= 2'h0;
    end else begin
      rptr <= _GEN_1[1:0];
    end
    if (reset) begin
      config_temp <= 2'h0;
    end else begin
      config_temp <= io_config;
    end
    if (reset) begin
      cnt <= 2'h0;
    end else if (_T_18) begin
      cnt <= 2'h0;
    end else if (_T_19) begin
      cnt <= 2'h1;
    end else if (_T_20) begin
      cnt <= _T_22;
    end
  end
endmodule
