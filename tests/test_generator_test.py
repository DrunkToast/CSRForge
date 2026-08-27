from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from csrforge import CsvParser, SemanticChecker, TestbenchGenerator
from csrforge.model import Field, Register, RegisterBlock


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class TestbenchGeneratorTests(unittest.TestCase):
    def setUp(self):
        block = CsvParser(PROJECT_ROOT / "examples" / "golden.csv").parse()
        self.block = SemanticChecker().validate(block)
        self.generator = TestbenchGenerator(self.block)

    def test_render_is_deterministic(self):
        self.assertEqual(self.generator.render(), self.generator.render())

    def test_instantiates_public_interface(self):
        tb = self.generator.render()
        self.assertIn("module csr_regs_tb;", tb)
        self.assertIn(".irq_status_done_set_i (irq_status_done_set_i)", tb)
        self.assertIn(".mixed_done_set_i (mixed_done_set_i)", tb)

    def test_generates_access_semantic_checks(self):
        tb = self.generator.render()
        self.assertIn("CTRL.EN RW ONE", tb)
        self.assertIn("STATUS.BUSY RO WRITE IGNORED", tb)
        self.assertIn("IRQ_STATUS.DONE WRITE ONE CLEARS", tb)
        self.assertIn("MIXED.DONE HW SET WINS SW CLEAR", tb)

    def test_generates_error_access_checks(self):
        tb = self.generator.render()
        self.assertIn("UNMAPPED READ ERROR", tb)
        self.assertIn("MISALIGNED WRITE ERROR", tb)
        self.assertIn("ILLEGAL WRITES PRESERVE STATE", tb)

    def test_does_not_import_rtl_generator_semantics(self):
        source = (
            PROJECT_ROOT / "csrforge" / "generator_test.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("generator_rtl", source)
        self.assertNotIn("RtlGenerator", source)

    def test_write_creates_requested_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "nested" / "csr_regs_tb.sv"
            self.generator.write(output)
            self.assertEqual(output.read_text(encoding="utf-8"), self.generator.render())

    def test_full_width_rw_output_needs_no_zero_width_concatenation(self):
        block = RegisterBlock(
            name="csr_regs",
            data_width=32,
            address_width=32,
            registers=(
                Register(
                    name="DATA",
                    offset=0,
                    fields=(Field("VALUE", 31, 0, "RW", 0),),
                ),
            ),
        )
        tb = TestbenchGenerator(block).render()
        self.assertNotIn("0'b0", tb)
        self.assertIn("check_equal(data_value_o, 32'hFFFFFFFF", tb)


if __name__ == "__main__":
    unittest.main()
