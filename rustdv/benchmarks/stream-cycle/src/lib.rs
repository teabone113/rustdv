use std::time::Instant;

use rustdv_cycle::{CycleModel, CycleStatus};
use rustdv_stream_bench_model::{BenchInputs, BenchModel, BenchOutputs, BenchReport, StepStatus};

mod bindings;

use bindings::{CycleInputs, CycleOutputs};

struct StreamCycleModel {
    model: BenchModel,
    values: BenchOutputs,
    target: u64,
    started: Instant,
}

impl CycleModel<CycleInputs, CycleOutputs> for StreamCycleModel {
    fn new(outputs: &mut CycleOutputs) -> Result<Self, String> {
        let target = env_u64("RUSTDV_BENCH_TRANSACTIONS", 100_000)?;
        let seed = env_u64("RUSTDV_BENCH_SEED", 1)?;
        let inject_error = env_flag("RUSTDV_BENCH_INJECT_ERROR");
        let (model, values) = BenchModel::new(target, seed, inject_error);
        write_outputs(&values, outputs);
        Ok(Self {
            model,
            values,
            target,
            started: Instant::now(),
        })
    }

    fn step(
        &mut self,
        inputs: &CycleInputs,
        outputs: &mut CycleOutputs,
    ) -> Result<CycleStatus, String> {
        let values = BenchInputs {
            s_ready: inputs.s_ready,
            m_valid: inputs.m_valid,
            m_data: inputs.m_data,
            m_id: inputs.m_id,
            m_last: inputs.m_last,
            m_user: inputs.m_user,
            accepted_count: inputs.accepted_count,
        };
        match self.model.step(&values, &mut self.values) {
            StepStatus::Continue => {
                write_outputs(&self.values, outputs);
                Ok(CycleStatus::Continue)
            }
            StepStatus::Pass(report) => {
                print_report(report, self.started.elapsed().as_secs_f64());
                Ok(CycleStatus::Pass)
            }
            StepStatus::Fail(message) => {
                println!(
                    "BENCHMARK: FAIL backend=rustdv-direct transactions={} message={message}",
                    self.target
                );
                Err(message)
            }
        }
    }
}

fn write_outputs(source: &BenchOutputs, destination: &mut CycleOutputs) {
    destination.reset_n = source.reset_n;
    destination.s_valid = source.s_valid;
    destination.s_data = source.s_data;
    destination.s_id = source.s_id;
    destination.s_last = source.s_last;
    destination.s_user = source.s_user;
    destination.m_ready = source.m_ready;
    destination.inject_error = source.inject_error;
}

fn print_report(report: BenchReport, elapsed: f64) {
    println!(
        "BENCHMARK: PASS backend=rustdv-direct transactions={} cycles={} digest={:016x} trace={:016x} elapsed_s={:.9} cycles_per_s={:.3}",
        report.transactions,
        report.cycles,
        report.digest,
        report.trace_digest,
        elapsed,
        report.cycles as f64 / elapsed
    );
}

fn env_u64(name: &str, default: u64) -> Result<u64, String> {
    match std::env::var(name) {
        Ok(value) => value
            .parse()
            .map_err(|error| format!("invalid {name}={value:?}: {error}")),
        Err(_) => Ok(default),
    }
}

fn env_flag(name: &str) -> bool {
    std::env::var(name)
        .map(|value| matches!(value.as_str(), "1" | "true" | "yes"))
        .unwrap_or(false)
}

rustdv_cycle::export_cycle_model!(
    model = StreamCycleModel,
    inputs = CycleInputs,
    outputs = CycleOutputs,
    schema_hash = bindings::SCHEMA_HASH,
);
