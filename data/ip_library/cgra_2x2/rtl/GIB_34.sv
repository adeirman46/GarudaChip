`include "cgra_defs.svh"
module GIB_34(
  input  [31:0] io_itrackW_0,
  output [31:0] io_otrackW_0,
  input  [31:0] io_itrackN_0,
  output [31:0] io_otrackN_0
);
  assign io_otrackW_0 = io_itrackN_0; // @[Interconnect.scala 844:21 Interconnect.scala 918:43]
  assign io_otrackN_0 = io_itrackW_0; // @[Interconnect.scala 845:21 Interconnect.scala 918:43]
endmodule
