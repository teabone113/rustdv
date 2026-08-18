import os
import time

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import NextTimeStep, ReadOnly, RisingEdge

MASK64 = (1 << 64) - 1
RESET_CYCLES = 4
DATA_XOR = 0xD6E8FEB86659FD93
DATA_ADD = 0xA5A55A5A12345678


def mix64(value: int) -> int:
    value = (value + 0x9E3779B97F4A7C15) & MASK64
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK64
    return (value ^ (value >> 31)) & MASK64


def payload(seed: int, index: int) -> int:
    return mix64(seed ^ ((index * 0x9E3779B97F4A7C15) & MASK64))


def user_value(seed: int, index: int) -> int:
    return mix64(seed ^ index ^ 0x6A09E667F3BCC909) >> 56


def source_open(seed: int, cycle: int) -> bool:
    return mix64(seed ^ ((cycle * 0xD1342543DE82EF95) & MASK64)) & 0x7 != 0


def ready_open(seed: int, cycle: int) -> bool:
    value = seed ^ ((cycle * 0x94D049BB133111EB) & MASK64) ^ 0xA4093822299F31D0
    return mix64(value) & 0xF != 0


def transform_data(data: int, ident: int) -> int:
    value = data ^ DATA_XOR
    value = ((value << 13) | (value >> 51)) & MASK64
    return (value + DATA_ADD + ident) & MASK64


def digest_update(digest: int, data: int, ident: int, last: int, user: int) -> int:
    sidebands = ident | (last << 16) | (user << 24)
    rotated = ((digest << 7) | (digest >> 57)) & MASK64
    return rotated ^ data ^ ((sidebands * 0x9E3779B97F4A7C15) & MASK64)


def trace_digest_update(digest: int, cycle: int, dut) -> int:
    m_valid = int(dut.m_valid.value)
    s_valid = int(dut.s_valid.value)
    m_data = int(dut.m_data.value) if m_valid else 0
    s_data = int(dut.s_data.value) if s_valid else 0
    m_id = int(dut.m_id.value) if m_valid else 0
    s_id = int(dut.s_id.value) if s_valid else 0
    m_last = int(dut.m_last.value) if m_valid else 0
    s_last = int(dut.s_last.value) if s_valid else 0
    m_user = int(dut.m_user.value) if m_valid else 0
    s_user = int(dut.s_user.value) if s_valid else 0
    flags = (
        int(dut.reset_n.value)
        | (s_valid << 1)
        | (int(dut.s_ready.value) << 2)
        | (m_valid << 3)
        | (int(dut.m_ready.value) << 4)
        | (m_last << 5)
        | (s_last << 6)
        | (m_user << 8)
        | (s_user << 16)
    )
    sidebands = m_id | (s_id << 16) | (flags << 32)
    return mix64(
        digest
        ^ mix64(cycle)
        ^ mix64(int(dut.accepted_count.value))
        ^ mix64(m_data)
        ^ mix64(s_data)
        ^ mix64(sidebands & MASK64)
    )


def drive_source(dut, seed: int, index: int, cycle: int) -> None:
    if source_open(seed, cycle):
        dut.s_valid.value = 1
        dut.s_data.value = payload(seed, index)
        dut.s_id.value = index & 0xFFFF
        dut.s_last.value = int((index & 0xFF) == 0xFF)
        dut.s_user.value = user_value(seed, index)
    else:
        dut.s_valid.value = 0


@cocotb.test()
async def stream_throughput(dut):
    target = int(os.getenv("RUSTDV_BENCH_TRANSACTIONS", "100000"))
    seed = int(os.getenv("RUSTDV_BENCH_SEED", "1"))
    inject_error = os.getenv("RUSTDV_BENCH_INJECT_ERROR", "0") in {"1", "true", "yes"}

    dut.reset_n.value = 0
    dut.s_valid.value = 0
    dut.s_data.value = 0
    dut.s_id.value = 0
    dut.s_last.value = 0
    dut.s_user.value = 0
    dut.m_ready.value = 0
    dut.inject_error.value = int(inject_error)
    cocotb.start_soon(Clock(dut.clk, 2, unit="ns").start())

    cycles = 0
    transactions = 0
    digest = 0
    trace_digest = 0
    started = time.perf_counter()

    try:
        while True:
            await RisingEdge(dut.clk)
            await ReadOnly()
            cycles += 1
            trace_digest = trace_digest_update(trace_digest, cycles, dut)

            if not int(dut.reset_n.value):
                assert int(dut.m_valid.value) == 0
                assert int(dut.accepted_count.value) == 0
                if cycles >= RESET_CYCLES:
                    await NextTimeStep()
                    dut.reset_n.value = 1
                    dut.m_ready.value = int(ready_open(seed, 0))
                    drive_source(dut, seed, transactions, 0)
                continue

            accepted = bool(int(dut.s_ready.value) and int(dut.s_valid.value))
            emitted = bool(int(dut.m_valid.value) and int(dut.m_ready.value))
            assert accepted == emitted
            assert int(dut.s_ready.value) == int(dut.m_ready.value)
            assert int(dut.m_valid.value) == int(dut.s_valid.value)

            if int(dut.m_valid.value):
                expected_data = transform_data(payload(seed, transactions), transactions & 0xFFFF)
                expected_id = transactions & 0xFFFF
                expected_last = int((transactions & 0xFF) == 0xFF)
                expected_user = user_value(seed, transactions)
                got_data = int(dut.m_data.value)
                got_id = int(dut.m_id.value)
                got_last = int(dut.m_last.value)
                got_user = int(dut.m_user.value)
                assert (got_data, got_id, got_last, got_user) == (
                    expected_data,
                    expected_id,
                    expected_last,
                    expected_user,
                ), (
                    f"payload mismatch for transfer {transactions}: "
                    f"got data=0x{got_data:016x} id=0x{got_id:04x} "
                    f"last={got_last} user=0x{got_user:02x}"
                )
                if emitted:
                    digest = digest_update(digest, got_data, got_id, got_last, got_user)
                    transactions += 1

            assert int(dut.accepted_count.value) == transactions
            if transactions == target:
                active_cycles = cycles - RESET_CYCLES
                elapsed = time.perf_counter() - started
                print(
                    "BENCHMARK: PASS "
                    f"backend=cocotb transactions={transactions} cycles={active_cycles} "
                    f"digest={digest:016x} trace={trace_digest:016x} elapsed_s={elapsed:.9f} "
                    f"cycles_per_s={active_cycles / elapsed:.3f}"
                )
                return

            active_cycle = cycles - RESET_CYCLES
            await NextTimeStep()
            dut.m_ready.value = int(ready_open(seed, active_cycle))
            if accepted or not int(dut.s_valid.value):
                drive_source(dut, seed, transactions, active_cycle)
    except Exception as error:
        print(
            "BENCHMARK: FAIL "
            f"backend=cocotb transactions={target} message={type(error).__name__}:{error}"
        )
        raise
