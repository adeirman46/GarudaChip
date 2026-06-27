`include "cgra_defs.svh"
module ALU_12(
  input  [4:0]  io_config,
  input  [31:0] io_in_0,
  input  [31:0] io_in_1,
  output [31:0] io_out
);
  wire [31:0] _T_4 = io_in_0 + io_in_1; // @[Operations.scala 131:41]
  wire [31:0] _T_8 = io_in_0 - io_in_1; // @[Operations.scala 133:41]
  wire  _T_9 = 5'h0 == io_config; // @[Mux.scala 80:60]
  wire [31:0] _T_10 = _T_9 ? io_in_0 : 32'h0; // @[Mux.scala 80:57]
  wire  _T_11 = 5'h1 == io_config; // @[Mux.scala 80:60]
  wire [31:0] _T_12 = _T_11 ? _T_4 : _T_10; // @[Mux.scala 80:57]
  wire  _T_13 = 5'h2 == io_config; // @[Mux.scala 80:60]
  assign io_out = _T_13 ? _T_8 : _T_12; // @[ALU.scala 26:10]
endmodule
