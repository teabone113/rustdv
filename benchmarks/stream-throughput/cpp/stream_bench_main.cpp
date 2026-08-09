#include "Vrustdv_dut.h"
#include "rustdv_cycle_bindings.h"

#include "verilated.h"

#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <memory>

namespace {

using rustdv_cycle_bindings::CycleInputs;
using rustdv_cycle_bindings::CycleOutputs;

constexpr std::uint64_t kResetCycles = 4;
constexpr std::uint64_t kDataXor = 0xd6e8feb86659fd93ULL;
constexpr std::uint64_t kDataAdd = 0xa5a55a5a12345678ULL;

std::uint64_t env_u64(const char* name, std::uint64_t fallback) {
    const char* value = std::getenv(name);
    if (value == nullptr || *value == '\0') return fallback;
    char* end = nullptr;
    const auto parsed = std::strtoull(value, &end, 0);
    if (end == value || *end != '\0') {
        std::fprintf(stderr, "invalid %s=%s\n", name, value);
        std::exit(2);
    }
    return parsed;
}

bool env_flag(const char* name) {
    const char* value = std::getenv(name);
    return value != nullptr &&
           (std::strcmp(value, "1") == 0 || std::strcmp(value, "true") == 0 ||
            std::strcmp(value, "yes") == 0);
}

std::uint64_t rotate_left(std::uint64_t value, unsigned amount) {
    return (value << amount) | (value >> (64 - amount));
}

std::uint64_t mix64(std::uint64_t value) {
    value += 0x9e3779b97f4a7c15ULL;
    value = (value ^ (value >> 30)) * 0xbf58476d1ce4e5b9ULL;
    value = (value ^ (value >> 27)) * 0x94d049bb133111ebULL;
    return value ^ (value >> 31);
}

std::uint64_t payload(std::uint64_t seed, std::uint64_t index) {
    return mix64(seed ^ index * 0x9e3779b97f4a7c15ULL);
}

std::uint8_t user_value(std::uint64_t seed, std::uint64_t index) {
    return static_cast<std::uint8_t>(mix64(seed ^ index ^ 0x6a09e667f3bcc909ULL) >> 56);
}

bool source_open(std::uint64_t seed, std::uint64_t cycle) {
    return (mix64(seed ^ cycle * 0xd1342543de82ef95ULL) & 0x7) != 0;
}

bool ready_open(std::uint64_t seed, std::uint64_t cycle) {
    return (mix64(seed ^ cycle * 0x94d049bb133111ebULL ^ 0xa4093822299f31d0ULL) & 0xf) != 0;
}

std::uint64_t transform_data(std::uint64_t data, std::uint16_t id) {
    return rotate_left(data ^ kDataXor, 13) + kDataAdd + id;
}

std::uint64_t digest_update(std::uint64_t digest, std::uint64_t data, std::uint16_t id,
                            std::uint8_t last, std::uint8_t user) {
    const std::uint64_t sidebands = static_cast<std::uint64_t>(id) |
                                    (static_cast<std::uint64_t>(last) << 16) |
                                    (static_cast<std::uint64_t>(user) << 24);
    return rotate_left(digest, 7) ^ data ^ sidebands * 0x9e3779b97f4a7c15ULL;
}

std::uint64_t trace_digest_update(std::uint64_t digest, std::uint64_t cycle,
                                  const CycleInputs& inputs, const CycleOutputs& outputs) {
    const bool m_valid = inputs.m_valid != 0;
    const bool s_valid = outputs.s_valid != 0;
    const std::uint64_t m_data = m_valid ? inputs.m_data : 0;
    const std::uint64_t s_data = s_valid ? outputs.s_data : 0;
    const std::uint16_t m_id = m_valid ? inputs.m_id : 0;
    const std::uint16_t s_id = s_valid ? outputs.s_id : 0;
    const std::uint8_t m_last = m_valid ? inputs.m_last : 0;
    const std::uint8_t s_last = s_valid ? outputs.s_last : 0;
    const std::uint8_t m_user = m_valid ? inputs.m_user : 0;
    const std::uint8_t s_user = s_valid ? outputs.s_user : 0;
    const std::uint64_t flags = static_cast<std::uint64_t>(outputs.reset_n) |
                                (static_cast<std::uint64_t>(s_valid) << 1) |
                                (static_cast<std::uint64_t>(inputs.s_ready) << 2) |
                                (static_cast<std::uint64_t>(m_valid) << 3) |
                                (static_cast<std::uint64_t>(outputs.m_ready) << 4) |
                                (static_cast<std::uint64_t>(m_last) << 5) |
                                (static_cast<std::uint64_t>(s_last) << 6) |
                                (static_cast<std::uint64_t>(m_user) << 8) |
                                (static_cast<std::uint64_t>(s_user) << 16);
    const std::uint64_t sidebands = static_cast<std::uint64_t>(m_id) |
                                    (static_cast<std::uint64_t>(s_id) << 16) |
                                    (flags << 32);
    return mix64(digest ^ mix64(cycle) ^ mix64(inputs.accepted_count) ^ mix64(m_data) ^
                 mix64(s_data) ^ mix64(sidebands));
}

void load_source(CycleOutputs& outputs, std::uint64_t seed, std::uint64_t cycle,
                 std::uint64_t transaction, bool inject_error) {
    if (source_open(seed, cycle)) {
        outputs.s_valid = 1;
        outputs.s_data = payload(seed, transaction);
        outputs.s_id = static_cast<std::uint16_t>(transaction);
        outputs.s_last = static_cast<std::uint8_t>((transaction & 0xff) == 0xff);
        outputs.s_user = user_value(seed, transaction);
    } else {
        outputs.s_valid = 0;
    }
    outputs.inject_error = static_cast<std::uint8_t>(inject_error);
}

int fail(std::uint64_t target, const char* message) {
    std::printf("BENCHMARK: FAIL backend=cpp-direct transactions=%llu message=%s\n",
                static_cast<unsigned long long>(target), message);
    return 1;
}

}  // namespace

int main(int argc, char** argv) {
    const auto target = env_u64("RUSTDV_BENCH_TRANSACTIONS", 100000);
    const auto seed = env_u64("RUSTDV_BENCH_SEED", 1);
    const auto threads = env_u64("RUSTDV_VERILATOR_THREADS", 1);
    const bool inject_error = env_flag("RUSTDV_BENCH_INJECT_ERROR");
    if (threads != 1 && threads != 2 && threads != 4) {
        return fail(target, "RUSTDV_VERILATOR_THREADS must be 1, 2, or 4");
    }
    auto context = std::make_unique<VerilatedContext>();
    context->threads(static_cast<unsigned>(threads));
    context->commandArgs(argc, argv);
    auto dut = std::make_unique<Vrustdv_dut>(context.get());
    CycleInputs inputs{};
    CycleOutputs outputs{};
    outputs.inject_error = static_cast<std::uint8_t>(inject_error);

    std::uint64_t cycles = 0;
    std::uint64_t transactions = 0;
    std::uint64_t digest = 0;
    std::uint64_t trace_digest = 0;
    const auto started = std::chrono::steady_clock::now();

    while (!context->gotFinish()) {
        rustdv_cycle_bindings::apply_outputs(*dut, outputs);
        rustdv_cycle_bindings::set_clock(*dut, 0);
        dut->eval();
        rustdv_cycle_bindings::set_clock(*dut, 1);
        dut->eval();
        rustdv_cycle_bindings::capture_inputs(*dut, inputs);
        ++cycles;
        trace_digest = trace_digest_update(trace_digest, cycles, inputs, outputs);

        if (outputs.reset_n == 0) {
            if (inputs.m_valid != 0 || inputs.accepted_count != 0) {
                dut->final();
                return fail(target, "DUT active during reset");
            }
            if (cycles >= kResetCycles) {
                outputs.reset_n = 1;
                outputs.m_ready = static_cast<std::uint8_t>(ready_open(seed, 0));
                load_source(outputs, seed, 0, 0, inject_error);
            }
            continue;
        }

        const bool accepted = outputs.s_valid != 0 && inputs.s_ready != 0;
        const bool emitted = inputs.m_valid != 0 && outputs.m_ready != 0;
        if (accepted != emitted || inputs.s_ready != outputs.m_ready ||
            inputs.m_valid != outputs.s_valid) {
            dut->final();
            return fail(target, "ready/valid protocol mismatch");
        }

        if (inputs.m_valid != 0) {
            const auto expected_data = transform_data(payload(seed, transactions),
                                                      static_cast<std::uint16_t>(transactions));
            const auto expected_id = static_cast<std::uint16_t>(transactions);
            const auto expected_last = static_cast<std::uint8_t>((transactions & 0xff) == 0xff);
            const auto expected_user = user_value(seed, transactions);
            if (inputs.m_data != expected_data || inputs.m_id != expected_id ||
                inputs.m_last != expected_last || inputs.m_user != expected_user) {
                dut->final();
                return fail(target, "payload mismatch");
            }
            if (emitted) {
                digest = digest_update(digest, inputs.m_data, inputs.m_id, inputs.m_last, inputs.m_user);
                ++transactions;
            }
        }

        if (inputs.accepted_count != transactions) {
            dut->final();
            return fail(target, "accepted_count mismatch");
        }
        if (transactions == target) break;

        const auto active_cycle = cycles - kResetCycles;
        outputs.m_ready = static_cast<std::uint8_t>(ready_open(seed, active_cycle));
        if (accepted || outputs.s_valid == 0) {
            load_source(outputs, seed, active_cycle, transactions, inject_error);
        }
    }

    const std::uint64_t active_cycles = cycles - kResetCycles;
    const double elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - started).count();
    std::printf(
        "BENCHMARK: PASS backend=cpp-direct transactions=%llu cycles=%llu digest=%016llx "
        "trace=%016llx "
        "elapsed_s=%.9f cycles_per_s=%.3f\n",
        static_cast<unsigned long long>(transactions),
        static_cast<unsigned long long>(active_cycles),
        static_cast<unsigned long long>(digest),
        static_cast<unsigned long long>(trace_digest),
        elapsed,
        static_cast<double>(active_cycles) / elapsed);
    dut->final();
    return 0;
}
