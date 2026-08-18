#!/usr/bin/env python3
"""Run one already-built cocotb benchmark sample."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from cocotb_tools.runner import get_results, get_runner

BENCH = Path(__file__).resolve().parent


def main() -> int:
    build_dir = Path(sys.argv[1]).resolve()
    test_dir = build_dir / f"run-{os.getenv('RUSTDV_BENCH_ITERATION', '0')}"
    test_dir.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(BENCH / "cocotb"))
    results = test_dir / "results.xml"
    get_runner("verilator").test(
        test_module="stream_bench",
        hdl_toplevel="stream_bench",
        hdl_toplevel_lang="verilog",
        build_dir=build_dir,
        test_dir=test_dir,
        results_xml=str(results),
        extra_env=os.environ,
    )
    _, failed = get_results(results)
    return int(failed != 0)


if __name__ == "__main__":
    raise SystemExit(main())
