"""Generate the Stage 3 RTL artifact from the Golden CSV specification."""

from __future__ import annotations

from pathlib import Path
import sys

from csrforge import CsvParser, RtlGenerator, SemanticChecker


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    output = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else PROJECT_ROOT / "build" / "generated" / "csr_regs.sv"
    )
    block = CsvParser(PROJECT_ROOT / "examples" / "golden.csv").parse()
    SemanticChecker().validate(block)
    RtlGenerator(block).write(output)
    print(f"Generated {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

