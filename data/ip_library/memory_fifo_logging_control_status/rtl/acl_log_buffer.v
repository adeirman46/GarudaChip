module acl_log_buffer(
	clock, reset_n, restart,
	
	valid_data,
	block_state,
	log_address,
	log_flush,
	log_enable,
	log_empty,
   address, readdata, writedata, write,

	avm_live_data_dump_address,
	avm_live_data_dump_writedata,
	avm_live_data_dump_readdata,
	avm_live_data_dump_byteenable,
	avm_live_data_dump_burstcount,
	avm_live_data_dump_write,
	avm_live_data_dump_read,
	avm_live_data_dump_readdatavalid,
	avm_live_data_dump_waitrequest,
   avm_live_data_dump_writeack);

	localparam DATA_WIDTH = 672;  // 64 bytes (FIFO depth) + 128 bits (master stall bits) + 32 bits cycle number
   localparam NUM_WORDS_DWIDTH = DATA_WIDTH / 32;

	input clock, reset_n, restart, valid_data, log_flush, log_enable;
	output log_empty;
	input [4:0] address;
	output reg [31:0] readdata;
	input [31:0] writedata;
	input write;

	input [(DATA_WIDTH - 1):0] block_state;
	input [31:0] log_address;
	output reg [31:0] avm_live_data_dump_address;
	output [255:0] avm_live_data_dump_writedata;
	input [255:0] avm_live_data_dump_readdata;
	output [31:0] avm_live_data_dump_byteenable;
	output [6:0] avm_live_data_dump_burstcount;
	output avm_live_data_dump_write;
	output avm_live_data_dump_read;
	input avm_live_data_dump_readdatavalid;
	input avm_live_data_dump_waitrequest;
	input avm_live_data_dump_writeack;
assign avm_live_data_dump_address = 32'h0;
	assign avm_live_data_dump_writedata = 256'h0;
	assign avm_live_data_dump_byteenable = 256'hffffffff;
	assign avm_live_data_dump_burstcount = 7'h0;
	assign avm_live_data_dump_write = 1'b0;
	assign avm_live_data_dump_read = 1'b0;

   reg data_logging_triggered;
	
	reg [2:0] present_state;
	reg [2:0] next_state;
	
	parameter DEPTH = 256;  // 256 is the default only, usually overridden when instantiated
	
	localparam NUM_BITS_DEPTH = $clog2(DEPTH);
	
	wire [NUM_BITS_DEPTH:0] fifo_usedw;
	reg [7:0] words_read;
   wire read_buffer_exhausted;
	wire fifo_valid_in;
	wire [DATA_WIDTH-1:0] fifo_data_out;
	wire buffer_full = fifo_usedw[NUM_BITS_DEPTH];
	wire reboot;
	
  
   wire [4:0] word_address;
   assign word_address = writedata[4:0];

   wire [31:0] individual_words [NUM_WORDS_DWIDTH];
   generate
		genvar word_index;
		
		for(word_index = 0; word_index < NUM_WORDS_DWIDTH; word_index = word_index + 1)
		begin: wordAssignment
			assign individual_words[word_index] = fifo_data_out[((word_index+1)*32 -1):word_index*32];
		end
	endgenerate


   always@(*)
	begin
		if ((write) && (address == 5'h05))
      begin
         if ((writedata[31:5] == 27'h0) && (word_address < NUM_WORDS_DWIDTH))
            readdata <= individual_words[word_address];
         else
            readdata <= 32'hFFFFFFFF;
      end
	end
always@(posedge clock or negedge reset_n)
	begin
		if (~reset_n)
		begin
			data_logging_triggered <= 1'b0;
		end
		else 
		begin
			if (restart)
			begin
            data_logging_triggered <= 1'b0;
			end
			else
			begin
            // Trigger if past start cycle, and at least one of the FIFOs shows some life
            if (fifo_usedw[NUM_BITS_DEPTH])  // If FIFO full, stop logging
					data_logging_triggered <= 1'b0;
				else if (valid_data)
					data_logging_triggered <= 1'b1;
				else
					data_logging_triggered <= data_logging_triggered;
			end
		end
	end

   // FIFO to hold the cycle-by-cycle data.
	scfifo	dump_fifo (
				.clock (clock),
				.data (block_state),
				.rdreq ((write) && (address == 5'h05) && (writedata == 32'hFFFFFFFF)),
				.sclr (restart),
				.wrreq (data_logging_triggered && (~fifo_usedw[NUM_BITS_DEPTH]) && log_enable),
				.empty (log_empty),
				.full (fifo_usedw[NUM_BITS_DEPTH]),
				.q (fifo_data_out),
				.aclr (),
				.almost_empty (),
				.almost_full (),
				.usedw (fifo_usedw[NUM_BITS_DEPTH-1:0]));
	defparam
		dump_fifo.add_ram_output_register = "ON",
		dump_fifo.intended_device_family = "Stratix IV",
		dump_fifo.lpm_numwords = DEPTH,
		dump_fifo.lpm_showahead = "OFF",
		dump_fifo.lpm_type = "scfifo",
		dump_fifo.lpm_width = DATA_WIDTH,
		dump_fifo.lpm_widthu = NUM_BITS_DEPTH,
		dump_fifo.overflow_checking = "ON",
		dump_fifo.underflow_checking = "ON",
		dump_fifo.use_eab = "ON";

endmodule
