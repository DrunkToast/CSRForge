"""Run the public CLI verification workflow for the three v0.1 examples."""

from __future__ import annotations

from pathlib import Path

from csrforge.cli import main as cli_main


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ("basic", "mixed_access", "interrupt")


def main() -> int:
    for name in EXAMPLES:
        print(f"=== Verifying example: {name} ===")
        result = cli_main([
            "verify",
            str(PROJECT_ROOT / "examples" / f"{name}.csv"),
            "-o",
            str(PROJECT_ROOT / "build" / "examples" / name),
        ])
        if result != 0:
            print(f"Example verification failed: {name}")
            return result
    print(f"ALL EXAMPLES PASSED ({len(EXAMPLES)}/{len(EXAMPLES)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

