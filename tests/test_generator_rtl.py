from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from csrforge import CsvParser, RtlGenerator, SemanticChecker


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class RtlGeneratorTests(unittest.TestCase):
    def setUp(self):
        block = CsvParser(PROJECT_ROOT / "examples" / "golden.csv").parse()
        self.block = SemanticChecker().validate(block)
        self.generator = RtlGenerator(self.block)

    def test_render_is_deterministic(self):
        self.assertEqual(self.generator.render(), self.generator.render())

    def test_module_and_hardware_port_contract(self):
        rtl = self.generator.render()

        self.assertIn("module csr_regs (", rtl)
        self.assertIn("ctrl_en_o", rtl)
        self.assertIn("ctrl_mode_o", rtl)
        self.assertIn("status_busy_i", rtl)
        self.assertIn("irq_status_done_set_i", rtl)
        self.assertIn("mixed_enable_o", rtl)
        self.assertIn("mixed_busy_i", rtl)
        self.assertIn("mixed_done_set_i", rtl)
        self.assertNotIn("irq_done_set_i", rtl)

    def test_read_path_assigns_each_field_independently(self):
        rtl = self.generator.render()

        self.assertIn("PRDATA[0] = mixed_enable_o;", rtl)
        self.assertIn("PRDATA[1] = mixed_busy_i;", rtl)
        self.assertIn("PRDATA[2] = mixed_done_q;", rtl)

    def test_w1c_uses_bitwise_hardware_set_priority(self):
        rtl = self.generator.render()

        self.assertIn(
            "irq_status_done_q <= (irq_status_done_q & ~PWDATA[0]) | "
            "irq_status_done_set_i;",
            rtl,
        )
        self.assertIn(
            "mixed_done_q <= (mixed_done_q & ~PWDATA[2]) | mixed_done_set_i;",
            rtl,
        )

    def test_reserved_bits_are_not_assigned(self):
        rtl = self.generator.render()

        self.assertNotIn("PRDATA[31:3]", rtl)
        self.assertNotIn("PWDATA[31:3]", rtl)

    def test_output_contains_no_dynamic_timestamp(self):
        rtl = self.generator.render().lower()

        self.assertNotIn("generated at", rtl)
        self.assertNotIn("timestamp", rtl)

    def test_write_creates_requested_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "nested" / "csr_regs.sv"
            result = self.generator.write(output)

            self.assertEqual(result, output)
            self.assertEqual(output.read_text(encoding="utf-8"), self.generator.render())


if __name__ == "__main__":
    unittest.main()

