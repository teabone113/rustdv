//! Portable VPI execution adapter for value-oriented cycle models.

use rustdv_cycle::{CycleModel, CycleStatus};
use rustdv_sim::{next_time_step, read_only, Clock, LogicHandle, SimDuration};

/// Run a [`CycleModel`] on the portable VPI scheduler.
///
/// Generated or handwritten closures translate top-level handles to and from
/// the model's value types. The adapter owns clock generation and performs one
/// sample/step/drive sequence per rising edge.
pub async fn run_cycle_model_vpi<M, I, O, Sample, Drive>(
    clock: &LogicHandle,
    period: SimDuration,
    mut sample: Sample,
    mut drive: Drive,
) -> Result<CycleStatus, String>
where
    M: CycleModel<I, O>,
    O: Default,
    Sample: FnMut() -> Result<I, String>,
    Drive: FnMut(&O) -> Result<(), String>,
{
    let mut outputs = O::default();
    let mut model = M::new(&mut outputs)?;
    drive(&outputs)?;
    let running_clock = Clock::new(clock, period).start();

    let result: Result<CycleStatus, String> = async {
        loop {
            clock.rising_edge().await;
            read_only().await;
            let inputs = sample()?;
            match model.step(&inputs, &mut outputs)? {
                CycleStatus::Continue => {
                    next_time_step().await;
                    drive(&outputs)?;
                }
                status => break Ok(status),
            }
        }
    }
    .await;

    running_clock.cancel();
    let finish = model.finish();
    match (result, finish) {
        (Err(error), _) => Err(error),
        (Ok(_), Err(error)) => Err(error),
        (Ok(status), Ok(())) => Ok(status),
    }
}
