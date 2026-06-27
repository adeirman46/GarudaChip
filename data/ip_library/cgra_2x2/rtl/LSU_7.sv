`include "cgra_defs.svh"
module LSU_7(
  input         clock,
  input         reset,
  input         io_cfg_en,
  input  [17:0] io_cfg_addr,
  input  [31:0] io_cfg_data,
  input  [5:0]  io_hostInterface_read_addr,
  input         io_hostInterface_read_data_ready,
  output        io_hostInterface_read_data_valid,
  output [31:0] io_hostInterface_read_data_bits,
  input  [5:0]  io_hostInterface_write_addr,
  output        io_hostInterface_write_data_ready,
  input         io_hostInterface_write_data_valid,
  input  [31:0] io_hostInterface_write_data_bits,
  input  [2:0]  io_hostInterface_cycle,
  input         io_en,
  input  [31:0] io_in_0,
  output [31:0] io_out_0
);
  wire  Muxn_io_config; // @[LSU.scala 53:34]
  wire [31:0] Muxn_io_in_0; // @[LSU.scala 53:34]
  wire [31:0] Muxn_io_in_1; // @[LSU.scala 53:34]
  wire [31:0] Muxn_io_out; // @[LSU.scala 53:34]
  wire  Muxn_1_io_config; // @[LSU.scala 53:34]
  wire [31:0] Muxn_1_io_in_0; // @[LSU.scala 53:34]
  wire [31:0] Muxn_1_io_in_1; // @[LSU.scala 53:34]
  wire [31:0] Muxn_1_io_out; // @[LSU.scala 53:34]
  wire  DelayPipe_clock; // @[LSU.scala 54:42]
  wire  DelayPipe_reset; // @[LSU.scala 54:42]
  wire  DelayPipe_io_en; // @[LSU.scala 54:42]
  wire  DelayPipe_io_config; // @[LSU.scala 54:42]
  wire [31:0] DelayPipe_io_in; // @[LSU.scala 54:42]
  wire [31:0] DelayPipe_io_out; // @[LSU.scala 54:42]
  wire  DelayPipe_1_clock; // @[LSU.scala 54:42]
  wire  DelayPipe_1_reset; // @[LSU.scala 54:42]
  wire  DelayPipe_1_io_en; // @[LSU.scala 54:42]
  wire  DelayPipe_1_io_config; // @[LSU.scala 54:42]
  wire [31:0] DelayPipe_1_io_in; // @[LSU.scala 54:42]
  wire [31:0] DelayPipe_1_io_out; // @[LSU.scala 54:42]
  wire  mem_clock; // @[LSU.scala 77:19]
  wire  mem_io_enable; // @[LSU.scala 77:19]
  wire  mem_io_write_enable; // @[LSU.scala 77:19]
  wire [5:0] mem_io_addr; // @[LSU.scala 77:19]
  wire [31:0] mem_io_dataIn; // @[LSU.scala 77:19]
  wire [31:0] mem_io_dataOut; // @[LSU.scala 77:19]
  wire  cfg_clock; // @[LSU.scala 128:19]
  wire  cfg_reset; // @[LSU.scala 128:19]
  wire  cfg_io_cfg_en; // @[LSU.scala 128:19]
  wire  cfg_io_en; // @[LSU.scala 128:19]
  wire [2:0] cfg_io_cycle; // @[LSU.scala 128:19]
  wire [2:0] cfg_io_II; // @[LSU.scala 128:19]
  wire  cfg_io_cfg_addr; // @[LSU.scala 128:19]
  wire [31:0] cfg_io_cfg_data; // @[LSU.scala 128:19]
  wire [37:0] cfg_io_out_0; // @[LSU.scala 128:19]
  wire [2:0] cfg_io_current_t; // @[LSU.scala 128:19]
  wire [2:0] current_t = cfg_io_current_t; // @[LSU.scala 51:23 LSU.scala 139:13]
  wire [3:0] _GEN_11 = {{1'd0}, current_t}; // @[LSU.scala 68:39]
  wire [6:0] cfg_base_addr = 4'h8 * _GEN_11; // @[LSU.scala 68:39]
  wire [3:0] _GEN_12 = {{1'd0}, io_hostInterface_cycle}; // @[LSU.scala 73:47]
  wire [6:0] host_base_addr = _GEN_12 * 4'h8; // @[LSU.scala 73:47]
  wire [31:0] Oprand_0 = DelayPipe_io_out; // @[LSU.scala 47:20 LSU.scala 63:17]
  wire [6:0] _GEN_13 = {{1'd0}, io_hostInterface_read_addr}; // @[LSU.scala 98:68]
  wire [6:0] _T_3 = _GEN_13 + host_base_addr; // @[LSU.scala 98:68]
  wire [6:0] _GEN_14 = {{1'd0}, io_hostInterface_write_addr}; // @[LSU.scala 102:69]
  wire [6:0] _T_6 = _GEN_14 + host_base_addr; // @[LSU.scala 102:69]
  wire [31:0] opmode = {{30'd0}, cfg_io_out_0[37:36]}; // @[LSU.scala 48:20 LSU.scala 161:9]
  wire  _T_7 = opmode == 32'h1; // @[LSU.scala 104:17]
  wire  _T_8 = ~io_en; // @[LSU.scala 106:23]
  wire [6:0] _GEN_15 = {{1'd0}, Oprand_0[5:0]}; // @[LSU.scala 107:53]
  wire [6:0] _T_11 = _GEN_15 + cfg_base_addr; // @[LSU.scala 107:53]
  wire  _T_12 = opmode == 32'h2; // @[LSU.scala 108:23]
  wire [31:0] Oprand_1 = DelayPipe_1_io_out; // @[LSU.scala 47:20 LSU.scala 63:17]
  wire [6:0] _GEN_16 = {{1'd0}, Oprand_1[5:0]}; // @[LSU.scala 111:53]
  wire [6:0] _T_15 = _GEN_16 + cfg_base_addr; // @[LSU.scala 111:53]
  wire  _GEN_0 = _T_12 & io_en; // @[LSU.scala 108:32]
  wire  _GEN_2 = _T_7 ? io_en : _GEN_0; // @[LSU.scala 104:26]
  wire  _GEN_3 = _T_7 ? _T_8 : _GEN_0; // @[LSU.scala 104:26]
  wire [6:0] _GEN_4 = _T_7 ? _T_11 : _T_15; // @[LSU.scala 104:26]
  wire  _GEN_5 = io_hostInterface_write_data_valid | _GEN_2; // @[LSU.scala 99:49]
  wire  _GEN_6 = io_hostInterface_write_data_valid | _GEN_3; // @[LSU.scala 99:49]
  wire [6:0] _GEN_7 = io_hostInterface_write_data_valid ? _T_6 : _GEN_4; // @[LSU.scala 99:49]
  wire [6:0] _GEN_10 = io_hostInterface_read_data_ready ? _T_3 : _GEN_7; // @[LSU.scala 95:42]
  wire  _T_17 = 10'h50 == io_cfg_addr[17:8]; // @[LSU.scala 129:48]
  wire [37:0] cfgOut = cfg_io_out_0; // @[LSU.scala 142:20 LSU.scala 143:10]
  Muxn Muxn ( // @[LSU.scala 53:34]
    .io_config(Muxn_io_config),
    .io_in_0(Muxn_io_in_0),
    .io_in_1(Muxn_io_in_1),
    .io_out(Muxn_io_out)
  );
  Muxn Muxn_1 ( // @[LSU.scala 53:34]
    .io_config(Muxn_1_io_config),
    .io_in_0(Muxn_1_io_in_0),
    .io_in_1(Muxn_1_io_in_1),
    .io_out(Muxn_1_io_out)
  );
  DelayPipe_48 DelayPipe ( // @[LSU.scala 54:42]
    .clock(DelayPipe_clock),
    .reset(DelayPipe_reset),
    .io_en(DelayPipe_io_en),
    .io_config(DelayPipe_io_config),
    .io_in(DelayPipe_io_in),
    .io_out(DelayPipe_io_out)
  );
  DelayPipe_48 DelayPipe_1 ( // @[LSU.scala 54:42]
    .clock(DelayPipe_1_clock),
    .reset(DelayPipe_1_reset),
    .io_en(DelayPipe_1_io_en),
    .io_config(DelayPipe_1_io_config),
    .io_in(DelayPipe_1_io_in),
    .io_out(DelayPipe_1_io_out)
  );
  single_port_ram mem ( // @[LSU.scala 77:19]
    .clock(mem_clock),
    .io_enable(mem_io_enable),
    .io_write_enable(mem_io_write_enable),
    .io_addr(mem_io_addr),
    .io_dataIn(mem_io_dataIn),
    .io_dataOut(mem_io_dataOut)
  );
  ConfigMem_69 cfg ( // @[LSU.scala 128:19]
    .clock(cfg_clock),
    .reset(cfg_reset),
    .io_cfg_en(cfg_io_cfg_en),
    .io_en(cfg_io_en),
    .io_cycle(cfg_io_cycle),
    .io_II(cfg_io_II),
    .io_cfg_addr(cfg_io_cfg_addr),
    .io_cfg_data(cfg_io_cfg_data),
    .io_out_0(cfg_io_out_0),
    .io_current_t(cfg_io_current_t)
  );
  assign io_hostInterface_read_data_valid = io_hostInterface_read_data_ready; // @[LSU.scala 87:36]
  assign io_hostInterface_read_data_bits = mem_io_dataOut; // @[LSU.scala 85:35]
  assign io_hostInterface_write_data_ready = io_hostInterface_write_data_valid; // @[LSU.scala 90:37]
  assign io_out_0 = mem_io_dataOut; // @[LSU.scala 81:13]
  assign Muxn_io_config = cfgOut[32]; // @[LSU.scala 148:20]
  assign Muxn_io_in_0 = io_in_0; // @[LSU.scala 58:23]
  assign Muxn_io_in_1 = cfgOut[31:0]; // @[LSU.scala 60:29]
  assign Muxn_1_io_config = cfgOut[33]; // @[LSU.scala 148:20]
  assign Muxn_1_io_in_0 = 32'h0; // @[LSU.scala 58:23]
  assign Muxn_1_io_in_1 = cfgOut[31:0]; // @[LSU.scala 60:29]
  assign DelayPipe_clock = clock;
  assign DelayPipe_reset = reset;
  assign DelayPipe_io_en = io_en; // @[LSU.scala 61:25]
  assign DelayPipe_io_config = cfgOut[34]; // @[LSU.scala 154:29]
  assign DelayPipe_io_in = Muxn_io_out; // @[LSU.scala 62:25]
  assign DelayPipe_1_clock = clock;
  assign DelayPipe_1_reset = reset;
  assign DelayPipe_1_io_en = io_en; // @[LSU.scala 61:25]
  assign DelayPipe_1_io_config = cfgOut[35]; // @[LSU.scala 154:29]
  assign DelayPipe_1_io_in = Muxn_1_io_out; // @[LSU.scala 62:25]
  assign mem_clock = clock;
  assign mem_io_enable = io_hostInterface_read_data_ready | _GEN_5; // @[LSU.scala 78:17]
  assign mem_io_write_enable = io_hostInterface_read_data_ready ? 1'h0 : _GEN_6; // @[LSU.scala 79:23]
  assign mem_io_addr = _GEN_10[5:0]; // @[LSU.scala 80:15]
  assign mem_io_dataIn = io_hostInterface_write_data_valid ? io_hostInterface_write_data_bits : Oprand_0; // @[LSU.scala 82:17]
  assign cfg_clock = clock;
  assign cfg_reset = reset;
  assign cfg_io_cfg_en = io_cfg_en & _T_17; // @[LSU.scala 129:17]
  assign cfg_io_en = io_en; // @[LSU.scala 131:13]
  assign cfg_io_cycle = io_cfg_addr[5:3]; // @[LSU.scala 132:16]
  assign cfg_io_II = io_cfg_addr[2:0]; // @[LSU.scala 133:13]
  assign cfg_io_cfg_addr = io_cfg_addr[6]; // @[LSU.scala 130:19]
  assign cfg_io_cfg_data = io_cfg_data; // @[LSU.scala 134:19]
endmodule
