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
#include <cstdio>
#include <cstdlib>
#include <limits>
#include <memory>

// Statically linked VPI modules populate this array.  rustdv normally uses
// Verilator 5.050's +verilator+vpi+<library> runtime loader, where it is null.
extern "C" void (*vlog_startup_routines[])() VL_ATTR_WEAK;

namespace {

constexpr std::uint64_t kNoDeadline = std::numeric_limits<std::uint64_t>::max();
constexpr unsigned kSettleLimit = 100000;

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

int main(int argc, char** argv, char**) {
    Verilated::debug(0);
    const std::unique_ptr<VerilatedContext> contextp{new VerilatedContext};
    contextp->threads(1);
    contextp->commandArgs(argc, argv);

    const std::unique_ptr<Vrustdv_dut> dutp{new Vrustdv_dut{contextp.get(), ""}};

#if VM_TRACE_FST
    std::unique_ptr<VerilatedFstC> tracep;
    if (const char* const path = std::getenv("RUSTDV_FST")) {
        contextp->traceEverOn(true);
        tracep = std::make_unique<VerilatedFstC>();
        dutp->trace(tracep.get(), 99);
        tracep->open(path);
    }
#else
    if (std::getenv("RUSTDV_FST")) {
        std::fprintf(stderr,
                     "rustdv: RUSTDV_FST was set, but this model was not built with --trace-fst\n");
        return 2;
    }
#endif

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

#if VM_TRACE_FST
        if (tracep) tracep->dump(contextp->time());
#endif

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

#if VM_TRACE_FST
    if (tracep) tracep->close();
#endif

    contextp->statsPrintSummary();
    return scheduler_ok ? 0 : 1;
}
