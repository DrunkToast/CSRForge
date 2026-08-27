`timescale 1ns/1ps

module csr_regs_tb;

    localparam logic [31:0] CTRL_ADDR       = 32'h0000_0000;
    localparam logic [31:0] STATUS_ADDR     = 32'h0000_0004;
    localparam logic [31:0] IRQ_STATUS_ADDR = 32'h0000_0008;
    localparam logic [31:0] MIXED_ADDR      = 32'h0000_000C;

    logic        PCLK;
    logic        PRESETn;
    logic        PSEL;
    logic        PENABLE;
    logic        PWRITE;
    logic [31:0] PADDR;
    logic [31:0] PWDATA;
    logic [31:0] PRDATA;
    logic        PREADY;
    logic        PSLVERR;

    logic       ctrl_en_o;
    logic [1:0] ctrl_mode_o;
    logic       status_busy_i;
    logic       irq_status_done_set_i;
    logic       mixed_enable_o;
    logic       mixed_busy_i;
    logic       mixed_done_set_i;

    integer checks;
    integer failures;

    csr_regs dut (
        .PCLK              (PCLK),
        .PRESETn           (PRESETn),
        .PSEL              (PSEL),
        .PENABLE           (PENABLE),
        .PWRITE            (PWRITE),
        .PADDR             (PADDR),
        .PWDATA            (PWDATA),
        .PRDATA            (PRDATA),
        .PREADY            (PREADY),
        .PSLVERR           (PSLVERR),
        .ctrl_en_o         (ctrl_en_o),
        .ctrl_mode_o       (ctrl_mode_o),
        .status_busy_i     (status_busy_i),
        .irq_status_done_set_i (irq_status_done_set_i),
        .mixed_enable_o    (mixed_enable_o),
        .mixed_busy_i      (mixed_busy_i),
        .mixed_done_set_i  (mixed_done_set_i)
    );

    always #5 PCLK = ~PCLK;

    task automatic check_equal(
        input logic [31:0] actual,
        input logic [31:0] expected,
        input string       test_name
    );
        begin
            checks = checks + 1;
            if (actual !== expected) begin
                failures = failures + 1;
                $display("[FAIL] %s: expected=0x%08h actual=0x%08h",
                         test_name, expected, actual);
            end else begin
                $display("[PASS] %s", test_name);
            end
        end
    endtask

    task automatic reset_dut;
        begin
            PSEL    = 1'b0;
            PENABLE = 1'b0;
            PWRITE  = 1'b0;
            PADDR   = 32'b0;
            PWDATA  = 32'b0;
            PRESETn = 1'b0;

            repeat (2) @(posedge PCLK);
            @(negedge PCLK);
            PRESETn = 1'b1;
        end
    endtask

    task automatic apb_write(
        input  logic [31:0] addr,
        input  logic [31:0] data,
        output logic        error
    );
        begin
            @(negedge PCLK);
            PSEL    = 1'b1;
            PENABLE = 1'b0;
            PWRITE  = 1'b1;
            PADDR   = addr;
            PWDATA  = data;

            @(negedge PCLK);
            PENABLE = 1'b1;

            @(posedge PCLK);
            #1;
            error = PSLVERR;

            @(negedge PCLK);
            PSEL    = 1'b0;
            PENABLE = 1'b0;
            PWRITE  = 1'b0;
            PADDR   = 32'b0;
            PWDATA  = 32'b0;
        end
    endtask

    task automatic apb_read(
        input  logic [31:0] addr,
        output logic [31:0] data,
        output logic        error
    );
        begin
            @(negedge PCLK);
            PSEL    = 1'b1;
            PENABLE = 1'b0;
            PWRITE  = 1'b0;
            PADDR   = addr;
            PWDATA  = 32'b0;

            @(negedge PCLK);
            PENABLE = 1'b1;

            @(posedge PCLK);
            #1;
            data  = PRDATA;
            error = PSLVERR;

            @(negedge PCLK);
            PSEL    = 1'b0;
            PENABLE = 1'b0;
            PADDR   = 32'b0;
        end
    endtask

    task automatic pulse_irq_done_set;
        begin
            @(negedge PCLK);
            irq_status_done_set_i = 1'b1;
            @(posedge PCLK);
            #1;
            @(negedge PCLK);
            irq_status_done_set_i = 1'b0;
        end
    endtask

    task automatic pulse_mixed_done_set;
        begin
            @(negedge PCLK);
            mixed_done_set_i = 1'b1;
            @(posedge PCLK);
            #1;
            @(negedge PCLK);
            mixed_done_set_i = 1'b0;
        end
    endtask

    task automatic apb_clear_irq_with_hw_set(
        output logic error
    );
        begin
            @(negedge PCLK);
            PSEL    = 1'b1;
            PENABLE = 1'b0;
            PWRITE  = 1'b1;
            PADDR   = IRQ_STATUS_ADDR;
            PWDATA  = 32'h0000_0001;

            @(negedge PCLK);
            PENABLE          = 1'b1;
            irq_status_done_set_i = 1'b1;

            @(posedge PCLK);
            #1;
            error = PSLVERR;

            @(negedge PCLK);
            PSEL             = 1'b0;
            PENABLE          = 1'b0;
            PWRITE           = 1'b0;
            PADDR            = 32'b0;
            PWDATA           = 32'b0;
            irq_status_done_set_i = 1'b0;
        end
    endtask

    task automatic apb_read_with_phase_errors(
        input  logic [31:0] addr,
        output logic [31:0] data,
        output logic        setup_error,
        output logic        access_error_sample,
        output logic        idle_error
    );
        begin
            @(negedge PCLK);
            PSEL    = 1'b1;
            PENABLE = 1'b0;
            PWRITE  = 1'b0;
            PADDR   = addr;
            PWDATA  = 32'b0;
            #1;
            setup_error = PSLVERR;

            @(negedge PCLK);
            PENABLE = 1'b1;
            #1;
            data                = PRDATA;
            access_error_sample = PSLVERR;

            @(negedge PCLK);
            PSEL    = 1'b0;
            PENABLE = 1'b0;
            PADDR   = 32'b0;
            #1;
            idle_error = PSLVERR;
        end
    endtask

    task automatic apb_back_to_back_ctrl_write_read(
        input  logic [31:0] write_data,
        output logic [31:0] read_data_sample,
        output logic        write_error,
        output logic        read_error
    );
        begin
            // First transfer SETUP: CTRL write.
            @(negedge PCLK);
            PSEL    = 1'b1;
            PENABLE = 1'b0;
            PWRITE  = 1'b1;
            PADDR   = CTRL_ADDR;
            PWDATA  = write_data;

            // First transfer ACCESS.
            @(negedge PCLK);
            PENABLE = 1'b1;
            @(posedge PCLK);
            #1;
            write_error = PSLVERR;

            // Next transfer SETUP. PSEL remains asserted while PENABLE drops.
            @(negedge PCLK);
            PENABLE = 1'b0;
            PWRITE  = 1'b0;
            PADDR   = CTRL_ADDR;
            PWDATA  = 32'b0;

            // Second transfer ACCESS: CTRL read.
            @(negedge PCLK);
            PENABLE = 1'b1;
            @(posedge PCLK);
            #1;
            read_data_sample = PRDATA;
            read_error       = PSLVERR;

            @(negedge PCLK);
            PSEL    = 1'b0;
            PENABLE = 1'b0;
            PADDR   = 32'b0;
        end
    endtask

    logic [31:0] read_data;
    logic        access_error;
    logic        setup_error;
    logic        idle_error;
    logic        second_access_error;

    initial begin
        PCLK             = 1'b0;
        PRESETn          = 1'b1;
        PSEL             = 1'b0;
        PENABLE          = 1'b0;
        PWRITE           = 1'b0;
        PADDR            = 32'b0;
        PWDATA           = 32'b0;
        status_busy_i    = 1'b0;
        irq_status_done_set_i = 1'b0;
        mixed_busy_i     = 1'b0;
        mixed_done_set_i = 1'b0;
        checks           = 0;
        failures         = 0;

        reset_dut();

        check_equal({31'b0, ctrl_en_o}, 32'h0000_0000,
                    "RESET CTRL.EN");
        check_equal({30'b0, ctrl_mode_o}, 32'h0000_0000,
                    "RESET CTRL.MODE");
        check_equal({31'b0, mixed_enable_o}, 32'h0000_0000,
                    "RESET MIXED.ENABLE");
        check_equal({31'b0, PREADY}, 32'h0000_0001,
                    "PREADY ALWAYS ONE");

        apb_read(CTRL_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0000, "CTRL RESET READ");
        check_equal({31'b0, access_error}, 32'h0000_0000,
                    "CTRL RESET READ NO ERROR");

        apb_write(CTRL_ADDR, 32'h0000_0005, access_error);
        check_equal({31'b0, access_error}, 32'h0000_0000,
                    "CTRL WRITE NO ERROR");
        check_equal({31'b0, ctrl_en_o}, 32'h0000_0001,
                    "CTRL.EN WRITE ONE");
        check_equal({30'b0, ctrl_mode_o}, 32'h0000_0002,
                    "CTRL.MODE WRITE TWO");

        apb_read(CTRL_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0005, "CTRL WRITE READBACK");

        apb_write(CTRL_ADDR, 32'h0000_0004, access_error);
        check_equal({31'b0, ctrl_en_o}, 32'h0000_0000,
                    "CTRL.EN CLEAR");
        check_equal({30'b0, ctrl_mode_o}, 32'h0000_0002,
                    "CTRL.MODE PRESERVED BY WRITE DATA");

        apb_read(CTRL_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0004, "CTRL FINAL READBACK");

        status_busy_i = 1'b1;
        apb_read(STATUS_ADDR, read_data, access_error);
        check_equal({31'b0, access_error}, 32'h0000_0000,
                    "STATUS READ NO ERROR");
        check_equal(read_data, 32'h0000_0001,
                    "STATUS.BUSY REFLECTS HW ONE");

        apb_write(STATUS_ADDR, 32'hFFFF_FFFF, access_error);
        check_equal({31'b0, access_error}, 32'h0000_0000,
                    "STATUS WRITE NO ERROR");
        apb_read(STATUS_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0001,
                    "STATUS.BUSY IGNORES SOFTWARE WRITE");

        apb_read(CTRL_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0004,
                    "RO WRITE DOES NOT CHANGE CTRL");

        status_busy_i = 1'b0;
        apb_read(STATUS_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0000,
                    "STATUS.BUSY REFLECTS HW ZERO");

        apb_read(IRQ_STATUS_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0000, "IRQ.DONE RESET READ");
        check_equal({31'b0, access_error}, 32'h0000_0000,
                    "IRQ RESET READ NO ERROR");

        pulse_irq_done_set();
        apb_read(IRQ_STATUS_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0001,
                    "IRQ.DONE HARDWARE SET");

        apb_write(IRQ_STATUS_ADDR, 32'h0000_0000, access_error);
        apb_read(IRQ_STATUS_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0001,
                    "IRQ.DONE WRITE ZERO HOLDS");

        apb_write(IRQ_STATUS_ADDR, 32'h0000_0001, access_error);
        apb_read(IRQ_STATUS_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0000,
                    "IRQ.DONE WRITE ONE CLEARS");

        apb_clear_irq_with_hw_set(access_error);
        check_equal({31'b0, access_error}, 32'h0000_0000,
                    "IRQ CONFLICT WRITE NO ERROR");
        apb_read(IRQ_STATUS_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0001,
                    "IRQ.DONE HW SET WINS SW CLEAR");

        apb_write(IRQ_STATUS_ADDR, 32'h0000_0001, access_error);
        apb_read(IRQ_STATUS_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0000,
                    "IRQ.DONE FINAL CLEAR");

        mixed_busy_i = 1'b1;
        pulse_mixed_done_set();
        apb_read(MIXED_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0006,
                    "MIXED PRECONDITION RO ONE W1C ONE RW ZERO");

        // One write is interpreted independently by RW, RO, W1C, and
        // Reserved fields. ENABLE captures one, BUSY ignores the write,
        // DONE clears, and reserved ones do not appear in read data.
        apb_write(MIXED_ADDR, 32'hFFFF_FFFF, access_error);
        check_equal({31'b0, access_error}, 32'h0000_0000,
                    "MIXED WRITE NO ERROR");
        apb_read(MIXED_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0003,
                    "MIXED SINGLE WRITE FIELD SEMANTICS");
        check_equal({31'b0, mixed_enable_o}, 32'h0000_0001,
                    "MIXED.ENABLE RW CAPTURES ONE");

        // Re-set DONE, then write zero to all defined software-controlled
        // fields while keeping all reserved write bits high.
        pulse_mixed_done_set();
        apb_write(MIXED_ADDR, 32'hFFFF_FFF8, access_error);
        apb_read(MIXED_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0006,
                    "MIXED W1C ZERO HOLDS AND RESERVED WRITE IGNORED");
        check_equal({31'b0, mixed_enable_o}, 32'h0000_0000,
                    "MIXED.ENABLE RW CAPTURES ZERO");

        mixed_busy_i = 1'b0;
        apb_read(MIXED_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0004,
                    "MIXED.BUSY RO FOLLOWS HARDWARE INPUT");

        // Establish non-zero state in every software-stored register before
        // attempting illegal writes.
        apb_write(CTRL_ADDR, 32'h0000_0005, access_error);
        pulse_irq_done_set();
        mixed_busy_i = 1'b1;
        apb_write(MIXED_ADDR, 32'h0000_0001, access_error);

        apb_read_with_phase_errors(
            32'h0000_0010,
            read_data,
            setup_error,
            access_error,
            idle_error
        );
        check_equal({31'b0, setup_error}, 32'h0000_0000,
                    "UNMAPPED PSLVERR LOW IN SETUP");
        check_equal({31'b0, access_error}, 32'h0000_0001,
                    "UNMAPPED PSLVERR HIGH IN ACCESS");
        check_equal({31'b0, idle_error}, 32'h0000_0000,
                    "UNMAPPED PSLVERR LOW IN IDLE");
        check_equal(read_data, 32'h0000_0000,
                    "UNMAPPED READ RETURNS ZERO");

        apb_write(32'h0000_0010, 32'hFFFF_FFFF, access_error);
        check_equal({31'b0, access_error}, 32'h0000_0001,
                    "UNMAPPED WRITE REPORTS ERROR");

        apb_read_with_phase_errors(
            32'h0000_0001,
            read_data,
            setup_error,
            access_error,
            idle_error
        );
        check_equal({31'b0, setup_error}, 32'h0000_0000,
                    "MISALIGNED PSLVERR LOW IN SETUP");
        check_equal({31'b0, access_error}, 32'h0000_0001,
                    "MISALIGNED PSLVERR HIGH IN ACCESS");
        check_equal({31'b0, idle_error}, 32'h0000_0000,
                    "MISALIGNED PSLVERR LOW IN IDLE");
        check_equal(read_data, 32'h0000_0000,
                    "MISALIGNED READ RETURNS ZERO");

        apb_write(32'h0000_0001, 32'h0000_0000, access_error);
        check_equal({31'b0, access_error}, 32'h0000_0001,
                    "MISALIGNED WRITE REPORTS ERROR");

        apb_read(CTRL_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0005,
                    "ILLEGAL WRITES DO NOT CHANGE CTRL");
        apb_read(IRQ_STATUS_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0001,
                    "ILLEGAL WRITES DO NOT CHANGE IRQ");
        apb_read(MIXED_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0007,
                    "ILLEGAL WRITES DO NOT CHANGE MIXED");

        apb_back_to_back_ctrl_write_read(
            32'h0000_0002,
            read_data,
            access_error,
            second_access_error
        );
        check_equal({31'b0, access_error}, 32'h0000_0000,
                    "BACK-TO-BACK WRITE NO ERROR");
        check_equal({31'b0, second_access_error}, 32'h0000_0000,
                    "BACK-TO-BACK READ NO ERROR");
        check_equal(read_data, 32'h0000_0002,
                    "BACK-TO-BACK WRITE THEN READ");

        // Put observable state high, then assert reset between active clock
        // edges. Outputs must reset before another rising edge occurs.
        apb_write(CTRL_ADDR, 32'h0000_0007, access_error);
        apb_write(MIXED_ADDR, 32'h0000_0001, access_error);
        pulse_irq_done_set();

        @(negedge PCLK);
        #2;
        PRESETn = 1'b0;
        #1;
        check_equal({31'b0, ctrl_en_o}, 32'h0000_0000,
                    "ASYNC RESET CTRL.EN BEFORE CLOCK EDGE");
        check_equal({30'b0, ctrl_mode_o}, 32'h0000_0000,
                    "ASYNC RESET CTRL.MODE BEFORE CLOCK EDGE");
        check_equal({31'b0, mixed_enable_o}, 32'h0000_0000,
                    "ASYNC RESET MIXED.ENABLE BEFORE CLOCK EDGE");

        @(negedge PCLK);
        PRESETn = 1'b1;
        apb_read(IRQ_STATUS_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0000,
                    "ASYNC RESET IRQ.DONE");
        apb_read(MIXED_ADDR, read_data, access_error);
        check_equal(read_data, 32'h0000_0002,
                    "ASYNC RESET MIXED STORED FIELDS");

        if (failures != 0) begin
            $fatal(1, "Golden slice failed: %0d/%0d checks failed",
                   failures, checks);
        end

        $display("ALL TESTS PASSED (%0d checks)", checks);
        $finish;
    end

endmodule
