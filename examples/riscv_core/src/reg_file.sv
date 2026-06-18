// Register File

module reg_file (input logic clk, we, input logic [4:0] rs1, rs2, input logic [4:0] rd, input logic [31:0] wd, output logic [31:0] rd1, rd2);

logic [31:0] regs [0:31];

// Initialize all registers to zero
integer i;
initial begin
    for (i = 0; i < 32; i = i + 1)
        regs[i] = 32'h0;
end

// Read
always_comb begin
    rd1 = (rs1 == 5'b0) ? '0 : regs[rs1];
    rd2 = (rs2 == 5'b0) ? '0 : regs[rs2];
end

// Write
always_ff @(posedge clk) begin
    if (we && rd != 5'b0)
        regs[rd] <= wd;
end

endmodule
