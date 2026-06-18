// Branch Comparator

module branch_comp (input logic [31:0] a, b, input logic [2:0] func3, output logic branch_taken);

always_comb
	case (func3)
		3'b000: branch_taken = (a == b); // BEQ
		3'b001: branch_taken = (a != b); // BNE
		3'b100: branch_taken = ($signed(a) < $signed(b)); // BLT
		3'b101: branch_taken = ($signed(a) >= $signed(b)); // BGE
		3'b110: branch_taken = (a < b); // BLTU
		3'b111:	branch_taken = (a >= b); // BGEU
		default: branch_taken = 0;
	endcase
endmodule
