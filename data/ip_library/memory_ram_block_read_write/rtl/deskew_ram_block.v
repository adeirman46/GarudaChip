module deskew_ram_block (
    clk,
    reset, 
    addrwr,
    addrrd1,
    addrrd2,
    datain,
    we,
    re,
    dataout1,
    dataout2
    );

input       clk;
input       reset;
input   [15:0]  addrwr;
input   [15:0]  addrrd1;
input   [15:0]  addrrd2;
input   [13:0]  datain;
input       we, re;
output  [13:0]  dataout1;
output  [13:0]  dataout2;

parameter read_access_time = 0;
parameter write_access_time = 0;
parameter ram_width = 14;

reg [ram_width-1:0] dataout1_i, dataout2_i;
reg [ram_width-1:0] ram_array_d_0, ram_array_d_1, ram_array_d_2, ram_array_d_3,
            ram_array_d_4, ram_array_d_5, ram_array_d_6, ram_array_d_7,
            ram_array_d_8, ram_array_d_9, ram_array_d_10, ram_array_d_11,
            ram_array_d_12, ram_array_d_13, ram_array_d_14, ram_array_d_15,
            ram_array_q_0, ram_array_q_1, ram_array_q_2, ram_array_q_3,
            ram_array_q_4, ram_array_q_5, ram_array_q_6, ram_array_q_7,
            ram_array_q_8, ram_array_q_9, ram_array_q_10, ram_array_q_11,
            ram_array_q_12, ram_array_q_13, ram_array_q_14, ram_array_q_15;
wire [ram_width-1:0] data_reg_0, data_reg_1, data_reg_2, data_reg_3,
             data_reg_4, data_reg_5, data_reg_6, data_reg_7,
             data_reg_8, data_reg_9, data_reg_10, data_reg_11,
             data_reg_12, data_reg_13, data_reg_14, data_reg_15;
/* Modelling the read port */
 /* Assuming address trigerred operation only */
//assignment
assign
    data_reg_0 = ( addrwr[0] == 1'b1 ) ? datain : ram_array_q_0,
    data_reg_1 = ( addrwr[1] == 1'b1 ) ? datain : ram_array_q_1,
    data_reg_2 = ( addrwr[2] == 1'b1 ) ? datain : ram_array_q_2,
    data_reg_3 = ( addrwr[3] == 1'b1 ) ? datain : ram_array_q_3,
    data_reg_4 = ( addrwr[4] == 1'b1 ) ? datain : ram_array_q_4,
    data_reg_5 = ( addrwr[5] == 1'b1 ) ? datain : ram_array_q_5,
    data_reg_6 = ( addrwr[6] == 1'b1 ) ? datain : ram_array_q_6,
    data_reg_7 = ( addrwr[7] == 1'b1 ) ? datain : ram_array_q_7,
    data_reg_8 = ( addrwr[8] == 1'b1 ) ? datain : ram_array_q_8,
    data_reg_9 = ( addrwr[9] == 1'b1 ) ? datain : ram_array_q_9,
    data_reg_10 = ( addrwr[10] == 1'b1 ) ? datain : ram_array_q_10,
    data_reg_11 = ( addrwr[11] == 1'b1 ) ? datain : ram_array_q_11,
    data_reg_12 = ( addrwr[12] == 1'b1 ) ? datain : ram_array_q_12,
    data_reg_13 = ( addrwr[13] == 1'b1 ) ? datain : ram_array_q_13,
    data_reg_14 = ( addrwr[14] == 1'b1 ) ? datain : ram_array_q_14,
    data_reg_15 = ( addrwr[15] == 1'b1 ) ? datain : ram_array_q_15;


assign #read_access_time dataout1 = re ? 13'b0000000000000 : dataout1_i;
assign #read_access_time dataout2 = re ? 13'b0000000000000 : dataout2_i;
always @(
    ram_array_q_0   or 
    ram_array_q_1   or 
    ram_array_q_2   or 
    ram_array_q_3   or 
    ram_array_q_4       or
    ram_array_q_5       or
    ram_array_q_6       or
    ram_array_q_7       or 
    ram_array_q_8       or
    ram_array_q_9       or
    ram_array_q_10      or
    ram_array_q_11      or 
    ram_array_q_12      or
    ram_array_q_13      or
    ram_array_q_14      or
    ram_array_q_15      or 
    addrrd1     or
    addrrd2     )
begin
    case ( addrrd1 )  // synopsys parallel_case full_case
    16'b0000000000000001 : dataout1_i = ram_array_q_0;
    16'b0000000000000010 : dataout1_i = ram_array_q_1;
    16'b0000000000000100 : dataout1_i = ram_array_q_2;
    16'b0000000000001000 : dataout1_i = ram_array_q_3;
    16'b0000000000010000 : dataout1_i = ram_array_q_4;
    16'b0000000000100000 : dataout1_i = ram_array_q_5;
    16'b0000000001000000 : dataout1_i = ram_array_q_6;
    16'b0000000010000000 : dataout1_i = ram_array_q_7;
    16'b0000000100000000 : dataout1_i = ram_array_q_8;
    16'b0000001000000000 : dataout1_i = ram_array_q_9;
    16'b0000010000000000 : dataout1_i = ram_array_q_10;
    16'b0000100000000000 : dataout1_i = ram_array_q_11;
    16'b0001000000000000 : dataout1_i = ram_array_q_12;
    16'b0010000000000000 : dataout1_i = ram_array_q_13;
    16'b0100000000000000 : dataout1_i = ram_array_q_14;
    16'b1000000000000000 : dataout1_i = ram_array_q_15;
    endcase
case ( addrrd2 )  // synopsys parallel_case full_case
    16'b0000000000000001 : dataout2_i = ram_array_q_0;
    16'b0000000000000010 : dataout2_i = ram_array_q_1;
    16'b0000000000000100 : dataout2_i = ram_array_q_2;
    16'b0000000000001000 : dataout2_i = ram_array_q_3;
    16'b0000000000010000 : dataout2_i = ram_array_q_4;
    16'b0000000000100000 : dataout2_i = ram_array_q_5;
    16'b0000000001000000 : dataout2_i = ram_array_q_6;
    16'b0000000010000000 : dataout2_i = ram_array_q_7;
    16'b0000000100000000 : dataout2_i = ram_array_q_8;
    16'b0000001000000000 : dataout2_i = ram_array_q_9;
    16'b0000010000000000 : dataout2_i = ram_array_q_10;
    16'b0000100000000000 : dataout2_i = ram_array_q_11;
    16'b0001000000000000 : dataout2_i = ram_array_q_12;
    16'b0010000000000000 : dataout2_i = ram_array_q_13;
    16'b0100000000000000 : dataout2_i = ram_array_q_14;
    16'b1000000000000000 : dataout2_i = ram_array_q_15;
    endcase

end
/* Modelling the write port */
always @(posedge clk or posedge reset) 
begin
    if(reset) begin
    ram_array_q_0 <= #write_access_time 0;
    ram_array_q_1 <= #write_access_time 0;
    ram_array_q_2 <= #write_access_time 0; 
    ram_array_q_3 <= #write_access_time 0; 
        ram_array_q_4 <= #write_access_time 0;
        ram_array_q_5 <= #write_access_time 0;
        ram_array_q_6 <= #write_access_time 0;
        ram_array_q_7 <= #write_access_time 0; 
        ram_array_q_8 <= #write_access_time 0;
        ram_array_q_9 <= #write_access_time 0;
        ram_array_q_10 <= #write_access_time 0;
        ram_array_q_11 <= #write_access_time 0; 
        ram_array_q_12 <= #write_access_time 0;
        ram_array_q_13 <= #write_access_time 0;
        ram_array_q_14 <= #write_access_time 0;
        ram_array_q_15 <= #write_access_time 0; 
    end
    else begin
    ram_array_q_0 <= #write_access_time ram_array_d_0;
    ram_array_q_1 <= #write_access_time ram_array_d_1;
    ram_array_q_2 <= #write_access_time ram_array_d_2;
    ram_array_q_3 <= #write_access_time ram_array_d_3;
        ram_array_q_4 <= #write_access_time ram_array_d_4;
        ram_array_q_5 <= #write_access_time ram_array_d_5;
        ram_array_q_6 <= #write_access_time ram_array_d_6;
        ram_array_q_7 <= #write_access_time ram_array_d_7;
        ram_array_q_8 <= #write_access_time ram_array_d_8;
        ram_array_q_9 <= #write_access_time ram_array_d_9;
ram_array_q_7 <= #write_access_time ram_array_d_7;
        ram_array_q_8 <= #write_access_time ram_array_d_8;
        ram_array_q_9 <= #write_access_time ram_array_d_9;
        ram_array_q_10 <= #write_access_time ram_array_d_10;
        ram_array_q_11 <= #write_access_time ram_array_d_11;
        ram_array_q_12 <= #write_access_time ram_array_d_12;
        ram_array_q_13 <= #write_access_time ram_array_d_13;
        ram_array_q_14 <= #write_access_time ram_array_d_14;
        ram_array_q_15 <= #write_access_time ram_array_d_15;
    end
end
always @( 
    we          or 
    data_reg_0      or 
    data_reg_1      or 
    data_reg_2      or 
    data_reg_3      or
    data_reg_4          or
    data_reg_5          or
    data_reg_6          or
    data_reg_7          or
    data_reg_8          or
    data_reg_9          or
    data_reg_10         or
    data_reg_11         or
    data_reg_12         or
    data_reg_13         or
    data_reg_14         or
    data_reg_15         or
    ram_array_q_0   or 
    ram_array_q_1   or
    ram_array_q_2   or
    ram_array_q_3   or
    ram_array_q_4       or
    ram_array_q_5       or
    ram_array_q_6       or
    ram_array_q_7   or
    ram_array_q_8       or
    ram_array_q_9       or
    ram_array_q_10      or
    ram_array_q_11  or
    ram_array_q_12      or
    ram_array_q_13      or
    ram_array_q_14      or
    ram_array_q_15  )
begin
    if(we) begin
    ram_array_d_0 <= #write_access_time data_reg_0;
    ram_array_d_1 <= #write_access_time data_reg_1;
    ram_array_d_2 <= #write_access_time data_reg_2;
    ram_array_d_3 <= #write_access_time data_reg_3;
        ram_array_d_4 <= #write_access_time data_reg_4;
        ram_array_d_5 <= #write_access_time data_reg_5;
        ram_array_d_6 <= #write_access_time data_reg_6;
        ram_array_d_7 <= #write_access_time data_reg_7; 
        ram_array_d_8 <= #write_access_time data_reg_8;
        ram_array_d_9 <= #write_access_time data_reg_9;
        ram_array_d_10 <= #write_access_time data_reg_10;
ram_array_d_8 <= #write_access_time data_reg_8;
        ram_array_d_9 <= #write_access_time data_reg_9;
        ram_array_d_10 <= #write_access_time data_reg_10;
        ram_array_d_11 <= #write_access_time data_reg_11; 
        ram_array_d_12 <= #write_access_time data_reg_12;
        ram_array_d_13 <= #write_access_time data_reg_13;
        ram_array_d_14 <= #write_access_time data_reg_14;
        ram_array_d_15 <= #write_access_time data_reg_15; 
    end
    else begin
    ram_array_d_0 <= #write_access_time ram_array_q_0;
    ram_array_d_1 <= #write_access_time ram_array_q_1;
    ram_array_d_2 <= #write_access_time ram_array_q_2;
    ram_array_d_3 <= #write_access_time ram_array_q_3;
        ram_array_d_4 <= #write_access_time ram_array_q_4;
        ram_array_d_5 <= #write_access_time ram_array_q_5;
        ram_array_d_6 <= #write_access_time ram_array_q_6;
        ram_array_d_7 <= #write_access_time ram_array_q_7;
        ram_array_d_8 <= #write_access_time ram_array_q_8;
        ram_array_d_9 <= #write_access_time ram_array_q_9;
        ram_array_d_10 <= #write_access_time ram_array_q_10;
        ram_array_d_11 <= #write_access_time ram_array_q_11;
        ram_array_d_12 <= #write_access_time ram_array_q_12;
        ram_array_d_13 <= #write_access_time ram_array_q_13;
        ram_array_d_14 <= #write_access_time ram_array_q_14;
        ram_array_d_15 <= #write_access_time ram_array_q_15;
end
end

endmodule
