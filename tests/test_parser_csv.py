from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from csrforge.parser_csv import CsvParser, ParseError


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CsvParserTests(unittest.TestCase):
    def parse_text(self, text: str):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registers.csv"
            path.write_text(text, encoding="utf-8")
            return CsvParser(path).parse()

    def test_parse_golden_register_map(self):
        block = CsvParser(PROJECT_ROOT / "examples" / "golden.csv").parse()

        self.assertEqual(block.name, "csr_regs")
        self.assertEqual(block.data_width, 32)
        self.assertEqual(block.address_width, 32)
        self.assertEqual([register.name for register in block.registers], [
            "CTRL", "STATUS", "IRQ_STATUS", "MIXED"
        ])
        self.assertEqual([register.offset for register in block.registers], [
            0x00, 0x04, 0x08, 0x0C
        ])

        ctrl = block.registers[0]
        self.assertEqual([field.name for field in ctrl.fields], ["EN", "MODE"])
        self.assertEqual((ctrl.fields[1].msb, ctrl.fields[1].lsb), (2, 1))
        self.assertEqual(ctrl.fields[1].width, 2)
        self.assertEqual(ctrl.fields[1].access, "RW")

        mixed = block.registers[3]
        self.assertEqual(
            [field.access for field in mixed.fields], ["RW", "RO", "W1C"]
        )

    def test_json_serialization_is_deterministic(self):
        block = CsvParser(PROJECT_ROOT / "examples" / "golden.csv").parse()

        first = block.to_json()
        second = block.to_json()
        self.assertEqual(first, second)

        payload = json.loads(first)
        self.assertEqual(payload["name"], "csr_regs")
        self.assertEqual(payload["registers"][2]["offset"], 0x08)
        self.assertEqual(payload["registers"][2]["fields"][0]["access"], "W1C")

    def test_decimal_and_prefixed_integer_formats(self):
        block = self.parse_text(
            "Register,Offset,Field,Bits,Access,Reset\n"
            "CTRL,0x0,MODE,3:1,RW,0b101\n"
        )

        field = block.registers[0].fields[0]
        self.assertEqual(block.registers[0].offset, 0)
        self.assertEqual((field.msb, field.lsb), (3, 1))
        self.assertEqual(field.reset, 5)

    def test_fully_blank_rows_are_skipped(self):
        block = self.parse_text(
            "Register,Offset,Field,Bits,Access,Reset\n"
            "CTRL,0x00,EN,0,RW,0\n"
            ",,,,,\n"
        )

        self.assertEqual(len(block.registers), 1)

    def test_header_must_match_exactly(self):
        with self.assertRaisesRegex(ParseError, "header must be exactly"):
            self.parse_text(
                "Register,Offset,Field,Bits,Access\n"
                "CTRL,0x00,EN,0,RW\n"
            )

    def test_missing_required_cell_reports_row(self):
        with self.assertRaisesRegex(ParseError, "Row 2.*Field"):
            self.parse_text(
                "Register,Offset,Field,Bits,Access,Reset\n"
                "CTRL,0x00,,0,RW,0\n"
            )

    def test_invalid_integer_reports_row_and_column(self):
        with self.assertRaisesRegex(ParseError, "Row 2.*Offset"):
            self.parse_text(
                "Register,Offset,Field,Bits,Access,Reset\n"
                "CTRL,not-an-address,EN,0,RW,0\n"
            )

    def test_invalid_bits_syntax_reports_row(self):
        with self.assertRaisesRegex(ParseError, "Row 2.*Bits syntax"):
            self.parse_text(
                "Register,Offset,Field,Bits,Access,Reset\n"
                "CTRL,0x00,MODE,3:2:1,RW,0\n"
            )

    def test_empty_csv_is_rejected(self):
        with self.assertRaisesRegex(ParseError, "no register field rows"):
            self.parse_text("Register,Offset,Field,Bits,Access,Reset\n")


if __name__ == "__main__":
    unittest.main()

