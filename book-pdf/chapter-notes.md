# Chapter notes

One row per chapter. Read the row, read the source crate it names and that
crate's `README.md`, then write. `FABLE.md` has the rules that apply everywhere.

**Nothing is blocked.** The Interlude and ch40 present the complete TinyALU
testbench from `rustdv/tinyalu_tb`, and that crate was converted to the restored
framework on 2026-07-29 — phases, the ConfigDb, the factory, `AnalysisBus`, a
sequencer, and two struct tests that swap stimulus through the sequence factory.
Both chapters can be written from it as it stands. Its files are
`tinyalu_tb.rs`, `env.rs`, `components.rs`, `sequences.rs`, `alu_item.rs` and
`alu_bfm.rs`. ~~The manuscript currently cites a `tinyalu_tb/src/lib.rs`, which has
not existed for some time.~~ (Struck 2026-08-05: no `tinyalu_tb/src/lib.rs`
citation remains anywhere in `book-pdf/src` — ch40 Figure 1 shows the real
file list, and the only `lib.rs` mentions left are ch14/ch40 explaining the
convention.)

---

## Part I — chapters 1–14: Rust, before rustdv

**Source:** `output/examples/chNN-*/src/bin/`, one file per listing.
**Status:** these chapters were written against Rust, which did not change, so
the technical content stands. The work here is the dual-audience pass.

**Listings are frozen.** `book-sync` compares ch1–14 listings against their
example files verbatim and is wired into the git pre-push hook. Change a
character inside a code block and the suite goes red. Prose around the blocks is
yours.

The pass, for every chapter in this part:

- Replace the old `> **In Python we...**` recap label with `> **In the UVM...**`
  and rewrite the body in shared UVM API terms.
- Judge every "the Python book" / "In Python" passage individually — keep it
  (rewritten so it never assumes the reader lived it), pair it with the
  SystemVerilog analog where that analog is as sharp or sharper, or say it in
  Rust's own terms where the comparison was only scaffolding.
- Run the banned-framings list from `FABLE.md` over the result.

| Ch | Title | Notes |
|---|---|---|
| 1 | Why Rust | **Carries the frame, once, for the whole book — then stops.** The frame is the seam: *types for data and ownership; runtime indirection for topology and binding.* Not "Rust catches your bugs." Do **not** promise that config, factory or TLM errors become compile errors: they resolve at run time by design, ch27/ch28/ch31 say so plainly, and an earlier draft of this chapter made exactly that promise and was wrong. The two reasons for Rust that survive scrutiny, neither of them bug-finding: types scale with codebase and team size — a fifty-component testbench refactored by four people gets something a five-hundred-line pyuvm testbench does not — and a compiled language with no garbage collector is the *emulation* argument, which is about throughput. Where the compiler genuinely earned its keep on this project it was on **memory and ownership**, not binding: the `'static` bound on `spawn` refused an unsound concurrent design, and `async fn` in a trait forced an architectural decision early. Say that, and mean it, and then let the rest of the book show rather than argue. **This chapter sets the tone for 40 others — if it gloats, they all will.** Read "Do not sell types, and do not disparage what came before" in `FABLE.md` before writing a word of it. |
| 2 | Rust Concepts | Dual-audience pass. |
| 3 | Rust Basics | Dual-audience pass. |
| 4 | Conditions Loops Match | Dual-audience pass. |
| 5 | Ownership | Dual-audience pass. The concepts here are what Part II's ownership arguments rest on — `finish_item(cmd)` in ch36 is this chapter's payoff. |
| 6 | Borrowing References | Dual-audience pass. |
| 7 | Structs Enums Methods | Dual-audience pass. ch35 will lean on this. |
| 8 | Collections | Dual-audience pass. |
| 9 | Result Option Exceptions | Dual-audience pass. |
| 10 | Traits | Dual-audience pass. |
| 11 | Generics | Dual-audience pass. |
| 12 | Closures and Iterators | Dual-audience pass. |
| 13 | Smart Pointers | Dual-audience pass. `Rc`/`RefCell` here is what the framework's three sanctioned interior-mutability sites rest on. |
| 14 | Modules, Crates, and Cargo | Dual-audience pass. |

---

## The Interlude — the complete TinyALU testbench

**Source: `rustdv/tinyalu_tb/`.** The complete testbench, presented before the
climb — the best single answer to "what does rustdv code look like?", and the
reader's first sight of the destination.

It is the converted crate, so it is also the one place the whole restored
vocabulary appears at once: `build` creating children and `connect` wiring them,
the BFM arriving from the ConfigDb, five factory-built components with no
constructor arguments, an `AnalysisBus` per stream with each subscriber owning
its own storage, a sequencer, and two tests that differ only in which sequence
the factory builds. Resist explaining any of it here — the Interlude's job is to
let the reader see the shape and recognise it, not to teach it.

Read the transcript from a real run rather than composing one: the counts are
RandomTest 20 compared / 0 mismatches and MaxTest 4 / 0, and every log line
carries the component's path because the framework supplies it.

The Interlude's listings print `#[component(child)]` / `#[component(fifo)]` /
`#[component(sequencer)]` in eleven places. All three spellings are gone — the
attribute is bare `#[component]`. See the cross-cutting note at the head of
Part II.

---

## Part II onward — chapters 15–40: rustdv

Every chapter below has one example crate under `output/examples/`, and that
crate plus its `README.md` is the source of truth. Nothing checks these listings
against the manuscript, so copy them carefully.

**Cross-cutting, 2026-08-04 — DONE, no action needed. The manuscript's code is
now checked, and everything it flagged is fixed.**
`output/regression/verify-book-listings.py` compares every ch15–40 listing
against its crate and runs in the pre-push regression. On its first run it found
`Clock::new(...)` printed in ch18, ch19, ch20, ch40 and the Interlude — code
D112 deleted — plus a whole `start_of_simulation` phase in ch40 and the
Interlude that no longer exists, and a ch40 paragraph explaining a bare-DUT
exception that was retired. All corrected against the crates. The `#[component]`
sweep is applied across all 17 files. **176 listings verbatim, 0 drift.**

Standing consequence for the prose pass: **a listing you change must match its
crate, or the build fails.** Run
`python3 output/regression/verify-book-listings.py` — it takes a second. Three
exemptions are permanent and documented in the script; do not add a fourth to
make a build pass.

**Cross-cutting, 2026-07-30: the child attribute is now bare `#[component]`
— applied to the manuscript on 2026-08-04, nothing left to do.**
`#[component(child)]`, `#[component(fifo)]` and `#[component(sequencer)]` are
gone from the code — the argument never did anything. The macro only ever tested
whether one of those three words was *present*; it never read which. What a
field actually becomes is decided by its Rust type (a `RustdvComp` is a factory
slot, an `Option<T>` is declared-but-not-yet-built, a `Vec<T>` is a list), so the
word was decoration, and it had already gone wrong: `AnalysisBus` was declared
`#[component(fifo)]` while being no such thing. This closes D106's tail — there
is no per-type-versus-per-role naming question left, because there is no name.

The manuscript prints the old spelling in **16 files**: chapters 21, 24, 25, 26,
27, 28, 29, 30, 31, 32, 34, 36, 37, 38, 39, 40 and the Interlude. Every one is
stale. Take the attribute from the crate, never from the old text.

Two chapters owe more than a find-and-replace:

- **ch21** teaches `#[derive(Component)]` itself. If it explains what the
  argument means, that explanation has no subject now.
- **ch24** introduces the attribute to a reader for the first time. `#[component]`
  marks a field as a child in the tree — that is the whole rule, and it is now
  the whole syntax.

**Do not mention the change. The reader never knew the argument existed.** They
are meeting `#[component]` for the first time; there is no before-and-after to
explain, and explaining one would import a history the book does not have.

| Ch | Source crate | What must change |
|---|---|---|
| 15 | `ch15-async-await-executor` | 2 listings. **The prelude debt lands here or just before** — this is where rustdv's surface first appears (`FABLE.md`, "Two writing debts"). |
| 16 | `ch16-tasks-queues` | 15 listings. |
| 17 | `ch17-simulating-with-rustdv-sim` | 6 listings. Candidate home for the rustdv catalogue if you fold it in rather than adding a chapter. **2026-08-08:** the direct-VPI footnote now names the shipped Icarus and Verilator backends; VHPI/FLI through cocotb GPI remains future reach. |
| 18 | `ch18-basic-testbench-1.0` | 11 listings. **2026-08-08:** Figure 1 matches the self-clocking RTL again: `clk` is a read-only output port consumed by the BFM, not a testbench-driven input. |
| 19 | `ch19-tinyalubfm` | 6 listings. **There is no software clock.** The RTL self-clocks and the BFM only waits on edges. `Clock` is taught once, as a cocotb feature; chapters must stop opening with `Clock::new(...)`. The reason is emulation: a BFM that waits on edges ports to a transactor unchanged, one that drives them does not. |
| 20 | `ch20-struct-based-testbench-2.0` | 11 listings. TB 2.0. **This is a destination, not a stepping stone** — a reader must be able to write a complete, useful testbench with a DUT handle and signals and no components at all. If Part II reads as training wheels for Part III, the learning-curve objection wins. |
| 21 | `ch21-macros` | Listings are bins under `src/bin/`. No simulator test — it is a macro demonstration, and it is the one crate permanently outside the chapter runs. **The attribute is bare `#[component]` now** (cross-cutting note above); this is the chapter that teaches `#[derive(Component)]`, so any passage explaining what the argument selects has lost its subject. |
| 22 | *(none)* | No listings. Prose only. |
| 23 | `ch23-uvm-test-testbench-3.0` | 6 listings. TB 3.0 — **the test is the only component.** The BFM and scoreboard are ordinary locals inside `run`; the tester is a plain value, not a component. Do not introduce a component tree here; that is ch24's job. **Two front doors, both first-class:** `#[rustdv::test]` annotates either a free `async fn` or a struct — cocotb decorates a coroutine, pyuvm decorates a class. Introduce the struct form without implying the function form was training wheels. **Classes are re-shown, not imported:** the file repeats `Tester`, `RandomTester`, `MaxTester` and `Scoreboard` under "copied from testbench 2.0", as the Python book does — say why, because those classes *evolve* (a plain trait at 3.0, a component at 4.0) and re-showing them is how the reader sees the change. **Paths are named after your test:** logs read `[HelloWorldTest]` where UVM always says `uvm_test_top`; worth a sentence, and it is where `ctx.info()` first earns its keep over bare `log::info`. **Tests register under the type name, verbatim** — `RandomTest`, not `random_test`. |
| 24 | `ch24-components` | 4 listings. **Reversed argument — rewrite, do not edit.** The chapter currently says one-pass construction "has no gap for them to fill." The gap *was* the feature: the space between a component existing and its children existing is where configuration, factory overrides and TLM connection all live. `build` is top-down, `connect` is bottom-up, and both are real phase methods again. **Do not claim compile-time phase checking.** There is one context type, `RustdvCtx`; a phase-illegal operation is a run-time failure, exactly as in the UVM. Say that cost plainly. Also: `Component::run` is an `async fn` in a trait, so the trait is not object-safe and the framework carries a dyn-safe mirror users never write — invisible in every listing, but do not claim traits and `dyn` compose freely. It is a real edge Rust has not finished, and a good sidebar. **State the phase-direction divergence:** rustdv follows pyuvm's traversal order, which differs from SystemVerilog UVM for `end_of_elaboration`, `start_of_simulation`, `extract`, `check` and `report`. **This chapter introduces the child attribute**, now bare `#[component]` (cross-cutting note above): it marks a field as a child in the tree, and that is the entire rule. |
| 25 | `ch25-uvm-env-testbench-4.0` | 10 listings. TB 4.0, the environment. **The BFM lives in the ConfigDb from here on — there is no singleton anywhere in the book.** The test does `ConfigDb::set(None, "*", "BFM", ...)` and any component asks for it by name. Introduce the ConfigDb briefly, enough to read the two lines; ch27 stays the full treatment. Owe the reader one sentence on *why* not a singleton: a singleton asserts there is exactly one BFM, which is false for any testbench with two interfaces — and say that the case which would prove it (two DUTs, two agents) is not a testbench this book builds. The cost, stated: at ch25 the reader meets a database, a path glob and a `Result` while still learning what an environment is. The singleton machinery is *deleted*, not merely unused — do not describe it as available. |
| 26 | `ch26-logging` | 7 listings. Hierarchical logging through `ctx`. |
| 27 | `ch27-configuration` | 9 listings. **Reversed at the premise — re-argue from scratch.** The chapter is currently titled "The ConfigDB Problem, Solved by Types." A path-addressed runtime ConfigDb exists. Retitle and rewrite. **The decisive exhibit runs the other way:** SystemVerilog *did* apply heavy typing here — `uvm_config_db#(T)` is parameterized and the type flows into the lookup — and what it bought was a bug class, the `int`/`bit`/`uvm_bitstream_t` mismatch where `set` and `get` never meet and the failure is a silent `return 0` indistinguishable from "never set." Dropping the type parameter, as pyuvm did, removes the failure mode outright. rustdv returns a `Result` naming the cause. Also **cut the line** claiming "nobody ever used `wait_modified` in anger" — both UVM 1800.2-2020 and pyuvm implement it. |
| 28 | `ch28-config-debugging` | 9 listings. **The four compile-fail figures were deleted and must not come back** — they proved nothing, because config resolves at run time by design. The chapter is about `dump`, tracing, and `expect_error`: a debugger's toolkit, which is what late binding buys in exchange for compile-time checking. |
| 29 | `ch29-factory` | 10 listings. **Reversed argument.** The factory is restored: `Factory`, `RustdvComp`, `new_comp`/`create_comp`, universal registration. The chapter's ledger currently lists "`create()` + type override" as ported to a maker closure — **type override is not ported that way; split it into two rows.** This chapter's history is the cautionary tale for the whole book: four separate times the "rustdv is better than UVM here" instinct fired and was wrong. |
| 30 | `ch30-variation-point-testbench-5.0` | 5 listings. TB 5.0. The generic `AluEnv<T>` is gone: a variation point chosen at *run* time is a factory `create_comp()` slot swapped by a type override, not a type parameter. A generic base survives only for variation chosen at *compile* time. The reason is concrete — a factory override cannot reach a type parameter. **The testers are Chapter 20's `Tester` trait and testbench 2.0's `RandomTester`/`MaxTester`, now also components (D115).** They used to be a free `drive_stimulus` async fn called with closures; both were new machinery arriving where the chapter's subject is the factory, and both are gone. Do not reintroduce a helper here — the trait's provided `execute` *is* the abstract base class, and the reader has had it since Part II. |
| 31 | `ch31-component-communications` | 12 listings. **Reversed argument — "channels replace TLM-1" is wrong.** Ports, exports and FIFOs are restored. A TLM FIFO wraps a queue so two components connect to the *same FIFO* and **neither learns the other exists**; the FIFO is the point of decoupling, not a hierarchy ornament. Connection errors are **elaboration** errors, reported for the whole tree at once — that is correct and it is one of rustdv's three genuine wins. Its old `direction_mismatch` compile-fail figure is deleted; do not resurrect the idea. **Two things this chapter must carry**, both detailed below the table: the `try_put` ownership handback, and the y = 2x² pipeline. **2026-08-05 (Ray): the FIFO-taps section (old Figures 16–17) is deleted from this chapter** — it used analysis machinery before ch32 teaches it, so the chapter keeps one forward sentence naming `TlmFifo::put_ap()`/`TlmFifo::get_ap()`. **The code move is done (D117):** the tap example has left this crate for ch32's, the crate is down to 11 listings and four tests, and every ch31 transcript has been regenerated — `(1/5)` is now `(1/4)`. Nothing further is owed here. |
| 32 | `ch32-analysis-ports` | 7 listings, 3 tests. **`AnalysisFifo` is now `AnalysisBus`** — renamed everywhere, including four manuscript files. **The chapter's central new lesson is that the hub holds nothing**; see below the table. The broadcast transcript is at `0.00ns`, which is the point; the slow-subscriber test then shows writes at `0.00ns` and checks at 5/10/15ns, which is the other point. **2026-08-05: the code side of D116 and D117 is done** — the crate now has four tests and thirteen figures, the bus fields are named `bus`, the trait is `Subscriber`, the method is `subscribe()`, and the FIFO-tap demonstration has arrived from ch31 as Figures 11–13; see the long-form item below for what the prose still owes. Every listing in this chapter has been re-pasted from the crate and `custom/book-listings` is green. **The prose side landed 2026-08-05 as well**: the chapter's headings, paragraphs and Summary (and one paragraph each in ch33 and ch34, plus a second in ch33's summary) now use `Subscriber`/`subscribe`, "sink" is retired from the prose entirely, and the tap section is written — see the long-form item below. Prose discipline, kept and still binding: the *plain struct with `write`* is the subscriber; the component hosts it — stop calling the component "the subscriber," and state the divergence from `uvm_subscriber`-as-component in one sentence. `connect` chooses the stream; `subscribe` supplies the receiver — keep that distinction sharp, it is why the two names differ. |
| 33 | `ch34-connections-testbench-6.0` | **ch33 has no crate of its own.** Its six listings are the component definitions inside ch34's crate, captioned `// Chapter 33, Figure N:`. Each chapter's README maps its own listings. This is deliberate — a separate ch33 crate would need a cross-chapter import, and the book re-shows evolving classes rather than importing them. |
| 34 | `ch34-connections-testbench-6.0` | 10 listings; ch34 owns Figures 1–2 there, the env and the test. TB 6.0, the TinyALU wired with `TlmFifo` and two `AnalysisBus` buses. **Reversed argument.** Note for the prose: the Tester holds its objection for twenty clocks after its last put, where the Python testbench waits ten, because the multiply is last and slowest — without the wait the scoreboard silently checks fewer results than it saw commands. |
| 35 | `ch35-transactions` | Listings are bins under `src/bin/`. **Rebuilt from scratch — the figure numbering changed completely. Take the map from the crate's README, never from the old manuscript.** Seven runnable listings (the old chapter had five, two of them unrunnable "fragments"). Structure follows the Python book's *uvm_object in Python*: a `PersonRecord`, then a `StudentRecord` owning a list of grades, walked through the four transaction operations; the grades list is the point, because three scalars cannot show shallow versus deep. The TinyALU transactions arrive last, as the payoff. Three specifics below the table. |
| 36 | `ch36-sequence-testbench-7.0` | 7 listings. TB 7.0 — the structure holds still and the **program** changes. The Primer's line is the frame: overriding the tester to change stimulus is "like swapping out your car's steering wheel whenever you chose a different destination." A sequence is **not** a component: no place in the tree, no path, no phases, one `body` method. The sequencer **is** a component, and the env files its handle in the ConfigDb so a test three levels up can start sequences on it. **Why two calls and not one is the whole chapter:** `start_item` returns when the sequencer has granted this item its turn and the driver is blocked waiting for its contents, so everything between `start_item` and `finish_item` happens with the driver committed and holding still — that is where late stimulus setting lives. A single `send(cmd)` could not express it. SystemVerilog had `mailbox#(T)` and built this two-phase rendezvous anyway; pyuvm simplified nearly everything else about sequences and kept both phases. **The ownership paragraph belongs here:** `finish_item(cmd)` takes the transaction by value, so `finish_item(cmd)` and `finish_item(cmd.clone())` are both legal and which one you write depends on whether you need the command afterward. The compiler teaches the rule — use `cmd` after it moved and the error names the move. |
| 37 | `ch37-out-of-order-transaction-testbench-7.1` | 4 listings. TB 7.1 — **out-of-order transactions, not Fibonacci.** **Rewritten 2026-08-05: the repair-desk story is gone** (Ray: the example was too complicated to teach the concept). Chapter, crate and title all renamed. The example is now deliberately plain — `Req`/`Rsp`/`Driver`/`Seq`/`Env`, no metaphor and no names. Two changes carry the teaching: **the latency is in the request**, not chosen by an RNG, so the run is deterministic rather than seed-dependent; and the sequence **polls** its outstanding tickets with `try_get_response`, dropping each as it is answered, so the `got` lines come out in completion order. An earlier draft collected with blocking `get_response` in send order and proved nothing — the reordering was real and invisible. **The delays (10, 7, 4, 1) are load-bearing:** acceptance is 20 ns apart because the `start_item`/`finish_item` round trip costs a tick, while a delay tick is 10 ns, so a request must be more than two ticks shorter than its predecessor to overtake it. Narrow the spread and the lesson silently disappears without failing a test. Teaching the mechanism here comes first *because the TinyALU cannot show it* — it runs one operation at a time, so nothing ever returns out of order. |
| 38 | `ch38-fibonacci-testbench-7.2` | 5 listings. TB 7.2 — **Fibonacci on the TinyALU**, where each command needs the previous answer, with `get_response`. Because 7.1 already showed the case where a ticket is necessity, this chapter can say honestly that with one command in flight `get_response(Some(id))` is documentation rather than necessity. **The driver answers through the response, and nothing travels backwards.** Both source books write the result into the sequence item the sequence still holds — that is not a capability, it is what handles look like when two names point at one object. Rust has one owner, so there is nothing to restore and nothing missing. |
| 39 | `ch39-virtual-sequence-testbench-8.0` | 6 listings. TB 8.0. **Reversed argument.** A virtual sequence is started without a sequencer; it sends no items of its own, it starts other sequences. Three things: `TestAllSeq` runs two sequences in turn; `TestAllParallelSeq` runs them at once and the sequencer interleaves their items; then `OpSeq` plus four functions turn the testbench into a programming interface — `do_add(&seqr, a, b)` returns a number. `start_virtual()` exists rather than `start(None)` because Rust has no default arguments and `None` does not say "virtual". **Deliberately absent:** a separate `VirtualSequence` trait. It would make `start_item` inside a virtual sequence a compile error instead of a run-time one, and would forbid a shape the UVM allows — the Primer's `parallel_sequence` is started *with* a sequencer and is still virtual in the sense that matters. Better error message, at the cost of a capability. Say so; it is the book's own thesis applied to itself. |
| 40 | `rustdv/tinyalu_tb` | The same crate as the Interlude, now with everything taught. Where the Interlude showed the shape, this chapter walks it: why the BFM is in the ConfigDb rather than a singleton, why the components take no constructor arguments, why the scoreboard holds its own storage, and why two tests need no new components between them. **Do not cite `tinyalu_tb/src/lib.rs`** — the crate root is `tinyalu_tb.rs`, and no file in this project is named `lib.rs`. **D112/D119:** the DUT self-clocks and exposes `clk` as a read-only output; the BFM waits on its edges and never drives it. |
| ~~41~~ | — | **Cut (D111).** "The Future of Rust in Verification" is gone: Ray has no view of that future he considers worth publishing, and the honest-gaps inventory it carried was written against the pre-restoration framework. The book ends at ch40. Do not write it, do not restore it, and do not add a substitute — if a limitation belongs anywhere it belongs beside the thing it limits, in the chapter that teaches it. |

---

## Appendices

| | Notes |
|---|---|
| A — Chapter Maps to the Earlier Books | Check it against the current chapter numbering, including the 7.1/7.2 swap at ch37/ch38. |
| B — Python → Rust Idiom Translations | Review; extend where Part II+ added idioms. |
| C — SystemVerilog-UVM → rustdv Translations | Review; extend. The sequence and TLM chapters added translatable names. |
| D — What rustdv Provides | **New; you write it.** See `FABLE.md`, "Two writing debts." Add the `SUMMARY.md` line after Appendix C. |

---

## The four long-form items

### ch31 — the `try_put` handback

`try_put` returns `Result<(), T>` and `try_get` returns `Option<T>`. The pattern
the reader must see, from the crate's Figures 4–6:

```rust
let mut packet = Packet::new(n);
while let Err(back) = self.put_port.try_put(packet) {
    ctx.info("FIFO full, retrying");
    Timer::ns(1).await;
    packet = back; // the FIFO gave it back; try again with it
}
```

How to explain it: SystemVerilog's `try_put` returns a **bit** because it passes
a class handle and the caller still holds its own. rustdv's `try_put` takes the
packet **by value** — it must, since a successful put hands the packet to
whoever gets it next — so a bare "no" would have swallowed a packet that was
never delivered. `Err(back)` is the packet coming home.

Two things to state plainly:

1. **This is not Rust catching a bug SystemVerilog has.** SystemVerilog has no
   bug here; it has a different ownership model. Frame it as what the signature
   *must* be, not as a win.
2. Written the tempting way — `while port.try_put(packet).is_err()` — it does
   not compile, because `packet` moved on the first attempt. That error is real
   and was run; quote it from the crate if it helps, never invent one.

Do **not** demonstrate this with a `u32`. A `Copy` item makes the tempting loop
compile and teaches a pattern that breaks on the reader's first real
transaction — which is exactly how the defect was found. The crate carries a
non-`Copy` `Packet` for this reason. `try_get`'s `Option<T>` is the same
argument read the other way.

### ch31 — the y = 2x² pipeline (required; Ray's directive)

It is Figures 9–12 in the ch31 crate, as `SquareIt`, `TimesTwo` and `MathTest`.
**Do not drop it.**

```
MathTest(run) --put--> [x_fifo] --get--> SquareIt(run) --put--> [sq_fifo]
                                                                    |
MathTest(run) <--get-- [y_fifo] <--put-- TimesTwo(run) <--get-------+
```

The test picks x = 1..4, sends it into the pipeline, waits for y, and compares
against 2x² (2, 8, 18, 32). Two worker components do the arithmetic; each is
connected only to FIFOs and neither knows the other exists.

What no other listing covers:

- **The parent is a stage, not just a builder.** Every other component listing
  has a test that only builds and connects. Here the test has a `run` of its
  own, concurrent with its children's — the case that drove the entire
  concurrency design. A phaser that ran children to completion first could not
  execute this at all.
- **A request/response round trip**, not a one-way stream: put x, await y. The
  first closed loop through the component tree.
- **A parent holding its own ports** — the same `connect` call shape works for a
  child and for `self`, which is the framework's uniformity rule made visible.
- **Responders that never return.** The workers loop forever; the phase ends
  when the test's objection drops. That is what makes the objection
  load-bearing, and it is worth saying.
- **It is self-checking** — a broken pipeline fails rather than passing quietly.

It is also the DUT-free rehearsal for TB 7.0, where the test's `run` starts a
sequence while the driver waits for items forever. Explain it well and ch36 gets
much easier.

### ch32 — the subscriber owns the storage

This is a **new pattern the book must teach**, not a footnote. It is where a UVM
engineer's habit will mislead them.

An `AnalysisBus` is not a FIFO. It holds nothing: `write` calls every subscribed
object and returns, and a datum broadcast to nobody is gone. So "where does the
traffic go?" has a different answer than in the UVM — **wherever the subscriber
decides to put it**: a tally (Figure 1), a `Vec` (Figure 2), a comparison
against a prediction (ch34's scoreboard), or a `TlmFifo` the subscriber declares
itself.

**Say explicitly what this replaces**, or the reader goes looking for the
analysis FIFO and concludes something is missing. A UVM scoreboard routes each
stream into a `uvm_tlm_analysis_fifo` because a class gets **one** `write`
method: a second stream needs the `uvm_analysis_imp_decl` macros to mint a
differently-named one, and a FIFO per stream is the way around that. A rustdv
subscriber declares two `SubscribePort`s and two `Subscriber` impls, so the
workaround has nothing to work around, and the FIFO that used to sit in the
scoreboard is simply absent.

The one reason a rustdv subscriber *would* own a queue is different from the
UVM's, and Figures 6–7 exist to teach it: `write` is synchronous and cannot
await, so a subscriber whose work takes simulation time splits the job. `write`
does the one instant thing — `try_put` into an unbounded `TlmFifo` it owns — and
the component's `run` gets from that FIFO and takes as long as it likes.
`SlowChecker` is the component; `SlowSubscriberTest` is the proof.

Three things to draw out of those two listings:

1. **The FIFO is connected to no port.** It is an ordinary handoff *inside* one
   component, between a synchronous method and an asynchronous one — not part of
   the testbench topology. A reader who has just learned `connect` will expect
   otherwise.
2. **The inbox must be unbounded.** `write` cannot wait for space and analysis
   has no back-pressure, so a bounded inbox could only drop items. Say why, not
   just what.
3. **The transcript is the argument.** All three writes land at `0.00ns`; the
   checks come out at 5, 10 and 15ns. The publisher is never held up by what a
   subscriber does with an item.

If the prose explains the name `AnalysisBus`, the reason is that the old name
was borrowed from `uvm_tlm_analysis_fifo` — a *subscriber-side buffer*, the one
thing this design decided rustdv does not need — while the type it named is the
broadcast hub, which the UVM has no counterpart for at all.

### ch32 — the FIFO-tap demonstration moves here from ch31 (Ray, 2026-08-05)

ch31's "The FIFO's built-in taps" section is deleted from the manuscript: its
demonstration (`TapLog`/`TapWatcher`/`FifoTapTest`) used what is now
`Subscriber`, plus `SubscribePort`, `RustdvShared` and `subscribe`, before this
chapter teaches any of them. ch31 now carries a single forward sentence naming
`TlmFifo::put_ap()` and `TlmFifo::get_ap()` and deferring the explanation here.

The demonstration belongs near the end of this chapter, once subscribers are
understood. **Done, code and prose (2026-08-05):** the chapter now carries
"The FIFO's built-in taps" between the slow-subscriber section and the
Summary. The example is ch32 Figures 11–13 in the crate, the ch32 README
figure map lists them, and both chapters' transcripts have been regenerated
(ch31 has four tests, ch32 has four). The figures, as they appear:

- Figure 11 — `TapLog`/`TapWatcher`, an ordinary subscriber pointed at a tap.
- Figure 12 — `FifoTapTest`, the wiring.
- Figure 13 — the transcript, in the ch32 README, ending `tap saw [0, 1, 2]`.

`FifoTapTest` reuses Chapter 31's `Producer` and `Consumer` verbatim, and they
sit in the ch32 crate **uncaptioned on purpose**: the reader met them fifteen
pages ago, and reprinting put/get inside the analysis chapter would re-teach
the previous chapter's subject (D115). Refer back to Chapter 31 rather than
printing them — but if you disagree, they are ordinary code and captioning
them is a two-line change.

Then the prose: teach the taps as the port of `uvm_tlm_fifo`'s built-in
analysis ports, wired like any other subscription, naming the accessors
`TlmFifo::put_ap()` and `TlmFifo::get_ap()`. The sentence worth carrying over
from the deleted section: the FIFO's data path is still a queue — one consumer
takes each item, the producer blocks when it is full — while the taps are
observation running alongside; every subscriber sees every item, nothing is
consumed, and nobody is delayed.

### ch35 — a transaction is not an object

Ray was explicit that this belongs in the chapter, and unsure where; the natural
place is the opening, before Figure 1, since every later listing is a
consequence. Part I already taught structs, so this is a **reminder aimed at the
UVM habit**, not a first explanation — the reader knows what a struct is and
still has an object in mind.

- **It is not an object. It is a location in memory, referenced by a name.**
  `AluCommand { a, b, op }` is a layout — three fields side by side — and `cmd`
  is a binding to that place. Nothing is wrapped around it, nothing points at
  it, and there is no identity separate from the bytes. That is why the chapter
  opens with "plain struct, no base class": there is no object for a base class
  to be part of.
- **It is not a class, so there is no `super()`.** No inheritance chain means no
  `super().do_copy(other)` to remember and no virtual dispatch on a transaction.
  What a base class *gave* you — printing, comparing, copying — arrives instead
  as traits attached from the outside, which is why they are derives rather than
  inherited methods.

This also sets up ch36: because a transaction is a place and not a handle,
`finish_item(cmd)` hands over the *contents*, and the sequence does not keep a
reference to something the driver is also holding.

**Two claims in the current ch35 text must not survive.**

1. **`Debug` is not `convert2string()`.** The manuscript says so three times —
   in a figure comment, in the prose, and in the summary. `Debug` is the
   developer field-dump (`{:?}`) and comes free with the derive;
   `convert2string()` / `__str__()` is **`Display`** (`{}`), and `Display` is
   **not derivable** — you write it, because only the author knows which fields
   are worth reading. Figure 1 now teaches both forms.
2. **Comparison policy does not move to the checker.** The current summary says
   policy "moved out of the data type and into the scoreboard as a closure."
   That figure existed and Ray cut it: too fancy, not in keeping with the UVM,
   and confusing for a reader learning both Rust and the UVM at once. The UVM
   does not pass behaviour around for equality and neither does `__eq__`.
   **Equality lives on the transaction**, where `do_compare()` puts it — derived
   when every field counts, hand-written when "the same" means something
   narrower (Figure 2, Batman and Bruce Wayne).

New material worth prose: **`PartialEq` versus `Eq`** (Figure 3). There are two
traits because `PartialEq` does not promise `a == a` — IEEE 754 says NaN equals
nothing — and `Eq` adds that promise. It bites a verification engineer in one
specific place: `HashSet` requires `Eq`, so a transaction carrying a *measured*
value like a float delay cannot be a coverage key.
