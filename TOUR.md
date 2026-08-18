# A Tour of This Repository

*New here — human or AI? This is the walk-around. Ten minutes, and you'll
know what this project is, what's been proven, and where everything lives.
Last verified 2026-08-08; the proven claims below are checked by the
regression suite, not aspirational.*

> **Both products are complete.** The framework is done — every chapter crate
> green on the Icarus reference, with the TinyALU, scheduler, callback-lifecycle,
> and mutation paths also green on Verilator. **The book is done
> too:** every transcript is real simulator output, every ch15–40 listing is
> checked against its crate, and the end-to-end read has run. The UVM
> restoration that dominated this repo's history is finished; `#[component]`
> and the phase/ConfigDb/factory/TLM layer are the settled design, not work in
> progress. What happens now is revision.
>
> **"Where the work stands", at the bottom of this file, is the live status.**
> `output/.design-decisions.md` is the decision log; read its §0 before
> proposing anything architectural.
>
> **No document here names a branch.** Branches are ephemeral; ask git.

## What this project is

**rustdv** is a hardware verification framework in Rust — the cocotb +
pyuvm story retold with a compiler: a simulator-driven async executor,
triggers, a UVM-style component methodology (ownership tree, typed
configs, maker-closure factories, channels/analysis ports, the full
sequencer handshake), running testbenches as native shared libraries
loaded by Icarus or Verilator over VPI. Zero Rust dependencies. **v0.1 is
publicly live** (2026-08-06/07): `rustdv` 0.1.1 is published on crates.io,
the `rustdv/rustdv` GitHub repo is public with Discussions on and
Issues/PRs off, and the companion site is up at rustdv.org.

**"Rust for RTL Verification"** is its book — the third in Ray Salemi's
series after [*The UVM Primer*](https://www.uvmprimer.com) (SystemVerilog)
and [*Python for RTL Verification*](https://a.co/d/0hTKAJvh): 40 chapters,
an interlude, and four appendices in `book-pdf/src/` (mdBook).
The premise: the reader is a UVM verification engineer — from SystemVerilog
or Python; neither earlier book is a prerequisite — who learns Rust chapter
by chapter while rebuilding the TinyALU testbench, versions 1.0 through 8.0.
Every figure runs; every simulation transcript in the book is genuine 
Icarus output.

## What's been proven

All of this is reproducible from this tree and enforced by the git
pre-push hook:

- `sim/run_rustdv.sh` — the shipped TinyALU testbench ends `REGRESSION: PASS`
  (RandomTest: 20 compared, 0 mismatches, every op covered; MaxTest: 4/0). It
  runs in the suite on Icarus and Verilator, with both entries asserting those
  counts. Icarus owns four-state/reference behavior; Verilator owns FAST
  functional runs. `TOOLS.md` is the contract.
- **Mutation-checked**: with the DUT's XOR deliberately corrupted to OR,
  the scoreboard flags every affected transaction and the regression
  fails; restored, it passes. The checking has teeth.
- **Callback ownership is stress-checked**: one million fired ReadOnly and
  NextTimeStep registrations reach a stable RSS plateau under Verilator. With
  one-shot removal deliberately disabled, the same check grows linearly and
  fails.
- `output/regression/regress.py` — the current tree is green on macOS/arm64,
  including every Verilator entry. The Icarus-only entries were not rerun on
  that machine because Icarus was absent; the Linux CI matrix is their next
  gate. (`--list` prints the current entry count; do not trust a number written
  in prose.) One package is quarantined in `regress.json`: `ch21_macros`, a
  macro demonstration with no simulator test, which never comes off the list.
- **Three tiers of framework test under the chapter runs** — no-simulator tests
  (`--suite unit`, ~2 s), targeted simulator tests in `rustdv/framework-tests/`
  plus `sim-mutation`, and compile-fail cases each asserting its `error[E….]`.
  `output/regression/TESTING.md` is the operating manual.
- `cargo test --workspace` in `/rustdv` — the whole methodology layer
  (ConfigDb, factory, ports, FIFO, analysis bus, objections, the phase walk,
  the sequencer handshake), no simulator required.

## Where everything lives

| You want | Look at |
|---|---|
| The framework | `/rustdv` (workspace: `rustdv-gpi-sys` → `rustdv-gpi` → `rustdv-sim` → `rustdv-methodology` → `rustdv`, plus `tinyalu_tb`) |
| The book manuscript | `/book-pdf/src` (TOC in `SUMMARY.md`); render with `mdbook build book-pdf` |
| Why it's designed this way | `output/.design-decisions.md` — the authoritative decision log (§0 = mission + method). Internal: never cite it in reader-facing output. |
| Runnable book figures | `/output/examples` (`README.md` has per-chapter run commands) |
| The regression suite | `/output/regression/regress.py` (`--help` works; wired into pre-push) |
| Simulator policy | `/TOOLS.md` (pinned tools, FAST/DEBUG visibility, FST, four-state boundary) |
| Implementation history & the deviations log | `STATUS.md` (chronological, bottom-up) |
| The book's prose pass | `book-pdf/FABLE.md` (the rules) and `book-pdf/chapter-notes.md` (one row per chapter). These supersede the older `fable-brief.md`, `notes-for-fable.md` and `dual-audience-style.md`. |
| AI verification skills | `/skills` (spec+RTL → testbench → verified coverage report) |
| Upstream sources | `../rustdv-reference` — **read-only, outside the repo** (cocotb, pyuvm, SystemVerilog UVM, both earlier books) |

## Highlights worth your first half hour

- **The Interlude** (`book-pdf/src/interlude-tinyalu-testbench.md`) — the
  complete testbench, presented before the climb. The best single answer
  to "what does rustdv code look like?"
- **The compile-error figures** (`output/examples/*/compile-fail/`) — Part I
  shows the compiler catching mistakes before the simulator runs (a mis-typed
  handle is `E0308`, and so on). *Note under the restoration:* this covers
  data and ownership, **not** the late-binding layer — config, factory and
  TLM resolve at run time by design, so the old "a config conflict is a
  compile error" figures were removed (D68, and the reasoning in §0.4).
- **Fibonacci on the TinyALU** (chapter 38 — TB 7.2) — stimulus that needs the
  DUT's answers: `Fibonacci Sequence: [0, 1, 1, 2, 3, 5, 8, 13, 21]`.
- **The gaps inventory** — `STATUS.md`'s deviations and the decision log's open
  questions. What this project can't do yet is written down next to what it can.
  (The book's own "future of Rust in verification" chapter was cut — D111.)

## Rules of the road

- Keep the pre-push hook green: if you touch code or book figures, run
  `python3 output/regression/regress.py` before pushing.
- Transcripts in the book and READMEs are real output and must stay in
  sync with reruns — verify claims by running things.
- `../rustdv-reference` (outside the repo) is read-only. `/output` holds
  generated deliverables.
- **Change an example, update the chapter that quotes it, in the same session.**
  `book-pdf/FABLE.md` is the authority on how the prose sounds and what it must
  not claim — read it before writing a paragraph of the book — and
  `chapter-notes.md` carries one row per chapter. Two checks enforce agreement:
  `custom/book-listings` and `custom/readme-transcripts` fail the push if the
  book and the code disagree. Run them directly; they are seconds, not minutes.
  **Both also cover the repository `README.md`**, which walks `tinyalu_tb` the
  way the Interlude does: its listings are compared against the crate (ids
  `chRM/N`) and its transcript against a fresh run.
- **Never write a version number into reader-facing prose.** It is right the
  day you type it and wrong at the next release. The crates.io badge carries
  the version, `cargo add rustdv` writes the dependency line, and
  `rust-toolchain.toml` pins the compiler — point at those instead of restating
  them. `custom/no-stale-versions` enforces it; `STATUS.md` and the design log
  are exempt, because a dated record should name the version that ran.
- **Figures are one numbering space** (D110): a chapter's code listings,
  drawings, tables and transcripts all draw from the same sequence, in order of
  appearance, and every one of them is a "Figure". If Figure 1 is a drawing, the
  first listing is Figure 2. Captions read `// Chapter N, Figure M:` in the
  example crates, output follows `--`, and each chapter README in
  `output/examples` maps its figures to runnable code.

---

## Notes for AI sessions

Context that matters to an AI working in this folder (via Claude Cowork
or similar) and to nobody else:

- **Never write a loadable binary or compiled design into the repo folder
  (D113).** This is the expensive one. The folder syncs to Ray's Mac, so a Linux
  `.so` copied to `sim/build/tinyalu_tb.vpi` is what his `vvp` then tries to
  `dlopen` — macOS refuses the foreign image with `Killed: 9` and **no output at
  all**, which is indistinguishable from a crash in whatever code changed most
  recently. It cost an afternoon once. The sim scripts build under
  `/tmp/rustdv-$(id -u)/` now and `SIM_BUILD_DIR` overrides, but check where any
  script writes its `.vpi`/`.vvp` before running it. Source and documents into
  the repo, yes; `.vpi`, `.vvp`, `.so`, `.dylib`, object files and simulator
  output directories, no.
- **A green sandbox run is evidence about the sandbox.** macOS/arm64 is a
  shipping platform for this project. Say "verified on Linux" when that is what
  happened, and ask Ray to confirm on the Mac before calling anything done. The
  same applies to a checker: `output/regression/verify-transcripts.sh` had two
  bugs that only surfaced when it was run somewhere the sims genuinely failed.
- **Never bulk-delete-and-recreate directories from the sandbox VM** —
  the desktop sync engine races and forks `dir 2/` duplicates. Build
  trees in `/tmp` and `cp` over; file deletion needs the permission tool.
- **Request file-deletion permission for this folder before running `git`
  here** — including `git status`. With deletion enabled git removes its own
  `.git/index.lock` and leaves nothing behind. If you see `unable to unlink
  '…/.git/index.lock': Operation not permitted`, grant deletion and
  `rm -f .git/index.lock` in the same session; do not try to shift the file
  with `mv` or truncation, which leaves two locks instead of one. `git log`,
  `git diff` and `git branch --show-current` never take the lock and need none
  of this. *Why it matters:* a leftover lock fails every later
  `git add`/`commit`/`checkout` with `File exists`, and Ray does the commits,
  so it breaks his machine, not yours.
- The Cowork VM has no network: toolchain comes from `toolchain-drop/`
  (extract from a `/tmp` copy — extracting off the mount is ~15× slower).
  `mdbook` **is** in the drop and installs offline to `/tmp/rust/bin/mdbook` —
  it builds the book's HTML in the VM, which is enough to catch a broken
  `SUMMARY.md` or an orphaned chapter. The **PDF** backend is what needs a
  Chromium the VM lacks, so PDF rendering happens on Ray's Mac.
- Long shell commands: the VM kills background processes between calls
  and each call has a ~45 s budget — chunk accordingly. `regress.py` takes
  a few minutes from cold, so pre-build the example workspace first
  (`cargo build --workspace --exclude` each quarantined crate) and then run it.
- **Keep all your scratch in one place you own: `/tmp/rustdv-$(id -u)/`.**
  More than one session can share the VM, each under a different uid, and each
  sees the other's files as owned by `nobody`. A bare `/tmp/rustdv-target` is
  therefore a landmine: whoever creates it first owns it, and the next session
  cannot write to it *or* delete it (`/tmp` is sticky), so a stale directory
  from a thread that has since gone away can block builds indefinitely. The
  failure is unhelpful — `Permission denied` deep in a cargo or `cp` line, or
  every sim test failing at once. `run_sim.sh` and `sim/run_rustdv.sh` default
  into this root already; put your own logs and extracted files under
  `scratch/` there too, and clean up with one `rm -rf /tmp/rustdv-$(id -u)`.
  For the same reason, never write to a fixed shared path from a test.
- **Disk fills up.** The VM has ~9.6 GB and a debug build of the framework plus
  the examples reaches ~1.1 GB; a full disk shows up as `regress.py` failures
  reading `No space left on device`, which looks like a real regression and is
  not. Two ways out: `CARGO_PROFILE_DEV_DEBUG=0` cuts those builds to ~240 MB
  (debuginfo is nearly all of it, and transcripts are unaffected — `file!()`
  and `line!()` are compile-time macros), and
  `rm -rf /tmp/rustdv-$(id -u)/*-target/debug/incremental` reclaims a few
  hundred MB more.
- **Editing an example's comments must be line-count-neutral** *unless you are
  regenerating its transcript anyway*. Transcripts embed `file:line`
  (`…/ch25_uvm_env_testbench_4_0.rs:256`), so adding or removing a line
  invalidates every transcript in that crate. Either change digits inside
  existing comment lines, or rerun the sim and repaste the transcript into both
  the crate README and the chapter.
- **Never write a branch name into a document.** Branches are ephemeral and a
  branch named in a file is wrong within days. Ask git.
- **Ending your session? Run the `close-out-thread` skill**
  (`.claude/skills/close-out-thread/SKILL.md`) — the checklist that keeps this
  file true and produces the next thread's prompt.
- `CLAUDE.md` has the standing rules; persistent memory notes point here.
  Deeper history: `STATUS.md`, newest at the bottom.

**The fast checks, cheapest first:**

```
python3 output/regression/regress.py --suite unit      # no simulator, ~2 s
python3 output/regression/verify-book-listings.py      # every ch15-40 listing vs its crate
bash output/regression/verify-transcripts.sh           # every README and book transcript
python3 output/regression/regress.py --filter ch37     # one chapter, sim included
python3 output/regression/regress.py                   # full, a few minutes
```

Running one chapter's sim by hand, which is what you want while iterating on an
example (it builds into `/tmp`, never into the repo):

```
export PATH="/tmp/rust/bin:/tmp/oss-cad-suite/bin:$PATH"
export CARGO_TARGET_DIR=/tmp/rustdv-$(id -u)/examples-target
cd output/examples && sim-common/run_sim.sh <crate_name> <top_module>
```

### Where the work stands — read this before proposing anything

**Both products are complete, and the work now is revision.** Every chapter
crate ch15–ch39 runs on Icarus; `tinyalu_tb` also runs on Verilator through the
shared scheduler host and is mutation-checked on both. The Verilator-compatible
framework probe covers VPI-only timers and ReadWrite-to-ReadOnly RTL settling;
its callback-lifecycle lane also proves one million fired one-shots reach a
stable RSS plateau. The two X/Z cases remain Icarus-only. The only quarantined
package is `ch21_macros`, a macro demonstration with no simulator test, marked
`no_sim_test` in `regress.json`; it never comes off the list. `.design-decisions.md`
§16 is empty. **D116/D117 landed on 2026-08-05**: the analysis trait is
`Subscriber`, its method is supplied with `subscribe()`, no identifier is
named `analysis_fifo`, the legacy `Subscriber`/`AnalysisPort`/`connect_fifo`
surface is deleted, and the FIFO-tap demonstration has moved from the ch31
crate to ch32's as Figures 11–13. **The prose caught up the same day**: ch32's
headings, paragraphs and Summary use the new vocabulary, the tap section is
written as ch32 Figures 11–13, and the ch33/ch34 paragraphs are repaired —
see STATUS.md's "ch32 prose catches up with its vocabulary" entry. No directed
code job is queued. **The final
publication sweep of the manuscript ran on 2026-08-05** — TOC titles, appendix
cross-references and chapter pointers verified against the crates, spelling and
figure-reference conventions unified — and `book-pdf/FABLE.md`'s top notes are
satisfied (marked done in place). D119/D120's Verilator integration and callback
ownership are verified on macOS/arm64; Linux CI and an Icarus transcript rerun
remain pending.

**The test suite**, in three tiers under the chapter runs
(`output/regression/TESTING.md` is the operating manual, including the two
runner behaviours a simulator test must know about):

| Tier | Where | What it is |
|---|---|---|
| no-simulator | `#[cfg(test)]` modules in `rustdv/` | `regress.py --suite unit`, ~2 s |
| targeted simulator | `rustdv/framework-tests/` | seven named groups, plus `sim-mutation` |
| compile-fail | `rustdv/framework-tests/compile-fail/` | each case asserts its `error[E….]` |

`python3 output/regression/regress.py --list` prints the current entry count and
every test id. Prefer that to any number written in prose — the numbers in these
documents have gone stale twice.

**Editing the manuscript.** `book-pdf/src` used to be closed to code threads.
It is not now: when you change an example, you update the chapter that quotes
it, in the same session. What gates that is not a rule but two checks —
`custom/book-listings` and `custom/readme-transcripts` — which fail the push if
the book and the code disagree.

**Read `book-pdf/FABLE.md` before writing a paragraph of the book.** It carries
two things: Ray's outstanding notes on specific chapters at the top (what is
wrong and what he wants instead), and below them the standing rules — the voice,
the reader it addresses, and the claims that must not survive. Its "you change
no code" rule is addressed to a prose-only pass; a thread that is changing an
example *and* its chapter is not that pass, but everything else in the file
still applies, above all *when the code and the chapter disagree, the code
wins*. `book-pdf/chapter-notes.md` carries one row per chapter.

The four things a new thread most needs to know, all in
`output/.design-decisions.md`:

- **D3 — resist making late binding static.** Where a statically-typed language
  with a static option in hand still chose runtime indirection, the indirection
  is load-bearing. SystemVerilog had `mailbox#(T)` and built TLM anyway; typed
  classes and built a factory; parameters and built a config DB. The pull to
  replace runtime indirection with a type feels like craftsmanship and is the
  error that destroyed build/connect in the first place. §0.1–0.4 is the
  argument; read it before proposing anything architectural.

- **D83b — connection is a trait method, not a registry.** A parent reaches an
  erased child's port through `ComponentNode::port_slot`, which works through
  `dyn` and therefore answers for a child slot and for `self` alike. A path-keyed
  registry was built first and struck: it could address a child but not the
  connecting component itself. If a mechanism works for a child but needs a
  second spelling for `self`, it has broken the UVM's uniformity — that is the
  tell.
- **D82b/D82c — concurrency and cancellation.** `RustdvComp` children are moved
  *out* of the parent for the run phase so a parent's `run` is concurrent with
  theirs, and each component races the objection-drained event *individually*.
  Racing the whole tree drops it mid-phase and destroys the components before
  extract/check/report can walk them — which showed up as a test passing with
  its scoreboard never running.
- **D90 — the analysis hub holds nothing.** `AnalysisBus` is a subscriber list;
  `write` calls each subscriber and returns, and a datum broadcast to nobody is
  gone. Storage belongs to the subscriber.

**Chronological history lives in `STATUS.md`, newest at the bottom.** It is the
account of how each piece got this way — the TinyALU refactor, both runner bugs,
the figure renumbering, the two new checks, the three CI root causes. Read it
when you need to know *why* something is the way it is; do not expect this file
to summarise it, because a summary that must be maintained in two places is a
summary that goes stale.

### Two habits this project learned the hard way

**Repo prose is not evidence.** Every expensive mistake in recent sessions came
from quoting a document instead of checking the code: a STATUS.md note described
an attribute as live logic months after it was deleted; a handoff file recorded a
chapter edit as finished when only half of it had happened. If a document tells
you something about the code, verify it with `ripgrep` or by running the thing
before you act on it or repeat it.

**A green sandbox run is evidence about the sandbox.** macOS/arm64 is a shipping
platform. Say "verified on Linux" when that is what happened, and ask Ray to
confirm on the Mac before calling anything done.
