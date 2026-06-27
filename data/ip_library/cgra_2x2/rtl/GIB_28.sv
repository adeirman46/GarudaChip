`include "cgra_defs.svh"
module GIB_28(
  input  [31:0] io_itrackN_0,
  output [31:0] io_otrackN_0,
  input  [31:0] io_itrackE_0,
  output [31:0] io_otrackE_0
);
  assign io_otrackN_0 = io_itrackE_0; // @[Interconnect.scala 845:21 Interconnect.scala 918:43]
  assign io_otrackE_0 = io_itrackN_0; // @[Interconnect.scala 846:21 Interconnect.scala 918:43]
endmodule
