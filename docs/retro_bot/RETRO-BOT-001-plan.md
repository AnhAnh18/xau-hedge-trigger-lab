# RETRO-BOT-001 Implementation Plan

Status: revised after two independent plan critiques on 2026-08-01. Both
recommended the `complex` implementation profile because raw-data provenance
and the M5 firewall are part of correctness. The plan explicitly excludes the
untrusted `.ex5` artifact, so no binary analysis or sandbox execution occurs
in v1.

## Working Profile

Use high-reasoning review only for contracts, privacy/firewall design, and the
final independent review. Use the balanced model for implementation and a
low-cost deterministic model for test reruns, hashes, formatting, and routine
inventory. Do not trade safety or independent review for a lower-cost model.

## RB-001: Register the Lane

1. Add the contract and roadmap in `docs/retro_bot/`.
2. Add a compact task list under `.local_ai/` only after independent review of
the plan confirms the lane can be registered without changing M5 status.
3. Add tests that assert the contract has source digests, all policy ids, all
clock ids, a complete eligibility/censoring/metric definition, exclusion of
the August blocks, and an explicit M5 firewall. The firewall inventory pins
the protected path set with a self-digest and rejects its three casefolded lane
tokens in every listed file. The machine-readable config and inventory must
also match their hard-coded expected canonical digests, have unique
workspace-contained relative paths, and be rejected on any payload change.
4. Run the new documentation/privacy tests and `git diff --check`.
5. Stage only the new RETRO-BOT files and commit the RB-001 milestone.

Acceptance: the owner authorization, source boundary, clock hypotheses,
policies, prohibited claims, and stop conditions are explicit.

## RB-002: Build Safe Replay Inputs

1. Add `src/xau_trigger/retro_bot.py` with immutable clock/policy configuration
and quarantine-manifest verification helpers.
2. Accept only the exact 9 report aliases and exact 39 tick aliases in the
machine config plus the two pinned manifest digests; independently enumerate
the accepted receipt and require the alias sets and hashes to match before
opening any source. Resolve every source path below a supplied quarantine run.
Enforce the contract's half-open server-time population window before any
replay or aggregate calculation.
3. Add a streaming tick accessor that returns the first valid tick timestamp
in the contract's half-open `[target, observed_rehedge)` window. Return the
registered right-censor reason instead of scanning or emitting an action at or
after the observed following re-hedge. Do not write tick data to tracked or
derived files.
4. Add synthetic fixtures and tests for path escape, hash mismatch, partial
file, UTC+2/UTC+3/EET-EEST clock conversion, cross-midnight, both DST inverse
failure modes (spring gap and fall-back fold), and tick gaps.
5. Commit only the source, fixtures, tests, and docs needed for RB-002.

Acceptance: all source validation failures are fail-closed and the accessor is
no-lookahead and deterministic.

## RB-003: Implement the Surrogate

1. Convert deterministically reconstructed `UNLOCK_TO_*` plus following
`REHEDGE_*` pairs into minimal observed intervals.
2. Replay all four frozen policies from the observed unlock and select the
first available tick after the policy delay.
3. Emit conceptual candidate actions with only interval ids, policy/clock ids,
side-match status, and timing-error bands; do not emit a price, ticket, or
broker order.
4. Test opposite-side mapping, future-tick prohibition, absent coverage,
immutable policy ids, and deterministic ordering.
5. Commit RB-003 only after focused tests pass.

Acceptance: it is mechanically impossible for a candidate action to occur
before the unlock, before its delay, at or after the observed re-hedge, or at
a non-existent tick.

## RB-004: Evaluate and Report

1. Implement an aggregate evaluator and canonical JSON serializer with a
self-digest.
2. Write an ignored-run CLI that verifies sources, parses one report at a time,
streams only relevant ticks, and retains its aggregate payload below the
ignored RETRO-BOT run directory.
3. Add a tracked report generator that consumes only the aggregate payload and
uses `observed`/`compatible`/`unresolved` language.
4. Test repeatability, privacy-schema rejection, aggregate tamper detection,
and explicit M5-reference scanning.
5. Commit RB-004 after targeted and full tests pass.

Acceptance: a historical run exposes neither raw data nor a selected-best
policy and cannot be used by M5.

## RB-005: Run, Review, and Close

1. Create a fresh source receipt for the exact previously accepted object set
and register one deterministic historical run.
2. Run the aggregate CLI for all three clock scenarios and all four policies.
3. Obtain a fresh independent review in a separate session. The reviewer may
read code and the named privacy-validated ignored aggregate payload, but not
raw data, credentials, quarantine sources, detailed traces, or any other
ignored run file.
4. Fix confirmed findings, rerun the independent review, then run the complete
suite in an isolated pytest base directory.
5. Update `STATUS.md`, `TASKS.md`, and `SESSION_LOG.md` only if the final
review passes. Commit state recording separately from code.

Acceptance: the review has no P0-P3 finding, artifacts and tests are
reproducible, and M5's frozen files and August outcome blindness are intact.

## Non-goals

This plan does not inspect or execute `MomentumHedgeEA_LiveSafe_A_Fixed.ex5`,
generate MQL5, send orders, optimize P/L, establish the original trigger, or
produce a live-trading recommendation. Any such work is a new contract.
