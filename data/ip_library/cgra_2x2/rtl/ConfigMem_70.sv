`include "cgra_defs.svh"
module ConfigMem_70(
  input         clock,
  input         reset,
  input         io_cfg_en,
  input         io_en,
  input  [2:0]  io_cycle,
  input  [2:0]  io_II,
  input         io_cfg_addr,
  input  [31:0] io_cfg_data,
  output [39:0] io_out_0,
  output [2:0]  io_current_t
);
`ifdef RANDOMIZE_REG_INIT
  reg [63:0] _RAND_0;
  reg [63:0] _RAND_1;
  reg [63:0] _RAND_2;
  reg [63:0] _RAND_3;
  reg [63:0] _RAND_4;
  reg [63:0] _RAND_5;
  reg [63:0] _RAND_6;
  reg [63:0] _RAND_7;
  reg [31:0] _RAND_8;
  reg [31:0] _RAND_9;
`endif // RANDOMIZE_REG_INIT
  reg [39:0] configmem_0_0; // @[ConfigMem.scala 84:26]
  reg [39:0] configmem_0_1; // @[ConfigMem.scala 84:26]
  reg [39:0] configmem_0_2; // @[ConfigMem.scala 84:26]
  reg [39:0] configmem_0_3; // @[ConfigMem.scala 84:26]
  reg [39:0] configmem_0_4; // @[ConfigMem.scala 84:26]
  reg [39:0] configmem_0_5; // @[ConfigMem.scala 84:26]
  reg [39:0] configmem_0_6; // @[ConfigMem.scala 84:26]
  reg [39:0] configmem_0_7; // @[ConfigMem.scala 84:26]
  reg [2:0] config_pointer_i; // @[ConfigMem.scala 98:32]
  reg [2:0] config_pointer; // @[ConfigMem.scala 99:30]
  wire  _T_1 = ~io_cfg_addr; // @[ConfigMem.scala 114:38]
  wire  _T_2 = io_cfg_en & _T_1; // @[ConfigMem.scala 114:22]
  wire [39:0] _GEN_1 = 3'h1 == io_cycle ? configmem_0_1 : configmem_0_0; // @[ConfigMem.scala 116:64]
  wire [39:0] _GEN_2 = 3'h2 == io_cycle ? configmem_0_2 : _GEN_1; // @[ConfigMem.scala 116:64]
  wire [39:0] _GEN_3 = 3'h3 == io_cycle ? configmem_0_3 : _GEN_2; // @[ConfigMem.scala 116:64]
  wire [39:0] _GEN_4 = 3'h4 == io_cycle ? configmem_0_4 : _GEN_3; // @[ConfigMem.scala 116:64]
  wire [39:0] _GEN_5 = 3'h5 == io_cycle ? configmem_0_5 : _GEN_4; // @[ConfigMem.scala 116:64]
  wire [39:0] _GEN_6 = 3'h6 == io_cycle ? configmem_0_6 : _GEN_5; // @[ConfigMem.scala 116:64]
  wire [39:0] _GEN_7 = 3'h7 == io_cycle ? configmem_0_7 : _GEN_6; // @[ConfigMem.scala 116:64]
  wire [39:0] _T_4 = {_GEN_7[39:32],io_cfg_data}; // @[Cat.scala 29:58]
  wire  _T_6 = io_cfg_en & io_cfg_addr; // @[ConfigMem.scala 114:22]
  wire [63:0] _T_8 = {io_cfg_data,_GEN_7[31:0]}; // @[Cat.scala 29:58]
  wire  _T_9 = config_pointer_i == io_II; // @[ConfigMem.scala 127:46]
  wire [2:0] _T_11 = config_pointer_i + 3'h1; // @[ConfigMem.scala 127:77]
  wire [39:0] _GEN_42 = 3'h1 == config_pointer ? configmem_0_1 : configmem_0_0; // @[ConfigMem.scala 134:45]
  wire [39:0] _GEN_43 = 3'h2 == config_pointer ? configmem_0_2 : _GEN_42; // @[ConfigMem.scala 134:45]
  wire [39:0] _GEN_44 = 3'h3 == config_pointer ? configmem_0_3 : _GEN_43; // @[ConfigMem.scala 134:45]
  wire [39:0] _GEN_45 = 3'h4 == config_pointer ? configmem_0_4 : _GEN_44; // @[ConfigMem.scala 134:45]
  wire [39:0] _GEN_46 = 3'h5 == config_pointer ? configmem_0_5 : _GEN_45; // @[ConfigMem.scala 134:45]
  wire [39:0] _GEN_47 = 3'h6 == config_pointer ? configmem_0_6 : _GEN_46; // @[ConfigMem.scala 134:45]
  assign io_out_0 = 3'h7 == config_pointer ? configmem_0_7 : _GEN_47; // @[ConfigMem.scala 134:45]
  assign io_current_t = config_pointer; // @[ConfigMem.scala 132:16]
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
  _RAND_0 = {2{`RANDOM}};
  configmem_0_0 = _RAND_0[39:0];
  _RAND_1 = {2{`RANDOM}};
  configmem_0_1 = _RAND_1[39:0];
  _RAND_2 = {2{`RANDOM}};
  configmem_0_2 = _RAND_2[39:0];
  _RAND_3 = {2{`RANDOM}};
  configmem_0_3 = _RAND_3[39:0];
  _RAND_4 = {2{`RANDOM}};
  configmem_0_4 = _RAND_4[39:0];
  _RAND_5 = {2{`RANDOM}};
  configmem_0_5 = _RAND_5[39:0];
  _RAND_6 = {2{`RANDOM}};
  configmem_0_6 = _RAND_6[39:0];
  _RAND_7 = {2{`RANDOM}};
  configmem_0_7 = _RAND_7[39:0];
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
      configmem_0_0 <= 40'h0;
    end else if (_T_6) begin
      if (3'h0 == io_cycle) begin
        configmem_0_0 <= _T_8[39:0];
      end else if (_T_2) begin
        if (3'h0 == io_cycle) begin
          configmem_0_0 <= _T_4;
        end
      end
    end else if (_T_2) begin
      if (3'h0 == io_cycle) begin
        configmem_0_0 <= _T_4;
      end
    end
    if (reset) begin
      configmem_0_1 <= 40'h0;
    end else if (_T_6) begin
      if (3'h1 == io_cycle) begin
        configmem_0_1 <= _T_8[39:0];
      end else if (_T_2) begin
        if (3'h1 == io_cycle) begin
          configmem_0_1 <= _T_4;
        end
      end
    end else if (_T_2) begin
      if (3'h1 == io_cycle) begin
        configmem_0_1 <= _T_4;
      end
    end
    if (reset) begin
      configmem_0_2 <= 40'h0;
    end else if (_T_6) begin
      if (3'h2 == io_cycle) begin
        configmem_0_2 <= _T_8[39:0];
      end else if (_T_2) begin
        if (3'h2 == io_cycle) begin
          configmem_0_2 <= _T_4;
        end
      end
    end else if (_T_2) begin
      if (3'h2 == io_cycle) begin
        configmem_0_2 <= _T_4;
      end
    end
    if (reset) begin
      configmem_0_3 <= 40'h0;
    end else if (_T_6) begin
      if (3'h3 == io_cycle) begin
        configmem_0_3 <= _T_8[39:0];
      end else if (_T_2) begin
        if (3'h3 == io_cycle) begin
          configmem_0_3 <= _T_4;
        end
      end
    end else if (_T_2) begin
      if (3'h3 == io_cycle) begin
        configmem_0_3 <= _T_4;
      end
    end
    if (reset) begin
      configmem_0_4 <= 40'h0;
    end else if (_T_6) begin
      if (3'h4 == io_cycle) begin
        configmem_0_4 <= _T_8[39:0];
      end else if (_T_2) begin
        if (3'h4 == io_cycle) begin
          configmem_0_4 <= _T_4;
        end
      end
    end else if (_T_2) begin
      if (3'h4 == io_cycle) begin
        configmem_0_4 <= _T_4;
      end
    end
    if (reset) begin
      configmem_0_5 <= 40'h0;
    end else if (_T_6) begin
      if (3'h5 == io_cycle) begin
        configmem_0_5 <= _T_8[39:0];
      end else if (_T_2) begin
        if (3'h5 == io_cycle) begin
          configmem_0_5 <= _T_4;
        end
      end
    end else if (_T_2) begin
      if (3'h5 == io_cycle) begin
        configmem_0_5 <= _T_4;
      end
    end
    if (reset) begin
      configmem_0_6 <= 40'h0;
    end else if (_T_6) begin
      if (3'h6 == io_cycle) begin
        configmem_0_6 <= _T_8[39:0];
      end else if (_T_2) begin
        if (3'h6 == io_cycle) begin
          configmem_0_6 <= _T_4;
        end
      end
    end else if (_T_2) begin
      if (3'h6 == io_cycle) begin
        configmem_0_6 <= _T_4;
      end
    end
    if (reset) begin
      configmem_0_7 <= 40'h0;
    end else if (_T_6) begin
      if (3'h7 == io_cycle) begin
        configmem_0_7 <= _T_8[39:0];
      end else if (_T_2) begin
        if (3'h7 == io_cycle) begin
          configmem_0_7 <= _T_4;
        end
      end
    end else if (_T_2) begin
      if (3'h7 == io_cycle) begin
        configmem_0_7 <= _T_4;
      end
    end
    if (reset) begin
      config_pointer_i <= 3'h0;
    end else if (io_en) begin
      if (_T_9) begin
        config_pointer_i <= 3'h0;
      end else begin
        config_pointer_i <= _T_11;
      end
    end else begin
      config_pointer_i <= 3'h0;
    end
    config_pointer <= config_pointer_i;
  end
endmodule
