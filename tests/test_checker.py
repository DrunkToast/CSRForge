from __future__ import annotations

from pathlib import Path
import unittest

from csrforge.checker import SemanticChecker, ValidationError
from csrforge.model import Field, Register, RegisterBlock
from csrforge.parser_csv import CsvParser


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def make_block(*registers: Register, name: str = "csr_regs") -> RegisterBlock:
    return RegisterBlock(
        name=name,
        data_width=32,
        address_width=32,
        registers=tuple(registers),
    )


def make_register(
    name: str = "CTRL",
    offset: int = 0,
    *fields: Field,
) -> Register:
    if not fields:
        fields = (Field("EN", 0, 0, "RW", 0),)
    return Register(name=name, offset=offset, fields=tuple(fields))


class SemanticCheckerTests(unittest.TestCase):
    def setUp(self):
        self.checker = SemanticChecker()

    def assert_invalid(self, block: RegisterBlock, message: str):
        with self.assertRaisesRegex(ValidationError, message):
            self.checker.validate(block)

    def test_golden_csv_is_valid(self):
        block = CsvParser(PROJECT_ROOT / "examples" / "golden.csv").parse()
        self.assertIs(self.checker.validate(block), block)

    def test_misaligned_register_offset(self):
        self.assert_invalid(make_block(make_register(offset=2)), "not 4-byte aligned")

    def test_offset_must_fit_unsigned_32_bit(self):
        self.assert_invalid(make_block(make_register(offset=-4)), "outside the 32-bit")

    def test_different_registers_cannot_share_offset(self):
        block = make_block(
            make_register("CTRL", 0x00),
            make_register("STATUS", 0x00),
        )
        self.assert_invalid(block, "both use offset")

    def test_same_register_name_cannot_use_different_offsets(self):
        block = make_block(
            make_register("CTRL", 0x00),
            make_register("CTRL", 0x04),
        )
        self.assert_invalid(block, "inconsistent offsets")

    def test_field_overlap(self):
        block = make_block(make_register(
            "CTRL",
            0x00,
            Field("MODE", 3, 1, "RW", 0),
            Field("EN", 2, 0, "RW", 0),
        ))
        self.assert_invalid(block, "overlaps field")

    def test_reversed_bit_range(self):
        block = make_block(make_register(
            "CTRL", 0x00, Field("MODE", 1, 3, "RW", 0)
        ))
        self.assert_invalid(block, "invalid bit range")

    def test_bit_range_above_data_width(self):
        block = make_block(make_register(
            "CTRL", 0x00, Field("MODE", 32, 31, "RW", 0)
        ))
        self.assert_invalid(block, "expected 0 <= lsb <= msb <= 31")

    def test_reset_overflow(self):
        block = make_block(make_register(
            "CTRL", 0x00, Field("MODE", 2, 1, "RW", 4)
        ))
        self.assert_invalid(block, "does not fit its 2-bit width")

    def test_negative_reset(self):
        block = make_block(make_register(
            "CTRL", 0x00, Field("EN", 0, 0, "RW", -1)
        ))
        self.assert_invalid(block, "allowed 0..1")

    def test_unsupported_access_type(self):
        block = make_block(make_register(
            "CTRL", 0x00, Field("EN", 0, 0, "WO", 0)  # type: ignore[arg-type]
        ))
        self.assert_invalid(block, "unsupported access 'WO'")

    def test_duplicate_field_name(self):
        block = make_block(make_register(
            "CTRL",
            0x00,
            Field("EN", 0, 0, "RW", 0),
            Field("EN", 1, 1, "RW", 0),
        ))
        self.assert_invalid(block, "duplicate field name")

    def test_nonportable_register_and_field_identifiers(self):
        block = make_block(make_register(
            "BAD-REG", 0x00, Field("BAD.FIELD", 0, 0, "RW", 0)
        ))
        with self.assertRaises(ValidationError) as context:
            self.checker.validate(block)

        self.assertEqual(len(context.exception.issues), 2)
        self.assertIn("Register 'BAD-REG'", context.exception.issues[0])
        self.assertIn("Field BAD-REG.BAD.FIELD", context.exception.issues[1])

    def test_all_issues_are_reported_together(self):
        block = make_block(make_register(
            "CTRL",
            2,
            Field("MODE", 40, 20, "WO", 0),  # type: ignore[arg-type]
        ))
        with self.assertRaises(ValidationError) as context:
            self.checker.validate(block)

        self.assertEqual(len(context.exception.issues), 3)
        message = str(context.exception)
        self.assertIn("not 4-byte aligned", message)
        self.assertIn("invalid bit range", message)
        self.assertIn("unsupported access", message)


if __name__ == "__main__":
    unittest.main()

