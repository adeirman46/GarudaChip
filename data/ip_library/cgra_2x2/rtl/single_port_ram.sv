`include "cgra_defs.svh"
module single_port_ram(
  input         clock,
  input         io_enable,
  input         io_write_enable,
  input  [5:0]  io_addr,
  input  [31:0] io_dataIn,
  output [31:0] io_dataOut
);
`ifdef RANDOMIZE_MEM_INIT
  reg [31:0] _RAND_0;
`endif // RANDOMIZE_MEM_INIT
`ifdef RANDOMIZE_REG_INIT
  reg [31:0] _RAND_1;
  reg [31:0] _RAND_2;
`endif // RANDOMIZE_REG_INIT
  reg [31:0] mem [0:63]; // @[SRAM.scala 125:24]
  wire [31:0] mem__T_r_data; // @[SRAM.scala 125:24]
  wire [5:0] mem__T_r_addr; // @[SRAM.scala 125:24]
  wire [31:0] mem__T_w_data; // @[SRAM.scala 125:24]
  wire [5:0] mem__T_w_addr; // @[SRAM.scala 125:24]
  wire  mem__T_w_mask; // @[SRAM.scala 125:24]
  wire  mem__T_w_en; // @[SRAM.scala 125:24]
  reg  mem__T_r_en_pipe_0;
  reg [5:0] mem__T_r_addr_pipe_0;
  wire  _GEN_8 = io_enable & io_write_enable; // @[SRAM.scala 127:19]
  wire  _GEN_11 = ~_GEN_8;
  assign mem__T_r_addr = mem__T_r_addr_pipe_0;
  assign mem__T_r_data = mem[mem__T_r_addr]; // @[SRAM.scala 125:24]
  assign mem__T_w_data = io_dataIn;
  assign mem__T_w_addr = io_addr;
  assign mem__T_w_mask = io_write_enable;
  assign mem__T_w_en = io_enable & _GEN_8;
  assign io_dataOut = mem__T_r_data; // @[SRAM.scala 130:34]
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
`ifdef RANDOMIZE_MEM_INIT
  _RAND_0 = {1{`RANDOM}};
  for (initvar = 0; initvar < 64; initvar = initvar+1)
    mem[initvar] = _RAND_0[31:0];
`endif // RANDOMIZE_MEM_INIT
`ifdef RANDOMIZE_REG_INIT
  _RAND_1 = {1{`RANDOM}};
  mem__T_r_en_pipe_0 = _RAND_1[0:0];
  _RAND_2 = {1{`RANDOM}};
  mem__T_r_addr_pipe_0 = _RAND_2[5:0];
`endif // RANDOMIZE_REG_INIT
  `endif // RANDOMIZE
end // initial
`ifdef FIRRTL_AFTER_INITIAL
`FIRRTL_AFTER_INITIAL
`endif
`endif // SYNTHESIS
  always @(posedge clock) begin
    if(mem__T_w_en & mem__T_w_mask) begin
      mem[mem__T_w_addr] <= mem__T_w_data; // @[SRAM.scala 125:24]
    end
    mem__T_r_en_pipe_0 <= io_enable & _GEN_11;
    if (io_enable & _GEN_11) begin
      mem__T_r_addr_pipe_0 <= io_addr;
    end
  end
endmodule
