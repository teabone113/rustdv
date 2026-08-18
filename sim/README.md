# Simulator scaffold

The TinyALU DUT, the shared Verilator host, and smoke/regression entry points.
Both free simulators are exercised in CI so the native VPI loading path cannot
rot unnoticed.

## Files

- `hdl/tinyalu.sv` — the TinyALU derived from the pyuvm project
  (`reference/pyuvm-master/examples/TinyALU/hdl/verilog/tinyalu.sv`,
  Apache-2.0, © Ray Salemi). Its self-generated clock is exposed as a
  read-only top-level port so a FAST VPI testbench needs no internal visibility.
- `tb/smoke_tb.sv` — minimal self-checking testbench: five operations,
  prints `SMOKE: PASS` on success.
- `run_smoke.sh` — HDL-only simulator selector.
- `run_rustdv.sh` — builds and runs the Rust TinyALU testbench.
- `run_verilator.sh` / `verilator_main.cpp` — shared Verilator build wrapper
  and correctness-critical event loop.
- `verilator-debug.vlt` — TinyALU's deliberately selected DEBUG internals.

## Running

| Simulator | Command | Notes |
|---|---|---|
| Icarus Verilog | `sim/run_smoke.sh icarus` | free; runs in CI |
| Verilator | `sim/run_smoke.sh verilator` | free; runs the self-checking RTL smoke test in CI |
| Synopsys VCS | `sim/run_smoke.sh vcs` | needs license; run locally |
| Siemens Questa | `sim/run_smoke.sh questa` | needs license; run locally |
| Cadence Xcelium | `sim/run_smoke.sh xcelium` | needs license; run locally |

The same tests run through the regression system
(`output/regression/regress.py --suite custom --filter sim`) and skip
automatically on machines without the simulator installed.

Run the Rust testbench with either backend:

```sh
sim/run_rustdv.sh release icarus
sim/run_rustdv.sh release verilator
RUSTDV_VERILATOR_MODE=debug sim/run_rustdv.sh release verilator
RUSTDV_VERILATOR_MODE=inspect sim/run_rustdv.sh release verilator
```

DEBUG writes an FST under `/tmp/rustdv-$(id -u)/`. FAST exposes only top-level
ports; DEBUG adds the signals in a Verilator control file and an FST; INSPECT
adds the same selected VPI visibility without building or emitting a waveform.
The small framework probe alone uses full visibility. See [`TOOLS.md`](../TOOLS.md)
for the scheduling contract, simulator controls, and two-state/four-state
boundary.

Commercial-simulator invocations are the standard ones but **untested here**
— public CI cannot hold EDA licenses. If you have a license and the command
needs adjusting for your site, that's expected; the testbench itself is
plain SystemVerilog and should run anywhere.

## Why no EDA Playground?

EDA Playground runs SystemVerilog and Python/cocotb, but has no Rust
toolchain, so rustdv testbenches can't execute there. The HDL side (this
DUT, this smoke test) pastes into EDA Playground fine. For the book's
pure-Rust figures, use the per-figure Rust Playground links in the chapter
READMEs, or open the repo in GitHub Codespaces for the full environment.
