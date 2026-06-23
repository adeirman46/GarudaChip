module channelizer_xlaxififogen(
 s_aclk,
 ce,
 aresetn,
 axis_underflow,
 axis_overflow,
 axis_data_count,
 axis_prog_full_thresh,
 axis_prog_empty_thresh,
 s_axis_tdata,
 s_axis_tstrb,
 s_axis_tkeep,
 s_axis_tlast,
 s_axis_tid,
 s_axis_tdest,
 s_axis_tuser,
 s_axis_tvalid,
 s_axis_tready,
 m_axis_tdata,
 m_axis_tstrb,
 m_axis_tkeep,
 m_axis_tlast,
 m_axis_tid,
 m_axis_tdest,
 m_axis_tuser,
 m_axis_tvalid,
 m_axis_tready
 );
 parameter core_name0 = "";
 parameter has_aresetn = -1;
 parameter tdata_width = -1;
 parameter tdest_width = -1;
 parameter tstrb_width = -1;
 parameter tkeep_width = -1;
 parameter tid_width = -1;
 parameter tuser_width = -1;
 parameter depth_bits = -1; 
 input ce;
input s_aclk;
input aresetn;
output axis_underflow;
output axis_overflow;
output [depth_bits-1:0] axis_data_count;
input  [depth_bits-2:0] axis_prog_full_thresh;
input  [depth_bits-2:0] axis_prog_empty_thresh;
input  [tdata_width-1:0] s_axis_tdata;
input  [tstrb_width-1:0] s_axis_tstrb;
input  [tkeep_width-1:0] s_axis_tkeep;
input                     s_axis_tlast;
input  [tid_width-1:0] s_axis_tid;
input  [tdest_width-1:0] s_axis_tdest;
input  [tuser_width-1:0] s_axis_tuser;
input                     s_axis_tvalid;
output                    s_axis_tready;
output  [tdata_width-1:0] m_axis_tdata;
output  [tstrb_width-1:0] m_axis_tstrb;
output  [tkeep_width-1:0] m_axis_tkeep;
output                        m_axis_tlast;
output  [tid_width-1:0] m_axis_tid;
output  [tdest_width-1:0] m_axis_tdest;
output  [tuser_width-1:0] m_axis_tuser;
output                        m_axis_tvalid;
input                 m_axis_tready;


   wire srst;
   reg reset_gen1 = 1'b0;
   reg reset_gen_d1 = 1'b0;
   reg reset_gen_d2 = 1'b0;
 
   always @(posedge s_aclk)
   begin
   	reset_gen1 <= 1'b1;
 	reset_gen_d1 <= reset_gen1;
 	reset_gen_d2 <= reset_gen_d1;
   end
 
   generate
   if(has_aresetn == 0)
   begin:if_block
         assign srst = reset_gen_d2;
   end
   else
   begin:else_block
     assign srst = ~((~aresetn) & ce);
   end
   endgenerate
 
   generate
if (core_name0 == "channelizer_fifo_generator_v12_0_0") 
     begin:comp0
channelizer_fifo_generator_v12_0_0 core_instance0 ( 
        .s_aclk(s_aclk),
        .s_aresetn(srst),
        .s_axis_tdata(s_axis_tdata),
        .s_axis_tlast(s_axis_tlast),
        .s_axis_tid  (s_axis_tid),
        .s_axis_tdest(s_axis_tdest),
        .s_axis_tuser(s_axis_tuser),
        .s_axis_tvalid(s_axis_tvalid),
        .s_axis_tready(s_axis_tready),
        .m_axis_tdata(m_axis_tdata),
        .m_axis_tlast(m_axis_tlast),
        .m_axis_tid  (m_axis_tid),
        .m_axis_tdest(m_axis_tdest),
        .m_axis_tuser(m_axis_tuser),
        .m_axis_tvalid(m_axis_tvalid),
        .m_axis_tready(m_axis_tready)
 
       ); 
     end 

endgenerate
 endmodule
