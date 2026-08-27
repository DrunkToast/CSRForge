module csr_regs (
    input  logic        PCLK,
    input  logic        PRESETn,

    input  logic        PSEL,
    input  logic        PENABLE,
    input  logic        PWRITE,
    input  logic [31:0] PADDR,
    input  logic [31:0] PWDATA,

    output logic [31:0] PRDATA,
    output logic        PREADY,
    output logic        PSLVERR,

    output logic        ctrl_en_o,
    output logic [1:0]  ctrl_mode_o,
    input  logic        status_busy_i,
    input  logic        irq_status_done_set_i,
    output logic        mixed_enable_o,
    input  logic        mixed_busy_i,
    input  logic        mixed_done_set_i
);

    // Stage 1, slice 4: all Golden registers are implemented.
    localparam logic [31:0] CTRL_ADDR       = 32'h0000_0000;
    localparam logic [31:0] STATUS_ADDR     = 32'h0000_0004;
    localparam logic [31:0] IRQ_STATUS_ADDR = 32'h0000_0008;
    localparam logic [31:0] MIXED_ADDR      = 32'h0000_000C;

    logic apb_access;
    logic apb_write;
    logic apb_read;
    logic addr_misaligned;
    logic addr_mapped;
    logic irq_done_q;
    logic mixed_done_q;

    assign PREADY          = 1'b1;
    assign apb_access      = PSEL && PENABLE && PREADY;
    assign apb_write       = apb_access && PWRITE;
    assign apb_read        = apb_access && !PWRITE;
    assign addr_misaligned = (PADDR[1:0] != 2'b00);
    assign addr_mapped     = (PADDR == CTRL_ADDR) ||
                             (PADDR == STATUS_ADDR) ||
                             (PADDR == IRQ_STATUS_ADDR) ||
                             (PADDR == MIXED_ADDR);
    assign PSLVERR         = apb_access && (addr_misaligned || !addr_mapped);

    always_comb begin
        PRDATA = 32'b0;

        if (apb_read && !addr_misaligned && addr_mapped) begin
            case (PADDR)
                CTRL_ADDR:   PRDATA = {29'b0, ctrl_mode_o, ctrl_en_o};
                STATUS_ADDR: PRDATA = {31'b0, status_busy_i};
                IRQ_STATUS_ADDR: PRDATA = {31'b0, irq_done_q};
                MIXED_ADDR: PRDATA = {
                    29'b0,
                    mixed_done_q,
                    mixed_busy_i,
                    mixed_enable_o
                };
                default:     PRDATA = 32'b0;
            endcase
        end
    end

    always_ff @(posedge PCLK or negedge PRESETn) begin
        if (!PRESETn) begin
            ctrl_en_o   <= 1'b0;
            ctrl_mode_o <= 2'b00;
        end else if (apb_write && !addr_misaligned && addr_mapped) begin
            case (PADDR)
                CTRL_ADDR: begin
                    ctrl_en_o   <= PWDATA[0];
                    ctrl_mode_o <= PWDATA[2:1];
                end
                default: begin
                    ctrl_en_o   <= ctrl_en_o;
                    ctrl_mode_o <= ctrl_mode_o;
                end
            endcase
        end
    end

    // Reset > hardware set > software clear. A concurrent hardware event is
    // retained even when software writes one to clear the previous status.
    always_ff @(posedge PCLK or negedge PRESETn) begin
        if (!PRESETn) begin
            irq_done_q <= 1'b0;
        end else if (irq_status_done_set_i) begin
            irq_done_q <= 1'b1;
        end else if (apb_write && (PADDR == IRQ_STATUS_ADDR) && PWDATA[0]) begin
            irq_done_q <= 1'b0;
        end
    end

    // All fields in MIXED independently interpret the same APB write:
    // ENABLE captures PWDATA[0], BUSY ignores PWDATA[1], DONE clears only
    // when PWDATA[2] is one, and reserved PWDATA[31:3] is ignored.
    always_ff @(posedge PCLK or negedge PRESETn) begin
        if (!PRESETn) begin
            mixed_enable_o <= 1'b0;
        end else if (apb_write && (PADDR == MIXED_ADDR)) begin
            mixed_enable_o <= PWDATA[0];
        end
    end

    // Reset > hardware set > software clear also applies to MIXED.DONE.
    always_ff @(posedge PCLK or negedge PRESETn) begin
        if (!PRESETn) begin
            mixed_done_q <= 1'b0;
        end else if (mixed_done_set_i) begin
            mixed_done_q <= 1'b1;
        end else if (apb_write && (PADDR == MIXED_ADDR) && PWDATA[2]) begin
            mixed_done_q <= 1'b0;
        end
    end

endmodule
