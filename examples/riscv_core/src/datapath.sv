// Data Path Design
// Top Level For Single Cycle RV Core
module datapath (input logic clk, rst, output logic [31:0] pc_out);

// Internal Signals
logic [31:0] pc_curr, pc_next, pc_plus4, pc_branch, pc_jump;
logic [31:0] instr;
logic [31:0] rd1, rd2;
logic [31:0] imm;
logic [31:0] alu_a, alu_b;
logic [31:0] alu_result;
logic        alu_zero;
logic [31:0] mem_rd;
logic [31:0] result;
logic        branch_taken;
logic        is_rtype;

// Control Signals
logic        reg_write, alu_src, mem_write, mem_read, branch, jump;
logic [1:0]  alu_op, result_src;
logic [2:0]  imm_sel;
logic [3:0]  alu_ctrl;
logic 	     pc_sel;

// PC Connections
assign pc_plus4  = pc_curr + 4;
assign pc_branch = pc_curr + imm;       // B-type and JAL target
assign pc_jump   = alu_result;          // JALR target = RS1 + imm
assign pc_out    = pc_curr;

// PC next mux
// JALR: instr[3]=0, JAL: instr[3]=1
assign pc_next = (branch & branch_taken) ? pc_branch :  // B-type
                  jump & ~instr[3]       ? pc_jump   :  // JALR
                  jump                  ? pc_branch  :  // JAL
                                          pc_plus4;     // normal

// PC
pc u_pc (
    .clk     (clk),
    .rst     (rst),
    .pc_next (pc_next),
    .pc_out  (pc_curr)
);

// Instruction Memory
inst_mem u_inst_mem (
    .addr  (pc_curr),
    .instr (instr)
);

// Control
control u_control (
    .opcode     (instr[6:0]),
    .reg_write  (reg_write),
    .alu_src    (alu_src),
    .mem_write  (mem_write),
    .mem_read   (mem_read),
    .branch     (branch),
    .jump       (jump),
    .pc_sel     (pc_sel),
    .alu_op     (alu_op),
    .imm_sel    (imm_sel),
    .result_src (result_src)
);

// Register File
reg_file u_reg_file (
    .clk (clk),
    .we  (reg_write),
    .rs1 (instr[19:15]),
    .rs2 (instr[24:20]),
    .rd  (instr[11:7]),
    .wd  (result),
    .rd1 (rd1),
    .rd2 (rd2)
);

// Immediate Generator
imm_gen u_imm_gen (
    .instr   (instr),
    .imm_sel (imm_sel),
    .imm     (imm)
);

assign is_rtype = (instr[6:0] == 7'b0110011);

// ALU Control
alu_control u_alu_control (
    .alu_op   (alu_op),
    .func3    (instr[14:12]),
    .func7    (instr[31:25]),
    .is_rtype (is_rtype),
    .alu_ctrl (alu_ctrl)
);

// ALU Input Muxes
assign alu_a = (pc_sel | (jump & instr[3])) ? pc_curr : rd1;  // JAL/AUIPC use PC, others use RS1
assign alu_b = alu_src ? imm : rd2;   // I-type/S-type use imm, R-type uses RS2

// ALU
alu u_alu (
    .a        (alu_a),
    .b        (alu_b),
    .alu_ctrl (alu_ctrl),
    .result   (alu_result),
    .zero     (alu_zero)
);

// Branch Comparator
branch_comp u_branch_comp (
    .a            (rd1),
    .b            (rd2),
    .func3        (instr[14:12]),
    .branch_taken (branch_taken)
);

// Data Memory
data_mem u_data_mem (
    .clk  (clk),
    .we   (mem_write),
    .re   (mem_read),
    .addr (alu_result),
    .wd   (rd2),
    .rd   (mem_rd)
);

// Result Mux (writeback)
always_comb
    case (result_src)
        2'b00: result = alu_result;  // R-type, I-type
        2'b01: result = mem_rd;      // Load
        2'b10: result = pc_plus4;    // JAL/JALR link address
        2'b11: result = imm;         // LUI
        default: result = '0;
    endcase

endmodule
