//! Simulator-independent model for the stream-throughput benchmark.

pub const RESET_CYCLES: u64 = 4;
const DATA_XOR: u64 = 0xd6e8_feb8_6659_fd93;
const DATA_ADD: u64 = 0xa5a5_5a5a_1234_5678;

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct BenchInputs {
    pub s_ready: u8,
    pub m_valid: u8,
    pub m_data: u64,
    pub m_id: u16,
    pub m_last: u8,
    pub m_user: u8,
    pub accepted_count: u64,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct BenchOutputs {
    pub reset_n: u8,
    pub s_valid: u8,
    pub s_data: u64,
    pub s_id: u16,
    pub s_last: u8,
    pub s_user: u8,
    pub m_ready: u8,
    pub inject_error: u8,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub enum StepStatus {
    Continue,
    Pass(BenchReport),
    Fail(String),
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct BenchReport {
    pub transactions: u64,
    pub cycles: u64,
    pub digest: u64,
    pub trace_digest: u64,
}

pub struct BenchModel {
    target: u64,
    seed: u64,
    inject_error: bool,
    cycles: u64,
    transactions: u64,
    digest: u64,
    trace_digest: u64,
}

impl BenchModel {
    pub fn new(target: u64, seed: u64, inject_error: bool) -> (Self, BenchOutputs) {
        assert!(target > 0, "benchmark transaction count must be positive");
        let outputs = BenchOutputs {
            reset_n: 0,
            m_ready: 0,
            inject_error: u8::from(inject_error),
            ..BenchOutputs::default()
        };
        (
            Self {
                target,
                seed,
                inject_error,
                cycles: 0,
                transactions: 0,
                digest: 0,
                trace_digest: 0,
            },
            outputs,
        )
    }

    pub fn step(&mut self, inputs: &BenchInputs, outputs: &mut BenchOutputs) -> StepStatus {
        self.cycles += 1;
        self.trace_digest = trace_digest_update(self.trace_digest, self.cycles, inputs, outputs);

        if outputs.reset_n == 0 {
            if inputs.m_valid != 0 || inputs.accepted_count != 0 {
                return StepStatus::Fail(format!(
                    "DUT was active during reset: m_valid={} accepted_count={}",
                    inputs.m_valid, inputs.accepted_count
                ));
            }
            if self.cycles >= RESET_CYCLES {
                outputs.reset_n = 1;
                outputs.m_ready = u8::from(ready_open(self.seed, 0));
                self.load_source_for_cycle(0, outputs);
            }
            return StepStatus::Continue;
        }

        let accepted = outputs.s_valid != 0 && inputs.s_ready != 0;
        let emitted = inputs.m_valid != 0 && outputs.m_ready != 0;
        if accepted != emitted {
            return StepStatus::Fail(format!(
                "ready/valid transfer disagreement at cycle {}: input={} output={}",
                self.cycles, accepted, emitted
            ));
        }

        if inputs.s_ready != outputs.m_ready {
            return StepStatus::Fail(format!(
                "ready path mismatch at cycle {}: s_ready={} m_ready={}",
                self.cycles, inputs.s_ready, outputs.m_ready
            ));
        }
        if inputs.m_valid != outputs.s_valid {
            return StepStatus::Fail(format!(
                "valid path mismatch at cycle {}: m_valid={} s_valid={}",
                self.cycles, inputs.m_valid, outputs.s_valid
            ));
        }

        if inputs.m_valid != 0 {
            let index = self.transactions;
            let expected_data = transform_data(payload(self.seed, index), index as u16);
            let expected_id = index as u16;
            let expected_last = u8::from((index & 0xff) == 0xff);
            let expected_user = user_value(self.seed, index);

            if inputs.m_data != expected_data
                || inputs.m_id != expected_id
                || inputs.m_last != expected_last
                || inputs.m_user != expected_user
            {
                return StepStatus::Fail(format!(
                    "payload mismatch for transfer {index}: got data=0x{:016x} id=0x{:04x} last={} user=0x{:02x}; expected data=0x{expected_data:016x} id=0x{expected_id:04x} last={expected_last} user=0x{expected_user:02x}",
                    inputs.m_data, inputs.m_id, inputs.m_last, inputs.m_user
                ));
            }

            if emitted {
                self.digest = digest_update(
                    self.digest,
                    inputs.m_data,
                    inputs.m_id,
                    inputs.m_last,
                    inputs.m_user,
                );
                self.transactions += 1;
            }
        }

        if inputs.accepted_count != self.transactions {
            return StepStatus::Fail(format!(
                "DUT accepted_count mismatch at cycle {}: got {}, expected {}",
                self.cycles, inputs.accepted_count, self.transactions
            ));
        }

        if self.transactions == self.target {
            outputs.s_valid = 0;
            return StepStatus::Pass(BenchReport {
                transactions: self.transactions,
                cycles: self.cycles - RESET_CYCLES,
                digest: self.digest,
                trace_digest: self.trace_digest,
            });
        }

        let active_cycle = self.cycles - RESET_CYCLES;
        outputs.m_ready = u8::from(ready_open(self.seed, active_cycle));
        if accepted || outputs.s_valid == 0 {
            self.load_source_for_cycle(active_cycle, outputs);
        }
        StepStatus::Continue
    }

    fn load_source_for_cycle(&self, active_cycle: u64, outputs: &mut BenchOutputs) {
        if source_open(self.seed, active_cycle) {
            let index = self.transactions;
            outputs.s_valid = 1;
            outputs.s_data = payload(self.seed, index);
            outputs.s_id = index as u16;
            outputs.s_last = u8::from((index & 0xff) == 0xff);
            outputs.s_user = user_value(self.seed, index);
        } else {
            outputs.s_valid = 0;
        }
        outputs.inject_error = u8::from(self.inject_error);
    }
}

pub fn mix64(mut value: u64) -> u64 {
    value = value.wrapping_add(0x9e37_79b9_7f4a_7c15);
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

pub fn payload(seed: u64, index: u64) -> u64 {
    mix64(seed ^ index.wrapping_mul(0x9e37_79b9_7f4a_7c15))
}

pub fn user_value(seed: u64, index: u64) -> u8 {
    (mix64(seed ^ index ^ 0x6a09_e667_f3bc_c909) >> 56) as u8
}

pub fn source_open(seed: u64, cycle: u64) -> bool {
    mix64(seed ^ cycle.wrapping_mul(0xd134_2543_de82_ef95)) & 0x7 != 0
}

pub fn ready_open(seed: u64, cycle: u64) -> bool {
    mix64(seed ^ cycle.wrapping_mul(0x94d0_49bb_1331_11eb) ^ 0xa409_3822_299f_31d0) & 0xf != 0
}

pub fn transform_data(data: u64, id: u16) -> u64 {
    (data ^ DATA_XOR)
        .rotate_left(13)
        .wrapping_add(DATA_ADD)
        .wrapping_add(id as u64)
}

pub fn digest_update(digest: u64, data: u64, id: u16, last: u8, user: u8) -> u64 {
    let sidebands = (id as u64) | ((last as u64) << 16) | ((user as u64) << 24);
    digest.rotate_left(7) ^ data ^ sidebands.wrapping_mul(0x9e37_79b9_7f4a_7c15)
}

pub fn trace_digest_update(
    digest: u64,
    cycle: u64,
    inputs: &BenchInputs,
    outputs: &BenchOutputs,
) -> u64 {
    let m_data = if inputs.m_valid != 0 {
        inputs.m_data
    } else {
        0
    };
    let s_data = if outputs.s_valid != 0 {
        outputs.s_data
    } else {
        0
    };
    let (m_id, m_last, m_user) = if inputs.m_valid != 0 {
        (inputs.m_id, inputs.m_last, inputs.m_user)
    } else {
        (0, 0, 0)
    };
    let (s_id, s_last, s_user) = if outputs.s_valid != 0 {
        (outputs.s_id, outputs.s_last, outputs.s_user)
    } else {
        (0, 0, 0)
    };
    let flags = (outputs.reset_n as u64)
        | ((outputs.s_valid as u64) << 1)
        | ((inputs.s_ready as u64) << 2)
        | ((inputs.m_valid as u64) << 3)
        | ((outputs.m_ready as u64) << 4)
        | ((m_last as u64) << 5)
        | ((s_last as u64) << 6)
        | ((m_user as u64) << 8)
        | ((s_user as u64) << 16);
    let sidebands = (m_id as u64) | ((s_id as u64) << 16) | (flags << 32);
    mix64(
        digest
            ^ mix64(cycle)
            ^ mix64(inputs.accepted_count)
            ^ mix64(m_data)
            ^ mix64(s_data)
            ^ mix64(sidebands),
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn deterministic_vectors_are_stable() {
        assert_eq!(payload(1, 0), 0x910a_2dec_8902_5cc1);
        assert_eq!(payload(1, 1), 0xe99f_f867_dbf6_82c9);
        assert_eq!(
            transform_data(0x0123_4567_89ab_cdef, 0x1234),
            0x1d21_5858_5844_03a5
        );
        assert_eq!(user_value(1, 0), 0x1a);
        assert_eq!(
            trace_digest_update(0, 1, &BenchInputs::default(), &BenchOutputs::default()),
            0x5e41_ab08_7439_611e
        );
    }

    #[test]
    fn stalled_source_payload_is_retained() {
        let (mut model, mut outputs) = BenchModel::new(2, 1, false);
        let reset_inputs = BenchInputs::default();
        for _ in 0..RESET_CYCLES {
            assert_eq!(
                model.step(&reset_inputs, &mut outputs),
                StepStatus::Continue
            );
        }
        outputs.m_ready = 0;
        let before = outputs;
        let inputs = BenchInputs {
            m_valid: 1,
            m_data: transform_data(outputs.s_data, 0),
            m_user: user_value(1, 0),
            ..BenchInputs::default()
        };
        assert_eq!(model.step(&inputs, &mut outputs), StepStatus::Continue);
        assert_eq!(outputs.s_valid, before.s_valid);
        assert_eq!(outputs.s_data, before.s_data);
    }
}
