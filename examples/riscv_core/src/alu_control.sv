// ALU Control

module alu_control (input logic [1:0] alu_op, input logic [2:0] func3, input logic [6:0] func7, input logic is_rtype, output logic [3:0] alu_ctrl);

always_comb begin
	case (alu_op)
		2'b00: alu_ctrl = 4'b0000; // ADD
		2'b01: alu_ctrl = 4'b0001; // SUB
		2'b10: 
			case (func3)
				3'b000: alu_ctrl = (is_rtype & func7[5]) ? 4'b0001 : 4'b0000; // SUB : ADD
				3'b101: alu_ctrl = func7[5] ? 4'b0111 : 4'b0110; // SRA : SRL
				3'b111: alu_ctrl = 4'b0010; // AND
				3'b110: alu_ctrl = 4'b0011; // OR
				3'b100: alu_ctrl = 4'b0100; // XOR
				3'b001: alu_ctrl = 4'b0101; // SLL
				3'b010: alu_ctrl = 4'b1000; // SLT
				3'b011: alu_ctrl = 4'b1001; // SLTU
				default: alu_ctrl = '0;
			endcase
		default: alu_ctrl = '0;
	endcase
end

endmodule
