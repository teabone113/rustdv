# Stream throughput benchmark

This benchmark measures simulator/testbench boundary cost with the same
deterministic ready/valid workload in cocotb, RustDV VPI and RustDV direct
cycle mode. An equivalent direct C++ loop establishes the simulator-only
ceiling. Every implementation checks accepted
transfers, all payload sidebands, stalls, a DUT-maintained transfer counter,
and a final digest. Build time is excluded from each testbench's reported
elapsed time.

The benchmark is intentionally a cheap RTL model so testbench overhead is
visible. It is not a claim about every DUT: large Verilated models can become
evaluation- or cache-limited.

Use a Python environment containing the pinned package in `requirements.txt`:

```sh
/path/to/python benchmarks/stream-throughput/run.py \
  --backend all --transactions 1000000 --repeats 3 --warmup \
  --native --threads 1 --rustdv-opt o3 --acceptance
```

`--backend all` requires the direct backend to reach at least 10x cocotb by
default and at least 75% of the equivalent C++ loop; change the explicit gates
with `--minimum-direct-speedup` and `--minimum-cpp-fraction`. The checked-in
pre-change result under `results/` was captured before any runtime or VPI
optimization, against framework revision `3038cdd`.
`--acceptance` additionally rejects a run with fewer than one million
transactions, fewer than three measured repetitions, no warmup, or an
incomplete backend set.

On the Apple M1 Pro reference machine with Verilator 5.050, cocotb 2.0.1,
Rust 1.97.0 and Apple Clang 17, the one-million transaction run completed the
same 1,209,415 active cycles, accepted-transaction digest
`f2a1c4267802b565`, and per-cycle trace digest `57e0f80eafd04513`
in every backend. Three-sample medians were:

| Backend | Cycles/s | Versus cocotb |
|---|---:|---:|
| cocotb | 16,773 | 1.00x |
| RustDV VPI | 374,379 | 22.32x |
| RustDV direct | 14,704,611 | 876.68x |
| direct C++ | 17,487,709 | 1,042.61x |

RustDV direct reached 84.09% of the equivalent C++ ceiling. One model thread
was fastest for this cheap DUT: RustDV direct measured 14.70M, 11.29M, and
11.55M cycles/s with one, two, and four threads respectively. Portable `-O3`
measured 15.44M cycles/s versus 13.13M with the default `-Os`; `-march=native`
remains an explicit local-only option. Raw samples and configurations are in
`results/`.

The matched 100,000-transaction files isolate the low-risk VPI work from the
new direct backend. Before vector-valued access and cycle-agent write/read
suppression, RustDV VPI measured 205,293 cycles/s and 8.76x cocotb. After
those changes it measured 379,795 cycles/s and 15.02x cocotb. The longer table
above is the acceptance result; the shorter pair is retained only as the
pre/post optimization evidence.

Failure injection must produce process failure in all four implementations:

```sh
/path/to/python benchmarks/stream-throughput/run.py \
  --backend all --transactions 1000 --repeats 1 --inject-error
```

The JSON output records the Git revision and source-diff hash, tool versions,
workload, individual samples, median cycles/second, transaction and trace
digests, cycle count, and cross-backend speedup.

The port ABI is authored once in `cycle-schema.json`. Regenerate both sides
after changing it:

```sh
python3 sim/generate_cycle_bindings.py \
  benchmarks/stream-throughput/cycle-schema.json \
  --rust rustdv/benchmarks/stream-cycle/src/bindings.rs \
  --cpp benchmarks/stream-throughput/generated/rustdv_cycle_bindings.h
```
