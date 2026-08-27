"""Prove that the generated TB rejects representative broken RTL variants."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys


def _replace_once(source: str, old: str, new: str, name: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Mutation {name!r} expected one source match, found {count}."
        )
    return source.replace(old, new, 1)


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: run_mutation_tests.py RTL TB OUTPUT_DIR", file=sys.stderr)
        return 2

    rtl_path = Path(sys.argv[1])
    tb_path = Path(sys.argv[2])
    output_dir = Path(sys.argv[3])
    output_dir.mkdir(parents=True, exist_ok=True)
    source = rtl_path.read_text(encoding="utf-8")

    correct_w1c = (
        "irq_status_done_q <= (irq_status_done_q & ~PWDATA[0]) | "
        "irq_status_done_set_i;"
    )
    mutations = (
        (
            "rw_stuck_zero",
            "ctrl_en_o <= PWDATA[0];",
            "ctrl_en_o <= 1'b0;",
        ),
        (
            "w1c_clear_removed",
            correct_w1c,
            "irq_status_done_q <= irq_status_done_q | irq_status_done_set_i;",
        ),
        (
            "w1c_software_clear_wins",
            correct_w1c,
            "irq_status_done_q <= (irq_status_done_q | "
            "irq_status_done_set_i) & ~PWDATA[0];",
        ),
    )

    failures = 0
    for name, old, new in mutations:
        mutant = _replace_once(source, old, new, name)
        mutant_path = output_dir / f"{name}.sv"
        sim_path = output_dir / f"{name}_sim"
        mutant_path.write_text(mutant, encoding="utf-8", newline="\n")

        compile_result = subprocess.run(
            [
                "iverilog",
                "-g2012",
                "-s",
                "csr_regs_tb",
                "-o",
                str(sim_path),
                str(mutant_path),
                str(tb_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if compile_result.returncode != 0:
            failures += 1
            print(f"[FAIL] mutation {name}: RTL no longer compiles")
            print(compile_result.stdout + compile_result.stderr)
            continue

        simulation = subprocess.run(
            ["vvp", str(sim_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if simulation.returncode == 0:
            failures += 1
            print(f"[FAIL] mutation survived generated tests: {name}")
        else:
            print(f"[PASS] mutation killed: {name}")

    if failures:
        print(f"MUTATION TESTS FAILED ({failures}/{len(mutations)})")
        return 1

    print(f"ALL MUTATIONS KILLED ({len(mutations)}/{len(mutations)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

