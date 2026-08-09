use std::time::Instant;

use rustdv::prelude::*;
use rustdv::run_cycle_model_vpi;
use rustdv_stream_bench_model::{BenchInputs, BenchModel, BenchOutputs, StepStatus};

#[cfg(test)]
use rustdv_vpi_stubs as _;

rustdv::vpi_bootstrap!();

fn env_u64(name: &str, default: u64) -> Result<u64, TestError> {
    match std::env::var(name) {
        Ok(value) => value
            .parse()
            .map_err(|error| TestError::new(format!("invalid {name}={value:?}: {error}"))),
        Err(_) => Ok(default),
    }
}

fn env_flag(name: &str) -> bool {
    std::env::var(name)
        .map(|value| matches!(value.as_str(), "1" | "true" | "yes"))
        .unwrap_or(false)
}

fn drive(handles: &Handles, values: &BenchOutputs, previous: &mut Option<BenchOutputs>) {
    let old = previous.unwrap_or(BenchOutputs {
        reset_n: !values.reset_n,
        s_valid: !values.s_valid,
        s_data: !values.s_data,
        s_id: !values.s_id,
        s_last: !values.s_last,
        s_user: !values.s_user,
        m_ready: !values.m_ready,
        inject_error: !values.inject_error,
    });
    if values.reset_n != old.reset_n {
        handles.reset_n.set_u64_now(values.reset_n as u64);
    }
    if values.s_valid != old.s_valid {
        handles.s_valid.set_u64_now(values.s_valid as u64);
    }
    if values.s_data != old.s_data {
        handles.s_data.set_u64_now(values.s_data);
    }
    if values.s_id != old.s_id {
        handles.s_id.set_u64_now(values.s_id as u64);
    }
    if values.s_last != old.s_last {
        handles.s_last.set_u64_now(values.s_last as u64);
    }
    if values.s_user != old.s_user {
        handles.s_user.set_u64_now(values.s_user as u64);
    }
    if values.m_ready != old.m_ready {
        handles.m_ready.set_u64_now(values.m_ready as u64);
    }
    if values.inject_error != old.inject_error {
        handles.inject_error.set_u64_now(values.inject_error as u64);
    }
    *previous = Some(*values);
}

fn sample(handles: &Handles) -> Result<BenchInputs, TestError> {
    let m_valid = handles.m_valid.get_u64()? as u8;
    Ok(BenchInputs {
        s_ready: handles.s_ready.get_u64()? as u8,
        m_valid,
        m_data: if m_valid != 0 {
            handles.m_data.get_u64()?
        } else {
            0
        },
        m_id: if m_valid != 0 {
            handles.m_id.get_u64()? as u16
        } else {
            0
        },
        m_last: if m_valid != 0 {
            handles.m_last.get_u64()? as u8
        } else {
            0
        },
        m_user: if m_valid != 0 {
            handles.m_user.get_u64()? as u8
        } else {
            0
        },
        accepted_count: handles.accepted_count.get_u64()?,
    })
}

struct Handles {
    clk: LogicHandle,
    reset_n: LogicHandle,
    s_valid: LogicHandle,
    s_ready: LogicHandle,
    s_data: LogicHandle,
    s_id: LogicHandle,
    s_last: LogicHandle,
    s_user: LogicHandle,
    m_valid: LogicHandle,
    m_ready: LogicHandle,
    m_data: LogicHandle,
    m_id: LogicHandle,
    m_last: LogicHandle,
    m_user: LogicHandle,
    inject_error: LogicHandle,
    accepted_count: LogicHandle,
}

struct StreamVpiModel {
    model: BenchModel,
    values: BenchOutputs,
    target: u64,
    started: Instant,
}

impl CycleModel<BenchInputs, BenchOutputs> for StreamVpiModel {
    fn new(outputs: &mut BenchOutputs) -> Result<Self, String> {
        let target =
            env_u64("RUSTDV_BENCH_TRANSACTIONS", 100_000).map_err(|error| error.to_string())?;
        let seed = env_u64("RUSTDV_BENCH_SEED", 1).map_err(|error| error.to_string())?;
        let inject_error = env_flag("RUSTDV_BENCH_INJECT_ERROR");
        let (model, values) = BenchModel::new(target, seed, inject_error);
        *outputs = values;
        Ok(Self {
            model,
            values,
            target,
            started: Instant::now(),
        })
    }

    fn step(
        &mut self,
        inputs: &BenchInputs,
        outputs: &mut BenchOutputs,
    ) -> Result<CycleStatus, String> {
        match self.model.step(inputs, &mut self.values) {
            StepStatus::Continue => {
                *outputs = self.values;
                Ok(CycleStatus::Continue)
            }
            StepStatus::Pass(report) => {
                let elapsed = self.started.elapsed().as_secs_f64();
                println!(
                    "BENCHMARK: PASS backend=rustdv-vpi transactions={} cycles={} digest={:016x} trace={:016x} elapsed_s={:.9} cycles_per_s={:.3}",
                    report.transactions,
                    report.cycles,
                    report.digest,
                    report.trace_digest,
                    elapsed,
                    report.cycles as f64 / elapsed
                );
                Ok(CycleStatus::Pass)
            }
            StepStatus::Fail(message) => {
                println!(
                    "BENCHMARK: FAIL backend=rustdv-vpi transactions={} message={message}",
                    self.target
                );
                Err(message)
            }
        }
    }
}

impl Handles {
    fn new(dut: &HierarchyHandle) -> Result<Self, TestError> {
        Ok(Self {
            clk: dut.signal("clk")?,
            reset_n: dut.signal("reset_n")?,
            s_valid: dut.signal("s_valid")?,
            s_ready: dut.signal("s_ready")?,
            s_data: dut.signal("s_data")?,
            s_id: dut.signal("s_id")?,
            s_last: dut.signal("s_last")?,
            s_user: dut.signal("s_user")?,
            m_valid: dut.signal("m_valid")?,
            m_ready: dut.signal("m_ready")?,
            m_data: dut.signal("m_data")?,
            m_id: dut.signal("m_id")?,
            m_last: dut.signal("m_last")?,
            m_user: dut.signal("m_user")?,
            inject_error: dut.signal("inject_error")?,
            accepted_count: dut.signal("accepted_count")?,
        })
    }
}

#[rustdv::test(timeout_time = 60, timeout_unit = "s")]
async fn stream_throughput(ctx: RustdvCtx) -> Result<(), TestError> {
    let handles = Handles::new(&ctx.dut())?;
    let mut driven = None;
    let status = run_cycle_model_vpi::<StreamVpiModel, BenchInputs, BenchOutputs, _, _>(
        &handles.clk,
        SimDuration::ns(2),
        || sample(&handles).map_err(|error| error.to_string()),
        |outputs| {
            drive(&handles, outputs, &mut driven);
            Ok(())
        },
    )
    .await
    .map_err(TestError::new)?;
    if status == CycleStatus::Pass {
        Ok(())
    } else {
        Err(TestError::new("cycle model returned failure"))
    }
}
