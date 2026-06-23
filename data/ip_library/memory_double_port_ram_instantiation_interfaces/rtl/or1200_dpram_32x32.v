module or1200_dpram_32x32(
	// Generic synchronous double-port RAM interface
	clk_a, rst_a, ce_a, oe_a, addr_a, do_a,
	clk_b, rst_b, ce_b, we_b, addr_b, di_b
);

//
// Default address and data buses width
//
parameter aw = 5;
parameter dw = 32;

//
// Generic synchronous double-port RAM interface
//
input			clk_a;	// Clock
input			rst_a;	// Reset
input			ce_a;	// Chip enable input
input			oe_a;	// Output enable input
input 	[aw-1:0]	addr_a;	// address bus inputs
output	[dw-1:0]	do_a;	// output data bus
input			clk_b;	// Clock
input			rst_b;	// Reset
input			ce_b;	// Chip enable input
input			we_b;	// Write enable input
input 	[aw-1:0]	addr_b;	// address bus inputs
input	[dw-1:0]	di_b;	// input data bus

//
// Internal wires and registers
//

`ifdef OR1200_ARTISAN_SDP

//
// Instantiation of ASIC memory:
//
// Artisan Synchronous Double-Port RAM (ra2sh)
//
`ifdef UNUSED
art_hsdp_32x32 #(dw, 1<<aw, aw) artisan_sdp(
`else
art_hsdp_32x32 artisan_sdp(
`endif
	.qa(do_a),
	.clka(clk_a),
	.cena(~ce_a),
	.wena(1'b1),
	.aa(addr_a),
	.da(32'h00000000),
	.oena(~oe_a),
	.qb(),
	.clkb(clk_b),
	.cenb(~ce_b),
	.wenb(~we_b),
	.ab(addr_b),
	.db(di_b),
	.oenb(1'b1)
);

`else

`ifdef OR1200_AVANT_ATP
`else

`ifdef OR1200_AVANT_ATP

//
// Instantiation of ASIC memory:
//
// Avant! Asynchronous Two-Port RAM
//
avant_atp avant_atp(
	.web(~we),
	.reb(),
	.oeb(~oe),
	.rcsb(),
	.wcsb(),
	.ra(addr),
	.wa(addr),
	.di(di),
	.doq(doq)
);

`else

`ifdef OR1200_VIRAGE_STP

//
// Instantiation of ASIC memory:
//
// Virage Synchronous 2-port R/W RAM
//
virage_stp virage_stp(
	.QA(do_a),
	.QB(),

	.ADRA(addr_a),
	.DA(32'h00000000),
	.WEA(1'b0),
	.OEA(oe_a),
	.MEA(ce_a),
	.CLKA(clk_a),

	.ADRB(addr_b),
	.DB(di_b),
	.WEB(we_b),
	.OEB(1'b1),
	.MEB(ce_b),
	.CLKB(clk_b)
);

`else

`ifdef OR1200_VIRTUALSILICON_STP_T1

//
// Instantiation of ASIC memory:
//
// Virtual Silicon Two-port R/W SRAM Type 1
//
`ifdef UNUSED
vs_hdtp_64x32 #(1<<aw, aw-1, dw-1) vs_ssp(
`else
vs_hdtp_64x32 vs_ssp(
`endif
	.P1CK(clk_a),
	.P1CEN(~ce_a),
	.P1WEN(1'b1),
	.P1OEN(~oe_a),
	.P1ADR({1'b0, addr_a}),
	.P1DI(32'h0000_0000),
	.P1DOUT(do_a),

	.P2CK(clk_b),
	.P2CEN(~ce_b),
	.P2WEN(~ce_b),
	.P2OEN(1'b1),
	.P2ADR({1'b0, addr_b}),
	.P2DI(di_b),
	.P2DOUT()
);

`else

`ifdef OR1200_VIRTUALSILICON_STP_T2

//
// Instantiation of ASIC memory:
//
// Virtual Silicon Two-port R/W SRAM Type 2
//
`ifdef UNUSED
vs_hdtp_32x32 #(1<<aw, aw-1, dw-1) vs_ssp(
`else
vs_hdtp_32x32 vs_ssp(
`endif
        .RCK(clk_a),
        .REN(~ce_a),
        .OEN(~oe_a),
        .RADR(addr_a),
        .DOUT(do_a),

	.WCK(clk_b),
	.WEN(~ce_b),
	.WADR(addr_b),
	.DI(di_b)
);

`else

`ifdef OR1200_XILINX_RAM32X1D
.WCK(clk_b),
	.WEN(~ce_b),
	.WADR(addr_b),
	.DI(di_b)
);

`else

`ifdef OR1200_XILINX_RAM32X1D

//
// Instantiation of FPGA memory:
//
// Virtex/Spartan2
//

reg	[4:0]	addr_a_r;

always @(posedge clk_a or posedge rst_a)
	if (rst_a)
		addr_a_r <= #1 5'b00000;
	else if (ce_a)
		addr_a_r <= #1 addr_a;

//
// Block 0
//
or1200_xcv_ram32x8d xcv_ram32x8d_0 (
	.DPO(do_a[7:0]),
	.SPO(),
	.A(addr_b),
	.D(di_b[7:0]),
	.DPRA(addr_a_r),
	.WCLK(clk_b),
	.WE(we_b)
);

//
// Block 1
//
or1200_xcv_ram32x8d xcv_ram32x8d_1 (
	.DPO(do_a[15:8]),
	.SPO(),
	.A(addr_b),
	.D(di_b[15:8]),
	.DPRA(addr_a_r),
	.WCLK(clk_b),
	.WE(we_b)
);


//
// Block 2
//
or1200_xcv_ram32x8d xcv_ram32x8d_2 (
	.DPO(do_a[23:16]),
	.SPO(),
	.A(addr_b),
	.D(di_b[23:16]),
	.DPRA(addr_a_r),
	.WCLK(clk_b),
	.WE(we_b)
);

//
// Block 3
//
or1200_xcv_ram32x8d xcv_ram32x8d_3 (
	.DPO(do_a[31:24]),
	.SPO(),
	.A(addr_b),
	.D(di_b[31:24]),
	.DPRA(addr_a_r),
	.WCLK(clk_b),
	.WE(we_b)
);

`else

`ifdef OR1200_XILINX_RAMB4

//
// Instantiation of FPGA memory:
//
// Virtex/Spartan2
//

//
// Block 0
//
RAMB4_S16_S16 ramb4_s16_0(
	.CLKA(clk_a),
	.RSTA(rst_a),
	.ADDRA({3'b000, addr_a}),
	.DIA(16'h0000),
	.ENA(ce_a),
	.WEA(1'b0),
	.DOA(do_a[15:0]),

	.CLKB(clk_b),
	.RSTB(rst_b),
	.ADDRB({3'b000, addr_b}),
	.DIB(di_b[15:0]),
	.ENB(ce_b),
	.WEB(we_b),
	.DOB()
);

//
// Block 1
//
RAMB4_S16_S16 ramb4_s16_1(
	.CLKA(clk_a),
	.RSTA(rst_a),
	.ADDRA({3'b000, addr_a}),
	.DIA(16'h0000),
	.ENA(ce_a),
	.WEA(1'b0),
	.DOA(do_a[31:16]),
//
// Block 1
//
RAMB4_S16_S16 ramb4_s16_1(
	.CLKA(clk_a),
	.RSTA(rst_a),
	.ADDRA({3'b000, addr_a}),
	.DIA(16'h0000),
	.ENA(ce_a),
	.WEA(1'b0),
	.DOA(do_a[31:16]),

	.CLKB(clk_b),
	.RSTB(rst_b),
	.ADDRB({3'b000, addr_b}),
	.DIB(di_b[31:16]),
	.ENB(ce_b),
	.WEB(we_b),
	.DOB()
);

`else

`ifdef OR1200_XILINX_RAMB16

//
// Instantiation of FPGA memory:
//
// Virtex4/Spartan3E
//
// Added By Nir Mor
//

RAMB16_S36_S36 ramb16_s36_s36(
	.CLKA(clk_a),
	.SSRA(rst_a),
	.ADDRA({4'b0000, addr_a}),
	.DIA(32'h00000000),
	.DIPA(4'h0),
	.ENA(ce_a),
	.WEA(1'b0),
	.DOA(do_a),
	.DOPA(),

	.CLKB(clk_b),
	.SSRB(rst_b),
	.ADDRB({4'b0000, addr_b}),
	.DIB(di_b),
	.DIPB(4'h0),
	.ENB(ce_b),
	.WEB(we_b),
	.DOB(),
	.DOPB()
);

`else

`ifdef OR1200_ALTERA_LPM_XXX

//
// Instantiation of FPGA memory:
//
// Altera LPM
//
// Added By Jamil Khatib
//
altqpram altqpram_component (
        .wraddress_a (addr_a),
        .inclocken_a (ce_a),
        .wraddress_b (addr_b),
        .wren_a (we_a),
        .inclocken_b (ce_b),
        .wren_b (we_b),
        .inaclr_a (rst_a),
        .inaclr_b (rst_b),
        .inclock_a (clk_a),
        .inclock_b (clk_b),
        .data_a (di_a),
        .data_b (di_b),
        .q_a (do_a),
        .q_b (do_b)
);
defparam altqpram_component.operation_mode = "BIDIR_DUAL_PORT",
        altqpram_component.width_write_a = dw,
        altqpram_component.widthad_write_a = aw,
        altqpram_component.numwords_write_a = dw,
        altqpram_component.width_read_a = dw,
        altqpram_component.widthad_read_a = aw,
        altqpram_component.numwords_read_a = dw,
        altqpram_component.width_write_b = dw,
        altqpram_component.widthad_write_b = aw,
        altqpram_component.numwords_write_b = dw,
        altqpram_component.width_read_b = dw,
        altqpram_component.widthad_read_b = aw,
        altqpram_component.numwords_read_b = dw,
        altqpram_component.indata_reg_a = "INCLOCK_A",
        altqpram_component.wrcontrol_wraddress_reg_a = "INCLOCK_A",
        altqpram_component.outdata_reg_a = "INCLOCK_A",
        altqpram_component.indata_reg_b = "INCLOCK_B",
        altqpram_component.wrcontrol_wraddress_reg_b = "INCLOCK_B",
        altqpram_component.outdata_reg_b = "INCLOCK_B",
        altqpram_component.indata_aclr_a = "INACLR_A",
        altqpram_component.wraddress_aclr_a = "INACLR_A",
        altqpram_component.wrcontrol_aclr_a = "INACLR_A",
        altqpram_component.outdata_aclr_a = "INACLR_A",
        altqpram_component.indata_aclr_b = "NONE",
        altqpram_component.wraddress_aclr_b = "NONE",
        altqpram_component.wrcontrol_aclr_b = "NONE",
        altqpram_component.outdata_aclr_b = "INACLR_B",
        altqpram_component.lpm_hint = "USE_ESB=ON";
altqpram_component.wrcontrol_aclr_b = "NONE",
        altqpram_component.outdata_aclr_b = "INACLR_B",
        altqpram_component.lpm_hint = "USE_ESB=ON";
        //examplar attribute altqpram_component NOOPT TRUE
`else

//
// Generic double-port synchronous RAM model
//

//
// Generic RAM's registers and wires
//
reg	[dw-1:0]	mem [(1<<aw)-1:0];	// RAM content
reg	[aw-1:0]	addr_a_reg;		// RAM address registered

//
// Data output drivers
//
assign do_a = (oe_a) ? mem[addr_a_reg] : {dw{1'b0}};

//
// RAM read
//
always @(posedge clk_a or posedge rst_a)
	if (rst_a)
		addr_a_reg <= #1 {aw{1'b0}};
	else if (ce_a)
		addr_a_reg <= #1 addr_a;

//
// RAM write
//
always @(posedge clk_b)
	if (ce_b && we_b)
		mem[addr_b] <= #1 di_b;

`endif	// !OR1200_ALTERA_LPM
`endif	// !OR1200_XILINX_RAMB16
`endif	// !OR1200_XILINX_RAMB4
`endif	// !OR1200_XILINX_RAM32X1D
`endif	// !OR1200_VIRTUALSILICON_SSP_T1
`endif	// !OR1200_VIRTUALSILICON_SSP_T2
`endif	// !OR1200_VIRAGE_STP
`endif	// !OR1200_AVANT_ATP
`endif	// !OR1200_ARTISAN_SDP

endmodule
