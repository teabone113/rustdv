#!/usr/bin/env bash
# Direct-cycle smoke, generated-binding freshness, and failure propagation.
set -euo pipefail
cd "$(dirname "$0")/../../../.."

BENCH="benchmarks/stream-throughput"
RUST_BINDINGS="rustdv/benchmarks/stream-cycle/src/bindings.rs"
CPP_BINDINGS="$BENCH/generated/rustdv_cycle_bindings.h"
BUILD="/tmp/rustdv-$(id -u)/stream-cycle-regression"
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-/tmp/rustdv-$(id -u)/target}"

python3 sim/generate_cycle_bindings.py "$BENCH/cycle-schema.json" \
    --rust "$RUST_BINDINGS" --cpp "$CPP_BINDINGS" --check

(cd rustdv && cargo build --release -p rustdv-stream-bench-cycle)
LIB="$CARGO_TARGET_DIR/release/librustdv_stream_bench_cycle.so"
[ -f "$LIB" ] || LIB="$CARGO_TARGET_DIR/release/librustdv_stream_bench_cycle.dylib"

RUSTDV_BENCH_TRANSACTIONS=1000000 RUSTDV_BENCH_SEED=1 \
    RUSTDV_CYCLE_RSS_WARMUP_CYCLE=100000 \
    RUSTDV_CYCLE_MAX_RSS_GROWTH_KIB=16384 \
    sim/run_verilator_cycle.sh "$LIB" "$BENCH/cycle-schema.json" "$CPP_BINDINGS" stream_bench "$BUILD" \
    "$BENCH/hdl/stream_bench.sv"

set +e
failure_output=$(RUSTDV_BENCH_TRANSACTIONS=1000 RUSTDV_BENCH_SEED=1 \
    RUSTDV_BENCH_INJECT_ERROR=1 \
    sim/run_verilator_cycle.sh "$LIB" "$BENCH/cycle-schema.json" "$CPP_BINDINGS" stream_bench "$BUILD" \
    "$BENCH/hdl/stream_bench.sv" 2>&1)
failure_status=$?
set -e

if [ "$failure_status" -eq 0 ] || ! grep -q "BENCHMARK: FAIL backend=rustdv-direct" <<<"$failure_output"; then
    echo "$failure_output" >&2
    echo "CYCLE FAILURE: injected corruption was not propagated" >&2
    exit 1
fi
echo "CYCLE FAILURE: PASS"

case "$(uname -s)" in
    Darwin) cc -dynamiclib -o "$BUILD/abi_mismatch.dylib" \
        output/regression/tests/sim-cycle-verilator/abi_mismatch.c ;;
    Linux) cc -shared -fPIC -o "$BUILD/abi_mismatch.so" \
        output/regression/tests/sim-cycle-verilator/abi_mismatch.c ;;
    *) echo "CYCLE ABI: unsupported POSIX platform" >&2; exit 1 ;;
esac
ABI_LIB="$BUILD/abi_mismatch.dylib"
[ -f "$ABI_LIB" ] || ABI_LIB="$BUILD/abi_mismatch.so"
set +e
abi_output=$("$BUILD/obj_dir/rustdv_cycle_sim" "+rustdv+cycle+$ABI_LIB" 2>&1)
abi_status=$?
set -e
if [ "$abi_status" -eq 0 ] || ! grep -q "ABI header mismatch" <<<"$abi_output"; then
    echo "$abi_output" >&2
    echo "CYCLE ABI: undersized descriptor was not rejected" >&2
    exit 1
fi
echo "CYCLE ABI: PASS"
