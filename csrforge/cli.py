"""Command-line interface for CSRForge v0.1."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

from .checker import SemanticChecker, ValidationError
from .generator_doc import MarkdownGenerator
from .generator_header import CHeaderGenerator
from .generator_rtl import RtlGenerator
from .generator_test import TestbenchGenerator
from .model import RegisterBlock
from .parser_csv import CsvParser, ParseError


def _load(spec: str | Path, block_name: str) -> RegisterBlock:
    block = CsvParser(spec, block_name=block_name).parse()
    return SemanticChecker().validate(block)


def _write_artifacts(block: RegisterBlock, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "rtl": output_dir / f"{block.name}.sv",
        "tb": output_dir / f"{block.name}_tb.sv",
        "header": output_dir / f"{block.name}.h",
        "markdown": output_dir / f"{block.name}.md",
        "json": output_dir / f"{block.name}.json",
    }
    RtlGenerator(block).write(paths["rtl"])
    TestbenchGenerator(block).write(paths["tb"])
    CHeaderGenerator(block).write(paths["header"])
    MarkdownGenerator(block).write(paths["markdown"])
    paths["json"].write_text(block.to_json(), encoding="utf-8", newline="\n")
    return paths


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="csrforge",
        description="Compile a CSV CSR specification into RTL and executable verification.",
    )
    parser.add_argument("--version", action="version", version="CSRForge 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_spec_arguments(command: argparse.ArgumentParser) -> None:
        command.add_argument("spec", help="Path to the strict v0.1 CSV specification")
        command.add_argument(
            "--block-name",
            default="csr_regs",
            help="Generated module/file base name (default: csr_regs)",
        )

    check = subparsers.add_parser("check", help="Parse and validate a CSV spec")
    add_spec_arguments(check)

    dump_ir = subparsers.add_parser("dump-ir", help="Print validated JSON IR")
    add_spec_arguments(dump_ir)

    generate = subparsers.add_parser("generate", help="Generate all v0.1 artifacts")
    add_spec_arguments(generate)
    generate.add_argument("-o", "--output-dir", required=True)

    verify = subparsers.add_parser(
        "verify", help="Generate artifacts and run self-checking Icarus simulation"
    )
    add_spec_arguments(verify)
    verify.add_argument("-o", "--output-dir", default="build/csrforge")
    return parser


def _run_verify(paths: dict[str, Path], block_name: str) -> int:
    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    if not iverilog or not vvp:
        print(
            "ERROR: csrforge verify requires both 'iverilog' and 'vvp' in PATH.",
            file=sys.stderr,
        )
        return 2

    simulation = paths["rtl"].parent / f"{block_name}_sim"
    compile_result = subprocess.run(
        [
            iverilog,
            "-g2012",
            "-s",
            f"{block_name}_tb",
            "-o",
            str(simulation),
            str(paths["rtl"]),
            str(paths["tb"]),
        ],
        check=False,
    )
    if compile_result.returncode != 0:
        return compile_result.returncode

    return subprocess.run([vvp, str(simulation)], check=False).returncode


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    try:
        block = _load(args.spec, args.block_name)
        if args.command == "check":
            field_count = sum(len(register.fields) for register in block.registers)
            print(
                f"PASS: {args.spec} contains {len(block.registers)} register(s), "
                f"{field_count} field(s)."
            )
            return 0
        if args.command == "dump-ir":
            print(block.to_json(), end="")
            return 0

        output_dir = Path(args.output_dir)
        paths = _write_artifacts(block, output_dir)
        for artifact, path in paths.items():
            print(f"Generated {artifact}: {path}")

        if args.command == "generate":
            return 0
        return _run_verify(paths, block.name)
    except (ParseError, ValidationError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

