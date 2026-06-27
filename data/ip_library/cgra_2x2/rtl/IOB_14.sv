`include "cgra_defs.svh"
module IOB_14(
  input         clock,
  input         reset,
  input         io_cfg_en,
  input  [17:0] io_cfg_addr,
  input  [31:0] io_cfg_data,
  input  [31:0] io_in_0,
  input  [31:0] io_in_1,
  input         io_en,
  output [31:0] io_out_0
);
  wire  Muxn_io_config; // @[IOB.scala 40:41]
  wire [31:0] Muxn_io_in_0; // @[IOB.scala 40:41]
  wire [31:0] Muxn_io_in_1; // @[IOB.scala 40:41]
  wire [31:0] Muxn_io_out; // @[IOB.scala 40:41]
  wire  ConfigMem_clock; // @[IOB.scala 41:21]
  wire  ConfigMem_reset; // @[IOB.scala 41:21]
  wire  ConfigMem_io_cfg_en; // @[IOB.scala 41:21]
  wire  ConfigMem_io_en; // @[IOB.scala 41:21]
  wire [2:0] ConfigMem_io_cycle; // @[IOB.scala 41:21]
  wire [2:0] ConfigMem_io_II; // @[IOB.scala 41:21]
  wire [31:0] ConfigMem_io_cfg_data; // @[IOB.scala 41:21]
  wire  ConfigMem_io_out_0; // @[IOB.scala 41:21]
  wire  _T_1 = 10'hb == io_cfg_addr[17:8]; // @[IOB.scala 42:50]
  Muxn Muxn ( // @[IOB.scala 40:41]
    .io_config(Muxn_io_config),
    .io_in_0(Muxn_io_in_0),
    .io_in_1(Muxn_io_in_1),
    .io_out(Muxn_io_out)
  );
  ConfigMem ConfigMem ( // @[IOB.scala 41:21]
    .clock(ConfigMem_clock),
    .reset(ConfigMem_reset),
    .io_cfg_en(ConfigMem_io_cfg_en),
    .io_en(ConfigMem_io_en),
    .io_cycle(ConfigMem_io_cycle),
    .io_II(ConfigMem_io_II),
    .io_cfg_data(ConfigMem_io_cfg_data),
    .io_out_0(ConfigMem_io_out_0)
  );
  assign io_out_0 = Muxn_io_out; // @[IOB.scala 55:17]
  assign Muxn_io_config = ConfigMem_io_out_0; // @[IOB.scala 56:22]
  assign Muxn_io_in_0 = io_in_0; // @[IOB.scala 53:23]
  assign Muxn_io_in_1 = io_in_1; // @[IOB.scala 53:23]
  assign ConfigMem_clock = clock;
  assign ConfigMem_reset = reset;
  assign ConfigMem_io_cfg_en = io_cfg_en & _T_1; // @[IOB.scala 42:19]
  assign ConfigMem_io_en = io_en; // @[IOB.scala 44:15]
  assign ConfigMem_io_cycle = io_cfg_addr[5:3]; // @[IOB.scala 45:18]
  assign ConfigMem_io_II = io_cfg_addr[2:0]; // @[IOB.scala 46:15]
  assign ConfigMem_io_cfg_data = io_cfg_data; // @[IOB.scala 47:21]
endmodule
