module RAM32M (
  output [1:0] DOA,
  output [1:0] DOB,
  output [1:0] DOC,
  output [1:0] DOD,
  input  [4:0] ADDRA, ADDRB, ADDRC,
  input  [4:0] ADDRD,
  input  [1:0] DIA,
  input  [1:0] DIB,
  input  [1:0] DIC,
  input  [1:0] DID,
  (* clkbuf_sink *)
  (* invertible_pin = "IS_WCLK_INVERTED" *)
  input        WCLK,
  input        WE
);
  parameter [63:0] INIT_A = 64'h0000000000000000;
  parameter [63:0] INIT_B = 64'h0000000000000000;
  parameter [63:0] INIT_C = 64'h0000000000000000;
  parameter [63:0] INIT_D = 64'h0000000000000000;
  parameter [0:0] IS_WCLK_INVERTED = 1'b0;
  reg [63:0] mem_a = INIT_A;
  reg [63:0] mem_b = INIT_B;
  reg [63:0] mem_c = INIT_C;
  reg [63:0] mem_d = INIT_D;
  assign DOA = mem_a[2*ADDRA+:2];
  assign DOB = mem_b[2*ADDRB+:2];
  assign DOC = mem_c[2*ADDRC+:2];
  assign DOD = mem_d[2*ADDRD+:2];
  wire clk = WCLK ^ IS_WCLK_INVERTED;
  always @(posedge clk)
    if (WE) begin
      mem_a[2*ADDRD+:2] <= DIA;
      mem_b[2*ADDRD+:2] <= DIB;
      mem_c[2*ADDRD+:2] <= DIC;
      mem_d[2*ADDRD+:2] <= DID;
    end
  specify
    // Max delay from: https://github.com/SymbiFlow/prjxray-db/blob/31f51ac5ec7448dd6f79a8267f147123e4413c21/artix7/timings/CLBLM_R.sdf#L986
    $setup(ADDRD[0], posedge WCLK &&& !IS_WCLK_INVERTED && WE, 245);
    $setup(ADDRD[0], negedge WCLK &&&  IS_WCLK_INVERTED && WE, 245);
$setup(ADDRD[0], posedge WCLK &&& !IS_WCLK_INVERTED && WE, 245);
    $setup(ADDRD[0], negedge WCLK &&&  IS_WCLK_INVERTED && WE, 245);
    $setup(ADDRD[1], posedge WCLK &&& !IS_WCLK_INVERTED && WE, 208);
    $setup(ADDRD[1], negedge WCLK &&&  IS_WCLK_INVERTED && WE, 208);
    $setup(ADDRD[2], posedge WCLK &&& !IS_WCLK_INVERTED && WE, 147);
    $setup(ADDRD[2], negedge WCLK &&&  IS_WCLK_INVERTED && WE, 147);
    $setup(ADDRD[3], posedge WCLK &&& !IS_WCLK_INVERTED && WE, 68);
    $setup(ADDRD[3], negedge WCLK &&&  IS_WCLK_INVERTED && WE, 68);
    $setup(ADDRD[4], posedge WCLK &&& !IS_WCLK_INVERTED && WE, 66);
    $setup(ADDRD[4], negedge WCLK &&&  IS_WCLK_INVERTED && WE, 66);
    // Max delay from: https://github.com/SymbiFlow/prjxray-db/blob/31f51ac5ec7448dd6f79a8267f147123e4413c21/artix7/timings/CLBLM_R.sdf#L986-L988
    $setup(DIA[0], posedge WCLK &&& !IS_WCLK_INVERTED && WE, 453);
    $setup(DIA[0], negedge WCLK &&&  IS_WCLK_INVERTED && WE, 453);
    $setup(DIA[1], posedge WCLK &&& !IS_WCLK_INVERTED && WE, 384);
    $setup(DIA[1], negedge WCLK &&&  IS_WCLK_INVERTED && WE, 384);
    // Max delay from: https://github.com/SymbiFlow/prjxray-db/blob/31f51ac5ec7448dd6f79a8267f147123e4413c21/artix7/timings/CLBLM_R.sdf#L1054-L1056
    $setup(DIB[0], posedge WCLK &&& !IS_WCLK_INVERTED && WE, 461);
    $setup(DIB[0], negedge WCLK &&&  IS_WCLK_INVERTED && WE, 461);
    $setup(DIB[1], posedge WCLK &&& !IS_WCLK_INVERTED && WE, 354);
$setup(DIB[0], negedge WCLK &&&  IS_WCLK_INVERTED && WE, 461);
    $setup(DIB[1], posedge WCLK &&& !IS_WCLK_INVERTED && WE, 354);
    $setup(DIB[1], negedge WCLK &&&  IS_WCLK_INVERTED && WE, 354);
    // Max delay from: https://github.com/SymbiFlow/prjxray-db/blob/31f51ac5ec7448dd6f79a8267f147123e4413c21/artix7/timings/CLBLM_R.sdf#L1122-L1124
    $setup(DIC[0], posedge WCLK &&& !IS_WCLK_INVERTED && WE, 457);
    $setup(DIC[0], negedge WCLK &&&  IS_WCLK_INVERTED && WE, 457);
    $setup(DIC[1], posedge WCLK &&& !IS_WCLK_INVERTED && WE, 375);
    $setup(DIC[1], negedge WCLK &&&  IS_WCLK_INVERTED && WE, 375);
    // Max delay from: https://github.com/SymbiFlow/prjxray-db/blob/31f51ac5ec7448dd6f79a8267f147123e4413c21/artix7/timings/CLBLM_R.sdf#L1190-L1192
    $setup(DID[0], posedge WCLK &&& !IS_WCLK_INVERTED && WE, 310);
    $setup(DID[0], negedge WCLK &&&  IS_WCLK_INVERTED && WE, 310);
    $setup(DID[1], posedge WCLK &&& !IS_WCLK_INVERTED && WE, 334);
    $setup(DID[1], negedge WCLK &&&  IS_WCLK_INVERTED && WE, 334);
    // Max delay from: https://github.com/SymbiFlow/prjxray-db/blob/31f51ac5ec7448dd6f79a8267f147123e4413c21/artix7/timings/CLBLM_R.sdf#L834
    $setup(WE, posedge WCLK &&& !IS_WCLK_INVERTED, 654);
    $setup(WE, negedge WCLK &&&  IS_WCLK_INVERTED, 654);
    // Max delay from: https://github.com/SymbiFlow/prjxray-db/blob/34ea6eb08a63d21ec16264ad37a0a7b142ff6031/artix7/timings/CLBLM_R.sdf#L889
$setup(WE, negedge WCLK &&&  IS_WCLK_INVERTED, 654);
    // Max delay from: https://github.com/SymbiFlow/prjxray-db/blob/34ea6eb08a63d21ec16264ad37a0a7b142ff6031/artix7/timings/CLBLM_R.sdf#L889
    if (!IS_WCLK_INVERTED && WE) (posedge WCLK => (DOA[0] : DIA[0])) = 1153;
    if ( IS_WCLK_INVERTED && WE) (negedge WCLK => (DOA[0] : DIA[0])) = 1153;
    // Max delay from: https://github.com/SymbiFlow/prjxray-db/blob/34ea6eb08a63d21ec16264ad37a0a7b142ff6031/artix7/timings/CLBLM_R.sdf#L857
    if (!IS_WCLK_INVERTED && WE) (posedge WCLK => (DOA[1] : DIA[1])) = 1188;
    if ( IS_WCLK_INVERTED && WE) (negedge WCLK => (DOA[1] : DIA[1])) = 1188;
    // Max delay from: https://github.com/SymbiFlow/prjxray-db/blob/34ea6eb08a63d21ec16264ad37a0a7b142ff6031/artix7/timings/CLBLM_R.sdf#L957
    if (!IS_WCLK_INVERTED && WE) (posedge WCLK => (DOB[0] : DIB[0])) = 1161;
    if ( IS_WCLK_INVERTED && WE) (negedge WCLK => (DOB[0] : DIB[0])) = 1161;
    // Max delay from: https://github.com/SymbiFlow/prjxray-db/blob/34ea6eb08a63d21ec16264ad37a0a7b142ff6031/artix7/timings/CLBLM_R.sdf#L925
    if (!IS_WCLK_INVERTED && WE) (posedge WCLK => (DOB[1] : DIB[1])) = 1187;
    if ( IS_WCLK_INVERTED && WE) (negedge WCLK => (DOB[1] : DIB[1])) = 1187;
    // Max delay from: https://github.com/SymbiFlow/prjxray-db/blob/34ea6eb08a63d21ec16264ad37a0a7b142ff6031/artix7/timings/CLBLM_R.sdf#L993
    if (!IS_WCLK_INVERTED && WE) (posedge WCLK => (DOC[0] : DIC[0])) = 1158;
if (!IS_WCLK_INVERTED && WE) (posedge WCLK => (DOC[0] : DIC[0])) = 1158;
    if ( IS_WCLK_INVERTED && WE) (negedge WCLK => (DOC[0] : DIC[0])) = 1158;
    // Max delay from: https://github.com/SymbiFlow/prjxray-db/blob/34ea6eb08a63d21ec16264ad37a0a7b142ff6031/artix7/timings/CLBLM_R.sdf#L1025
    if (!IS_WCLK_INVERTED && WE) (posedge WCLK => (DOC[1] : DIC[1])) = 1180;
    if ( IS_WCLK_INVERTED && WE) (negedge WCLK => (DOC[1] : DIC[1])) = 1180;
    // Max delay from: https://github.com/SymbiFlow/prjxray-db/blob/34ea6eb08a63d21ec16264ad37a0a7b142ff6031/artix7/timings/CLBLM_R.sdf#L1093
    if (!IS_WCLK_INVERTED && WE) (posedge WCLK => (DOD[0] : DID[0])) = 1163;
    if ( IS_WCLK_INVERTED && WE) (negedge WCLK => (DOD[0] : DID[0])) = 1163;
    // Max delay from: https://github.com/SymbiFlow/prjxray-db/blob/34ea6eb08a63d21ec16264ad37a0a7b142ff6031/artix7/timings/CLBLM_R.sdf#L1061
    if (!IS_WCLK_INVERTED && WE) (posedge WCLK => (DOD[1] : DID[1])) = 1190;
    if ( IS_WCLK_INVERTED && WE) (negedge WCLK => (DOD[1] : DID[1])) = 1190;
    (ADDRA[0] *> DOA) = 642; (ADDRB[0] *> DOB) = 642; (ADDRC[0] *> DOC) = 642; (ADDRD[0] *> DOD) = 642;
    (ADDRA[1] *> DOA) = 631; (ADDRB[1] *> DOB) = 631; (ADDRC[1] *> DOC) = 631; (ADDRD[1] *> DOD) = 631;
    (ADDRA[2] *> DOA) = 472; (ADDRB[2] *> DOB) = 472; (ADDRC[2] *> DOC) = 472; (ADDRD[2] *> DOD) = 472;
    (ADDRA[3] *> DOA) = 407; (ADDRB[3] *> DOB) = 407; (ADDRC[3] *> DOC) = 407; (ADDRD[3] *> DOD) = 407;
(ADDRA[3] *> DOA) = 407; (ADDRB[3] *> DOB) = 407; (ADDRC[3] *> DOC) = 407; (ADDRD[3] *> DOD) = 407;
    (ADDRA[4] *> DOA) = 238; (ADDRB[4] *> DOB) = 238; (ADDRC[4] *> DOC) = 238; (ADDRD[4] *> DOD) = 238;
  endspecify
endmodule
