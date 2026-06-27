`include "cgra_defs.svh"
module ConfigMem_36(
  input         clock,
  input         reset,
  input         io_cfg_en,
  input         io_en,
  input  [2:0]  io_cycle,
  input  [2:0]  io_II,
  input  [31:0] io_cfg_data,
  output [7:0]  io_out_0
);
`ifdef RANDOMIZE_REG_INIT
  reg [31:0] _RAND_0;
  reg [31:0] _RAND_1;
  reg [31:0] _RAND_2;
  reg [31:0] _RAND_3;
  reg [31:0] _RAND_4;
  reg [31:0] _RAND_5;
  reg [31:0] _RAND_6;
  reg [31:0] _RAND_7;
  reg [31:0] _RAND_8;
  reg [31:0] _RAND_9;
`endif // RANDOMIZE_REG_INIT
  reg [7:0] configmem_0_0; // @[ConfigMem.scala 84:26]
  reg [7:0] configmem_0_1; // @[ConfigMem.scala 84:26]
  reg [7:0] configmem_0_2; // @[ConfigMem.scala 84:26]
  reg [7:0] configmem_0_3; // @[ConfigMem.scala 84:26]
  reg [7:0] configmem_0_4; // @[ConfigMem.scala 84:26]
  reg [7:0] configmem_0_5; // @[ConfigMem.scala 84:26]
  reg [7:0] configmem_0_6; // @[ConfigMem.scala 84:26]
  reg [7:0] configmem_0_7; // @[ConfigMem.scala 84:26]
  reg [2:0] config_pointer_i; // @[ConfigMem.scala 98:32]
  reg [2:0] config_pointer; // @[ConfigMem.scala 99:30]
  wire [7:0] _GEN_8 = io_cfg_en ? io_cfg_data[7:0] : 8'h0; // @[ConfigMem.scala 105:54]
  wire  _T_5 = config_pointer_i == io_II; // @[ConfigMem.scala 127:46]
  wire [2:0] _T_7 = config_pointer_i + 3'h1; // @[ConfigMem.scala 127:77]
  wire [7:0] _GEN_19 = 3'h1 == config_pointer ? configmem_0_1 : configmem_0_0; // @[ConfigMem.scala 134:45]
  wire [7:0] _GEN_20 = 3'h2 == config_pointer ? configmem_0_2 : _GEN_19; // @[ConfigMem.scala 134:45]
  wire [7:0] _GEN_21 = 3'h3 == config_pointer ? configmem_0_3 : _GEN_20; // @[ConfigMem.scala 134:45]
  wire [7:0] _GEN_22 = 3'h4 == config_pointer ? configmem_0_4 : _GEN_21; // @[ConfigMem.scala 134:45]
  wire [7:0] _GEN_23 = 3'h5 == config_pointer ? configmem_0_5 : _GEN_22; // @[ConfigMem.scala 134:45]
  wire [7:0] _GEN_24 = 3'h6 == config_pointer ? configmem_0_6 : _GEN_23; // @[ConfigMem.scala 134:45]
  assign io_out_0 = 3'h7 == config_pointer ? configmem_0_7 : _GEN_24; // @[ConfigMem.scala 134:45]
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
  configmem_0_0 = _RAND_0[7:0];
  _RAND_1 = {1{`RANDOM}};
  configmem_0_1 = _RAND_1[7:0];
  _RAND_2 = {1{`RANDOM}};
  configmem_0_2 = _RAND_2[7:0];
  _RAND_3 = {1{`RANDOM}};
  configmem_0_3 = _RAND_3[7:0];
  _RAND_4 = {1{`RANDOM}};
  configmem_0_4 = _RAND_4[7:0];
  _RAND_5 = {1{`RANDOM}};
  configmem_0_5 = _RAND_5[7:0];
  _RAND_6 = {1{`RANDOM}};
  configmem_0_6 = _RAND_6[7:0];
  _RAND_7 = {1{`RANDOM}};
  configmem_0_7 = _RAND_7[7:0];
  _RAND_8 = {1{`RANDOM}};
  config_pointer_i = _RAND_8[2:0];
  _RAND_9 = {1{`RANDOM}};
  config_pointer = _RAND_9[2:0];
`endif // RANDOMIZE_REG_INIT
  `endif // RANDOMIZE
end // initial
`ifdef FIRRTL_AFTER_INITIAL
`FIRRTL_AFTER_INITIAL
`endif
`endif // SYNTHESIS
  always @(posedge clock) begin
    if (reset) begin
      configmem_0_0 <= 8'h0;
    end else if (io_cfg_en) begin
      if (3'h0 == io_cycle) begin
        if (io_cfg_en) begin
          configmem_0_0 <= io_cfg_data[7:0];
        end else begin
          configmem_0_0 <= 8'h0;
        end
      end
    end
    if (reset) begin
      configmem_0_1 <= 8'h0;
    end else if (io_cfg_en) begin
      if (3'h1 == io_cycle) begin
        if (io_cfg_en) begin
          configmem_0_1 <= io_cfg_data[7:0];
        end else begin
          configmem_0_1 <= 8'h0;
        end
      end
    end
    if (reset) begin
      configmem_0_2 <= 8'h0;
    end else if (io_cfg_en) begin
      if (3'h2 == io_cycle) begin
        if (io_cfg_en) begin
          configmem_0_2 <= io_cfg_data[7:0];
        end else begin
          configmem_0_2 <= 8'h0;
        end
      end
    end
    if (reset) begin
      configmem_0_3 <= 8'h0;
    end else if (io_cfg_en) begin
      if (3'h3 == io_cycle) begin
        if (io_cfg_en) begin
          configmem_0_3 <= io_cfg_data[7:0];
        end else begin
          configmem_0_3 <= 8'h0;
        end
      end
    end
    if (reset) begin
      configmem_0_4 <= 8'h0;
    end else if (io_cfg_en) begin
      if (3'h4 == io_cycle) begin
        configmem_0_4 <= _GEN_8;
      end
    end
    if (reset) begin
      configmem_0_5 <= 8'h0;
    end else if (io_cfg_en) begin
      if (3'h5 == io_cycle) begin
        configmem_0_5 <= _GEN_8;
      end
    end
    if (reset) begin
      configmem_0_6 <= 8'h0;
    end else if (io_cfg_en) begin
      if (3'h6 == io_cycle) begin
        configmem_0_6 <= _GEN_8;
      end
    end
    if (reset) begin
      configmem_0_7 <= 8'h0;
    end else if (io_cfg_en) begin
      if (3'h7 == io_cycle) begin
        configmem_0_7 <= _GEN_8;
      end
    end
    if (reset) begin
      config_pointer_i <= 3'h0;
    end else if (io_en) begin
      if (_T_5) begin
        config_pointer_i <= 3'h0;
      end else begin
        config_pointer_i <= _T_7;
      end
    end else begin
      config_pointer_i <= 3'h0;
    end
    config_pointer <= config_pointer_i;
  end
endmodule
