`include "cgra_defs.svh"
module Muxn_65(
  input  [2:0]  io_config,
  input  [31:0] io_in_0,
  input  [31:0] io_in_1,
  input  [31:0] io_in_2,
  input  [31:0] io_in_3,
  input  [31:0] io_in_4,
  output [31:0] io_out
);
  wire  _T_2 = 3'h1 == io_config; // @[Mux.scala 80:60]
  wire [31:0] _T_3 = _T_2 ? io_in_1 : io_in_0; // @[Mux.scala 80:57]
  wire  _T_4 = 3'h2 == io_config; // @[Mux.scala 80:60]
  wire [31:0] _T_5 = _T_4 ? io_in_2 : _T_3; // @[Mux.scala 80:57]
  wire  _T_6 = 3'h3 == io_config; // @[Mux.scala 80:60]
  wire [31:0] _T_7 = _T_6 ? io_in_3 : _T_5; // @[Mux.scala 80:57]
  wire  _T_8 = 3'h4 == io_config; // @[Mux.scala 80:60]
  assign io_out = _T_8 ? io_in_4 : _T_7; // @[Multiplexer.scala 20:10]
endmodule
