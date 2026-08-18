#!/usr/bin/env python3
"""Build and compare the cocotb and RustDV stream-throughput testbenches."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import re
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BENCH = Path(__file__).resolve().parent
BUILD_ROOT = Path(os.getenv("RUSTDV_BENCH_BUILD", f"/tmp/rustdv-{os.getuid()}/stream-bench"))
SUMMARY_RE = re.compile(
    r"BENCHMARK: (?P<status>PASS|FAIL) backend=(?P<backend>\S+) "
    r"transactions=(?P<transactions>\d+)(?: cycles=(?P<cycles>\d+) "
    r"digest=(?P<digest>[0-9a-f]+) trace=(?P<trace>[0-9a-f]+) "
    r"elapsed_s=(?P<elapsed>[0-9.]+) "
    r"cycles_per_s=(?P<cps>[0-9.]+)| message=(?P<message>.*))"
)


def command_output(command: list[str]) -> str:
    return subprocess.run(command, check=True, text=True, capture_output=True).stdout.strip()


def cpu_model() -> str:
    if sys.platform == "darwin":
        value = subprocess.run(
            ["sysctl", "-n", "machdep.cpu.brand_string"],
            text=True,
            capture_output=True,
        ).stdout.strip()
        if value:
            return value
    if sys.platform.startswith("linux"):
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    return platform.processor() or "unknown"


def source_diff_sha256() -> str:
    digest = hashlib.sha256()
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD"], check=True, stdout=subprocess.PIPE
    ).stdout
    digest.update(diff)
    untracked = command_output(["git", "ls-files", "--others", "--exclude-standard"])
    for relative in sorted(filter(None, untracked.splitlines())):
        if relative.startswith("benchmarks/stream-throughput/results/"):
            continue
        path = ROOT / relative
        if path.is_file():
            digest.update(relative.encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def parse_summary(output: str) -> dict[str, object]:
    matches = list(SUMMARY_RE.finditer(output))
    if not matches:
        raise RuntimeError(f"benchmark produced no machine-readable summary:\n{output[-4000:]}")
    match = matches[-1]
    result: dict[str, object] = {
        "status": match.group("status").lower(),
        "backend": match.group("backend"),
        "transactions": int(match.group("transactions")),
    }
    if match.group("status") == "PASS":
        result.update(
            cycles=int(match.group("cycles")),
            digest=match.group("digest"),
            trace_digest=match.group("trace"),
            elapsed_s=float(match.group("elapsed")),
            cycles_per_s=float(match.group("cps")),
        )
    else:
        result["message"] = match.group("message")
    return result


def run_process(command: list[str], environment: dict[str, str], expect_failure: bool) -> dict[str, object]:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    summary = parse_summary(completed.stdout)
    expected_status = "fail" if expect_failure else "pass"
    if summary["status"] != expected_status:
        print(completed.stdout, file=sys.stderr)
        raise RuntimeError(
            f"{summary['backend']} reported {summary['status']}, expected {expected_status}"
        )
    if expect_failure and completed.returncode == 0:
        raise RuntimeError(f"{summary['backend']} failure injection returned process success")
    if not expect_failure and completed.returncode != 0:
        print(completed.stdout, file=sys.stderr)
        raise RuntimeError(f"{summary['backend']} exited {completed.returncode}")
    return summary


def benchmark_environment(args: argparse.Namespace) -> dict[str, str]:
    environment = dict(os.environ)
    environment.update(
        RUSTDV_BENCH_TRANSACTIONS=str(args.transactions),
        RUSTDV_BENCH_SEED=str(args.seed),
        RUSTDV_BENCH_INJECT_ERROR="1" if args.inject_error else "0",
        COCOTB_LOG_LEVEL="WARNING",
        COCOTB_REDUCED_LOG_FMT="1",
    )
    compiler_flags = "-Os" if args.rustdv_opt == "default" else "-O3"
    if args.native:
        compiler_flags += " -march=native"
    environment.update(
        OPT_FAST=compiler_flags, OPT_GLOBAL=compiler_flags, OPT_SLOW="-O0"
    )
    return environment


def build_variant(args: argparse.Namespace) -> str:
    machine = "native" if args.native else "portable"
    return f"t{args.threads}-{args.rustdv_opt}-{machine}"


def build_cocotb(args: argparse.Namespace) -> Path:
    from cocotb_tools import config

    build = BUILD_ROOT / f"cocotb-{build_variant(args)}"
    build.mkdir(parents=True, exist_ok=True)
    compiler_flags = "-Os" if args.rustdv_opt == "default" else "-O3"
    if args.native:
        compiler_flags += " -march=native"
    port_control = build / "cocotb-top-ports.vlt"
    port_control.write_text(
        "`verilator_config\npublic_flat_rw -module \"stream_bench\" -port \"*\"\n",
        encoding="utf-8",
    )
    verilator_cpp = config.share_dir / "lib" / "verilator" / "verilator.cpp"
    linker_flags = (
        f"-Wl,-rpath,{config.libs_dir} -L{config.libs_dir} -lcocotbvpi_verilator"
    )
    with patched_environment(benchmark_environment(args)):
        subprocess.run(
            [
                "verilator",
                "--cc",
                "--exe",
                "-sv",
                "--timing",
                "--vpi",
                "--prefix",
                "Vtop",
                "--top-module",
                "stream_bench",
                "--Mdir",
                str(build),
                "-o",
                "stream_bench",
                "--threads",
                str(args.threads),
                "-CFLAGS",
                compiler_flags,
                "-LDFLAGS",
                linker_flags,
                str(port_control),
                str(verilator_cpp),
                str(BENCH / "hdl" / "stream_bench.sv"),
            ],
            cwd=ROOT,
            check=True,
        )
        subprocess.run(
            [
                "make",
                "-C",
                str(build),
                "-f",
                "Vtop.mk",
                "VM_TRACE=0",
                f"OPT_FAST={compiler_flags}",
                f"OPT_GLOBAL={compiler_flags}",
                "OPT_SLOW=-O0",
                "-j",
                str(os.cpu_count() or 1),
            ],
            cwd=ROOT,
            check=True,
        )
    return build


class patched_environment:
    def __init__(self, values: dict[str, str]):
        self.values = values
        self.previous: dict[str, str | None] = {}

    def __enter__(self):
        for key, value in self.values.items():
            self.previous[key] = os.environ.get(key)
            os.environ[key] = value

    def __exit__(self, *_):
        for key, value in self.previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def run_cocotb(
    args: argparse.Namespace, iteration: int, build: Path
) -> dict[str, object]:
    script = BENCH / "run_cocotb.py"
    environment = benchmark_environment(args)
    environment["RUSTDV_BENCH_ITERATION"] = str(iteration)
    return run_process(
        [sys.executable, str(script), str(build)], environment, args.inject_error
    )


def build_rustdv_vpi() -> Path:
    environment = dict(os.environ)
    environment.setdefault("CARGO_TARGET_DIR", f"/tmp/rustdv-{os.getuid()}/target")
    subprocess.run(
        ["cargo", "build", "--release", "-p", "rustdv-stream-bench-vpi"],
        cwd=ROOT / "rustdv",
        env=environment,
        check=True,
    )
    suffix = ".dylib" if sys.platform == "darwin" else ".so"
    return Path(environment["CARGO_TARGET_DIR"]) / "release" / f"librustdv_stream_bench_vpi{suffix}"


def build_rustdv_direct() -> Path:
    environment = dict(os.environ)
    environment.setdefault("CARGO_TARGET_DIR", f"/tmp/rustdv-{os.getuid()}/target")
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "sim" / "generate_cycle_bindings.py"),
            str(BENCH / "cycle-schema.json"),
            "--rust",
            str(ROOT / "rustdv" / "benchmarks" / "stream-cycle" / "src" / "bindings.rs"),
            "--cpp",
            str(BENCH / "generated" / "rustdv_cycle_bindings.h"),
            "--check",
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        ["cargo", "build", "--release", "-p", "rustdv-stream-bench-cycle"],
        cwd=ROOT / "rustdv",
        env=environment,
        check=True,
    )
    suffix = ".dylib" if sys.platform == "darwin" else ".so"
    return Path(environment["CARGO_TARGET_DIR"]) / "release" / f"librustdv_stream_bench_cycle{suffix}"


def run_rustdv_vpi(args: argparse.Namespace, library: Path) -> dict[str, object]:
    environment = benchmark_environment(args)
    environment.update(
        RUSTDV_VERILATOR_THREADS=str(args.threads),
        RUSTDV_VERILATOR_OPT=args.rustdv_opt,
        RUSTDV_VERILATOR_NATIVE="1" if args.native else "0",
    )
    build = BUILD_ROOT / f"rustdv-vpi-{build_variant(args)}"
    return run_process(
        [
            str(ROOT / "sim" / "run_verilator.sh"),
            str(library),
            "stream_bench",
            str(build),
            str(BENCH / "hdl" / "stream_bench.sv"),
        ],
        environment,
        args.inject_error,
    )


def run_rustdv_direct(args: argparse.Namespace, library: Path) -> dict[str, object]:
    environment = benchmark_environment(args)
    environment.update(
        RUSTDV_VERILATOR_THREADS=str(args.threads),
        RUSTDV_VERILATOR_OPT=args.rustdv_opt,
        RUSTDV_VERILATOR_NATIVE="1" if args.native else "0",
    )
    build = BUILD_ROOT / f"rustdv-direct-{build_variant(args)}"
    return run_process(
        [
            str(ROOT / "sim" / "run_verilator_cycle.sh"),
            str(library),
            str(BENCH / "cycle-schema.json"),
            str(BENCH / "generated" / "rustdv_cycle_bindings.h"),
            "stream_bench",
            str(build),
            str(BENCH / "hdl" / "stream_bench.sv"),
        ],
        environment,
        args.inject_error,
    )


def run_cpp_direct(args: argparse.Namespace) -> dict[str, object]:
    environment = benchmark_environment(args)
    environment.update(
        RUSTDV_VERILATOR_THREADS=str(args.threads),
        RUSTDV_VERILATOR_OPT=args.rustdv_opt,
        RUSTDV_VERILATOR_NATIVE="1" if args.native else "0",
    )
    environment["RUSTDV_CPP_BENCH_BUILD"] = str(
        BUILD_ROOT / f"cpp-direct-{build_variant(args)}"
    )
    return run_process(
        [str(BENCH / "run_cpp_direct.sh")], environment, args.inject_error
    )


def summarize(samples: list[dict[str, object]]) -> dict[str, object]:
    passed = [sample for sample in samples if sample["status"] == "pass"]
    if not passed:
        return {"status": "expected-failure", "samples": samples}
    cps = [float(sample["cycles_per_s"]) for sample in passed]
    elapsed = [float(sample["elapsed_s"]) for sample in passed]
    return {
        "status": "pass",
        "backend": passed[0]["backend"],
        "transactions": passed[0]["transactions"],
        "cycles": passed[0]["cycles"],
        "digest": passed[0]["digest"],
        "trace_digest": passed[0]["trace_digest"],
        "median_cycles_per_s": statistics.median(cps),
        "median_elapsed_s": statistics.median(elapsed),
        "samples": samples,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--backend",
        choices=("all", "cocotb", "rustdv-vpi", "rustdv-direct", "cpp-direct"),
        default="all",
    )
    parser.add_argument("--transactions", type=int, default=100_000)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", action="store_true")
    parser.add_argument("--inject-error", action="store_true")
    parser.add_argument("--native", action="store_true")
    parser.add_argument("--threads", type=int, choices=(1, 2, 4), default=1)
    parser.add_argument("--rustdv-opt", choices=("default", "o3"), default="o3")
    parser.add_argument("--minimum-direct-speedup", type=float, default=10.0)
    parser.add_argument("--minimum-cpp-fraction", type=float, default=0.75)
    parser.add_argument("--acceptance", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.transactions <= 0 or args.repeats <= 0:
        parser.error("transactions and repeats must be positive")
    if args.acceptance:
        if args.backend != "all":
            parser.error("--acceptance requires --backend all")
        if args.transactions < 1_000_000:
            parser.error("--acceptance requires at least 1000000 transactions")
        if args.repeats < 3:
            parser.error("--acceptance requires at least 3 measured repetitions")
        if not args.warmup:
            parser.error("--acceptance requires --warmup")
        if args.inject_error:
            parser.error("--acceptance cannot be combined with --inject-error")

    backends = (
        ("cocotb", "rustdv-vpi", "rustdv-direct", "cpp-direct")
        if args.backend == "all"
        else (args.backend,)
    )
    runners = {}
    if "cocotb" in backends:
        build = build_cocotb(args)
        runners["cocotb"] = (
            lambda iteration, build=build: run_cocotb(args, iteration, build)
        )
    if "rustdv-vpi" in backends:
        library = build_rustdv_vpi()
        runners["rustdv-vpi"] = (
            lambda _iteration, library=library: run_rustdv_vpi(args, library)
        )
    if "rustdv-direct" in backends:
        library = build_rustdv_direct()
        runners["rustdv-direct"] = (
            lambda _iteration, library=library: run_rustdv_direct(args, library)
        )
    if "cpp-direct" in backends:
        runners["cpp-direct"] = lambda _iteration: run_cpp_direct(args)

    if args.warmup:
        for name, runner in runners.items():
            print(f"warming {name}", flush=True)
            runner(-1)

    results: dict[str, object] = {}
    for name, runner in runners.items():
        samples = []
        for iteration in range(args.repeats):
            print(f"running {name} {iteration + 1}/{args.repeats}", flush=True)
            sample = runner(iteration)
            samples.append(sample)
            if sample["status"] == "pass":
                print(f"  {sample['cycles_per_s']:.0f} cycles/s", flush=True)
        results[name] = summarize(samples)

    passed = [value for value in results.values() if value["status"] == "pass"]
    target_met = None
    if len(passed) > 1:
        reference = passed[0]
        for candidate in passed[1:]:
            if (
                candidate["cycles"],
                candidate["digest"],
                candidate["trace_digest"],
            ) != (
                reference["cycles"],
                reference["digest"],
                reference["trace_digest"],
            ):
                raise RuntimeError(
                    "backends produced different cycle counts, transaction digests, or cycle traces"
                )
        results["speedups"] = {
            f"{candidate['backend']}_vs_{reference['backend']}": (
                candidate["median_cycles_per_s"] / reference["median_cycles_per_s"]
            )
            for candidate in passed[1:]
        }
        direct_speedup = results["speedups"].get("rustdv-direct_vs_cocotb")
        cpp_speedup = results["speedups"].get("cpp-direct_vs_cocotb")
        if direct_speedup is not None and cpp_speedup is not None:
            cpp_fraction = direct_speedup / cpp_speedup
            speedup_met = direct_speedup >= args.minimum_direct_speedup
            cpp_fraction_met = cpp_fraction >= args.minimum_cpp_fraction
            gate = {
                "minimum_direct_speedup": args.minimum_direct_speedup,
                "actual_direct_speedup": direct_speedup,
                "direct_speedup_met": speedup_met,
                "minimum_cpp_fraction": args.minimum_cpp_fraction,
                "actual_cpp_fraction": cpp_fraction,
                "cpp_fraction_met": cpp_fraction_met,
            }
            if args.acceptance:
                target_met = speedup_met and cpp_fraction_met
                gate["met"] = target_met
                results["target"] = gate
            else:
                gate["would_meet"] = speedup_met and cpp_fraction_met
                results["exploratory_target"] = gate

    document = {
        "schema": "rustdv.stream-throughput-benchmark/v1",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_revision": command_output(["git", "rev-parse", "HEAD"]),
        "source_diff_sha256": source_diff_sha256(),
        "working_tree_dirty": bool(command_output(["git", "status", "--porcelain"])),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_model": cpu_model(),
        "python": sys.version.split()[0],
        "cocotb": importlib.metadata.version("cocotb"),
        "rustc": command_output(["rustc", "--version"]),
        "cxx": command_output(["c++", "--version"]).splitlines()[0],
        "verilator": command_output(["verilator", "--version"]),
        "configuration": {
            "acceptance": args.acceptance,
            "transactions": args.transactions,
            "seed": args.seed,
            "repeats": args.repeats,
            "native": args.native,
            "threads": args.threads,
            "rustdv_opt": args.rustdv_opt,
            "inject_error": args.inject_error,
            "minimum_direct_speedup": args.minimum_direct_speedup,
            "minimum_cpp_fraction": args.minimum_cpp_fraction,
            "measurement": "median simulator/testbench elapsed time; build excluded",
            "visibility": "top-level ports only",
            "cocotb_opt": args.rustdv_opt,
        },
        "results": results,
    }
    rendered = json.dumps(document, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    return 0 if target_met is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
