module wb_sseg_ctrl
  #(
    parameter n_digits    =    8,
    parameter n_segs      =    8,
    parameter def_clk_div =  128,
    //parameter def_clk_div =    4,
    parameter dw          =   16,
    parameter aw          =    4
    )
   (
    input                  wb_clk_i,
    input                  wb_rst_i,
    input                  async_rst_i,

    // Wishbone Interface
    input  [aw-1:0]        wb_adr_i,
    input  [dw-1:0]        wb_dat_i,
    input  [3:0]           wb_sel_i,
    input                  wb_we_i,
    input                  wb_cyc_i,
    input                  wb_stb_i,
    input  [2:0]           wb_cti_i,
    input  [1:0]           wb_bte_i,
    output reg [dw-1:0]    wb_dat_o,
    output reg             wb_ack_o,
    output                 wb_err_o,
    output                 wb_rty_o,

    // display i/f
    output [n_segs-1:0]    seg_o,
    output [n_digits-1:0]  seg_sel_o,

    // frame sync irq (end of the sweep)
    output                 irq_o
    );

   wire sync;

   // address decoder
   reg [2**aw-1:0]  sel;
   integer          i;
   always @(*)
     begin
        sel = {2**aw{1'b0}};
        for (i = 0; i < 2**aw; i = i + 1)
          if (wb_adr_i == i)
            sel[i] = 1'b1;
     end
// enable register
   reg enable_reg;
   always @(posedge wb_clk_i or posedge async_rst_i)
     if (async_rst_i)
       enable_reg <= 1'b0;
     else if (wb_rst_i)
       enable_reg <= 1'b0;
     else if (wb_cyc_i & wb_stb_i & wb_we_i & sel[0])
       enable_reg <= wb_dat_i[0];

   // mask IRQ register
   reg IRQ_mask_reg;
   always @(posedge wb_clk_i or posedge async_rst_i)
     if (async_rst_i)
       IRQ_mask_reg <= 1'b0;
     else if (wb_rst_i)
       IRQ_mask_reg <= 1'b0;
     else if (wb_cyc_i & wb_stb_i & wb_we_i & sel[0])
       IRQ_mask_reg <= wb_dat_i[1];

   // clock divider register
   reg [15:0] clk_div_reg;
   always @(posedge wb_clk_i or posedge async_rst_i)
     if (async_rst_i)
       clk_div_reg <= def_clk_div;
     else if (wb_rst_i)
       clk_div_reg <= def_clk_div;
     else if (wb_cyc_i & wb_stb_i & wb_we_i & sel[1])
       clk_div_reg <= wb_dat_i[15:0];

   // brightness register
   reg [7:0] brightness_reg;
   always @(posedge wb_clk_i or posedge async_rst_i)
     if (async_rst_i)
       brightness_reg <= 8'hff;
     else if (wb_rst_i)
       brightness_reg <= 8'hff;
     else if (wb_cyc_i & wb_stb_i & wb_we_i & sel[2])
       brightness_reg <= wb_dat_i[7:0];
// data to display
   reg [n_digits*n_segs-1:0] segments_reg;
   always @(posedge wb_clk_i or posedge async_rst_i)
     if (async_rst_i)
       segments_reg <= 0;
     else if (wb_rst_i)
       segments_reg <= 0;
     else if (wb_cyc_i & wb_stb_i & wb_we_i)
       for (i = 0; i < n_digits; i = i + 1)
         if (sel[i+8])
           segments_reg[n_segs*(i+1)-1 -: n_segs] <= wb_dat_i[n_segs-1:0];

   // IRQ flag
   // write '1' to clear it
   reg IRQ_flag_reg;
   always @(posedge wb_clk_i or posedge async_rst_i)
     if (async_rst_i)
       IRQ_flag_reg <= 1'b0;
     else if (wb_rst_i)
       IRQ_flag_reg <= 1'b0;
     else if (wb_cyc_i & wb_stb_i & wb_we_i & sel[3] & wb_dat_i[0])
       IRQ_flag_reg <= 1'b0;
     else if (sync)
       IRQ_flag_reg <= 1'b1;

   assign irq_o = IRQ_flag_reg & IRQ_mask_reg;

   // read back register values
   always @(posedge wb_clk_i)
     if (wb_rst_i)
       wb_dat_o <= 32'b0;
     else if (wb_cyc_i)
       begin
          wb_dat_o <= 0;
          if (sel[0]) wb_dat_o[1:0]  <= {IRQ_mask_reg, enable_reg};
          if (sel[1]) wb_dat_o[15:0] <= clk_div_reg;
          if (sel[2]) wb_dat_o[7:0]  <= brightness_reg;
          if (sel[3]) wb_dat_o[0]    <= IRQ_flag_reg;
          for (i = 0; i < n_digits; i = i + 1)
            if (sel[i+8])
              wb_dat_o[n_segs-1:0] <= segments_reg[n_segs*(i+1)-1 -: n_segs];
       end
// Ack generation
   always @(posedge wb_clk_i)
     if (wb_rst_i)
       wb_ack_o <= 0;
     else if (wb_ack_o)
       wb_ack_o <= 0;
     else if (wb_cyc_i & wb_stb_i & !wb_ack_o)
       wb_ack_o <= 1;

   assign wb_err_o = 0;
   assign wb_rty_o = 0;

   // instantiate the controller
   sseg_ctrl #(.n_digits(n_digits)) ctrl
     (
      .clk_i          (wb_clk_i),
      .rst_i          (wb_rst_i),
      .async_rst_i    (async_rst_i),
      // config registers
      .enable_i       (enable_reg),
      .clk_div_i      (clk_div_reg),
      .brightness_i   (brightness_reg),
      .segments_i     (segments_reg),
      // display i/f
      .seg_o          (seg_o),
      .seg_sel_o      (seg_sel_o),
      // sync irq
      .sync_o         (sync)
      );

endmodule
