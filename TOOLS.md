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
| `framework` | `--public-flat-rw` | off | Small rustdv scheduler/handle probes only |

FAST does not use global `--public-flat-rw`. The build generates a control
file under `/tmp` that marks only the selected top module's ports for VPI.
DEBUG requires `RUSTDV_VERILATOR_CONTROL_FILE`; the TinyALU entry point
defaults it to `sim/verilator-debug.vlt`. Framework mode is deliberately
expensive and must not be copied into a large DUT flow.

```sh
# Four-state reference, and the source of exact book transcripts.
sim/run_rustdv.sh release icarus

# Two-state FAST regression.
sim/run_rustdv.sh release verilator

# Selected internals plus /tmp/.../tinyalu.fst.
RUSTDV_VERILATOR_MODE=debug sim/run_rustdv.sh release verilator
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

## Callback handle ownership

Icarus and Verilator agree on callback scheduling but not on the returned VPI
handle after a one-shot fires. Icarus reaps the active callback object when the
callback returns. Verilator removes the scheduled record but retains the
separate handle object until the user releases it. RustDV therefore removes a
fired one-shot from inside its trampoline, while the handle is valid on both
simulators. Dropping an unfired or recurring callback retains the normal RAII
remove behavior. Detaching a callback gives up only the Rust owner: a one-shot
still self-cleans when it fires.

`sim-callback-lifecycle-verilator` runs one million ReadOnly/NextTimeStep
iterations and samples the simulator process after a warm-up period. It fails
if callback RSS continues growing instead of reaching a plateau.

## Direct cycle backend

Long, synchronous, two-state workloads may use the optional direct cycle
backend instead of VPI. Its public Rust contract is value-oriented:

```rust
fn step(inputs: &CycleInputs, outputs: &mut CycleOutputs) -> CycleStatus;
```

`sim/generate_cycle_bindings.py` consumes one JSON schema and emits both the
Rust `#[repr(C)]` structures and the C++ top-port adapter. The loader rejects
ABI-version, structure-size, alignment, or schema-hash mismatches before the
first cycle. Shared ABI fields are fixed-width integers; Rust `bool` is not
accepted by the generator.

The ABI descriptor is library-owned and begins with an immutable eight-byte
version/size prefix, so the host can reject an older or newer descriptor
without first writing through an assumed layout. Before compilation, the run
wrapper compares the schema's top, complete port set, directions, signedness,
and exact logical widths against Verilator's elaborated JSON metadata.

The first direct backend deliberately supports one synchronous clock,
top-level two-state ports, and driving/sampling at cycle boundaries. Arbitrary
timers, multiple independently scheduled clocks, X/Z-sensitive behavior,
combinational feedback through Rust, and dynamic hierarchical access remain on
VPI. The direct host returns nonzero on `CycleStatus::Fail`; it does not depend
on transcript parsing for its verdict.

`rustdv::run_cycle_model_vpi` is the portable adapter for the same public
`CycleModel` contract. Generated or handwritten sample/drive closures map VPI
handles to value structs, so a cycle model can keep VPI as its fallback without
embedding simulator handles in protocol or scoreboard logic.

FAST compiler and model-thread controls are measured options:

```sh
RUSTDV_VERILATOR_OPT=o3 RUSTDV_VERILATOR_THREADS=1 \
    sim/run_verilator_cycle.sh <library> <schema> <bindings.h> <top> <build> <hdl...>

# Local-machine experiment only; not a portable default.
RUSTDV_VERILATOR_NATIVE=1 RUSTDV_VERILATOR_THREADS=2 ...
```

Use `default|o3` for `RUSTDV_VERILATOR_OPT` and `1|2|4` model threads. More
optimization or threads are not assumed to help; record the fastest repeated
configuration for the actual model. `-march=native` remains explicitly opt-in.

The stream-throughput acceptance harness under `benchmarks/` runs identical
checking through cocotb, RustDV VPI, RustDV direct, and an equivalent direct
C++ control loop. Its one-million-transaction reference run requires RustDV
direct to exceed cocotb by 10x and reach at least 75% of direct C++ throughput.
It compares cycle count, accepted-transaction digest, and a per-cycle boundary
trace digest before evaluating either performance gate.
The direct-cycle regression also samples simulator RSS after 100,000 cycles
of a one-million-transaction run and rejects more than 16 MiB of subsequent
growth.

Verilator references:

- [VPI integration](https://verilator.org/guide/latest/connecting.html#verification-procedural-interface-vpi)
- [Control files and selected visibility](https://verilator.org/guide/latest/control.html)
- [Simulation runtime and FST](https://verilator.org/guide/latest/exe_sim.html)
