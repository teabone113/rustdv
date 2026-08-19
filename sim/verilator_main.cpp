// Shared rustdv host for Verilated designs.
//
// Verilator's generated --main loop advances only while the RTL model has a
// pending event.  A rustdv testbench can instead be waiting solely on a VPI
// timer, so the generated loop may stop at time zero.  This host treats the
// RTL and VPI queues as peers and implements the simulator phase ordering the
// framework relies on.

#include "Vrustdv_dut.h"
#include "verilated.h"
#include "verilated_vpi.h"

#if VM_TRACE_FST
#include "verilated_fst_c.h"
#endif

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <memory>

// Statically linked VPI modules populate this array.  rustdv normally uses
// Verilator 5.050's +verilator+vpi+<library> runtime loader, where it is null.
extern "C" void (*vlog_startup_routines[])() VL_ATTR_WEAK;

#if defined(_WIN32)
#define RUSTDV_EXPORT __declspec(dllexport)
#else
#define RUSTDV_EXPORT __attribute__((visibility("default")))
#endif

struct RustdvTraceStatus {
    std::uint32_t abi_version;
    std::uint32_t capability;
    std::uint32_t state;
    std::uint32_t reserved;
    std::uint64_t start_time_steps;
    std::uint64_t end_time_steps;
    std::uint64_t dump_count;
};

namespace {

constexpr std::uint64_t kNoDeadline = std::numeric_limits<std::uint64_t>::max();
constexpr unsigned kSettleLimit = 100000;

class RuntimeTrace final {
  public:
    RuntimeTrace(VerilatedContext& context, Vrustdv_dut& dut)
        : context_{context}, dut_{dut} {
#if VM_TRACE_FST
        // Verilator requires traceEverOn before time zero.  This only executes
        // in models compiled with --trace-fst; FAST remains uninstrumented.
        context_.traceEverOn(true);
#endif
    }

    bool available() const {
#if VM_TRACE_FST
        return true;
#else
        return false;
#endif
    }

    bool active() const {
#if VM_TRACE_FST
        return static_cast<bool>(tracep_);
#else
        return false;
#endif
    }

    std::uint64_t start_time() const { return start_time_; }
    std::uint64_t end_time() const { return end_time_; }
    std::uint64_t dump_count() const { return dump_count_; }

    bool start(const char* path, bool dump_now, const char*& error) {
#if VM_TRACE_FST
        if (tracep_) {
            error = "an FST capture is already active";
            return false;
        }
        if (!path || !*path) {
            error = "an FST capture path is required";
            return false;
        }

        tracep_ = std::make_unique<VerilatedFstC>();
        dut_.trace(tracep_.get(), 99);
        tracep_->open(path);
        start_time_ = context_.time();
        end_time_ = start_time_;
        dump_count_ = 0;
        has_last_dump_time_ = false;
        if (dump_now) dump_settled_time();
        return true;
#else
        (void)path;
        (void)dump_now;
        error = "this Verilator model was not built with --trace-fst";
        return false;
#endif
    }

    bool flush(const char*& error) {
#if VM_TRACE_FST
        if (!tracep_) {
            error = "no FST capture is active";
            return false;
        }
        dump_settled_time();
        tracep_->flush();
        return true;
#else
        error = "this Verilator model was not built with --trace-fst";
        return false;
#endif
    }

    bool stop(const char*& error) {
#if VM_TRACE_FST
        if (!tracep_) {
            error = "no FST capture is active";
            return false;
        }
        dump_settled_time();
        tracep_->close();
        tracep_.reset();
        end_time_ = context_.time();
        return true;
#else
        error = "this Verilator model was not built with --trace-fst";
        return false;
#endif
    }

    void dump_settled_time() {
#if VM_TRACE_FST
        if (!tracep_) return;
        const std::uint64_t now = context_.time();
        if (has_last_dump_time_ && last_dump_time_ == now) return;
        tracep_->dump(now);
        last_dump_time_ = now;
        has_last_dump_time_ = true;
        end_time_ = now;
        ++dump_count_;
#endif
    }

  private:
    VerilatedContext& context_;
    Vrustdv_dut& dut_;
#if VM_TRACE_FST
    std::unique_ptr<VerilatedFstC> tracep_;
#endif
    std::uint64_t start_time_{0};
    std::uint64_t end_time_{0};
    std::uint64_t dump_count_{0};
    std::uint64_t last_dump_time_{0};
    bool has_last_dump_time_{false};
};

RuntimeTrace* runtime_tracep = nullptr;

void fill_trace_status(RustdvTraceStatus* status) {
    if (!status) return;
    std::memset(status, 0, sizeof(*status));
    status->abi_version = 1;
    if (!runtime_tracep) return;
    status->capability = runtime_tracep->available() ? 1 : 0;
    status->state = runtime_tracep->active() ? 1 : 0;
    status->start_time_steps = runtime_tracep->start_time();
    status->end_time_steps = runtime_tracep->end_time();
    status->dump_count = runtime_tracep->dump_count();
}

void write_trace_error(char* destination, std::size_t capacity, const char* message) {
    if (!destination || capacity == 0) return;
    const char* const source = message ? message : "Verilator trace host error";
    std::snprintf(destination, capacity, "%s", source);
}

bool settle(Vrustdv_dut& dut) {
    for (unsigned iteration = 0; iteration < kSettleLimit; ++iteration) {
        // Apply any inertially delayed VPI writes before evaluating the RTL.
        // Clear the dirty flag because this eval consumes all writes made so
        // far; writes made by callbacks below set it again.
        VerilatedVpi::doInertialPuts();
        VerilatedVpi::clearEvalNeeded();
        dut.eval();

        // RTL changes wake edge/value awaiters.  Those tasks may queue writes
        // or ReadWrite callbacks, so ReadOnly is not legal until this reaches
        // a fixed point.
        VerilatedVpi::callValueCbs();
        VerilatedVpi::callCbs(cbReadWriteSynch);

        if (!VerilatedVpi::evalNeeded()
            && !VerilatedVpi::hasCbs(cbReadWriteSynch)) {
            VerilatedVpi::callCbs(cbAtEndOfSimTime);
            VerilatedVpi::callCbs(cbReadOnlySynch);
            return true;
        }
    }

    std::fprintf(stderr,
                 "rustdv: Verilator scheduler did not settle after %u iterations at time %llu\n",
                 kSettleLimit,
                 static_cast<unsigned long long>(Verilated::time()));
    return false;
}

}  // namespace

extern "C" RUSTDV_EXPORT int rustdv_verilator_trace_control(
    std::uint32_t command,
    const char* path,
    RustdvTraceStatus* status,
    char* error,
    std::size_t error_capacity) {
    fill_trace_status(status);
    if (!runtime_tracep || !runtime_tracep->available()) {
        write_trace_error(error,
                          error_capacity,
                          "this Verilator model was not built with --trace-fst");
        return 1;
    }

    const char* message = nullptr;
    bool ok = false;
    switch (command) {
    case 0:
        return 0;
    case 1:
        ok = runtime_tracep->start(path, true, message);
        break;
    case 2:
        ok = runtime_tracep->stop(message);
        break;
    case 3:
        ok = runtime_tracep->flush(message);
        break;
    default:
        write_trace_error(error, error_capacity, "unknown Verilator trace command");
        return 2;
    }

    fill_trace_status(status);
    if (ok) return 0;
    write_trace_error(error, error_capacity, message);
    return command == 1 && (!path || !*path) ? 3 : 4;
}

int main(int argc, char** argv, char**) {
    Verilated::debug(0);
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->threads(1);
    contextp->commandArgs(argc, argv);

    const std::unique_ptr<Vrustdv_dut> dutp{new Vrustdv_dut{contextp.get(), ""}};
    RuntimeTrace runtime_trace{*contextp, *dutp};
    runtime_tracep = &runtime_trace;

    if (const char* const path = std::getenv("RUSTDV_FST")) {
        const char* error = nullptr;
        if (!runtime_trace.start(path, false, error)) {
            std::fprintf(stderr, "rustdv: %s\n", error);
            return 2;
        }
    }

    if (vlog_startup_routines) {
        for (auto routinep = &vlog_startup_routines[0]; *routinep; ++routinep) {
            (*routinep)();
        }
    }
    VerilatedVpi::callCbs(cbStartOfSimulation);

    bool scheduler_ok = true;
    while (!contextp->gotFinish()) {
        // Timed callbacks run before model evaluation at their deadline.
        VerilatedVpi::callTimedCbs();
        VerilatedVpi::callCbs(cbNextSimTime);
        VerilatedVpi::callCbs(cbAtStartOfSimTime);

        if (!settle(*dutp)) {
            scheduler_ok = false;
            break;
        }

        runtime_trace.dump_settled_time();

        if (contextp->gotFinish()) break;

        const std::uint64_t rtl_deadline
            = dutp->eventsPending() ? dutp->nextTimeSlot() : kNoDeadline;
        const std::uint64_t vpi_deadline = VerilatedVpi::cbNextDeadline();
        const std::uint64_t deadline = std::min(rtl_deadline, vpi_deadline);

        if (deadline == kNoDeadline) break;
        if (deadline < contextp->time()) {
            std::fprintf(stderr,
                         "rustdv: Verilator scheduler deadline moved backwards (%llu < %llu)\n",
                         static_cast<unsigned long long>(deadline),
                         static_cast<unsigned long long>(contextp->time()));
            scheduler_ok = false;
            break;
        }
        contextp->time(deadline);
    }

    dutp->final();
    VerilatedVpi::callCbs(cbEndOfSimulation);

    if (runtime_trace.active()) {
        const char* error = nullptr;
        if (!runtime_trace.stop(error)) {
            std::fprintf(stderr, "rustdv: failed to close FST capture: %s\n", error);
            scheduler_ok = false;
        }
    }
    runtime_tracep = nullptr;

    contextp->statsPrintSummary();
    return scheduler_ok ? 0 : 1;
}
