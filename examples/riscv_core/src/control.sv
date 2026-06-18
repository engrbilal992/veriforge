// Control module

module control (input logic [6:0] opcode, 
    output logic reg_write, alu_src, mem_write, mem_read, branch, jump, pc_sel,
    output logic [1:0] alu_op, 
    output logic [2:0] imm_sel, 
    output logic [1:0] result_src);

always_comb
    case (opcode)
        7'b0110011: begin // R-type
            reg_write=1; alu_src=0; mem_read=0; mem_write=0;
            branch=0; jump=0; pc_sel=0; alu_op=2'b10; imm_sel=3'b000; result_src=2'b00;
        end
        7'b0010011: begin // I-type
            reg_write=1; alu_src=1; mem_read=0; mem_write=0;
            branch=0; jump=0; pc_sel=0; alu_op=2'b10; imm_sel=3'b000; result_src=2'b00;
        end
        7'b0000011: begin // Load
            reg_write=1; alu_src=1; mem_read=1; mem_write=0;
            branch=0; jump=0; pc_sel=0; alu_op=2'b00; imm_sel=3'b000; result_src=2'b01;
        end
        7'b0100011: begin // Store
            reg_write=0; alu_src=1; mem_read=0; mem_write=1;
            branch=0; jump=0; pc_sel=0; alu_op=2'b00; imm_sel=3'b001; result_src=2'b00;
        end
        7'b1100011: begin // Branch
            reg_write=0; alu_src=0; mem_read=0; mem_write=0;
            branch=1; jump=0; pc_sel=0; alu_op=2'b01; imm_sel=3'b010; result_src=2'b00;
        end
        7'b1101111: begin // JAL
            reg_write=1; alu_src=0; mem_read=0; mem_write=0;
            branch=0; jump=1; pc_sel=0; alu_op=2'b00; imm_sel=3'b100; result_src=2'b10;
        end
        7'b1100111: begin // JALR
            reg_write=1; alu_src=1; mem_read=0; mem_write=0;
            branch=0; jump=1; pc_sel=0; alu_op=2'b00; imm_sel=3'b000; result_src=2'b10;
        end
        7'b0110111: begin // LUI
            reg_write=1; alu_src=0; mem_read=0; mem_write=0;
            branch=0; jump=0; pc_sel=0; alu_op=2'b00; imm_sel=3'b011; result_src=2'b11;
        end
        7'b0010111: begin // AUIPC
            reg_write=1; alu_src=1; mem_read=0; mem_write=0;
            branch=0; jump=0; pc_sel=1; alu_op=2'b00; imm_sel=3'b011; result_src=2'b00;
        end
        default: begin
            reg_write=0; alu_src=0; mem_read=0; mem_write=0;
            branch=0; jump=0; pc_sel=0; alu_op=2'b00; imm_sel=3'b000; result_src=2'b00;
        end
    endcase
endmodule
