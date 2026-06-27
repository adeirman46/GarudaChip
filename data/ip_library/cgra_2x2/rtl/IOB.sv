`include "cgra_defs.svh"
module IOB(
  input  [31:0] io_in_0,
  output [31:0] io_out_0
);
  assign io_out_0 = io_in_0; // @[IOB.scala 60:42]
endmodule
