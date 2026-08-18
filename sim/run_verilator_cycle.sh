#!/usr/bin/env bash
# Build and run a generated direct-cycle RustDV testbench.
# Usage: run_verilator_cycle.sh <cycle-library> <schema> <bindings-header> <top> <build-dir> <hdl...>
set -euo pipefail

if [ "$#" -lt 6 ]; then
    echo "usage: $0 <cycle-library> <schema> <bindings-header> <top> <build-dir> <hdl...>" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LIB="$1"
SCHEMA="$2"
BINDINGS="$3"
TOP="$4"
BUILD="$5"
shift 5
HDL=("$@")

if [ ! -f "$LIB" ]; then
    echo "rustdv-cycle: library not found: $LIB" >&2
    exit 2
fi
if [ ! -f "$SCHEMA" ]; then
    echo "rustdv-cycle: schema not found: $SCHEMA" >&2
    exit 2
fi
if [ ! -f "$BINDINGS" ]; then
    echo "rustdv-cycle: generated bindings not found: $BINDINGS" >&2
    exit 2
fi
if [[ ! "$TOP" =~ ^[A-Za-z_][A-Za-z0-9_\$]*$ ]]; then
    echo "rustdv-cycle: unsupported top-module name: $TOP" >&2
    exit 2
fi

THREADS="${RUSTDV_VERILATOR_THREADS:-1}"
case "$THREADS" in
    1|2|4) ;;
    *) echo "rustdv-cycle: RUSTDV_VERILATOR_THREADS must be 1, 2, or 4" >&2; exit 2 ;;
esac

case "${RUSTDV_VERILATOR_OPT:-o3}" in
    default) OPT_FAST="-Os" ;;
    o3) OPT_FAST="-O3" ;;
    *) echo "rustdv-cycle: RUSTDV_VERILATOR_OPT must be default or o3" >&2; exit 2 ;;
esac
if [ "${RUSTDV_VERILATOR_NATIVE:-0}" = 1 ]; then
    OPT_FAST="$OPT_FAST -march=native"
fi

mkdir -p "$BUILD"
OBJ="$BUILD/obj_dir"
mkdir -p "$OBJ"
cp "$BINDINGS" "$OBJ/rustdv_cycle_bindings.h"

AST="$BUILD/rustdv-cycle.tree.json"
AST_META="$BUILD/rustdv-cycle.tree.meta.json"
verilator --json-only -sv --top-module "$TOP" \
    --json-only-output "$AST" --json-only-meta-output "$AST_META" "${HDL[@]}"
python3 "$SCRIPT_DIR/generate_cycle_bindings.py" "$SCHEMA" \
    --cpp "$BINDINGS" --check --verilator-json "$AST"

VERILATOR_ARGS=(
    --cc --exe -sv
    --prefix Vrustdv_dut
    --top-module "$TOP"
    --Mdir "$OBJ"
    --threads "$THREADS"
    -CFLAGS "$OPT_FAST"
    -o rustdv_cycle_sim
)
if [ "$(uname -s)" = Linux ]; then
    VERILATOR_ARGS+=(-LDFLAGS "-ldl")
fi

verilator "${VERILATOR_ARGS[@]}" "${HDL[@]}" "$SCRIPT_DIR/verilator_cycle_main.cpp"

make -C "$OBJ" -f Vrustdv_dut.mk -j "${RUSTDV_VERILATOR_JOBS:-1}" \
    OPT_FAST="$OPT_FAST" OPT_GLOBAL="$OPT_FAST" OPT_SLOW="-O0"

"$OBJ/rustdv_cycle_sim" "+rustdv+cycle+$LIB"
