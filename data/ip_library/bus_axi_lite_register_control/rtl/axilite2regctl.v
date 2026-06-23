module axilite2regctl #
(
	// Width of S_AXI data bus
	parameter integer C_DATA_WIDTH	= 32,
	// Width of S_AXI address bus
	parameter integer C_ADDR_WIDTH	= 10,
	// Width of REG address
	parameter integer C_REG_IDX_WIDTH = 8

)
(
	input wire  clk,
	input wire  resetn,

	/// reg ctl interface
	output rd_en,
	output [C_REG_IDX_WIDTH-1:0] rd_addr,
	input [C_DATA_WIDTH-1:0] rd_data,

	output wr_en,
	output [C_REG_IDX_WIDTH-1:0] wr_addr,
	output [C_DATA_WIDTH-1:0] wr_data,

	/// slave axi lite
	input wire [C_ADDR_WIDTH-1 : 0] s_axi_awaddr,
	input wire  s_axi_awvalid,
	output wire  s_axi_awready,
	input wire [C_DATA_WIDTH-1 : 0] s_axi_wdata,
	input wire  s_axi_wvalid,
	output wire  s_axi_wready,
	output wire [1 : 0] s_axi_bresp,
	output wire  s_axi_bvalid,
	input wire  s_axi_bready,
	input wire [C_ADDR_WIDTH-1 : 0] s_axi_araddr,
	input wire  s_axi_arvalid,
	output wire  s_axi_arready,
	output wire [C_DATA_WIDTH-1 : 0] s_axi_rdata,
	output wire [1 : 0] s_axi_rresp,
	output wire  s_axi_rvalid,
	input wire  s_axi_rready
);
// AXI4LITE signals
	reg [C_ADDR_WIDTH-1 : 0] 	axi_awaddr;
	reg  	axi_awready;
	reg  	axi_wready;
	reg  	axi_bvalid;
	reg  	axi_arready;
	reg  	axi_rvalid;

	wire	 slv_reg_rden;
	wire	 slv_reg_wren;
	integer	 byte_index;
	reg	 aw_en;

	/**
	 * read/write interface
	 */
	assign rd_en = slv_reg_rden;
	assign rd_addr = s_axi_araddr[C_ADDR_WIDTH-1:C_ADDR_WIDTH-C_REG_IDX_WIDTH];
	assign wr_addr = axi_awaddr[C_ADDR_WIDTH-1:C_ADDR_WIDTH-C_REG_IDX_WIDTH];
	assign wr_en = slv_reg_wren;
	assign wr_data = s_axi_wdata;

	// I/O Connections assignments

	assign s_axi_awready	= axi_awready;
	assign s_axi_wready	= axi_wready;
	assign s_axi_bresp	= 0;
	assign s_axi_bvalid	= axi_bvalid;
	assign s_axi_arready	= axi_arready;
	assign s_axi_rdata	= rd_data;
	assign s_axi_rresp	= 0;
	assign s_axi_rvalid	= axi_rvalid;
	// Implement axi_awready generation
	// axi_awready is asserted for one clk clock cycle when both
	// s_axi_awvalid and s_axi_wvalid are asserted. axi_awready is
	// de-asserted when reset is low.

	always @( posedge clk )
	begin
		if ( resetn == 1'b0 ) begin
			axi_awready <= 1'b0;
			aw_en <= 1'b1;
		end
		else if (~axi_awready && s_axi_awvalid && s_axi_wvalid && aw_en) begin
			axi_awready <= 1'b1;
			aw_en <= 1'b0;
		end
		else if (s_axi_bready && axi_bvalid) begin
			aw_en <= 1'b1;
			axi_awready <= 1'b0;
		end
		else begin
			axi_awready <= 1'b0;
		end
	end
// Implement axi_awaddr latching
	// This process is used to latch the address when both
	// s_axi_awvalid and s_axi_wvalid are valid.

	always @( posedge clk )
	begin
		if ( resetn == 1'b0 )
			axi_awaddr <= 0;
		else if (~axi_awready && s_axi_awvalid && s_axi_wvalid && aw_en)
			axi_awaddr <= s_axi_awaddr;
		else
			axi_awaddr <= axi_awaddr;
	end

	// Implement axi_wready generation
	// axi_wready is asserted for one clk clock cycle when both
	// s_axi_awvalid and s_axi_wvalid are asserted. axi_wready is
	// de-asserted when reset is low.

	always @( posedge clk ) begin
		if ( resetn == 1'b0 )
			axi_wready <= 1'b0;
		else if (~axi_wready && s_axi_wvalid && s_axi_awvalid && aw_en )
			axi_wready <= 1'b1;
		else
			axi_wready <= 1'b0;
	end

	// Implement memory mapped register select and write logic generation
	// The write data is accepted and written to memory mapped registers when
	// axi_awready, s_axi_wvalid, axi_wready and s_axi_wvalid are asserted. Write strobes are used to
	// select byte enables of slave registers while writing.
	// These registers are cleared when reset (active low) is applied.
	// Slave register write enable is asserted when valid address and data are available
	// and the slave is ready to accept the write address and write data.
	assign slv_reg_wren = axi_wready && s_axi_wvalid && axi_awready && s_axi_awvalid;
// Implement write response logic generation
	// The write response and response valid signals are asserted by the slave
	// when axi_wready, s_axi_wvalid, axi_wready and s_axi_wvalid are asserted.
	// This marks the acceptance of address and indicates the status of
	// write transaction.

	always @( posedge clk )
	begin
		if ( resetn == 1'b0 )
			axi_bvalid  <= 0;
		else if (axi_awready && s_axi_awvalid && ~axi_bvalid && axi_wready && s_axi_wvalid)
			axi_bvalid <= 1'b1;
		else if (s_axi_bready && axi_bvalid)
			axi_bvalid <= 1'b0;
	end

	// Implement axi_arready generation
	// axi_arready is asserted for one clk clock cycle when
	// s_axi_arvalid is asserted. axi_awready is
	// de-asserted when reset (active low) is asserted.
	// The read address is also latched when s_axi_arvalid is
	// asserted. axi_araddr is reset to zero on reset assertion.

	always @( posedge clk ) begin
		if ( resetn == 1'b0 )
			axi_arready <= 1'b0;
		else if (~axi_arready && s_axi_arvalid)
			// indicates that the slave has acceped the valid read address
			axi_arready <= 1'b1;
		else
			axi_arready <= 1'b0;
	end
// Implement axi_arvalid generation
	// axi_rvalid is asserted for one clk clock cycle when both
	// s_axi_arvalid and axi_arready are asserted. The slave registers
	// data are available on the axi_rdata bus at this instance. The
	// assertion of axi_rvalid marks the validity of read data on the
	// bus and axi_rresp indicates the status of read transaction.axi_rvalid
	// is deasserted on reset (active low). axi_rresp and axi_rdata are
	// cleared to zero on reset (active low).
	always @( posedge clk ) begin
		if ( resetn == 1'b0 )
			axi_rvalid <= 0;
		else if (axi_arready && s_axi_arvalid && ~axi_rvalid)
			axi_rvalid <= 1'b1;
		else if (axi_rvalid && s_axi_rready)
			axi_rvalid <= 1'b0;
	end

	// Implement memory mapped register select and read logic generation
	// Slave register read enable is asserted when valid address is available
	// and the slave is ready to accept the read address.
	assign slv_reg_rden = axi_arready & s_axi_arvalid & ~axi_rvalid;
endmodule
