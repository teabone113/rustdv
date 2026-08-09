#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
BENCH="$ROOT/benchmarks/stream-throughput"
BUILD=${RUSTDV_CPP_BENCH_BUILD:-/tmp/rustdv-${UID}/stream-bench/cpp-direct-t${RUSTDV_VERILATOR_THREADS:-1}}
OBJ="$BUILD/obj_dir"
THREADS=${RUSTDV_VERILATOR_THREADS:-1}
OPT=${RUSTDV_VERILATOR_OPT:-o3}
NATIVE=${RUSTDV_VERILATOR_NATIVE:-0}

case "$OPT" in
    default) OPT_FAST=-Os; OPT_GLOBAL=-Os; OPT_SLOW=-Os ;;
    o3) OPT_FAST=-O3; OPT_GLOBAL=-O3; OPT_SLOW=-O0 ;;
    *) echo "RUSTDV_VERILATOR_OPT must be default or o3" >&2; exit 2 ;;
esac
if [[ "$NATIVE" == 1 ]]; then
    OPT_FAST="$OPT_FAST -march=native"
    OPT_GLOBAL="$OPT_GLOBAL -march=native"
fi

mkdir -p "$BUILD"
verilator --cc --exe -sv \
    --prefix Vrustdv_dut \
    --top-module stream_bench \
    --threads "$THREADS" \
    -Mdir "$OBJ" \
    -CFLAGS "-std=c++17 -I$BENCH/generated" \
    -o cpp_direct_bench \
    "$BENCH/hdl/stream_bench.sv" \
    "$BENCH/cpp/stream_bench_main.cpp"
make -C "$OBJ" -f Vrustdv_dut.mk \
    OPT_FAST="$OPT_FAST" OPT_GLOBAL="$OPT_GLOBAL" OPT_SLOW="$OPT_SLOW" \
    -j "${RUSTDV_VERILATOR_JOBS:-$(sysctl -n hw.logicalcpu 2>/dev/null || nproc 2>/dev/null || echo 1)}"
"$OBJ/cpp_direct_bench"
