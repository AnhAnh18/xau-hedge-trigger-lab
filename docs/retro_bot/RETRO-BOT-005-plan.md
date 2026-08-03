# RETRO-BOT-005 Implementation Plan

Status: draft pending independent plan critique; implementation has not
started.

1. Add separate immutable `PolicyAction` and `OracleLabel` dataclasses,
   state/action enums, idempotency keys, and the locked transition table.
2. Add bootstrap constructors for the RB-008 fixed `HEDGED` seed and
   `left_censored` state; reject any caller-supplied seed not present in the
   RB-008 config.
3. Implement a causal transition reducer that accepts only caller-provided
   policy actions in strictly increasing timestamp order; never sort input.
   Same-second, duplicate-key, reordered, censored-state, and post-terminal
   actions fail closed. Keep oracle labels in a separate diagnostic path that
   cannot call the reducer; add label-injection invariance tests.
4. Add explicit rejection for opposite/same-side actions, duplicate actions,
   non-increasing timestamps, post-terminal actions, malformed action fields,
   and invalid state/action pairs.
5. Add aggregate-only transition accounting with self-digest and privacy
   validation. Do not retain event timestamps, raw identifiers, or traces.
   Emit the RB-007-compatible in-memory action schema: mapped action side,
   action kind, decision time, state epoch, and explicit no-mark/no-side
   representation for termination/censoring; no identity fields survive
   aggregation. Enforce abstract quantity-1.0 leg conservation.
6. Add synthetic tests for the complete transition matrix, both bootstrap
   modes, oracle-label separation, same-second collisions, duplicate actions,
   cross-midnight/fold behavior, terminal/censored precedence, determinism,
   schema tampering, privacy, and the M5 firewall.
7. Run focused RB-009 tests, the RETRO suite, `py_compile`, privacy,
   `git diff --check`, and full suite using a workspace `--basetemp`.
8. Submit to an independent reviewer, fix every confirmed in-scope P0-P3
   finding, run a fresh re-review, and commit only after PASS.

Acceptance: the reducer is a deterministic causal state machine and cannot
be driven by observed future labels or invalid action order.
