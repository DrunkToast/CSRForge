# CSRForge

[![CI](https://github.com/DrunkToast/CSRForge/actions/workflows/ci.yml/badge.svg)](https://github.com/DrunkToast/CSRForge/actions/workflows/ci.yml)

**Status:** CSRForge v0.1 is complete; the full local and GitHub Actions
regressions pass.

CSRForge compiles a strict CSV register specification into a synthesizable
32-bit APB3 CSR slave, a self-checking SystemVerilog testbench, a C header,
JSON IR, and Markdown documentation.

The defining workflow is **spec-to-simulation**, not only spec-to-RTL:

```text
CSV → Parser → Semantic Checker → Canonical IR
                                  ├─ SystemVerilog RTL
                                  ├─ Self-checking SV TB
                                  ├─ C Header
                                  ├─ Markdown Register Map
                                  └─ JSON
                                           ↓
                                   Icarus PASS / FAIL
```

CSRForge is deterministic and has no runtime LLM or API dependency.

## AI-assisted development

CSRForge was developed with AI coding-agent assistance for requirement 
decomposition, implementation, test construction, debugging, and refactoring.

Protocol semantics and acceptance criteria were defined in a written 
specification and enforced through hand-written Golden RTL/TB, 
cross-checking generated RTL against the Golden TB, mutation testing, 
and continuous integration. 
CSRForge itself is deterministic and has no runtime LLM or API dependency.


## v0.1 scope

- 32-bit APB3 slave using local byte offsets
- 4-byte aligned registers
- `PREADY` always high; no wait states
- active-low asynchronous reset
- `RW`, `RO`, and `W1C` fields
- mixed-access registers and reserved-bit handling
- hardware-set priority over software clear for W1C fields
- strict CSV input
- Icarus functional simulation
- optional Verilator lint during development

See [SPEC.md](SPEC.md) for the normative behavior and explicit exclusions.

## Requirements

- Python 3.10 or newer
- Icarus Verilog (`iverilog` and `vvp`) for `verify`
- Verilator for repository development checks

On Ubuntu/WSL:

```bash
sudo apt update
sudo apt install -y iverilog verilator
```

## Quick start

Run directly from a source checkout:

```bash
python3 -m csrforge check examples/basic.csv
python3 -m csrforge generate examples/basic.csv -o build/basic
python3 -m csrforge verify examples/basic.csv -o build/basic
```

Or install the local command:

```bash
python3 -m pip install -e .
csrforge verify examples/basic.csv -o build/basic
```

A successful verification ends with output similar to:

```text
[PASS] CTRL.ENABLE RW ONE
[PASS] STATUS.READY RO WRITE IGNORED
ALL GENERATED TESTS PASSED
```

Any failed check returns a non-zero process exit code.

## CSV format

The header must be exactly:

```csv
Register,Offset,Field,Bits,Access,Reset
```

Example:

```csv
Register,Offset,Field,Bits,Access,Reset
CTRL,0x00,ENABLE,0,RW,0
CTRL,0x00,MODE,2:1,RW,0
STATUS,0x04,READY,0,RO,0
IRQ_STATUS,0x08,DONE,0,W1C,0
```

Register and field identifiers must match `[A-Za-z_][A-Za-z0-9_]*`.
Uncovered bits are reserved, read as zero, and ignore writes.

## Commands

```text
csrforge check SPEC.csv
csrforge dump-ir SPEC.csv
csrforge generate SPEC.csv -o OUTPUT_DIR
csrforge verify SPEC.csv -o OUTPUT_DIR
```

Use `--block-name NAME` to change the generated module and file base name.

`generate` writes:

```text
NAME.sv       generated APB3 CSR RTL
NAME_tb.sv    generated self-checking testbench
NAME.h        C register macros
NAME.md       Markdown register map
NAME.json     canonical machine-readable IR
```

## Examples

- `examples/basic.csv`: RW control and RO status
- `examples/mixed_access.csv`: RW, RO, W1C, and reserved bits in one register
- `examples/interrupt.csv`: multi-field W1C status and RW enable registers
- `examples/golden.csv`: fixed map used by the independent Golden TB

## Verification strategy

The hand-written Golden RTL and Golden TB establish the reference behavior.
Generated RTL must pass the independently maintained Golden TB before generated
verification is trusted. The generated testbench does not import or call the
RTL generator's access-semantic implementation.

Repository mutation tests deliberately inject three RTL faults:

- RW stuck at zero
- W1C clear removed
- software clear incorrectly winning over hardware set

All three must be rejected by the generated testbench.

Run the complete repository regression in WSL/Linux:

```bash
make check
```

## Continuous integration

The GitHub Actions workflow runs the same quality gates on Ubuntu for every
push and pull request:

- Python parser, IR, checker, and generator tests
- Verilator lint of hand-written and generated RTL
- Golden RTL simulation
- generated RTL against the independent Golden TB
- generated RTL against the generated self-checking TB
- mutation tests and all public examples

The workflow can also be started manually. A CI badge will be added after the
repository has a final GitHub owner and URL.

## Explicit v0.1 exclusions

CSRForge v0.1 does not support AXI4-Lite, AHB-Lite, APB wait states,
`PSTRB`, Excel/YAML input, UVM, CDC insertion, base-address decoding, GUI,
or runtime AI/LLM features.
