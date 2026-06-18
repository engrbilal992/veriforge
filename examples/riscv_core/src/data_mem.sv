// Data Memory

module data_mem (input logic clk, we, re, input logic [31:0] addr, wd, output logic [31:0] rd);

logic [31:0] mem [0:255];

// read
assign rd = re ? mem[addr[31:2]] : '0;

// write
always_ff @ (posedge clk) begin
	if (we)
		mem[addr[31:2]] <= wd;
end

endmodule
