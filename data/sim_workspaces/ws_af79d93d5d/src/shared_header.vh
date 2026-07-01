`ifndef SHARED_HEADER_VH
`define SHARED_HEADER_VH

//============================================================================
// shared_header.vh — single-include aggregator for the CGRA 2x2 design.
//
// Every RTL/testbench file includes ONLY this header; it pulls in the canonical
// macro package (cgra_pkg.vh) exactly once via its CGRA_PKG_VH guard. Do NOT
// duplicate any `define here or `include this file from itself — the canonical
// values live in cgra_pkg.vh only.
//============================================================================
`include "cgra_pkg.vh"

`endif // SHARED_HEADER_VH
