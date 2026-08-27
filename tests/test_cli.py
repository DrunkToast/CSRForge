from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest

from csrforge.cli import main


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_CSV = PROJECT_ROOT / "examples" / "golden.csv"


class CliTests(unittest.TestCase):
    def test_check_valid_spec(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            result = main(["check", str(GOLDEN_CSV)])
        self.assertEqual(result, 0)
        self.assertIn("4 register(s), 7 field(s)", stdout.getvalue())

    def test_dump_ir(self):
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            result = main(["dump-ir", str(GOLDEN_CSV)])
        self.assertEqual(result, 0)
        self.assertIn('"name": "csr_regs"', stdout.getvalue())

    def test_generate_writes_all_v01_artifacts(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with redirect_stdout(io.StringIO()):
                result = main([
                    "generate",
                    str(GOLDEN_CSV),
                    "-o",
                    temp_dir,
                ])
            self.assertEqual(result, 0)
            self.assertEqual(
                {path.name for path in Path(temp_dir).iterdir()},
                {
                    "csr_regs.sv",
                    "csr_regs_tb.sv",
                    "csr_regs.h",
                    "csr_regs.md",
                    "csr_regs.json",
                },
            )

    def test_invalid_spec_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            spec = Path(temp_dir) / "invalid.csv"
            spec.write_text(
                "Register,Offset,Field,Bits,Access,Reset\n"
                "CTRL,0x02,EN,0,RW,0\n",
                encoding="utf-8",
            )
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = main(["check", str(spec)])
            self.assertEqual(result, 2)
            self.assertIn("not 4-byte aligned", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()

