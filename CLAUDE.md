# Project: rustdv & "Rust for RTL Verification"

## Context
rustdv is a Rust hardware verification framework (a cocotb + pyuvm analog) by
Ray Salemi, companion to the book *Rust for RTL Verification*. The repo holds
two products (see TOUR.md for the tour):

1. **rustdv** — the framework (crates in /rustdv), with the TinyALU regression
   passing on Icarus and Verilator. Icarus remains the four-state/book reference;
   Verilator is the FAST two-state backend (`TOOLS.md`).
2. **"Rust for RTL Verification"** — chapters 1–40 plus an Interlude and four
   appendices in /book-pdf/src (mdBook), every figure verified running.

**Both products are complete.** The framework's UVM restoration is finished —
phases, the ConfigDb, the factory and the whole TLM layer are the settled
design, not work in progress — and the manuscript is written, with every
transcript real simulator output and every ch15–40 listing checked against its
crate. Ongoing work is revision, not construction.

**Never write a branch name into a document.** Branches are ephemeral; a branch
named in a file is stale within days and has repeatedly sent threads to the
wrong place. Run `git status` and `git branch --show-current` if you need to
know where you are. Nothing in this repository's prose should answer that
question.

`output/.design-decisions.md` is the authoritative decision log — read its
§0 (the mission and method) before proposing anything
architectural. The decisions that most shape new code: **D83b** (connection is
a trait method, not a registry — if a mechanism works for a child but needs a
second spelling for `self`, it has broken the UVM's uniformity), **D82b/D82c**
(children move out of the parent for the run phase, and each component races
the objection event individually, never the whole tree), **D90** (the analysis
hub stores nothing — the subscriber owns its storage), and **D3** (where a
statically-typed language with a static option in hand still chose runtime
indirection, the indirection is load-bearing; resist the urge to make late
binding static, which is the error this project exists to undo).

TOUR.md is the orientation for a new thread — read it first; its "Notes for AI
sessions" carries the sandbox hazards.

Ground truth for the methodology — the cocotb, pyuvm and SystemVerilog UVM
sources, plus the example code from the earlier books — lives outside this
repository at ../rustdv-reference, so the repo carries only its own product.

## Folder map
- /rustdv — the framework workspace (crates rustdv-gpi-sys … rustdv, plus
  tinyalu_tb). Runs via sim/run_rustdv.sh.
- /book-pdf/src — the manuscript. Rebuild rendered book: `mdbook build book-pdf`.
- /output/examples — every book figure, runnable (Part I per-figure files,
  Parts II–V as sim chapter crates).
- /output/regression — regress.py, wired into the git pre-push hook.
- /skills — AI verification skills (rtl-spec-analysis, rustdv-testbench,
  rustdv-verify-cover).
- /.claude/skills — skills for working *on* this repo: `start-thread` (run as
  your session begins), `close-out-thread` (run before it ends), `cleanup-tmp`,
  `write-a-bfm`, `debug-a-regression`, `new-rustdv-testbench`.
- STATUS.md — authoritative implementation history and deviations log.
- TOUR.md — orientation for new readers and new threads (start there).

## Standing rules
- The pre-push hook runs the full regression; keep it green. Verify claims
  by running things — transcripts in the book/README files are real output
  and must stay in sync with reruns.

### Leave no documentation debt — the rule that costs the most when ignored

**When you change code, update the artifacts that quote it, in the same
session.** This project's expensive failures have all been the same shape:
something changed, the prose describing it did not, and nothing noticed for
weeks. ch23/ch24/ch26 carried wrong `file:line` references and an undocumented
test; ch18–20's transcripts were 5ns stale after the DUT began self-clocking;
ch37's README described a chapter that does not exist. Each was cheap to fix at
the time and expensive to find later — one session spent ~20% of its context
paying that debt down.

**The same rule applies to this file and TOUR.md.** A stale orientation
document costs more than stale prose, because every new thread reads it and
acts on it. If you finish work these files describe, update them in the same
session.

So, if you change:

| this | then regenerate |
|---|---|
| an example crate's code | its `README.md` figure map **and** its transcript |
| anything a transcript quotes (timing, paths, test count) | every README quoting it — `bash output/regression/verify-transcripts.sh` finds them |
| a `.rs` figure caption | the README figure map — they must agree, and caption edits stay line-count-neutral |
| framework syntax (an attribute, a name) | every call site, `skills/`, `.claude/skills/`, and a note in `book-pdf/chapter-notes.md` |
| `tinyalu_tb`'s code | the repository `README.md`, which walks it — both checks below cover it, so this one is enforced rather than remembered |

**Prefer a check to a note.** A rule written down is a rule someone must
remember; a rule in the regression is enforced. These checks exist because the
drift they catch went unnoticed for months while a full green regression ran
over it every push:

| check | what it gates |
|---|---|
| `custom/readme-transcripts` | every transcript in an example README, **in `book-pdf/src`, and in the repository `README.md`** is what the simulator prints (22 chapters) |
| `custom/book-listings` | every Rust listing in ch15–40 **and in the repository `README.md`** (ids `chRM/N`) is real code from that chapter's crate |
| `custom/no-stale-versions` | no reader-facing document hardcodes a rustdv version — the badge, `cargo add`, and `rust-toolchain.toml` carry those, and they update themselves |
| `book-sync` (pre-existing) | ch1–14 listings, byte-for-byte |

Run them directly while working — they are far cheaper than the full
regression: `python3 output/regression/verify-book-listings.py`,
`python3 output/regression/verify-no-stale-versions.py` (instant, no toolchain)
and `bash output/regression/verify-transcripts.sh`.

`no-stale-versions` encodes Ray's rule that **a version written into a file is
a staleness source**: it is right the day it is typed and wrong at the next
release, and nothing about releasing reminds anyone to go and fix it. Reach for
the mechanism that updates itself — the crates.io badge for the version,
`cargo add rustdv` for a dependency line, `rust-toolchain.toml` for the
compiler. Its `ALLOW` list is empty and is not a debt register; `STATUS.md` and
the design log are out of scope because a dated record is *supposed* to name
the version that ran.

`book-listings` separates two things that look alike and are not.
`QUOTED` holds listings that were never ours — the `Future` trait from the
standard library, a deliberately tidied macro expansion. Those are quotations,
carry no debt, and will not shrink. `KNOWN_DRIFT` is the debt register: a book
and a codebase disagreeing. **It is currently empty, and adding to it to make a
build pass is how drift comes back.** Keep the two apart; listing permanent
quotations as outstanding work makes a clean register look dirty and trains
everyone to ignore it.

If you find a class of error nothing catches, add the check rather than only
documenting the instance — and **make the check fail once on purpose before
trusting it.** Both of the above were mutation-tested that way; the first
version of `verify-transcripts.sh` reported success on chapters whose sims had
not run at all.

**Ask the process, not the prose.** A check that decides pass/fail by
pattern-matching human-readable output can be defeated by formatting. The
compile-fail suite tested "did it compile?" with `grep -E '^error'`; GitHub's
cargo emits ANSI colour, so the line began with an escape sequence, `^error`
never matched, and CI reported "compiled — no longer rejected" while printing
`error[E0277]` underneath. Exit codes, structured output and
`CARGO_TERM_COLOR=never` are not decoration — they are the difference between a
check and a guess.

**Do not create per-thread prompt files.** Orientation lives in TOUR.md
("Notes for AI sessions" has the sandbox hazards) and in this file. A new thread
is pointed at those, not handed a restatement of them that will itself go stale.

**Before your session ends, run the `close-out-thread` skill**
(`.claude/skills/close-out-thread/SKILL.md`). It is the checklist that keeps
this file and TOUR.md true: green tree, no document naming a branch, orientation
documents matching reality, notes struck that your session made false, and the
prompt for whoever comes next. It exists because three orientation files were
found describing finished work as active, and a thread acted on all three.
- Flag uncertainty openly (Open Questions / STATUS deviations) rather than
  presenting guesses as settled.
