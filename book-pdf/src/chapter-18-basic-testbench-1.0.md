# Chapter 18: Basic Testbench: 1.0

The TinyALU is back. From here to the end of the book we do what both earlier books did: write increasingly modular and maintainable versions of one testbench, for one DUT, with the version numbers meaning the same architectural steps they have always meant. This chapter is version 1.0 — a single loop, easy to follow, deliberately naive — and its private teaching agenda is watching `Result`, `?`, and `match`-hardened enums shape testbench code.

> **In the UVM...** both earlier books began exactly here. The TinyALU: two 8-bit legs `A` and `B`, an `op` bus, a 16-bit `result`. ADD, AND, and XOR take one clock; MUL takes three. The user drives the operands and raises `start`; the DUT raises `done` with the result. `reset_n` is active-low and synchronous. And testbench 1.0 was one loop on the falling clock edge, reading `start` and `done` to decide whether to send a command or check a result.

The DUT is the same `tinyalu.sv` the earlier books verified — same protocol, same timing. Its port list is the whole contract:

```text
# Figure 1: The TinyALU's interface

module tinyalu (input [7:0] A,
                input [7:0] B,
                input [2:0] op,
                input reset_n,
                input start,
                output bit clk,
                output done,
                output [15:0] result);
```

The rules that matter for the loop: a command is *sent* by raising `start` when both `start` and `done` are 0; a multi-cycle operation is *in flight* while `start` is 1 and `done` is 0; the *result* is valid on a falling edge where both are 1; and `done` while `start` is low is something the DUT must never do.

## The Ops enumeration

Every version of this testbench has had an `Ops` enum doing double duty: naming the operations and mapping each to its opcode. The Rust `Ops` has been with us since Chapter 7, and here is its final, working form:

```rust
// Figure 2: The operation enumeration

// Legal ops for the TinyALU
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
#[repr(u8)]
pub enum Ops {
    Add = 1,
    And = 2,
    Xor = 3,
    Mul = 4,
}

impl Ops {
    pub const ALL: [Ops; 4] = [Ops::Add, Ops::And, Ops::Xor, Ops::Mul];
}
```

Three details earn their keep today. `#[repr(u8)]` with explicit discriminants gives each op its opcode, so `op as u64` produces the value the `op` bus wants — the `IntEnum` job. `Hash` joins the derive list because this chapter's coverage lives in a `HashSet<Ops>` (Chapter 8). And `Ops::ALL` replaces Python's `list(Ops)` — Rust enums do not iterate themselves, so we say what "all of them" means, once, next to the definition.

## The alu_prediction() function

Constrained-random verification stands on prediction: generate random stimulus, predict the result, compare. Here is the golden model, and the figure where `match` retires the `if/elif` chain for good:

```rust
// Figure 3: The prediction function for the scoreboard

pub fn alu_prediction(a: u8, b: u8, op: Ops) -> u16 {
    // Rust model of the TinyALU
    let (a, b) = (a as u16, b as u16);
    match op {
        Ops::Add => a + b,
        Ops::And => a & b,
        Ops::Xor => a ^ b,
        Ops::Mul => a * b,
    }
}
```

Two whole classes of defensive code from the Python version are gone, not moved. The opening `assert isinstance(op, Ops)` vanished because the signature *is* the assertion — nothing but an `Ops` can arrive. And the unwritten fifth branch (what if op is none of the four?) vanished because Chapter 4's exhaustiveness rule proves there is no fifth `Ops`. The widths, meanwhile, got honest: `u8` legs, `u16` result, casts before arithmetic so ADD carries into bit eight and MUL fills the bus — details Python's unbounded integers let the book gloss over, and unit-test bait we already collected in Chapter 14.

## Setting up the TinyALU test

```rust
// Figure 4: The start of the TinyALU test. Reset the DUT

#[rustdv::test]
async fn alu_test(ctx: RustdvCtx) -> Result<(), TestError> {
    let dut = ctx.dut();
    let mut rng = ctx.rng();
    // The RTL self-clocks (tinyalu.sv); the BFM only waits on edges.
    let clk = dut.signal("clk")?;

    let mut passed = true;
    let mut cvg: HashSet<Ops> = HashSet::new(); // functional coverage

    let reset_n = dut.signal("reset_n")?;
    let start = dut.signal("start")?;
    clk.falling_edge().await;
    reset_n.set_u64(0);
    start.set_u64(0);
    clk.falling_edge().await;
    reset_n.set_u64(1);
```

The shape is the classic 1.0 exactly — `passed` flag, coverage set, reset sequence on falling edges — with Chapter 17's spellings. One newcomer: `ctx.rng()`. Python reached for the global `random` module, SystemVerilog for `$urandom` and a simulator seed flag; rustdv hands each test a seeded generator, and the runner prints the seed on every run (`RUSTDV_RANDOM_SEED=1` in this chapter's transcript), so a failure reproduces by exporting one variable. Randomness you cannot replay is a bug-report you cannot act on.

## Sending commands

```rust
// Figure 5: Creating one transaction for each operation

    let mut cmd_count = 1;
    let mut op_list: Vec<Ops> = Ops::ALL.to_vec();
    let num_ops = op_list.len();
    let (mut aa, mut bb) = (0u8, 0u8);
    let mut op = Ops::Add;
    while cmd_count <= num_ops {
        clk.falling_edge().await;
        let st = get_int(&start);
        let dn = get_int(&dut.signal("done")?);
```

(One honest Rust tax, visible above: `aa`, `bb`, and `op` are declared *before* the loop, because they are written in one falling-edge iteration — command sent — and read in a later one — result checked. Python let the book conjure `aa` into existence inside the `if` and trust it would still be there four clocks later; Rust makes the loop-spanning lifetime explicit. The compiler would have caught the case where a result arrives before any command set them — which is exactly the kind of protocol accident 1.0-style testbenches suffer.)

With the falling-edge values of `start` and `done` in hand, the loop dispatches on the protocol state, one figure per state:

```rust
// Figure 6: Creating a TinyALU command

        if st == 0 && dn == 0 {
            aa = rng.u8();
            bb = rng.u8();
            op = op_list.remove(0);
            cvg.insert(op);
            dut.signal("A")?.set_u64(aa as u64);
            dut.signal("B")?.set_u64(bb as u64);
            dut.signal("op")?.set_u64(op as u64);
            start.set_u64(1);
        }
```

`rng.u8()` is `random.randint(0, 255)` with the range in the type. `op_list.remove(0)` is `op_list.pop(0)` — pop-from-the-front keeps the op order deterministic even as operands randomize.

```rust
// Figure 7: Erroring on a state that must never happen

        if st == 0 && dn == 1 {
            return Err(TestError::from("DUT Error: done set to 1 without start"));
        }
```

The Python version raised `AssertionError` here. We return an `Err` instead, and the distinction is Chapter 9's taxonomy applied with a straight face: this is not a testbench bug, it is the *DUT misbehaving* — a check, and checks fail tests through `Result`. Panics stay reserved for our own broken code.

```rust
// Figure 8: If we are in an operation, continue

        if st == 1 && dn == 0 {
            continue;
        }
```

## Checking the result

```rust
// Figure 9: The operation is complete

        if st == 1 && dn == 1 {
            start.set_u64(0);
            cmd_count += 1;
            let result = get_int(&dut.signal("result")?) as u16;

// Figure 10: Checking results against the prediction

            let pr = alu_prediction(aa, bb, op);
            if result == pr {
                log::info(&format!("PASSED: {aa:02x} {op:?} {bb:02x} = {result:04x}"));
            } else {
                log::error(&format!(
                    "FAILED: {aa:02x} {op:?} {bb:02x} = {result:04x} - predicted {pr:04x}"
                ));
                passed = false;
            }
        }
    }
```

Format strings do the Python's job with the Python's syntax, near enough: `{aa:02x}` for hex operands, `{result:04x}` for the sixteen-bit result, and `{op:?}` — the `Debug` derive — where Python used `op.name`.

## Finishing the test

Belt and suspenders, ported: did we actually exercise every operation?

```rust
// Figure 11: Checking functional coverage using a set

    let missed: HashSet<Ops> =
        Ops::ALL.iter().filter(|op| !cvg.contains(op)).copied().collect();
    if !missed.is_empty() {
        log::error(&format!("Functional coverage error. Missed: {missed:?}"));
        passed = false;
    } else {
        log::info("Covered all operations");
    }
```

Python spelled it `set(Ops) - cvg`; Rust spells it as an iterator chain — filter `ALL` down to the ops the coverage set is missing, collect the survivors (Chapter 12's adapters, on duty). And where the Python test ended with `assert passed`, ours ends by *constructing its return value*:

```rust
// Figure 12: The final check relays pass/fail to rustdv

    if passed {
        Ok(())
    } else {
        Err(TestError::from("alu_test saw failing comparisons"))
    }
}
```

The test's last expression is the test's verdict — no exception mechanism carrying a boolean by proxy, just the `Result` the signature promised in figure 4.

```text
# Figure 13: A successful test
--
     40.00ns INFO     PASSED: c1 Add 67 = 0128
     60.00ns INFO     PASSED: 5e And 0b = 000a
     80.00ns INFO     PASSED: b9 Xor 80 = 0039
    130.00ns INFO     PASSED: a5 Mul 75 = 4b69
    130.00ns INFO     Covered all operations
    130.00ns INFO     alu_test PASSED
```

Four operations, random operands, all compared against prediction, all covered — the same happy transcript as the Python book's figure 15, sixty-five microseconds of that book's simulated time compressed to 130 nanoseconds mostly because our clock is faster and our reset shorter. MUL takes its three cycles (watch the 50ns gap before it); the others take one.

## Summary

Testbench 1.0 verified the TinyALU with one loop: reset, then a falling-edge state machine that sends a random command when the bus is idle, errors if `done` fires without `start`, waits out multi-cycle operations, and predicts-and-compares when `done` arrives — with a coverage set confirming every op ran. The Rust-specific texture: `Ops` carries its opcodes in its `repr` and its completeness in the type; `alu_prediction` lost its runtime type guard to the signature and its missing-branch anxiety to `match`; DUT misbehavior returns `Err` while panics stay reserved for testbench bugs; and the run is reproducible by seed, printed on every transcript.

And the earlier books' closing judgment of 1.0 needs no translation: this testbench works because the TinyALU is tiny. Everything is jammed in one loop — stimulus, protocol, checking, coverage — and no team could grow it. The first step out, then as now, is to split the *signal-level* work from the *testbench-level* work. That split has a name: the Bus Functional Model, and it is Chapter 19.
