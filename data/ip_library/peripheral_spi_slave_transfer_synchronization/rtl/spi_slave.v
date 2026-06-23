module spi_slave(clk, reset,
			spiclk, spimosi, spimiso, spicsl,
			we, re, wdat, addr, rdat);
	parameter asz = 7;				// address size
	parameter dsz = 32;				// databus word size
input clk;						// System clock
	input reset;					// System POR
	input spiclk;					// ARM SPI Clock output
	input spimosi;					// ARM SPI Master Out Slave In
	output spimiso;					// ARM SPI Master In Slave Out
	input spicsl;					// ARM SPI Chip Select Low
	output we;						// Write Enable
	output re;						// Read enable
	output [dsz-1:0] wdat;			// write databus
	output [asz-1:0] addr;			// address
	input [dsz-1:0] rdat;			// read databus
	
	// SPI Posedge Process
	reg [5:0]  mosi_cnt;			// input bit counter
	reg [dsz-1:0] mosi_shift;		// shift reg
	reg rd;							// direction flag
	reg [asz-1:0] addr;				// address bits
	reg eoa;						// end of address flag
	reg	re;							// read flag
	reg [dsz-1:0] wdat;				// write data reg
	reg eot;						// end of transfer flag
	wire       spi_reset = reset | spicsl;	// combined reset
 	always@(posedge spiclk or posedge spi_reset)
		if (spi_reset)
		begin
			mosi_cnt <= 'b0;
			mosi_shift <= 32'h0;
			eoa <= 'b0;
			rd <= 'b0;
			eot <= 'b0;
		end
		else 
		begin
			// Counter keeps track of bits received
			mosi_cnt <= mosi_cnt + 1;
			
			// Shift register grabs incoming data
			mosi_shift <= {mosi_shift[dsz-2:0], spimosi};
			
			// Grab Read bit
			if(mosi_cnt == 0)
				rd <= spimosi;
			
			// Grab Address
			if(mosi_cnt == asz)
			begin
				addr <= {mosi_shift[asz-2:0],spimosi};
				eoa <= 1'b1;
			end
			
			// Generate Read pulse
			re <= rd & (mosi_cnt == asz);
if(mosi_cnt == (asz+dsz))
			begin
				// Grab data
				wdat <= {mosi_shift[dsz-2:0],spimosi};
				
				// End-of-transmission (used to generate Write pulse)
				eot <= 1'b1;
			end
		end
	
  	// outgoing shift register is clocked on falling edge
	reg [dsz-1:0] miso_shift;
	always @(negedge spiclk or posedge spi_reset)
		if (spi_reset)
		begin
			miso_shift <= 32'h0;
		end
		else
		begin
			if(re)
				miso_shift <= rdat;
			else
				miso_shift <= {miso_shift[dsz-2:0],1'b0};
		end
	
  	// MISO is just msb of shift reg
	assign spimiso = eoa ? miso_shift[dsz-1] : 1'b0;
	
	// Delay/Sync & edge detect on eot to generate we
	reg [2:0] we_dly;
	reg we;
	always @(posedge clk)
		if(reset)
		begin
			we_dly <= 0;
			we <= 0;
		end
		else
	 	begin
			we_dly <= {we_dly[1:0],eot};
			we <= ~we_dly[2] & we_dly[1] & ~rd;
		end
endmodule
