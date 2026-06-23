module fifo_(
	     input 			     w_clk,
	     input 			     r_clk,
	     input 			     we,
	     input [RAM_DATA_WIDTH - 1 : 0]  d,
	     input 			     re,
	     input [RAM_DATA_WIDTH - 1 :0]   mask,
	     output [RAM_DATA_WIDTH - 1 : 0] q,
	     output 			     empty,
	     output 			     full
	     );
   
   function [ADDR_WIDTH :0] bin_to_gray;
      input [ADDR_WIDTH :0] 		     bin;
      bin_to_gray = (bin >> 1) ^ bin;
   endfunction // bin_to_gray
   
   parameter MODE = 0;
   parameter ADDR_WIDTH = 0;
   parameter ASYNC = 0;
   
   localparam RAM_ADDR_WIDTH = 11; 
   localparam RAM_DATA_WIDTH = 16;
   
   reg [ADDR_WIDTH - 1 : 0] 		     raddr = 0, waddr = 0;
   wire [RAM_ADDR_WIDTH - 1 : 0] 	     _waddr, _raddr;
   
   SB_RAM40_4K #(
		 .WRITE_MODE(MODE),
		 .READ_MODE(MODE)
		 ) bram (
			 .RDATA(q),
			 .RADDR(_raddr),
			 .RCLK(r_clk),
			 .RCLKE(1'b1),
			 .RE(re),
			 .WADDR(_waddr),
			 .WCLK(w_clk),
			 .WCLKE(1'b1),
			 .WDATA(d),
			 .WE(we),
			 .MASK(mask)
			 );
   
   assign _waddr = { {(RAM_ADDR_WIDTH - ADDR_WIDTH){1'b0}}, {waddr} };
   assign _raddr = { {(RAM_ADDR_WIDTH - ADDR_WIDTH){1'b0}}, {raddr} };
   
   always @ (posedge w_clk)
     begin
	if (we & ~full)
	  begin
	     waddr <= waddr + 1;
	  end
     end
always @ (posedge r_clk)
     begin
	if (re & ~empty)
	  begin
	     raddr <= raddr + 1;
	  end
     end
   
   generate
      
      if (ASYNC)
	begin : async_ctrs
	   
	   reg 					 _full = 0, _empty = 1;
	   reg [ADDR_WIDTH : 0] 		 wptr = 0, rptr = 0;
	   reg [ADDR_WIDTH : 0] 		 rq1_wptr = 0, rq2_wptr = 0;
	   reg [ADDR_WIDTH : 0] 		 wq1_rptr = 0, wq2_rptr = 0;

	   wire [ADDR_WIDTH : 0] 		 _wptr, _rptr;
	   
	   assign _wptr = bin_to_gray(waddr + (we & ~full));
	   assign _rptr = bin_to_gray(raddr + (re & ~empty));
	   
	   assign full = _full;
	   assign empty = _empty;
	   
	   always @ (posedge w_clk)
	     begin
		wptr <= _wptr;
		_full <= (_wptr ==
			  {~wq2_rptr[ADDR_WIDTH:ADDR_WIDTH-1], wq2_rptr[ADDR_WIDTH-2:0]});
	     end
	   
	   always @ (posedge r_clk)
	     begin
		_empty <= (_rptr == rq2_wptr);
		rptr <= _rptr;
	     end   
	   
	   always @ (posedge w_clk)
	     begin
		wq1_rptr <= rptr;
		wq2_rptr <= wq1_rptr;
	     end
	   
	   always @ (posedge r_clk)
	     begin
		rq1_wptr <= wptr;
		rq2_wptr <= rq1_wptr;
	     end
	   
	end // if (ASYNC)
      
      else
	begin : sync_ctrs

	   reg [ADDR_WIDTH - 1 : 0] ctr = 0;
	   
	   assign full = &ctr;
	   assign empty = ~&ctr; 
	   
	   always @ (posedge w_clk)
	     begin
		if (we & ~re & ~full)
		  begin
		     ctr <= ctr + 1;
		  end
		else if(re & ~we & ~empty)
		  begin
		     ctr <= ctr - 1;
		  end
	     end // always @ (posedge w_clk)
	   
	end // else: !if(ASYNC)
   endgenerate
      
endmodule
