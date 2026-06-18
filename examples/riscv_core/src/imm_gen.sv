// Immediate Genaration Module

module imm_gen (input logic [31:0] instr, input logic [2:0] imm_sel, output logic [31:0] imm);

// Case for Imm_Sel
always_comb
	case (imm_sel)
		3'b000: imm = { {20{instr[31]}}, instr[31:20] }; // I-type
		3'b001: imm = { {20{instr[31]}}, instr[31:25], instr[11:7] }; // S-Type
		3'b010: imm = { {19{instr[31]}}, instr[31], instr[7], instr[30:25], instr[11:8], 1'b0 }; // B-type
		3'b011: imm = { instr[31:12], 12'b0 }; // U-Type
		3'b100: imm = { {11{instr[31]}}, instr[31], instr[19:12], instr[20], instr[30:21], 1'b0 }; // J-Type
		default: imm = '0;
	endcase

endmodule
