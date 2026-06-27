`include "cgra_defs.svh"
module Muxn_62(
  input  [1:0]  io_config,
  input  [31:0] io_in_0,
  input  [31:0] io_in_1,
  input  [31:0] io_in_2,
  input  [31:0] io_in_3,
  output [31:0] io_out
);
  wire  _T = 2'h1 == io_config; // @[Mux.scala 80:60]
  wire [31:0] _T_1 = _T ? io_in_1 : io_in_0; // @[Mux.scala 80:57]
  wire  _T_2 = 2'h2 == io_config; // @[Mux.scala 80:60]
  wire [31:0] _T_3 = _T_2 ? io_in_2 : _T_1; // @[Mux.scala 80:57]
  wire  _T_4 = 2'h3 == io_config; // @[Mux.scala 80:60]
  assign io_out = _T_4 ? io_in_3 : _T_3; // @[Multiplexer.scala 20:10]
endmodule
