// ALU Design

module alu (input logic [31:0] a,b, input logic [3:0] alu_ctrl, output logic [31:0] result, output logic zero);

assign zero = (result == '0);

always_comb
	case (alu_ctrl)
		4'b0000: result = a + b;
		4'b0001: result = a - b;
		4'b0010: result = a & b;
		4'b0011: result = a | b;
		4'b0100: result = a ^ b;
		4'b0101: result = a << b[4:0];
		4'b0110: result = a >> b[4:0];
		4'b0111: result = $signed(a) >>> b[4:0];
		4'b1000: result = $signed(a) < $signed(b);
		4'b1001: result = a < b;
		default: result = '0;
	endcase

endmodule
