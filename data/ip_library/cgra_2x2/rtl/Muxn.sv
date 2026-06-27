`include "cgra_defs.svh"
module Muxn(
  input         io_config,
  input  [31:0] io_in_0,
  input  [31:0] io_in_1,
  output [31:0] io_out
);
  assign io_out = io_config ? io_in_1 : io_in_0; // @[Multiplexer.scala 20:10]
endmodule
