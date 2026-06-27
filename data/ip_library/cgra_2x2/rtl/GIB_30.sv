`include "cgra_defs.svh"
module GIB_30(
  input         clock,
  input         reset,
  input         io_cfg_en,
  input  [17:0] io_cfg_addr,
  input  [31:0] io_cfg_data,
  input         io_en,
  input  [31:0] io_itrackW_0,
  output [31:0] io_otrackW_0,
  input  [31:0] io_itrackN_0,
  output [31:0] io_otrackN_0,
  input  [31:0] io_itrackE_0,
  output [31:0] io_otrackE_0
);
  wire  ConfigMem_clock; // @[Interconnect.scala 878:21]
  wire  ConfigMem_reset; // @[Interconnect.scala 878:21]
  wire  ConfigMem_io_cfg_en; // @[Interconnect.scala 878:21]
  wire  ConfigMem_io_en; // @[Interconnect.scala 878:21]
  wire [2:0] ConfigMem_io_cycle; // @[Interconnect.scala 878:21]
  wire [2:0] ConfigMem_io_II; // @[Interconnect.scala 878:21]
  wire [31:0] ConfigMem_io_cfg_data; // @[Interconnect.scala 878:21]
  wire [2:0] ConfigMem_io_out_0; // @[Interconnect.scala 878:21]
  wire  Muxn_io_config; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_io_in_0; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_io_in_1; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_io_out; // @[Interconnect.scala 890:25]
  wire  Muxn_1_io_config; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_1_io_in_0; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_1_io_in_1; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_1_io_out; // @[Interconnect.scala 890:25]
  wire  Muxn_2_io_config; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_2_io_in_0; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_2_io_in_1; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_2_io_out; // @[Interconnect.scala 890:25]
  wire  _T_1 = 10'h53 == io_cfg_addr[17:8]; // @[Interconnect.scala 879:50]
  ConfigMem_64 ConfigMem ( // @[Interconnect.scala 878:21]
    .clock(ConfigMem_clock),
    .reset(ConfigMem_reset),
    .io_cfg_en(ConfigMem_io_cfg_en),
    .io_en(ConfigMem_io_en),
    .io_cycle(ConfigMem_io_cycle),
    .io_II(ConfigMem_io_II),
    .io_cfg_data(ConfigMem_io_cfg_data),
    .io_out_0(ConfigMem_io_out_0)
  );
  Muxn Muxn ( // @[Interconnect.scala 890:25]
    .io_config(Muxn_io_config),
    .io_in_0(Muxn_io_in_0),
    .io_in_1(Muxn_io_in_1),
    .io_out(Muxn_io_out)
  );
  Muxn Muxn_1 ( // @[Interconnect.scala 890:25]
    .io_config(Muxn_1_io_config),
    .io_in_0(Muxn_1_io_in_0),
    .io_in_1(Muxn_1_io_in_1),
    .io_out(Muxn_1_io_out)
  );
  Muxn Muxn_2 ( // @[Interconnect.scala 890:25]
    .io_config(Muxn_2_io_config),
    .io_in_0(Muxn_2_io_in_0),
    .io_in_1(Muxn_2_io_in_1),
    .io_out(Muxn_2_io_out)
  );
  assign io_otrackW_0 = Muxn_io_out; // @[Interconnect.scala 844:21 Interconnect.scala 896:45]
  assign io_otrackN_0 = Muxn_1_io_out; // @[Interconnect.scala 845:21 Interconnect.scala 896:45]
  assign io_otrackE_0 = Muxn_2_io_out; // @[Interconnect.scala 846:21 Interconnect.scala 896:45]
  assign ConfigMem_clock = clock;
  assign ConfigMem_reset = reset;
  assign ConfigMem_io_cfg_en = io_cfg_en & _T_1; // @[Interconnect.scala 879:19]
  assign ConfigMem_io_en = io_en; // @[Interconnect.scala 881:15]
  assign ConfigMem_io_cycle = io_cfg_addr[5:3]; // @[Interconnect.scala 882:18]
  assign ConfigMem_io_II = io_cfg_addr[2:0]; // @[Interconnect.scala 883:15]
  assign ConfigMem_io_cfg_data = io_cfg_data; // @[Interconnect.scala 884:21]
  assign Muxn_io_config = ConfigMem_io_out_0[0]; // @[Interconnect.scala 900:23]
  assign Muxn_io_in_0 = io_itrackN_0; // @[Interconnect.scala 892:63]
  assign Muxn_io_in_1 = io_itrackE_0; // @[Interconnect.scala 892:63]
  assign Muxn_1_io_config = ConfigMem_io_out_0[1]; // @[Interconnect.scala 900:23]
  assign Muxn_1_io_in_0 = io_itrackW_0; // @[Interconnect.scala 892:63]
  assign Muxn_1_io_in_1 = io_itrackE_0; // @[Interconnect.scala 892:63]
  assign Muxn_2_io_config = ConfigMem_io_out_0[2]; // @[Interconnect.scala 900:23]
  assign Muxn_2_io_in_0 = io_itrackW_0; // @[Interconnect.scala 892:63]
  assign Muxn_2_io_in_1 = io_itrackN_0; // @[Interconnect.scala 892:63]
endmodule
