//! Backend-neutral cycle models and the direct Verilator ABI.
//!
//! A cycle model consumes plain values, produces the next cycle's drive
//! values, and returns a structured status. The same model can sit behind a
//! VPI adapter or a generated direct-port adapter.

use std::ffi::CString;
use std::os::raw::{c_char, c_void};
use std::panic::{catch_unwind, AssertUnwindSafe};

pub const CYCLE_ABI_VERSION: u32 = 1;

#[repr(u32)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum CycleStatus {
    Continue = 0,
    Pass = 1,
    Fail = 2,
}

impl CycleStatus {
    pub fn from_raw(value: u32) -> Option<Self> {
        match value {
            0 => Some(Self::Continue),
            1 => Some(Self::Pass),
            2 => Some(Self::Fail),
            _ => None,
        }
    }
}

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CycleAbiHeader {
    pub abi_version: u32,
    pub info_size: u32,
}

#[repr(C)]
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct CycleAbiInfo {
    pub abi_version: u32,
    pub info_size: u32,
    pub input_size: u32,
    pub input_align: u32,
    pub output_size: u32,
    pub output_align: u32,
    pub schema_hash: u64,
    pub reserved: [u64; 4],
}

impl CycleAbiInfo {
    pub const fn for_types<I, O>(schema_hash: u64) -> Self {
        Self {
            abi_version: CYCLE_ABI_VERSION,
            info_size: std::mem::size_of::<Self>() as u32,
            input_size: std::mem::size_of::<I>() as u32,
            input_align: std::mem::align_of::<I>() as u32,
            output_size: std::mem::size_of::<O>() as u32,
            output_align: std::mem::align_of::<O>() as u32,
            schema_hash,
            reserved: [0; 4],
        }
    }
}

/// A synchronous value model independent of VPI and Verilator handles.
pub trait CycleModel<I, O>: Sized {
    /// Create the model and initialize the values driven before cycle zero.
    fn new(outputs: &mut O) -> Result<Self, String>;

    /// Observe the just-completed cycle and prepare drives for the next one.
    fn step(&mut self, inputs: &I, outputs: &mut O) -> Result<CycleStatus, String>;

    /// Optional end-of-simulation check.
    fn finish(&mut self) -> Result<(), String> {
        Ok(())
    }
}

#[doc(hidden)]
pub struct ExportContext<M> {
    model: M,
    error: CString,
}

#[doc(hidden)]
pub fn empty_error() -> CString {
    CString::new("").expect("empty CString")
}

#[doc(hidden)]
pub fn set_error<M>(context: &mut ExportContext<M>, message: impl AsRef<str>) {
    let without_nuls = message.as_ref().replace('\0', "\\0");
    context.error = CString::new(without_nuls).expect("NULs were replaced");
}

#[doc(hidden)]
pub fn panic_message(payload: Box<dyn std::any::Any + Send>) -> String {
    if let Some(message) = payload.downcast_ref::<&str>() {
        (*message).to_owned()
    } else if let Some(message) = payload.downcast_ref::<String>() {
        message.clone()
    } else {
        "non-string panic in cycle model".to_owned()
    }
}

#[doc(hidden)]
pub unsafe fn create_context<M, I, O>(outputs: *mut O) -> *mut c_void
where
    M: CycleModel<I, O>,
{
    if outputs.is_null() {
        return std::ptr::null_mut();
    }
    match catch_unwind(AssertUnwindSafe(|| M::new(&mut *outputs))) {
        Ok(Ok(model)) => Box::into_raw(Box::new(ExportContext {
            model,
            error: empty_error(),
        })) as *mut c_void,
        Ok(Err(message)) => {
            eprintln!("rustdv-cycle: model creation failed: {message}");
            std::ptr::null_mut()
        }
        Err(payload) => {
            eprintln!(
                "rustdv-cycle: model creation panicked: {}",
                panic_message(payload)
            );
            std::ptr::null_mut()
        }
    }
}

#[doc(hidden)]
pub unsafe fn step_context<M, I, O>(
    raw_context: *mut c_void,
    inputs: *const I,
    outputs: *mut O,
) -> u32
where
    M: CycleModel<I, O>,
{
    if raw_context.is_null() || inputs.is_null() || outputs.is_null() {
        return CycleStatus::Fail as u32;
    }
    let context = &mut *(raw_context as *mut ExportContext<M>);
    match catch_unwind(AssertUnwindSafe(|| {
        context.model.step(&*inputs, &mut *outputs)
    })) {
        Ok(Ok(status)) => status as u32,
        Ok(Err(message)) => {
            set_error(context, message);
            CycleStatus::Fail as u32
        }
        Err(payload) => {
            set_error(
                context,
                format!("cycle model panicked: {}", panic_message(payload)),
            );
            CycleStatus::Fail as u32
        }
    }
}

#[doc(hidden)]
pub unsafe fn finish_context<M, I, O>(raw_context: *mut c_void) -> u32
where
    M: CycleModel<I, O>,
{
    if raw_context.is_null() {
        return CycleStatus::Fail as u32;
    }
    let context = &mut *(raw_context as *mut ExportContext<M>);
    match catch_unwind(AssertUnwindSafe(|| context.model.finish())) {
        Ok(Ok(())) => CycleStatus::Pass as u32,
        Ok(Err(message)) => {
            set_error(context, message);
            CycleStatus::Fail as u32
        }
        Err(payload) => {
            set_error(
                context,
                format!(
                    "cycle model panicked during finish: {}",
                    panic_message(payload)
                ),
            );
            CycleStatus::Fail as u32
        }
    }
}

#[doc(hidden)]
pub unsafe fn context_error<M>(raw_context: *mut c_void) -> *const c_char {
    if raw_context.is_null() {
        return std::ptr::null();
    }
    let context = &*(raw_context as *mut ExportContext<M>);
    context.error.as_ptr()
}

#[doc(hidden)]
pub unsafe fn destroy_context<M>(raw_context: *mut c_void) {
    if !raw_context.is_null() {
        drop(Box::from_raw(raw_context as *mut ExportContext<M>));
    }
}

/// Export one [`CycleModel`] from a `cdylib` using rustdv's stable cycle ABI.
#[macro_export]
macro_rules! export_cycle_model {
    (
        model = $model:ty,
        inputs = $inputs:ty,
        outputs = $outputs:ty,
        schema_hash = $schema_hash:expr $(,)?
    ) => {
        static RUSTDV_CYCLE_ABI_INFO: $crate::CycleAbiInfo =
            $crate::CycleAbiInfo::for_types::<$inputs, $outputs>($schema_hash);

        #[no_mangle]
        pub extern "C" fn rustdv_cycle_abi_info() -> *const $crate::CycleAbiHeader {
            &RUSTDV_CYCLE_ABI_INFO as *const $crate::CycleAbiInfo as *const $crate::CycleAbiHeader
        }

        #[no_mangle]
        pub unsafe extern "C" fn rustdv_cycle_create(
            outputs: *mut $outputs,
        ) -> *mut ::std::os::raw::c_void {
            $crate::create_context::<$model, $inputs, $outputs>(outputs)
        }

        #[no_mangle]
        pub unsafe extern "C" fn rustdv_cycle_step(
            context: *mut ::std::os::raw::c_void,
            inputs: *const $inputs,
            outputs: *mut $outputs,
        ) -> u32 {
            $crate::step_context::<$model, $inputs, $outputs>(context, inputs, outputs)
        }

        #[no_mangle]
        pub unsafe extern "C" fn rustdv_cycle_finish(context: *mut ::std::os::raw::c_void) -> u32 {
            $crate::finish_context::<$model, $inputs, $outputs>(context)
        }

        #[no_mangle]
        pub unsafe extern "C" fn rustdv_cycle_last_error(
            context: *mut ::std::os::raw::c_void,
        ) -> *const ::std::os::raw::c_char {
            $crate::context_error::<$model>(context)
        }

        #[no_mangle]
        pub unsafe extern "C" fn rustdv_cycle_destroy(context: *mut ::std::os::raw::c_void) {
            $crate::destroy_context::<$model>(context)
        }
    };
}

#[cfg(test)]
mod tests {
    use super::*;

    #[repr(C)]
    #[derive(Default)]
    struct Inputs {
        value: u64,
    }

    #[repr(C)]
    #[derive(Default)]
    struct Outputs {
        value: u64,
    }

    struct Model;

    impl CycleModel<Inputs, Outputs> for Model {
        fn new(outputs: &mut Outputs) -> Result<Self, String> {
            outputs.value = 1;
            Ok(Self)
        }

        fn step(&mut self, inputs: &Inputs, outputs: &mut Outputs) -> Result<CycleStatus, String> {
            outputs.value += inputs.value;
            Ok(if outputs.value >= 4 {
                CycleStatus::Pass
            } else {
                CycleStatus::Continue
            })
        }
    }

    #[test]
    fn erased_context_runs_the_pure_contract() {
        let mut outputs = Outputs::default();
        let context = unsafe { create_context::<Model, Inputs, Outputs>(&mut outputs) };
        assert!(!context.is_null());
        assert_eq!(outputs.value, 1);
        let inputs = Inputs { value: 3 };
        let status =
            unsafe { step_context::<Model, Inputs, Outputs>(context, &inputs, &mut outputs) };
        assert_eq!(CycleStatus::from_raw(status), Some(CycleStatus::Pass));
        assert_eq!(outputs.value, 4);
        unsafe { destroy_context::<Model>(context) };
    }

    #[test]
    fn abi_info_describes_actual_layout() {
        let info = CycleAbiInfo::for_types::<Inputs, Outputs>(0x1234);
        assert_eq!(info.abi_version, CYCLE_ABI_VERSION);
        assert_eq!(info.input_size as usize, std::mem::size_of::<Inputs>());
        assert_eq!(info.output_align as usize, std::mem::align_of::<Outputs>());
        assert_eq!(info.schema_hash, 0x1234);
    }

    #[test]
    fn abi_header_is_a_fixed_prefix() {
        assert_eq!(std::mem::size_of::<CycleAbiHeader>(), 8);
        assert_eq!(std::mem::offset_of!(CycleAbiInfo, abi_version), 0);
        assert_eq!(std::mem::offset_of!(CycleAbiInfo, info_size), 4);
    }
}
