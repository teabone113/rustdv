# Tool contract

This file is the durable simulator contract for rustdv. The scripts are the
executable source of truth; this records why each tool is present and which
results may be compared.

| Tool | Role | Required behavior |
|---|---|---|
| Icarus Verilog | Four-state framework reference and book transcript source | SystemVerilog 2012, VPI modules, X/Z propagation |
| Verilator 5.050 | FAST two-state functional simulation | timing support, VPI, POSIX runtime VPI loading |
| Rust toolchain | Builds testbench cdylibs and unit tests | Pinned by `rust-toolchain.toml` |
| FST + GTKWave | DEBUG waveform path | Built with Verilator `--trace-fst`; `liblz4` development files are required |

CI and the development container build the checksum-pinned Verilator release
with `ci/install-verilator.sh`. A newer local Verilator may work, but 5.050 is
the compatibility floor because that release added the runtime
`+verilator+vpi+<library>` loader used by rustdv. Runtime loading is POSIX-only;
use Linux, macOS, or WSL rather than native Windows.

## Verilator modes

| Mode | VPI visibility | Trace | Intended use |
|---|---|---|---|
| `fast` | Ports of the selected top module only | off | Normal functional regression |
| `debug` | Top ports plus internals selected by a `.vlt` control file | FST | Focused diagnosis |
| `record` | Top ports plus optional `.vlt` selections | runtime-gated all-signal FST | MCP/history capture only while armed |
| `inspect` | Top ports plus internals selected by a `.vlt` control file | off | Live VPI diagnosis without waveform instrumentation |
| `framework` | `--public-flat-rw` | off | Small rustdv scheduler/handle probes only |

FAST does not use global `--public-flat-rw`. The build generates a control
file under `/tmp` that marks only the selected top module's ports for VPI.
DEBUG and INSPECT require `RUSTDV_VERILATOR_CONTROL_FILE`; the TinyALU entry
point defaults it to `sim/verilator-debug.vlt`. RECORD accepts the same selected
VPI control file but FST itself retains all traceable signals. It creates no
file and records no samples until runtime control calls `start`, and it closes
the capture synchronously on `stop`. Framework mode is deliberately expensive
and must not be copied into a large DUT flow.

```sh
# Four-state reference, and the source of exact book transcripts.
sim/run_rustdv.sh release icarus

# Two-state FAST regression.
sim/run_rustdv.sh release verilator

# Selected internals plus /tmp/.../tinyalu.fst.
RUSTDV_VERILATOR_MODE=debug sim/run_rustdv.sh release verilator

# Runtime-gated capture for a debug service; no FST is opened by this command alone.
RUSTDV_VERILATOR_MODE=record sim/run_rustdv.sh release verilator
```

Verilator cannot model general X/Z propagation. Randomizing initial values is
useful stress but is not a four-state substitute, so X/Z framework cases and
exact transcript comparisons remain Icarus-only. Codec and other functional
testbenches must still reset and initialize every state element explicitly.

The shared host is `sim/verilator_main.cpp`. Its phase contract is:

```text
earliest RTL event or VPI timer
  -> timed callbacks
  -> RTL evaluation and value-change callbacks
  -> ReadWrite callbacks
  -> re-evaluate after VPI writes until settled
  -> ReadOnly callbacks
```

It also invokes start/end callbacks, `final()`, honors `vpiFinish`, bounds
fixed-point settling, and selects the next deadline from both the RTL and VPI
queues. `sim/run_verilator.sh` treats `REGRESSION: FAIL` or a missing verdict
as a process failure because Verilator's `vpiFinish` path itself returns zero.

Verilator references:

- [VPI integration](https://verilator.org/guide/latest/connecting.html#verification-procedural-interface-vpi)
- [Control files and selected visibility](https://verilator.org/guide/latest/control.html)
- [Simulation runtime and FST](https://verilator.org/guide/latest/exe_sim.html)
