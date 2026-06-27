`include "cgra_defs.svh"
module GPE_12(
  input         clock,
  input         reset,
  input         io_cfg_en,
  input  [17:0] io_cfg_addr,
  input  [31:0] io_cfg_data,
  input         io_en,
  input  [31:0] io_in_0,
  input  [31:0] io_in_1,
  input  [31:0] io_in_2,
  input  [31:0] io_in_3,
  input  [31:0] io_in_4,
  input  [31:0] io_in_5,
  input  [31:0] io_in_6,
  input  [31:0] io_in_7,
  output [31:0] io_out_0
);
  wire [4:0] alu_io_config; // @[PE.scala 52:19]
  wire [31:0] alu_io_in_0; // @[PE.scala 52:19]
  wire [31:0] alu_io_in_1; // @[PE.scala 52:19]
  wire [31:0] alu_io_out; // @[PE.scala 52:19]
  wire  rf_clock; // @[PE.scala 53:18]
  wire  rf_reset; // @[PE.scala 53:18]
  wire  rf_io_en; // @[PE.scala 53:18]
  wire [31:0] rf_io_in_0; // @[PE.scala 53:18]
  wire [31:0] rf_io_out_0; // @[PE.scala 53:18]
  wire [31:0] rf_io_out_1; // @[PE.scala 53:18]
  wire  DelayPipe_clock; // @[PE.scala 54:54]
  wire  DelayPipe_reset; // @[PE.scala 54:54]
  wire  DelayPipe_io_en; // @[PE.scala 54:54]
  wire [2:0] DelayPipe_io_config; // @[PE.scala 54:54]
  wire [31:0] DelayPipe_io_in; // @[PE.scala 54:54]
  wire [31:0] DelayPipe_io_out; // @[PE.scala 54:54]
  wire  DelayPipe_1_clock; // @[PE.scala 54:54]
  wire  DelayPipe_1_reset; // @[PE.scala 54:54]
  wire  DelayPipe_1_io_en; // @[PE.scala 54:54]
  wire [2:0] DelayPipe_1_io_config; // @[PE.scala 54:54]
  wire [31:0] DelayPipe_1_io_in; // @[PE.scala 54:54]
  wire [31:0] DelayPipe_1_io_out; // @[PE.scala 54:54]
  wire [2:0] Muxn_io_config; // @[PE.scala 57:49]
  wire [31:0] Muxn_io_in_0; // @[PE.scala 57:49]
  wire [31:0] Muxn_io_in_1; // @[PE.scala 57:49]
  wire [31:0] Muxn_io_in_2; // @[PE.scala 57:49]
  wire [31:0] Muxn_io_in_3; // @[PE.scala 57:49]
  wire [31:0] Muxn_io_in_4; // @[PE.scala 57:49]
  wire [31:0] Muxn_io_in_5; // @[PE.scala 57:49]
  wire [31:0] Muxn_io_out; // @[PE.scala 57:49]
  wire [2:0] Muxn_1_io_config; // @[PE.scala 57:49]
  wire [31:0] Muxn_1_io_in_0; // @[PE.scala 57:49]
  wire [31:0] Muxn_1_io_in_1; // @[PE.scala 57:49]
  wire [31:0] Muxn_1_io_in_2; // @[PE.scala 57:49]
  wire [31:0] Muxn_1_io_in_3; // @[PE.scala 57:49]
  wire [31:0] Muxn_1_io_in_4; // @[PE.scala 57:49]
  wire [31:0] Muxn_1_io_in_5; // @[PE.scala 57:49]
  wire [31:0] Muxn_1_io_out; // @[PE.scala 57:49]
  wire  cfg_clock; // @[PE.scala 92:19]
  wire  cfg_reset; // @[PE.scala 92:19]
  wire  cfg_io_cfg_en; // @[PE.scala 92:19]
  wire  cfg_io_en; // @[PE.scala 92:19]
  wire [2:0] cfg_io_cycle; // @[PE.scala 92:19]
  wire [2:0] cfg_io_II; // @[PE.scala 92:19]
  wire  cfg_io_cfg_addr; // @[PE.scala 92:19]
  wire [31:0] cfg_io_cfg_data; // @[PE.scala 92:19]
  wire [48:0] cfg_io_out_0; // @[PE.scala 92:19]
  wire  _T_1 = 10'h3a == io_cfg_addr[17:8]; // @[PE.scala 93:48]
  wire [48:0] cfgOut = cfg_io_out_0; // @[PE.scala 102:20 PE.scala 103:10]
  ALU_12 alu ( // @[PE.scala 52:19]
    .io_config(alu_io_config),
    .io_in_0(alu_io_in_0),
    .io_in_1(alu_io_in_1),
    .io_out(alu_io_out)
  );
  RF rf ( // @[PE.scala 53:18]
    .clock(rf_clock),
    .reset(rf_reset),
    .io_en(rf_io_en),
    .io_in_0(rf_io_in_0),
    .io_out_0(rf_io_out_0),
    .io_out_1(rf_io_out_1)
  );
  DelayPipe DelayPipe ( // @[PE.scala 54:54]
    .clock(DelayPipe_clock),
    .reset(DelayPipe_reset),
    .io_en(DelayPipe_io_en),
    .io_config(DelayPipe_io_config),
    .io_in(DelayPipe_io_in),
    .io_out(DelayPipe_io_out)
  );
  DelayPipe DelayPipe_1 ( // @[PE.scala 54:54]
    .clock(DelayPipe_1_clock),
    .reset(DelayPipe_1_reset),
    .io_en(DelayPipe_1_io_en),
    .io_config(DelayPipe_1_io_config),
    .io_in(DelayPipe_1_io_in),
    .io_out(DelayPipe_1_io_out)
  );
  Muxn_12 Muxn ( // @[PE.scala 57:49]
    .io_config(Muxn_io_config),
    .io_in_0(Muxn_io_in_0),
    .io_in_1(Muxn_io_in_1),
    .io_in_2(Muxn_io_in_2),
    .io_in_3(Muxn_io_in_3),
    .io_in_4(Muxn_io_in_4),
    .io_in_5(Muxn_io_in_5),
    .io_out(Muxn_io_out)
  );
  Muxn_12 Muxn_1 ( // @[PE.scala 57:49]
    .io_config(Muxn_1_io_config),
    .io_in_0(Muxn_1_io_in_0),
    .io_in_1(Muxn_1_io_in_1),
    .io_in_2(Muxn_1_io_in_2),
    .io_in_3(Muxn_1_io_in_3),
    .io_in_4(Muxn_1_io_in_4),
    .io_in_5(Muxn_1_io_in_5),
    .io_out(Muxn_1_io_out)
  );
  ConfigMem_12 cfg ( // @[PE.scala 92:19]
    .clock(cfg_clock),
    .reset(cfg_reset),
    .io_cfg_en(cfg_io_cfg_en),
    .io_en(cfg_io_en),
    .io_cycle(cfg_io_cycle),
    .io_II(cfg_io_II),
    .io_cfg_addr(cfg_io_cfg_addr),
    .io_cfg_data(cfg_io_cfg_data),
    .io_out_0(cfg_io_out_0)
  );
  assign io_out_0 = rf_io_out_0; // @[PE.scala 79:13]
  assign alu_io_config = cfgOut[36:32]; // @[PE.scala 106:19]
  assign alu_io_in_0 = DelayPipe_io_out; // @[PE.scala 73:18]
  assign alu_io_in_1 = DelayPipe_1_io_out; // @[PE.scala 73:18]
  assign rf_clock = clock;
  assign rf_reset = reset;
  assign rf_io_en = io_en; // @[PE.scala 77:12]
  assign rf_io_in_0 = alu_io_out; // @[PE.scala 78:15]
  assign DelayPipe_clock = clock;
  assign DelayPipe_reset = reset;
  assign DelayPipe_io_en = io_en; // @[PE.scala 71:23]
  assign DelayPipe_io_config = cfgOut[39:37]; // @[PE.scala 119:29]
  assign DelayPipe_io_in = Muxn_io_out; // @[PE.scala 72:23]
  assign DelayPipe_1_clock = clock;
  assign DelayPipe_1_reset = reset;
  assign DelayPipe_1_io_en = io_en; // @[PE.scala 71:23]
  assign DelayPipe_1_io_config = cfgOut[42:40]; // @[PE.scala 119:29]
  assign DelayPipe_1_io_in = Muxn_1_io_out; // @[PE.scala 72:23]
  assign Muxn_io_config = cfgOut[45:43]; // @[PE.scala 127:23]
  assign Muxn_io_in_0 = io_in_0; // @[PE.scala 64:12]
  assign Muxn_io_in_1 = io_in_1; // @[PE.scala 64:12]
  assign Muxn_io_in_2 = io_in_2; // @[PE.scala 64:12]
  assign Muxn_io_in_3 = io_in_3; // @[PE.scala 64:12]
  assign Muxn_io_in_4 = cfgOut[31:0]; // @[PE.scala 66:12]
  assign Muxn_io_in_5 = rf_io_out_1; // @[PE.scala 68:12]
  assign Muxn_1_io_config = cfgOut[48:46]; // @[PE.scala 127:23]
  assign Muxn_1_io_in_0 = io_in_4; // @[PE.scala 64:12]
  assign Muxn_1_io_in_1 = io_in_5; // @[PE.scala 64:12]
  assign Muxn_1_io_in_2 = io_in_6; // @[PE.scala 64:12]
  assign Muxn_1_io_in_3 = io_in_7; // @[PE.scala 64:12]
  assign Muxn_1_io_in_4 = cfgOut[31:0]; // @[PE.scala 66:12]
  assign Muxn_1_io_in_5 = rf_io_out_1; // @[PE.scala 68:12]
  assign cfg_clock = clock;
  assign cfg_reset = reset;
  assign cfg_io_cfg_en = io_cfg_en & _T_1; // @[PE.scala 93:17]
  assign cfg_io_en = io_en; // @[PE.scala 95:13]
  assign cfg_io_cycle = io_cfg_addr[5:3]; // @[PE.scala 96:16]
  assign cfg_io_II = io_cfg_addr[2:0]; // @[PE.scala 97:13]
  assign cfg_io_cfg_addr = io_cfg_addr[6]; // @[PE.scala 94:19]
  assign cfg_io_cfg_data = io_cfg_data; // @[PE.scala 98:19]
endmodule
