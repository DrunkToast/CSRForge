"""Independent self-checking SystemVerilog testbench generation."""

from __future__ import annotations

from pathlib import Path

from .checker import SemanticChecker
from .model import Field, Register, RegisterBlock


def _base_name(register: Register, field: Field) -> str:
    return f"{register.name}_{field.name}".lower()


def _port_name(register: Register, field: Field) -> str:
    base = _base_name(register, field)
    if field.access == "RW":
        return f"{base}_o"
    if field.access == "RO":
        return f"{base}_i"
    return f"{base}_set_i"


def _addr_name(register: Register) -> str:
    return f"{register.name.upper()}_ADDR"


def _compact_range(field: Field) -> str:
    return "" if field.width == 1 else f"[{field.width - 1}:0] "


def _sv_literal(width: int, value: int) -> str:
    return f"{width}'b{value:0{width}b}"


def _word(value: int) -> str:
    return f"32'h{value & 0xFFFF_FFFF:08X}"


def _zero_extend_to_word(signal: str, width: int) -> str:
    if width == 32:
        return signal
    return f"{{{32 - width}'b0, {signal}}}"


def _field_mask(field: Field) -> int:
    return ((1 << field.width) - 1) << field.lsb


def _stored_reset_word(register: Register) -> int:
    value = 0
    for field in register.fields:
        if field.access != "RO":
            value |= field.reset << field.lsb
    return value


def _w1c_reset_word(register: Register) -> int:
    value = 0
    for field in register.fields:
        if field.access == "W1C":
            value |= field.reset << field.lsb
    return value


def _rw_mask_word(register: Register) -> int:
    value = 0
    for field in register.fields:
        if field.access == "RW":
            value |= _field_mask(field)
    return value


class TestbenchGenerator:
    """Generate tests from IR without using RTL generator semantics."""

    def __init__(self, block: RegisterBlock):
        self.block = SemanticChecker().validate(block)

    def render(self) -> str:
        lines = [
            "`timescale 1ns/1ps",
            "",
            "// Generated independently from the RTL generator.",
            f"module {self.block.name}_tb;",
            "",
        ]

        for register in self.block.registers:
            lines.append(
                f"    localparam logic [31:0] {_addr_name(register)} = "
                f"32'h{register.offset:08X};"
            )
        lines.extend([
            "",
            "    logic        PCLK;",
            "    logic        PRESETn;",
            "    logic        PSEL;",
            "    logic        PENABLE;",
            "    logic        PWRITE;",
            "    logic [31:0] PADDR;",
            "    logic [31:0] PWDATA;",
            "    logic [31:0] PRDATA;",
            "    logic        PREADY;",
            "    logic        PSLVERR;",
            "",
        ])

        for register in self.block.registers:
            for field in register.fields:
                lines.append(
                    f"    logic {_compact_range(field)}{_port_name(register, field)};"
                )

        lines.extend([
            "",
            "    integer checks;",
            "    integer failures;",
            "    logic [31:0] read_data;",
            "    logic        access_error;",
            "",
            f"    {self.block.name} dut (",
        ])

        connections = [
            ("PCLK", "PCLK"),
            ("PRESETn", "PRESETn"),
            ("PSEL", "PSEL"),
            ("PENABLE", "PENABLE"),
            ("PWRITE", "PWRITE"),
            ("PADDR", "PADDR"),
            ("PWDATA", "PWDATA"),
            ("PRDATA", "PRDATA"),
            ("PREADY", "PREADY"),
            ("PSLVERR", "PSLVERR"),
        ]
        for register in self.block.registers:
            for field in register.fields:
                name = _port_name(register, field)
                connections.append((name, name))

        for index, (port, signal) in enumerate(connections):
            comma = "," if index < len(connections) - 1 else ""
            lines.append(f"        .{port} ({signal}){comma}")
        lines.extend([
            "    );",
            "",
            "    always #5 PCLK = ~PCLK;",
            "",
        ])

        lines.extend(self._render_common_tasks())
        lines.extend(self._render_initial_block())
        lines.extend(["endmodule", ""])
        return "\n".join(lines)

    def write(self, output_path: str | Path) -> Path:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(), encoding="utf-8", newline="\n")
        return path

    def _render_common_tasks(self) -> list[str]:
        input_initializers = []
        for register in self.block.registers:
            for field in register.fields:
                if field.access in {"RO", "W1C"}:
                    input_initializers.append(
                        f"            {_port_name(register, field)} = "
                        f"{_sv_literal(field.width, 0)};"
                    )

        return [
            "    task automatic check_equal(",
            "        input logic [31:0] actual,",
            "        input logic [31:0] expected,",
            "        input string       test_name",
            "    );",
            "        begin",
            "            checks = checks + 1;",
            "            if (actual !== expected) begin",
            "                failures = failures + 1;",
            "                $display(\"[FAIL] %s: expected=0x%08h actual=0x%08h\",",
            "                         test_name, expected, actual);",
            "            end else begin",
            "                $display(\"[PASS] %s\", test_name);",
            "            end",
            "        end",
            "    endtask",
            "",
            "    task automatic reset_dut;",
            "        begin",
            "            PSEL    = 1'b0;",
            "            PENABLE = 1'b0;",
            "            PWRITE  = 1'b0;",
            "            PADDR   = 32'b0;",
            "            PWDATA  = 32'b0;",
            *input_initializers,
            "            PRESETn = 1'b0;",
            "            repeat (2) @(posedge PCLK);",
            "            @(negedge PCLK);",
            "            PRESETn = 1'b1;",
            "        end",
            "    endtask",
            "",
            "    task automatic apb_write(",
            "        input  logic [31:0] addr,",
            "        input  logic [31:0] data,",
            "        output logic        error",
            "    );",
            "        begin",
            "            @(negedge PCLK);",
            "            PSEL = 1'b1; PENABLE = 1'b0; PWRITE = 1'b1;",
            "            PADDR = addr; PWDATA = data;",
            "            @(negedge PCLK);",
            "            PENABLE = 1'b1;",
            "            @(posedge PCLK); #1;",
            "            error = PSLVERR;",
            "            @(negedge PCLK);",
            "            PSEL = 1'b0; PENABLE = 1'b0; PWRITE = 1'b0;",
            "            PADDR = 32'b0; PWDATA = 32'b0;",
            "        end",
            "    endtask",
            "",
            "    task automatic apb_read(",
            "        input  logic [31:0] addr,",
            "        output logic [31:0] data,",
            "        output logic        error",
            "    );",
            "        begin",
            "            @(negedge PCLK);",
            "            PSEL = 1'b1; PENABLE = 1'b0; PWRITE = 1'b0;",
            "            PADDR = addr; PWDATA = 32'b0;",
            "            @(negedge PCLK);",
            "            PENABLE = 1'b1;",
            "            @(posedge PCLK); #1;",
            "            data = PRDATA; error = PSLVERR;",
            "            @(negedge PCLK);",
            "            PSEL = 1'b0; PENABLE = 1'b0; PADDR = 32'b0;",
            "        end",
            "    endtask",
            "",
        ]

    def _render_initial_block(self) -> list[str]:
        lines = [
            "    initial begin",
            "        PCLK = 1'b0; PRESETn = 1'b1;",
            "        PSEL = 1'b0; PENABLE = 1'b0; PWRITE = 1'b0;",
            "        PADDR = 32'b0; PWDATA = 32'b0;",
            "        checks = 0; failures = 0;",
            "",
            "        reset_dut();",
            "        check_equal({31'b0, PREADY}, 32'h0000_0001,",
            "                    \"PREADY ALWAYS ONE\");",
            "",
        ]

        for register in self.block.registers:
            lines.extend(self._render_reset_test(register))
        for register in self.block.registers:
            for field in register.fields:
                if field.access == "RW":
                    lines.extend(self._render_rw_test(register, field))
                elif field.access == "RO":
                    lines.extend(self._render_ro_test(register, field))
                elif field.access == "W1C":
                    lines.extend(self._render_w1c_test(register, field))
        for register in self.block.registers:
            lines.extend(self._render_reserved_test(register))
        lines.extend(self._render_error_tests())

        lines.extend([
            "        if (failures != 0) begin",
            "            $fatal(1, \"Generated TB failed: %0d/%0d checks failed\",",
            "                   failures, checks);",
            "        end",
            "        $display(\"ALL GENERATED TESTS PASSED (%0d checks)\", checks);",
            "        $finish;",
            "    end",
            "",
        ])
        return lines

    @staticmethod
    def _render_reset_test(register: Register) -> list[str]:
        return [
            f"        // Reset: {register.name}",
            "        reset_dut();",
            f"        apb_read({_addr_name(register)}, read_data, access_error);",
            f"        check_equal(read_data, {_word(_stored_reset_word(register))},",
            f"                    \"RESET {register.name}\");",
            "",
        ]

    @staticmethod
    def _render_rw_test(register: Register, field: Field) -> list[str]:
        mask = _field_mask(field)
        after_one = _w1c_reset_word(register) | mask
        after_zero = _w1c_reset_word(register)
        port = _port_name(register, field)
        label = f"{register.name}.{field.name}"
        return [
            f"        // RW: {label}",
            "        reset_dut();",
            f"        apb_write({_addr_name(register)}, {_word(mask)}, access_error);",
            f"        apb_read({_addr_name(register)}, read_data, access_error);",
            f"        check_equal(read_data, {_word(after_one)}, \"{label} RW ONE\");",
            f"        check_equal({_zero_extend_to_word(port, field.width)}, {_word((1 << field.width) - 1)},",
            f"                    \"{label} HW OUTPUT\");",
            f"        apb_write({_addr_name(register)}, 32'b0, access_error);",
            f"        apb_read({_addr_name(register)}, read_data, access_error);",
            f"        check_equal(read_data, {_word(after_zero)}, \"{label} RW ZERO\");",
            "",
        ]

    @staticmethod
    def _render_ro_test(register: Register, field: Field) -> list[str]:
        mask = _field_mask(field)
        port = _port_name(register, field)
        label = f"{register.name}.{field.name}"
        expected_before_write = _stored_reset_word(register) | mask
        expected_after_write = _rw_mask_word(register) | mask
        return [
            f"        // RO: {label}",
            "        reset_dut();",
            f"        {port} = {_sv_literal(field.width, (1 << field.width) - 1)};",
            f"        apb_read({_addr_name(register)}, read_data, access_error);",
            f"        check_equal(read_data, {_word(expected_before_write)},",
            f"                    \"{label} RO HW VALUE\");",
            f"        apb_write({_addr_name(register)}, 32'hFFFF_FFFF, access_error);",
            f"        apb_read({_addr_name(register)}, read_data, access_error);",
            f"        check_equal(read_data, {_word(expected_after_write)},",
            f"                    \"{label} RO WRITE IGNORED\");",
            "",
        ]

    @staticmethod
    def _render_w1c_test(register: Register, field: Field) -> list[str]:
        mask = _field_mask(field)
        port = _port_name(register, field)
        label = f"{register.name}.{field.name}"
        after_set = _stored_reset_word(register) | mask
        after_write_zero = _w1c_reset_word(register) | mask
        after_clear = _w1c_reset_word(register) & ~mask
        after_conflict = _w1c_reset_word(register) | mask
        ones = _sv_literal(field.width, (1 << field.width) - 1)
        zeros = _sv_literal(field.width, 0)
        return [
            f"        // W1C: {label}",
            "        reset_dut();",
            "        @(negedge PCLK);",
            f"        {port} = {ones};",
            "        @(posedge PCLK); #1;",
            "        @(negedge PCLK);",
            f"        {port} = {zeros};",
            f"        apb_read({_addr_name(register)}, read_data, access_error);",
            f"        check_equal(read_data, {_word(after_set)},",
            f"                    \"{label} HW SET\");",
            f"        apb_write({_addr_name(register)}, 32'b0, access_error);",
            f"        apb_read({_addr_name(register)}, read_data, access_error);",
            f"        check_equal(read_data, {_word(after_write_zero)},",
            f"                    \"{label} WRITE ZERO HOLDS\");",
            f"        apb_write({_addr_name(register)}, {_word(mask)}, access_error);",
            f"        apb_read({_addr_name(register)}, read_data, access_error);",
            f"        check_equal(read_data, {_word(after_clear)},",
            f"                    \"{label} WRITE ONE CLEARS\");",
            "",
            "        reset_dut();",
            "        @(negedge PCLK);",
            "        PSEL = 1'b1; PENABLE = 1'b0; PWRITE = 1'b1;",
            f"        PADDR = {_addr_name(register)}; PWDATA = {_word(mask)};",
            "        @(negedge PCLK);",
            "        PENABLE = 1'b1;",
            f"        {port} = {ones};",
            "        @(posedge PCLK); #1;",
            "        access_error = PSLVERR;",
            "        @(negedge PCLK);",
            "        PSEL = 1'b0; PENABLE = 1'b0; PWRITE = 1'b0;",
            "        PADDR = 32'b0; PWDATA = 32'b0;",
            f"        {port} = {zeros};",
            f"        apb_read({_addr_name(register)}, read_data, access_error);",
            f"        check_equal(read_data, {_word(after_conflict)},",
            f"                    \"{label} HW SET WINS SW CLEAR\");",
            "",
        ]

    @staticmethod
    def _render_reserved_test(register: Register) -> list[str]:
        return [
            f"        // Reserved bits: {register.name}",
            "        reset_dut();",
            f"        apb_write({_addr_name(register)}, 32'hFFFF_FFFF, access_error);",
            f"        apb_read({_addr_name(register)}, read_data, access_error);",
            f"        check_equal(read_data, {_word(_rw_mask_word(register))},",
            f"                    \"{register.name} RESERVED BITS READ ZERO\");",
            "",
        ]

    def _render_error_tests(self) -> list[str]:
        mapped = {register.offset for register in self.block.registers}
        unmapped = next(
            offset for offset in range(0, 0x1_0000_0000, 4)
            if offset not in mapped
        )
        misaligned = self.block.registers[0].offset + 1
        first = self.block.registers[0]
        return [
            "        // Error accesses",
            "        reset_dut();",
            f"        apb_read({_word(unmapped)}, read_data, access_error);",
            "        check_equal(read_data, 32'b0, \"UNMAPPED READ DATA ZERO\");",
            "        check_equal({31'b0, access_error}, 32'h0000_0001,",
            "                    \"UNMAPPED READ ERROR\");",
            f"        apb_write({_word(unmapped)}, 32'hFFFF_FFFF, access_error);",
            "        check_equal({31'b0, access_error}, 32'h0000_0001,",
            "                    \"UNMAPPED WRITE ERROR\");",
            f"        apb_read({_word(misaligned)}, read_data, access_error);",
            "        check_equal(read_data, 32'b0, \"MISALIGNED READ DATA ZERO\");",
            "        check_equal({31'b0, access_error}, 32'h0000_0001,",
            "                    \"MISALIGNED READ ERROR\");",
            f"        apb_write({_word(misaligned)}, 32'hFFFF_FFFF, access_error);",
            "        check_equal({31'b0, access_error}, 32'h0000_0001,",
            "                    \"MISALIGNED WRITE ERROR\");",
            f"        apb_read({_addr_name(first)}, read_data, access_error);",
            f"        check_equal(read_data, {_word(_stored_reset_word(first))},",
            "                    \"ILLEGAL WRITES PRESERVE STATE\");",
            "",
        ]
