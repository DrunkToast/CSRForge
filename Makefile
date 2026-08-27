RTL := verification/golden/csr_regs.sv
TB  := verification/golden/csr_regs_tb.sv
SIM := build/csr_regs_sim
GEN_RTL := build/generated/csr_regs.sv
GEN_TB := build/generated/csr_regs_tb.sv
GEN_GOLDEN_SIM := build/generated/csr_regs_golden_tb_sim
GEN_SELF_SIM := build/generated/csr_regs_self_tb_sim

.PHONY: check lint sim python-test generated-check generated-lint generated-golden-sim generated-self-sim mutation-test examples-verify

check: lint sim python-test generated-check examples-verify

lint:
	verilator --lint-only --Wall -Wno-fatal --top-module csr_regs $(RTL)

sim: $(SIM)
	vvp $(SIM)

python-test:
	python3 -m unittest discover -s tests -v

generated-check: generated-lint generated-golden-sim generated-self-sim mutation-test

generated-lint: $(GEN_RTL)
	verilator --lint-only --Wall -Wno-fatal --top-module csr_regs $(GEN_RTL)

generated-golden-sim: $(GEN_GOLDEN_SIM)
	vvp $(GEN_GOLDEN_SIM)

generated-self-sim: $(GEN_SELF_SIM)
	vvp $(GEN_SELF_SIM)

mutation-test: $(GEN_RTL) $(GEN_TB) scripts/run_mutation_tests.py
	python3 -m scripts.run_mutation_tests $(GEN_RTL) $(GEN_TB) build/mutations

examples-verify:
	python3 -m scripts.verify_examples

$(GEN_RTL): examples/golden.csv scripts/generate_golden_rtl.py $(wildcard csrforge/*.py)
	python3 -m scripts.generate_golden_rtl $(GEN_RTL)

$(GEN_TB): examples/golden.csv scripts/generate_golden_tb.py $(wildcard csrforge/*.py)
	python3 -m scripts.generate_golden_tb $(GEN_TB)

$(GEN_GOLDEN_SIM): $(GEN_RTL) $(TB)
	iverilog -g2012 -s csr_regs_tb -o $(GEN_GOLDEN_SIM) $(GEN_RTL) $(TB)

$(GEN_SELF_SIM): $(GEN_RTL) $(GEN_TB)
	iverilog -g2012 -s csr_regs_tb -o $(GEN_SELF_SIM) $(GEN_RTL) $(GEN_TB)

$(SIM): $(RTL) $(TB)
	mkdir -p build
	iverilog -g2012 -s csr_regs_tb -o $(SIM) $(RTL) $(TB)
