# Pointer equality with a merged constant, then a load (#220206 item 1, repro from #220091)

## What happens

Two `unnamed_addr` constants (one `undef`, one zero) get merged to the same address.
Before that, GVN/SCCP saw `p == @a`, replaced `p` with `@a`, and folded the load to `undef`.
After merging, the same address reads back as two different values: on the native repro,
two calls return 17 and 29 while a direct read of the bytes returns 0.

`repro.ll` is the IR, `driver.ll` an unoptimized driver and `start.S` a small entry stub. The driver only takes
the equal branch after checking the real addresses.

## The change

Read/replacement side only (`Loads.cpp`, and the SCCP user in `SCCPSolver.cpp`): stop
replacing a pointer with a constant global just because their addresses compare equal.
Production code: 2 files, +6/-13. No header changes. Constant merging is not touched.

This follows the direction in #220091 and depends on how item 1 of #220206 is settled.
It does not assume that discussion is done.

## Cost

Three existing tests lose a fold (clang vtable devirtualization pattern and `select.ll`
test61): `GVN/assume-equal.ll`, `GVN/invariant.group.ll`, `InstCombine/select.ll`.
Two more expectations change on purpose: `SCCP/replace-dereferenceable-ptr-with-undereferenceable.ll`
and the `LoadsTest/CanReplacePointersIfEqual` unit test (the old TRUE allowed arbitrary uses).
The new SCCP test `gep_read` also shows a read of the fully defined half no longer being folded.

## How to check

Quickest: apply the two patches on 304cb72 and run the changed tests with `llvm-lit`
(they pass after patch 1 on the base, and after patch 2 with the change).

Full repro, if you have shared-library builds of the base and the patched tree:
`sh verify.sh BASE_BUILD V3_BUILD LLVM_SOURCE /path/to/ld.lld`.
It runs the native repro and the changed lit tests at each patch stage.

## Checks (base 304cb72bcb93, x86-64 Linux, Release + assertions, shared LLVM)

| Check | Baseline | v3 |
|---|---:|---:|
| Native repro | 17 / 29 vs memory 0 | consistent (0) |
| Rust rust-lang/rust#162078 IR, O1–O3 | inconsistent | exits normally |
| check-llvm, old expectations: pass / fail | 41,176 / 0 | 41,171 / 5 (the 5 above; all updated in patch 2) |
| clang file-based lit pass / fail | 19,690 / 1 | 19,690 / 1 (same test) |
| check-lld pass | 2,059 | 2,059 |
| Alive2 on touched functions (48) | – | 21 verified, 0 counterexamples, 27 timeout/unsupported |
| Small exhaustive (1–3 byte arrays, O1–O3) | 0 mismatches | 0 mismatches (this domain doesn't trigger the original bug either) |
| `opt -O2/-O3` time, 7 runs | – | TokenLexer.cpp / CGCleanup.cpp within ±6%; tiny inputs dominated by start-up |

clang unit tests were not run (they don't go through this code path).

## Known gaps

- Some SCCP `freeze`/`undef` cases are wrong on the baseline and still wrong with this
  change (confirmed natively). Not covered here.
- We also tried keeping the 3 folds with a bounded read-only exception. It brings back a
  baseline miscompile (a one-past-the-end pointer equal to an adjacent constant, reached
  through a GVN-equivalent value), so it is not included. The repro is available if useful.
- Alive2 checks IR only, not section classification or link-time merging.

Assisted-by: Claude, Codex
