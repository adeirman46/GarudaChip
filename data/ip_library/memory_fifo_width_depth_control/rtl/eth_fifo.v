module eth_fifo (data_in, data_out, clk, reset, write, read, clear, almost_full, full, almost_empty, empty, cnt);

parameter DATA_WIDTH    = 32;
parameter DEPTH         = 8;
parameter CNT_WIDTH     = 4;

parameter Tp            = 1;

input                     clk;
input                     reset;
input                     write;
input                     read;
input                     clear;
input   [DATA_WIDTH-1:0]  data_in;

output  [DATA_WIDTH-1:0]  data_out;
output                    almost_full;
output                    full;
output                    almost_empty;
output                    empty;
output  [CNT_WIDTH-1:0]   cnt;

`ifndef XILINX_SPARTAN6_FPGA
    reg     [DATA_WIDTH-1:0]  fifo  [0:DEPTH-1];
    reg     [DATA_WIDTH-1:0]  data_out;
`endif

reg     [CNT_WIDTH-1:0]   cnt;
reg     [CNT_WIDTH-2:0]   read_pointer;
reg     [CNT_WIDTH-2:0]   write_pointer;


always @ (posedge clk or posedge reset)
begin
  if(reset)
    cnt <=#Tp 0;
  else
  if(clear)
    cnt <=#Tp { {(CNT_WIDTH-1){1'b0}}, read^write};
  else
  if(read ^ write)
    if(read)
      cnt <=#Tp cnt - 1'b1;
    else
      cnt <=#Tp cnt + 1'b1;
end
always @ (posedge clk or posedge reset)
begin
  if(reset)
    read_pointer <=#Tp 0;
  else
  if(clear)
    read_pointer <=#Tp { {(CNT_WIDTH-2){1'b0}}, read};
  else
  if(read & ~empty)
    read_pointer <=#Tp read_pointer + 1'b1;
end

always @ (posedge clk or posedge reset)
begin
  if(reset)
    write_pointer <=#Tp 0;
  else
  if(clear)
    write_pointer <=#Tp { {(CNT_WIDTH-2){1'b0}}, write};
  else
  if(write & ~full)
    write_pointer <=#Tp write_pointer + 1'b1;
end

assign empty = ~(|cnt);
assign almost_empty = cnt == 1;
assign full  = cnt == DEPTH;
assign almost_full  = &cnt[CNT_WIDTH-2:0];



`ifdef XILINX_SPARTAN6_FPGA
  xilinx_dist_ram_16x32 fifo
  ( .data_out(data_out), 
    .we(write & ~full),
    .data_in(data_in),
    .read_address( clear ? {CNT_WIDTH-1{1'b0}} : read_pointer),
    .write_address(clear ? {CNT_WIDTH-1{1'b0}} : write_pointer),
    .wclk(clk)
  );
`else
  always @ (posedge clk)
  begin
    if(write & clear)
      fifo[0] <=#Tp data_in;
    else
   if(write & ~full)
      fifo[write_pointer] <=#Tp data_in;
  end
  

  always @ (posedge clk)
  begin
    if(clear)
      data_out <=#Tp fifo[0];
    else
      data_out <=#Tp fifo[read_pointer];
  end
`endif


endmodule
