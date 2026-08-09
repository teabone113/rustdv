// Direct cycle-oriented RustDV host for synchronous Verilated designs.

#include "Vrustdv_dut.h"
#include "rustdv_cycle_bindings.h"
#include "verilated.h"

#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <limits>
#include <memory>
#include <unistd.h>

namespace bindings = rustdv_cycle_bindings;

namespace {

constexpr std::uint32_t kAbiVersion = 1;
constexpr std::uint32_t kContinue = 0;
constexpr std::uint32_t kPass = 1;
constexpr std::uint32_t kFail = 2;

struct CycleAbiInfo {
    std::uint32_t abi_version;
    std::uint32_t info_size;
    std::uint32_t input_size;
    std::uint32_t input_align;
    std::uint32_t output_size;
    std::uint32_t output_align;
    std::uint64_t schema_hash;
    std::uint64_t reserved[4];
};

struct CycleAbiHeader {
    std::uint32_t abi_version;
    std::uint32_t info_size;
};

static_assert(sizeof(CycleAbiHeader) == 8, "cycle ABI header size");
static_assert(offsetof(CycleAbiInfo, abi_version) == 0, "cycle ABI version prefix");
static_assert(offsetof(CycleAbiInfo, info_size) == 4, "cycle ABI size prefix");

using AbiInfoFn = const CycleAbiHeader* (*)();
using CreateFn = void* (*)(bindings::CycleOutputs*);
using StepFn = std::uint32_t (*)(void*, const bindings::CycleInputs*, bindings::CycleOutputs*);
using FinishFn = std::uint32_t (*)(void*);
using LastErrorFn = const char* (*)(void*);
using DestroyFn = void (*)(void*);

template <typename Function>
Function load_symbol(void* library, const char* name) {
    dlerror();
    void* symbol = dlsym(library, name);
    if (const char* error = dlerror()) {
        std::fprintf(stderr, "rustdv-cycle: missing symbol %s: %s\n", name, error);
        return nullptr;
    }
    return reinterpret_cast<Function>(symbol);
}

const char* library_argument(int argc, char** argv) {
    constexpr const char* prefix = "+rustdv+cycle+";
    constexpr std::size_t prefix_size = 14;
    for (int index = 1; index < argc; ++index) {
        if (std::strncmp(argv[index], prefix, prefix_size) == 0) {
            return argv[index] + prefix_size;
        }
    }
    return std::getenv("RUSTDV_CYCLE_LIBRARY");
}

std::uint32_t runtime_threads() {
    const char* value = std::getenv("RUSTDV_VERILATOR_THREADS");
    if (!value || !*value) return 1;
    char* end = nullptr;
    const unsigned long parsed = std::strtoul(value, &end, 10);
    if (!end || *end || parsed == 0 || parsed > std::numeric_limits<std::uint32_t>::max()) {
        std::fprintf(stderr, "rustdv-cycle: invalid RUSTDV_VERILATOR_THREADS=%s\n", value);
        return 0;
    }
    return static_cast<std::uint32_t>(parsed);
}

std::uint64_t maximum_cycles() {
    const char* value = std::getenv("RUSTDV_CYCLE_MAX_CYCLES");
    if (!value || !*value) return 1'000'000'000ULL;
    char* end = nullptr;
    const unsigned long long parsed = std::strtoull(value, &end, 10);
    if (!end || *end || parsed == 0) return 0;
    return static_cast<std::uint64_t>(parsed);
}

bool positive_environment(const char* name, std::uint64_t fallback, std::uint64_t& result) {
    const char* value = std::getenv(name);
    if (!value || !*value) {
        result = fallback;
        return true;
    }
    char* end = nullptr;
    const unsigned long long parsed = std::strtoull(value, &end, 10);
    if (!end || *end || parsed == 0) {
        std::fprintf(stderr, "rustdv-cycle: invalid %s=%s\n", name, value);
        return false;
    }
    result = static_cast<std::uint64_t>(parsed);
    return true;
}

std::uint64_t resident_set_kib() {
    char command[64];
    std::snprintf(command, sizeof(command), "ps -o rss= -p %ld", static_cast<long>(getpid()));
    FILE* stream = popen(command, "r");
    if (!stream) return 0;
    unsigned long long value = 0;
    const int converted = std::fscanf(stream, "%llu", &value);
    const int close_status = pclose(stream);
    return converted == 1 && close_status == 0 ? static_cast<std::uint64_t>(value) : 0;
}

bool abi_matches(const CycleAbiInfo& info) {
    bool okay = true;
#define RUSTDV_CHECK(field, expected)                                                       \
    do {                                                                                    \
        if (info.field != (expected)) {                                                      \
            std::fprintf(stderr, "rustdv-cycle: ABI %s mismatch: Rust=%llu C++=%llu\n",   \
                         #field,                                                             \
                         static_cast<unsigned long long>(info.field),                        \
                         static_cast<unsigned long long>(expected));                         \
            okay = false;                                                                    \
        }                                                                                    \
    } while (false)
    RUSTDV_CHECK(abi_version, kAbiVersion);
    RUSTDV_CHECK(info_size, sizeof(CycleAbiInfo));
    RUSTDV_CHECK(input_size, bindings::kInputSize);
    RUSTDV_CHECK(input_align, bindings::kInputAlign);
    RUSTDV_CHECK(output_size, bindings::kOutputSize);
    RUSTDV_CHECK(output_align, bindings::kOutputAlign);
    RUSTDV_CHECK(schema_hash, bindings::kSchemaHash);
#undef RUSTDV_CHECK
    return okay;
}

}  // namespace

int main(int argc, char** argv, char**) {
    const char* library_path = library_argument(argc, argv);
    if (!library_path || !*library_path) {
        std::fprintf(stderr, "rustdv-cycle: pass +rustdv+cycle+<library>\n");
        return 2;
    }
    const std::uint32_t threads = runtime_threads();
    const std::uint64_t max_cycles = maximum_cycles();
    if (threads == 0 || max_cycles == 0) return 2;
    std::uint64_t rss_warmup_cycle = 0;
    std::uint64_t max_rss_growth_kib = 16 * 1024;
    if (!positive_environment("RUSTDV_CYCLE_RSS_WARMUP_CYCLE", 0, rss_warmup_cycle) ||
        !positive_environment(
            "RUSTDV_CYCLE_MAX_RSS_GROWTH_KIB", 16 * 1024, max_rss_growth_kib)) {
        return 2;
    }

    void* library = dlopen(library_path, RTLD_NOW | RTLD_LOCAL);
    if (!library) {
        std::fprintf(stderr, "rustdv-cycle: cannot load %s: %s\n", library_path, dlerror());
        return 2;
    }

    const auto abi_info = load_symbol<AbiInfoFn>(library, "rustdv_cycle_abi_info");
    const auto create = load_symbol<CreateFn>(library, "rustdv_cycle_create");
    const auto step = load_symbol<StepFn>(library, "rustdv_cycle_step");
    const auto finish = load_symbol<FinishFn>(library, "rustdv_cycle_finish");
    const auto last_error = load_symbol<LastErrorFn>(library, "rustdv_cycle_last_error");
    const auto destroy = load_symbol<DestroyFn>(library, "rustdv_cycle_destroy");
    if (!abi_info || !create || !step || !finish || !last_error || !destroy) {
        dlclose(library);
        return 2;
    }

    const CycleAbiHeader* header = abi_info();
    if (!header) {
        std::fprintf(stderr, "rustdv-cycle: library returned no ABI descriptor\n");
        dlclose(library);
        return 2;
    }
    if (header->abi_version != kAbiVersion || header->info_size != sizeof(CycleAbiInfo)) {
        std::fprintf(
            stderr,
            "rustdv-cycle: ABI header mismatch: version Rust=%u C++=%u, size Rust=%u C++=%zu\n",
            header->abi_version,
            kAbiVersion,
            header->info_size,
            sizeof(CycleAbiInfo));
        dlclose(library);
        return 2;
    }
    CycleAbiInfo info{};
    std::memcpy(&info, header, sizeof(info));
    if (!abi_matches(info)) {
        dlclose(library);
        return 2;
    }

    Verilated::debug(0);
    const std::unique_ptr<VerilatedContext> context{new VerilatedContext};
    context->threads(threads);
    context->commandArgs(argc, argv);
    const std::unique_ptr<Vrustdv_dut> dut{new Vrustdv_dut{context.get(), ""}};

    bindings::CycleInputs inputs{};
    bindings::CycleOutputs outputs{};
    void* model = create(&outputs);
    if (!model) {
        dut->final();
        dlclose(library);
        return 2;
    }

    std::uint32_t status = kContinue;
    std::uint64_t cycles = 0;
    std::uint64_t warmup_rss_kib = 0;
    while (status == kContinue && !context->gotFinish() && cycles < max_cycles) {
        bindings::apply_outputs(*dut, outputs);
        bindings::set_clock(*dut, 0);
        dut->eval();
        context->timeInc(1);

        bindings::set_clock(*dut, 1);
        dut->eval();
        bindings::capture_inputs(*dut, inputs);
        status = step(model, &inputs, &outputs);
        ++cycles;
        if (rss_warmup_cycle != 0 && warmup_rss_kib == 0 && cycles >= rss_warmup_cycle) {
            warmup_rss_kib = resident_set_kib();
            if (warmup_rss_kib == 0) {
                std::fprintf(stderr, "rustdv-cycle: could not sample RSS after warmup\n");
                status = kFail;
            }
        }
        context->timeInc(1);

        if (status != kContinue && status != kPass && status != kFail) {
            std::fprintf(stderr, "rustdv-cycle: model returned invalid status %u\n", status);
            status = kFail;
        }
    }

    if (status == kContinue) {
        if (context->gotFinish()) {
            std::fprintf(stderr, "rustdv-cycle: DUT called finish before model verdict\n");
        } else {
            std::fprintf(
                stderr,
                "rustdv-cycle: exceeded maximum cycle count %llu\n",
                static_cast<unsigned long long>(max_cycles));
        }
        status = kFail;
    }

    if (rss_warmup_cycle != 0 && status == kPass) {
        const std::uint64_t final_rss_kib = resident_set_kib();
        if (warmup_rss_kib == 0 || final_rss_kib == 0) {
            std::fprintf(stderr, "rustdv-cycle: RSS warmup cycle was not reached or sampled\n");
            status = kFail;
        } else {
            const std::uint64_t growth_kib =
                final_rss_kib > warmup_rss_kib ? final_rss_kib - warmup_rss_kib : 0;
            std::printf(
                "CYCLE RSS: warmup_cycle=%llu warmup_rss=%lluKiB final_rss=%lluKiB growth=%lluKiB\n",
                static_cast<unsigned long long>(rss_warmup_cycle),
                static_cast<unsigned long long>(warmup_rss_kib),
                static_cast<unsigned long long>(final_rss_kib),
                static_cast<unsigned long long>(growth_kib));
            if (growth_kib > max_rss_growth_kib) {
                std::fprintf(
                    stderr,
                    "rustdv-cycle: RSS grew by %lluKiB after warmup; limit is %lluKiB\n",
                    static_cast<unsigned long long>(growth_kib),
                    static_cast<unsigned long long>(max_rss_growth_kib));
                status = kFail;
            }
        }
    }

    if (finish(model) == kFail) status = kFail;
    if (status == kFail) {
        const char* message = last_error(model);
        if (message && *message) std::fprintf(stderr, "rustdv-cycle: %s\n", message);
    }

    dut->final();
    destroy(model);
    dlclose(library);
    return status == kPass ? 0 : 1;
}
