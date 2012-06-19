/*
Distributed under the MIT license.
Copyright (c) 2011 Dave McCoy (dave.mccoy@cospandesign.com)

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in 
the Software without restriction, including without limitation the rights to 
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies 
of the Software, and to permit persons to whom the Software is furnished to do 
so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all 
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR 
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, 
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE 
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER 
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, 
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE 
SOFTWARE.
*/


`timescale 1 ns/100 ps
`include "sdram_include.v"


module sdram_read (
  rst,
  clk,

  command,
  address,
  bank,
  data_in,

  enable,
  idle,
  auto_refresh,

  app_address,

  fifo_data,
  fifo_write,
  fifo_full
);

input               rst;
input               clk;

//RAM control
output  reg [2:0]   command;
output  reg [11:0]  address;
output  reg [1:0]   bank;
input       [15:0]  data_in;


input               enable;
output              idle;
input               auto_refresh;

input       [21:0]  app_address;

//FIFO
output  reg [31:0]  fifo_data;
output  reg         fifo_write;
input               fifo_full;

parameter           IDLE            = 4'h0;
parameter           READ_FINISHED   = 4'h1; 
parameter           ACTIVATE        = 4'h2;
parameter           READ_COMMAND    = 4'h3;
parameter           READ_TOP        = 4'h4;
parameter           READ_BOTTOM     = 4'h5;
parameter           BURST_TERMINATE = 4'h6;
parameter           PRECHARGE       = 4'h7;
parameter           FIFO_FULL_WAIT  = 4'h8;

reg         [3:0]   state = IDLE;
reg         [15:0]  delay;

reg         [21:0]  read_address;
reg                 read_top;
reg                 read_bottom;

wire        [11:0]  row;
wire        [7:0]   column;

//assign      bank    = read_address[21:20];
assign      row     = read_address[19:8];
assign      column  = {read_address[7:0]};

//assign idle
assign      idle    = ((delay == 0) && ((state == IDLE) || (state == READ_FINISHED)));

reg         [31:0]  ram_data;

always @ (posedge clk) begin
  if (rst) begin
    command <=  `SDRAM_CMD_NOP;
    delay   <=  0;
    state   <=  IDLE;
    address <=  12'h000;
    bank    <=  2'b0;
    read_top    <=  0;
    read_bottom <=  0;

    //TEST: Putting the read in this state machine
    fifo_write <=  0;
    fifo_data   <=  32'h0000;
    ram_data    <=  32'h0000;

  end
  else begin
    fifo_write          <=  0;

    if (read_top) begin
      fifo_data[31:16]  <=  data_in;
      //fifo_data[31:16]  <=  16'h3C4D;
    end
    else if (read_bottom) begin
      fifo_data[15:0]   <=  data_in;
      //fifo_data[15:0] <=  16'h1A2B;
      //send a write pulse to the FIFO
      fifo_write           <=  1;
    end

    //reading the top and bottom should always be a pulse to the other state machine
    //so always reset them
    read_top    <=  0;
    read_bottom <=  0;


    if (delay > 0) begin
      command <=  `SDRAM_CMD_NOP;
      delay   <=  delay - 1;
    end
    else begin
      case (state)
        IDLE: begin
          read_address  <=  app_address;
          if (enable && ~fifo_full && ~auto_refresh) begin
            $display ("SDRAM_READ: IDLE: Read request");
            state       <=  ACTIVATE;
          end
        end
        READ_FINISHED: begin
          $display ("SDRAM_READ: Wait for refresh to finish");
          if (~enable) begin
            state       <=  IDLE;
          end
          else if (~auto_refresh) begin
            state       <=  ACTIVATE;
          end
        end
        ACTIVATE: begin
          if (fifo_full) begin
            state <= FIFO_FULL_WAIT;
          end
          else begin
            $display ("SDRAM_READ: Activate row");
            command       <=  `SDRAM_CMD_ACT;
            state         <=  READ_COMMAND;
            address       <=  row;
            bank          <=  read_address[21:20];
            delay         <=  `T_RCD;
          end
        end
        READ_COMMAND: begin
          $display ("SDRAM_READ: Start reading");
          command       <=  `SDRAM_CMD_READ;
          state         <=  READ_TOP;
          address       <=  {4'b0000, column[7:0]};
          delay         <=  `T_CAS - 1;
        end
        READ_TOP: begin
          $display ("SDRAM_READ: Reading top word");
          read_top      <=  1;
          state         <=  READ_BOTTOM;
        end
        READ_BOTTOM: begin
          $display ("SDRAM_READ: Reading bottom word");
          read_address  <=  read_address + 2;
          read_bottom   <=  1;
          if (fifo_full || ~enable) begin
            state       <=  BURST_TERMINATE;
          end
          else begin
            state       <=  READ_TOP;
          end
        end
        BURST_TERMINATE: begin
          command       <=  `SDRAM_CMD_TERM;
          delay         <=  `T_WR;
          state         <=  PRECHARGE;
        end
        PRECHARGE: begin
          command       <=  `SDRAM_CMD_PRE;
          delay         <=  `T_RP;
          if (enable) begin
            state       <=  FIFO_FULL_WAIT;
          end
          else begin
            state       <=  IDLE;
          end
        end
        FIFO_FULL_WAIT: begin
          if (auto_refresh) begin
            $display ("REFRESH happend during a FIFO_FULL_WAIT");
            state       <=  IDLE;
          end
          else if (~enable) begin
            state       <=  IDLE;
          end
          else if (~fifo_full) begin
            $display ("FIFO not full anymore");
            state       <=  ACTIVATE;
          end
        end
        default: begin
          $display ("SDRAM_READ: Entered Illegal state");
          state         <=  IDLE;
        end
      endcase
    end
  end
end

endmodule
