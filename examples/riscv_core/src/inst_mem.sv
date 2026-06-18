// Instruction Memory

module inst_mem (input logic [31:0] addr, output logic [31:0] instr);

    logic [31:0] mem [0:255];  // WORD addressed, not byte

    always_comb
        instr = mem[addr[31:2]];

endmodule
