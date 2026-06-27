`include "cgra_defs.svh"
module GIB_6(
  input         clock,
  input         reset,
  input         io_cfg_en,
  input  [17:0] io_cfg_addr,
  input  [31:0] io_cfg_data,
  input         io_en,
  output [31:0] io_ipinNW_0,
  input  [31:0] io_opinNW_0,
  output [31:0] io_ipinSE_0,
  input  [31:0] io_opinSE_0,
  output [31:0] io_ipinSW_0,
  output [31:0] io_ipinSW_1,
  input  [31:0] io_opinSW_0,
  input  [31:0] io_itrackW_0,
  output [31:0] io_otrackW_0,
  input  [31:0] io_itrackS_0,
  output [31:0] io_otrackS_0
);
  wire  ConfigMem_clock; // @[Interconnect.scala 878:21]
  wire  ConfigMem_reset; // @[Interconnect.scala 878:21]
  wire  ConfigMem_io_cfg_en; // @[Interconnect.scala 878:21]
  wire  ConfigMem_io_en; // @[Interconnect.scala 878:21]
  wire [2:0] ConfigMem_io_cycle; // @[Interconnect.scala 878:21]
  wire [2:0] ConfigMem_io_II; // @[Interconnect.scala 878:21]
  wire [31:0] ConfigMem_io_cfg_data; // @[Interconnect.scala 878:21]
  wire [7:0] ConfigMem_io_out_0; // @[Interconnect.scala 878:21]
  wire [1:0] Muxn_io_config; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_io_in_0; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_io_in_1; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_io_in_2; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_io_in_3; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_io_out; // @[Interconnect.scala 890:25]
  wire  Muxn_1_io_config; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_1_io_in_0; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_1_io_in_1; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_1_io_out; // @[Interconnect.scala 890:25]
  wire  Muxn_2_io_config; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_2_io_in_0; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_2_io_in_1; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_2_io_out; // @[Interconnect.scala 890:25]
  wire [1:0] Muxn_3_io_config; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_3_io_in_0; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_3_io_in_1; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_3_io_in_2; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_3_io_out; // @[Interconnect.scala 890:25]
  wire [1:0] Muxn_4_io_config; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_4_io_in_0; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_4_io_in_1; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_4_io_in_2; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_4_io_out; // @[Interconnect.scala 890:25]
  wire  _T_1 = 10'h17 == io_cfg_addr[17:8]; // @[Interconnect.scala 879:50]
  ConfigMem_36 ConfigMem ( // @[Interconnect.scala 878:21]
    .clock(ConfigMem_clock),
    .reset(ConfigMem_reset),
    .io_cfg_en(ConfigMem_io_cfg_en),
    .io_en(ConfigMem_io_en),
    .io_cycle(ConfigMem_io_cycle),
    .io_II(ConfigMem_io_II),
    .io_cfg_data(ConfigMem_io_cfg_data),
    .io_out_0(ConfigMem_io_out_0)
  );
  Muxn_62 Muxn ( // @[Interconnect.scala 890:25]
    .io_config(Muxn_io_config),
    .io_in_0(Muxn_io_in_0),
    .io_in_1(Muxn_io_in_1),
    .io_in_2(Muxn_io_in_2),
    .io_in_3(Muxn_io_in_3),
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
  Muxn_63 Muxn_3 ( // @[Interconnect.scala 890:25]
    .io_config(Muxn_3_io_config),
    .io_in_0(Muxn_3_io_in_0),
    .io_in_1(Muxn_3_io_in_1),
    .io_in_2(Muxn_3_io_in_2),
    .io_out(Muxn_3_io_out)
  );
  Muxn_63 Muxn_4 ( // @[Interconnect.scala 890:25]
    .io_config(Muxn_4_io_config),
    .io_in_0(Muxn_4_io_in_0),
    .io_in_1(Muxn_4_io_in_1),
    .io_in_2(Muxn_4_io_in_2),
    .io_out(Muxn_4_io_out)
  );
  assign io_ipinNW_0 = Muxn_io_out; // @[Interconnect.scala 840:20 Interconnect.scala 896:45]
  assign io_ipinSE_0 = Muxn_1_io_out; // @[Interconnect.scala 843:20 Interconnect.scala 896:45]
  assign io_ipinSW_0 = Muxn_2_io_out; // @[Interconnect.scala 842:20 Interconnect.scala 896:45]
  assign io_ipinSW_1 = io_itrackS_0; // @[Interconnect.scala 842:20 Interconnect.scala 908:45]
  assign io_otrackW_0 = Muxn_3_io_out; // @[Interconnect.scala 844:21 Interconnect.scala 896:45]
  assign io_otrackS_0 = Muxn_4_io_out; // @[Interconnect.scala 847:21 Interconnect.scala 896:45]
  assign ConfigMem_clock = clock;
  assign ConfigMem_reset = reset;
  assign ConfigMem_io_cfg_en = io_cfg_en & _T_1; // @[Interconnect.scala 879:19]
  assign ConfigMem_io_en = io_en; // @[Interconnect.scala 881:15]
  assign ConfigMem_io_cycle = io_cfg_addr[5:3]; // @[Interconnect.scala 882:18]
  assign ConfigMem_io_II = io_cfg_addr[2:0]; // @[Interconnect.scala 883:15]
  assign ConfigMem_io_cfg_data = io_cfg_data; // @[Interconnect.scala 884:21]
  assign Muxn_io_config = ConfigMem_io_out_0[1:0]; // @[Interconnect.scala 900:23]
  assign Muxn_io_in_0 = io_opinSE_0; // @[Interconnect.scala 892:63]
  assign Muxn_io_in_1 = io_opinSW_0; // @[Interconnect.scala 892:63]
  assign Muxn_io_in_2 = io_itrackW_0; // @[Interconnect.scala 892:63]
  assign Muxn_io_in_3 = io_itrackS_0; // @[Interconnect.scala 892:63]
  assign Muxn_1_io_config = ConfigMem_io_out_0[2]; // @[Interconnect.scala 900:23]
  assign Muxn_1_io_in_0 = io_opinNW_0; // @[Interconnect.scala 892:63]
  assign Muxn_1_io_in_1 = io_itrackW_0; // @[Interconnect.scala 892:63]
  assign Muxn_2_io_config = ConfigMem_io_out_0[3]; // @[Interconnect.scala 900:23]
  assign Muxn_2_io_in_0 = io_opinSE_0; // @[Interconnect.scala 892:63]
  assign Muxn_2_io_in_1 = io_itrackS_0; // @[Interconnect.scala 892:63]
  assign Muxn_3_io_config = ConfigMem_io_out_0[5:4]; // @[Interconnect.scala 900:23]
  assign Muxn_3_io_in_0 = io_opinSE_0; // @[Interconnect.scala 892:63]
  assign Muxn_3_io_in_1 = io_opinSW_0; // @[Interconnect.scala 892:63]
  assign Muxn_3_io_in_2 = io_itrackS_0; // @[Interconnect.scala 892:63]
  assign Muxn_4_io_config = ConfigMem_io_out_0[7:6]; // @[Interconnect.scala 900:23]
  assign Muxn_4_io_in_0 = io_opinNW_0; // @[Interconnect.scala 892:63]
  assign Muxn_4_io_in_1 = io_opinSE_0; // @[Interconnect.scala 892:63]
  assign Muxn_4_io_in_2 = io_itrackW_0; // @[Interconnect.scala 892:63]
endmodule
