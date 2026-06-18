// Program Counter Module

module pc (input logic clk, rst, input logic [31 :0] pc_next, output logic [31:0] pc_out);
	
	always_ff @ (posedge clk or posedge rst) begin
		if (rst)
			pc_out <= '0;
		else
			pc_out <= pc_next;
	end

endmodule
