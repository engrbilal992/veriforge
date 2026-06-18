# RISC-V Single-Cycle Core (example project)

A complete RV32I single-cycle processor in SystemVerilog, used to demonstrate
VeriForge's SystemVerilog support.

## Run it

GUI:  File -> Open Project -> this folder, then Simulate (F5).
CLI:  ./veriforge sim examples/riscv_core --top tb_top

The testbench runs 34 self-checks and prints "ALL TESTS PASSED - FULL RV32I".

## Note on data files
`program.hex` and `data.hex` live in the project ROOT (not src/), because the
testbench loads them with relative `$readmemh("program.hex", ...)` and VeriForge
runs the simulation from the project root.
