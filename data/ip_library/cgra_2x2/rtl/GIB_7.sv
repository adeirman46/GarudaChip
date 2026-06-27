`include "cgra_defs.svh"
module GIB_7(
  input         clock,
  input         reset,
  input         io_cfg_en,
  input  [17:0] io_cfg_addr,
  input  [31:0] io_cfg_data,
  input         io_en,
  output [31:0] io_ipinNW_0,
  input  [31:0] io_opinNW_0,
  output [31:0] io_ipinNE_0,
  output [31:0] io_ipinNE_1,
  input  [31:0] io_opinNE_0,
  output [31:0] io_ipinSE_0,
  output [31:0] io_ipinSE_1,
  input  [31:0] io_opinSE_0,
  output [31:0] io_ipinSW_0,
  input  [31:0] io_opinSW_0,
  input  [31:0] io_itrackN_0,
  output [31:0] io_otrackN_0,
  input  [31:0] io_itrackE_0,
  output [31:0] io_otrackE_0,
  input  [31:0] io_itrackS_0,
  output [31:0] io_otrackS_0
);
`ifdef RANDOMIZE_REG_INIT
  reg [31:0] _RAND_0;
  reg [31:0] _RAND_1;
  reg [31:0] _RAND_2;
`endif // RANDOMIZE_REG_INIT
  wire  ConfigMem_clock; // @[Interconnect.scala 878:21]
  wire  ConfigMem_reset; // @[Interconnect.scala 878:21]
  wire  ConfigMem_io_cfg_en; // @[Interconnect.scala 878:21]
  wire  ConfigMem_io_en; // @[Interconnect.scala 878:21]
  wire [2:0] ConfigMem_io_cycle; // @[Interconnect.scala 878:21]
  wire [2:0] ConfigMem_io_II; // @[Interconnect.scala 878:21]
  wire [31:0] ConfigMem_io_cfg_data; // @[Interconnect.scala 878:21]
  wire [20:0] ConfigMem_io_out_0; // @[Interconnect.scala 878:21]
  wire [1:0] Muxn_io_config; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_io_in_0; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_io_in_1; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_io_in_2; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_io_in_3; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_io_out; // @[Interconnect.scala 890:25]
  wire [1:0] Muxn_1_io_config; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_1_io_in_0; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_1_io_in_1; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_1_io_in_2; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_1_io_in_3; // @[Interconnect.scala 890:25]
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
  wire [2:0] Muxn_5_io_config; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_5_io_in_0; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_5_io_in_1; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_5_io_in_2; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_5_io_in_3; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_5_io_in_4; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_5_io_out; // @[Interconnect.scala 890:25]
  wire [2:0] Muxn_6_io_config; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_6_io_in_0; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_6_io_in_1; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_6_io_in_2; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_6_io_in_3; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_6_io_in_4; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_6_io_out; // @[Interconnect.scala 890:25]
  wire [2:0] Muxn_7_io_config; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_7_io_in_0; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_7_io_in_1; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_7_io_in_2; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_7_io_in_3; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_7_io_in_4; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_7_io_out; // @[Interconnect.scala 890:25]
  wire [2:0] Muxn_8_io_config; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_8_io_in_0; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_8_io_in_1; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_8_io_in_2; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_8_io_in_3; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_8_io_in_4; // @[Interconnect.scala 890:25]
  wire [31:0] Muxn_8_io_out; // @[Interconnect.scala 890:25]
  wire  _T_1 = 10'h21 == io_cfg_addr[17:8]; // @[Interconnect.scala 879:50]
  reg [31:0] _T_12; // @[Interconnect.scala 894:55]
  reg [31:0] _T_14; // @[Interconnect.scala 894:55]
  reg [31:0] _T_16; // @[Interconnect.scala 894:55]
  ConfigMem_37 ConfigMem ( // @[Interconnect.scala 878:21]
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
  Muxn_62 Muxn_1 ( // @[Interconnect.scala 890:25]
    .io_config(Muxn_1_io_config),
    .io_in_0(Muxn_1_io_in_0),
    .io_in_1(Muxn_1_io_in_1),
    .io_in_2(Muxn_1_io_in_2),
    .io_in_3(Muxn_1_io_in_3),
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
  Muxn_65 Muxn_5 ( // @[Interconnect.scala 890:25]
    .io_config(Muxn_5_io_config),
    .io_in_0(Muxn_5_io_in_0),
    .io_in_1(Muxn_5_io_in_1),
    .io_in_2(Muxn_5_io_in_2),
    .io_in_3(Muxn_5_io_in_3),
    .io_in_4(Muxn_5_io_in_4),
    .io_out(Muxn_5_io_out)
  );
  Muxn_65 Muxn_6 ( // @[Interconnect.scala 890:25]
    .io_config(Muxn_6_io_config),
    .io_in_0(Muxn_6_io_in_0),
    .io_in_1(Muxn_6_io_in_1),
    .io_in_2(Muxn_6_io_in_2),
    .io_in_3(Muxn_6_io_in_3),
    .io_in_4(Muxn_6_io_in_4),
    .io_out(Muxn_6_io_out)
  );
  Muxn_65 Muxn_7 ( // @[Interconnect.scala 890:25]
    .io_config(Muxn_7_io_config),
    .io_in_0(Muxn_7_io_in_0),
    .io_in_1(Muxn_7_io_in_1),
    .io_in_2(Muxn_7_io_in_2),
    .io_in_3(Muxn_7_io_in_3),
    .io_in_4(Muxn_7_io_in_4),
    .io_out(Muxn_7_io_out)
  );
  Muxn_65 Muxn_8 ( // @[Interconnect.scala 890:25]
    .io_config(Muxn_8_io_config),
    .io_in_0(Muxn_8_io_in_0),
    .io_in_1(Muxn_8_io_in_1),
    .io_in_2(Muxn_8_io_in_2),
    .io_in_3(Muxn_8_io_in_3),
    .io_in_4(Muxn_8_io_in_4),
    .io_out(Muxn_8_io_out)
  );
  assign io_ipinNW_0 = Muxn_io_out; // @[Interconnect.scala 840:20 Interconnect.scala 896:45]
  assign io_ipinNE_0 = Muxn_1_io_out; // @[Interconnect.scala 841:20 Interconnect.scala 896:45]
  assign io_ipinNE_1 = Muxn_2_io_out; // @[Interconnect.scala 841:20 Interconnect.scala 896:45]
  assign io_ipinSE_0 = Muxn_3_io_out; // @[Interconnect.scala 843:20 Interconnect.scala 896:45]
  assign io_ipinSE_1 = Muxn_4_io_out; // @[Interconnect.scala 843:20 Interconnect.scala 896:45]
  assign io_ipinSW_0 = Muxn_5_io_out; // @[Interconnect.scala 842:20 Interconnect.scala 896:45]
  assign io_otrackN_0 = _T_12; // @[Interconnect.scala 845:21 Interconnect.scala 894:45]
  assign io_otrackE_0 = _T_14; // @[Interconnect.scala 846:21 Interconnect.scala 894:45]
  assign io_otrackS_0 = _T_16; // @[Interconnect.scala 847:21 Interconnect.scala 894:45]
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
  assign Muxn_io_in_2 = io_itrackE_0; // @[Interconnect.scala 892:63]
  assign Muxn_io_in_3 = io_itrackS_0; // @[Interconnect.scala 892:63]
  assign Muxn_1_io_config = ConfigMem_io_out_0[3:2]; // @[Interconnect.scala 900:23]
  assign Muxn_1_io_in_0 = io_opinNW_0; // @[Interconnect.scala 892:63]
  assign Muxn_1_io_in_1 = io_opinSW_0; // @[Interconnect.scala 892:63]
  assign Muxn_1_io_in_2 = io_itrackN_0; // @[Interconnect.scala 892:63]
  assign Muxn_1_io_in_3 = io_itrackS_0; // @[Interconnect.scala 892:63]
  assign Muxn_2_io_config = ConfigMem_io_out_0[4]; // @[Interconnect.scala 900:23]
  assign Muxn_2_io_in_0 = io_itrackN_0; // @[Interconnect.scala 892:63]
  assign Muxn_2_io_in_1 = io_itrackS_0; // @[Interconnect.scala 892:63]
  assign Muxn_3_io_config = ConfigMem_io_out_0[6:5]; // @[Interconnect.scala 900:23]
  assign Muxn_3_io_in_0 = io_opinNW_0; // @[Interconnect.scala 892:63]
  assign Muxn_3_io_in_1 = io_itrackN_0; // @[Interconnect.scala 892:63]
  assign Muxn_3_io_in_2 = io_itrackE_0; // @[Interconnect.scala 892:63]
  assign Muxn_4_io_config = ConfigMem_io_out_0[8:7]; // @[Interconnect.scala 900:23]
  assign Muxn_4_io_in_0 = io_opinNE_0; // @[Interconnect.scala 892:63]
  assign Muxn_4_io_in_1 = io_itrackN_0; // @[Interconnect.scala 892:63]
  assign Muxn_4_io_in_2 = io_itrackE_0; // @[Interconnect.scala 892:63]
  assign Muxn_5_io_config = ConfigMem_io_out_0[11:9]; // @[Interconnect.scala 900:23]
  assign Muxn_5_io_in_0 = io_opinNE_0; // @[Interconnect.scala 892:63]
  assign Muxn_5_io_in_1 = io_opinSE_0; // @[Interconnect.scala 892:63]
  assign Muxn_5_io_in_2 = io_itrackN_0; // @[Interconnect.scala 892:63]
  assign Muxn_5_io_in_3 = io_itrackE_0; // @[Interconnect.scala 892:63]
  assign Muxn_5_io_in_4 = io_itrackS_0; // @[Interconnect.scala 892:63]
  assign Muxn_6_io_config = ConfigMem_io_out_0[14:12]; // @[Interconnect.scala 900:23]
  assign Muxn_6_io_in_0 = io_opinNW_0; // @[Interconnect.scala 892:63]
  assign Muxn_6_io_in_1 = io_opinSE_0; // @[Interconnect.scala 892:63]
  assign Muxn_6_io_in_2 = io_opinSW_0; // @[Interconnect.scala 892:63]
  assign Muxn_6_io_in_3 = io_itrackE_0; // @[Interconnect.scala 892:63]
  assign Muxn_6_io_in_4 = io_itrackS_0; // @[Interconnect.scala 892:63]
  assign Muxn_7_io_config = ConfigMem_io_out_0[17:15]; // @[Interconnect.scala 900:23]
  assign Muxn_7_io_in_0 = io_opinNW_0; // @[Interconnect.scala 892:63]
  assign Muxn_7_io_in_1 = io_opinNE_0; // @[Interconnect.scala 892:63]
  assign Muxn_7_io_in_2 = io_opinSW_0; // @[Interconnect.scala 892:63]
  assign Muxn_7_io_in_3 = io_itrackN_0; // @[Interconnect.scala 892:63]
  assign Muxn_7_io_in_4 = io_itrackS_0; // @[Interconnect.scala 892:63]
  assign Muxn_8_io_config = ConfigMem_io_out_0[20:18]; // @[Interconnect.scala 900:23]
  assign Muxn_8_io_in_0 = io_opinNW_0; // @[Interconnect.scala 892:63]
  assign Muxn_8_io_in_1 = io_opinNE_0; // @[Interconnect.scala 892:63]
  assign Muxn_8_io_in_2 = io_opinSE_0; // @[Interconnect.scala 892:63]
  assign Muxn_8_io_in_3 = io_itrackN_0; // @[Interconnect.scala 892:63]
  assign Muxn_8_io_in_4 = io_itrackE_0; // @[Interconnect.scala 892:63]
`ifdef RANDOMIZE_GARBAGE_ASSIGN
`define RANDOMIZE
`endif
`ifdef RANDOMIZE_INVALID_ASSIGN
`define RANDOMIZE
`endif
`ifdef RANDOMIZE_REG_INIT
`define RANDOMIZE
`endif
`ifdef RANDOMIZE_MEM_INIT
`define RANDOMIZE
`endif
`ifndef RANDOM
`define RANDOM $random
`endif
`ifdef RANDOMIZE_MEM_INIT
  integer initvar;
`endif
`ifndef SYNTHESIS
`ifdef FIRRTL_BEFORE_INITIAL
`FIRRTL_BEFORE_INITIAL
`endif
initial begin
  `ifdef RANDOMIZE
    `ifdef INIT_RANDOM
      `INIT_RANDOM
    `endif
    `ifndef VERILATOR
      `ifdef RANDOMIZE_DELAY
        #`RANDOMIZE_DELAY begin end
      `else
        #0.002 begin end
      `endif
    `endif
`ifdef RANDOMIZE_REG_INIT
  _RAND_0 = {1{`RANDOM}};
  _T_12 = _RAND_0[31:0];
  _RAND_1 = {1{`RANDOM}};
  _T_14 = _RAND_1[31:0];
  _RAND_2 = {1{`RANDOM}};
  _T_16 = _RAND_2[31:0];
`endif // RANDOMIZE_REG_INIT
  `endif // RANDOMIZE
end // initial
`ifdef FIRRTL_AFTER_INITIAL
`FIRRTL_AFTER_INITIAL
`endif
`endif // SYNTHESIS
  always @(posedge clock) begin
    _T_12 <= Muxn_6_io_out;
    _T_14 <= Muxn_7_io_out;
    _T_16 <= Muxn_8_io_out;
  end
endmodule
