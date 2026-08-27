from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from csrforge import (
    CHeaderGenerator,
    CsvParser,
    MarkdownGenerator,
    SemanticChecker,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class OutputGeneratorTests(unittest.TestCase):
    def setUp(self):
        block = CsvParser(PROJECT_ROOT / "examples" / "golden.csv").parse()
        self.block = SemanticChecker().validate(block)

    def test_c_header_contains_offsets_masks_and_shifts(self):
        header = CHeaderGenerator(self.block).render()
        self.assertIn("#define CSR_CTRL_OFFSET 0x00000000u", header)
        self.assertIn("#define CSR_CTRL_MODE_MASK 0x00000006u", header)
        self.assertIn("#define CSR_CTRL_MODE_SHIFT 1u", header)
        self.assertIn("#define CSR_IRQ_STATUS_DONE_MASK 0x00000001u", header)

    def test_markdown_contains_register_map(self):
        markdown = MarkdownGenerator(self.block).render()
        self.assertIn("# csr_regs Register Map", markdown)
        self.assertIn("## CTRL — 0x00000000", markdown)
        self.assertIn("| MODE | 2:1 | RW | 0x0 | 0x00000006 |", markdown)

    def test_outputs_are_deterministic(self):
        self.assertEqual(
            CHeaderGenerator(self.block).render(),
            CHeaderGenerator(self.block).render(),
        )
        self.assertEqual(
            MarkdownGenerator(self.block).render(),
            MarkdownGenerator(self.block).render(),
        )

    def test_generators_write_requested_paths(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            header = Path(temp_dir) / "include" / "csr_regs.h"
            markdown = Path(temp_dir) / "docs" / "csr_regs.md"
            CHeaderGenerator(self.block).write(header)
            MarkdownGenerator(self.block).write(markdown)
            self.assertTrue(header.is_file())
            self.assertTrue(markdown.is_file())


if __name__ == "__main__":
    unittest.main()

