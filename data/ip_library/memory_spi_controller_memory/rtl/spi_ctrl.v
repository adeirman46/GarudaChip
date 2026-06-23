module spi_ctrl 
( 
    // General
    clk_i, 
    rst_i, 
    // Memory interface    
    mem_address_o, 
    mem_data_o, 
    mem_data_i, 
    mem_rd_o, 
    mem_wr_o, 
    // SPI Access    
    spi_start_o, 
    spi_done_i, 
    spi_busy_i, 
    spi_data_i, 
    spi_data_o, 
    // Control    
    xfer_count_i, 
    xfer_address_i, 
    xfer_start_i, 
    xfer_rx_only_i, 
    xfer_done_o, 
    xfer_busy_o 
);

//-----------------------------------------------------------------
// Params
//-----------------------------------------------------------------
parameter  [31:0]               MEM_ADDR_WIDTH = 18;
parameter  [31:0]               XFER_COUNT_WIDTH = 32;
parameter  [31:0]               TRANSFER_WIDTH = 8;
//-----------------------------------------------------------------
// I/O
//----------------------------------------------------------------- 
input                           clk_i /*verilator public*/;
input                           rst_i /*verilator public*/;
output [(MEM_ADDR_WIDTH - 1):0] mem_address_o /*verilator public*/;
output [(TRANSFER_WIDTH - 1):0] mem_data_o /*verilator public*/;
input [(TRANSFER_WIDTH - 1):0]  mem_data_i /*verilator public*/;
output                          mem_rd_o /*verilator public*/;
output                          mem_wr_o /*verilator public*/;
output                          spi_start_o /*verilator public*/;
input                           spi_done_i /*verilator public*/;
input                           spi_busy_i /*verilator public*/;
input [(TRANSFER_WIDTH - 1):0]  spi_data_i /*verilator public*/;
output [(TRANSFER_WIDTH - 1):0] spi_data_o /*verilator public*/;
input [(XFER_COUNT_WIDTH - 1):0]xfer_count_i /*verilator public*/;
input [(MEM_ADDR_WIDTH - 1):0]  xfer_address_i /*verilator public*/;
input                           xfer_start_i /*verilator public*/;
input                           xfer_rx_only_i /*verilator public*/;
output                          xfer_done_o /*verilator public*/;
output                          xfer_busy_o /*verilator public*/;
//-----------------------------------------------------------------
// Registers
//-----------------------------------------------------------------
parameter                        STATE_IDLE = 3'd0;
parameter                        STATE_READ = 3'd1;
parameter                        STATE_READWAIT = 3'd2;
parameter                        STATE_XFER = 3'd3;
parameter                        STATE_WRITE = 3'd4;
    
reg [2:0]                       reg_state;
reg [(XFER_COUNT_WIDTH - 1):0]  reg_count;
reg [(XFER_COUNT_WIDTH - 1):0]  reg_current;
reg [(MEM_ADDR_WIDTH - 1):0]    reg_address;
reg                             reg_rx_only;
reg [(MEM_ADDR_WIDTH - 1):0]    mem_address_o;
reg [(TRANSFER_WIDTH - 1):0]    mem_data_o;
reg                             mem_rd_o;
reg                             mem_wr_o;
reg                             spi_start_o;
reg [(TRANSFER_WIDTH - 1):0]    spi_data_o;
reg                             xfer_done_o;
reg                             xfer_busy_o;
//-----------------------------------------------------------------
// Implementation
//-----------------------------------------------------------------   
always @ (posedge clk_i or posedge rst_i)
begin 
    if (rst_i == 1'b1) 
    begin 
        mem_rd_o        <= 1'b0;
        mem_wr_o        <= 1'b0;
        mem_address_o   <= {(MEM_ADDR_WIDTH - 0){1'b0}};
        mem_data_o      <= {(TRANSFER_WIDTH - 0){1'b0}};
        xfer_done_o     <= 1'b0;
        xfer_busy_o     <= 1'b0;
        spi_start_o     <= 1'b0;
        spi_data_o      <= {(TRANSFER_WIDTH - 0){1'b0}};
        reg_count       <= {(XFER_COUNT_WIDTH - 0){1'b0}};
        reg_current     <= {(XFER_COUNT_WIDTH - 0){1'b0}};
        reg_address     <= {(MEM_ADDR_WIDTH - 0){1'b0}};
        reg_rx_only     <= 1'b0;
        reg_state       <= STATE_IDLE;
    end
   else 
   begin 
       xfer_done_o      <= 1'b0;
       spi_start_o      <= 1'b0;
       mem_rd_o         <= 1'b0;
       mem_wr_o         <= 1'b0;
       
       case (reg_state)
       //-------------------------------
       // STATE_IDLE
       //-------------------------------
       STATE_IDLE : 
       begin
           if ((xfer_start_i == 1'b1) & (xfer_count_i != 0))
           begin 
               xfer_busy_o  <= 1'b1;
               reg_count    <= xfer_count_i;
               reg_current  <= 32'h00000001;
               reg_address  <= xfer_address_i;
               reg_rx_only  <= xfer_rx_only_i;
               reg_state    <= STATE_READ;
reg_current  <= 32'h00000001;
               reg_address  <= xfer_address_i;
               reg_rx_only  <= xfer_rx_only_i;
               reg_state    <= STATE_READ;
           end
           else 
                xfer_busy_o <= 1'b0;
       end
       //-------------------------------
       // STATE_READ
       //-------------------------------
       STATE_READ : 
       begin 
           mem_address_o <= reg_address;
           mem_rd_o      <= 1'b1;
           reg_state     <= STATE_READWAIT;
       end
       //-------------------------------
       // STATE_READWAIT
       //-------------------------------
       STATE_READWAIT : 
            reg_state <= STATE_XFER;
       //-------------------------------
       // STATE_XFER
       //-------------------------------
       STATE_XFER : 
       begin 
           if (reg_rx_only == 1'b0)
                spi_data_o <= mem_data_i;
           else 
                spi_data_o <= {((TRANSFER_WIDTH - 1)-0+1- 0){1'b1}};
spi_start_o <= 1'b1;
           reg_state <= STATE_WRITE;
       end
       //-------------------------------
       // STATE_WRITE
       //-------------------------------
       STATE_WRITE : 
       begin
           if (spi_done_i == 1'b1) 
           begin 
               mem_address_o <= reg_address;
               mem_data_o <= spi_data_i;
               mem_wr_o <= 1'b1;
               if (reg_current == reg_count)
                   begin 
                       xfer_done_o <= 1'b1;
                       reg_state <= STATE_IDLE;
                   end
               else 
                   begin 
                       reg_address <= (reg_address + 1'b1);
                       reg_current <= (reg_current + 1'b1);
                       reg_state <= STATE_READ;
                   end

               
           end
       end
       
       default : 
            ;
       endcase
   end
end

endmodule
