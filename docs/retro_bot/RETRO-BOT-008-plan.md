# RETRO-BOT-008 Implementation Plan

Status: revised after independent plan critique; implementation may begin.

Locked exploratory defaults: the only policy ids are `always_hold` and
`first_legal_match` with direction rules `ONE_BUY -> OPEN_SELL` and
`ONE_SELL -> OPEN_BUY`; one terminal outcome is retained per one-leg window;
RB-008 censor precedence is inherited and the first censor ends the window;
same-second ticks are rejected; epochs and anchor inclusivity are checked
before feature construction; RB-011 earliest-unused oracle bands are reused;
canonical UTF-8 JSON uses fixed insertion order; accepted action is applied
through RB-009 immediately and no later tick is read.

1. Add immutable RB-012 configuration and dataclasses for one-leg windows,
   candidate outcomes (`hold`, `action`, `censored`), bounded censor reasons,
   and aggregate rows. Lock only `always_hold` and `first_legal_match`, with
   `open_buy`/`open_sell` direction rules as specified by the contract.
   Inherit RB-008 source/config digests and assert the M5 firewall.
2. Implement a chronological one-leg replay engine over RB-009 policy state.
   Evaluate the first valid tick at/after the decision anchor, then each later
   valid tick, without sorting, interpolation, future reads, or retries that
   widen the causal prefix. Permit only `ONE_BUY -> OPEN_SELL` and
   `ONE_SELL -> OPEN_BUY`; require exact `StateSnapshot.epoch` equality with
   `expected_epoch`, reject same-second collisions, and apply at most one
   action per state epoch.
3. Integrate RB-010 snapshot/rule evaluation. Map `feature_missing`, invalid
   chronology, duplicate/out-of-order input, and coverage loss to `censored`
   using RB-008 precedence; the first censor is terminal for the window;
   map legal matching rules to one conceptual action and non-matching rules to
   `hold`. Preserve deterministic rule-id tie resolution and immutable
   configuration after run start. Apply a legal action immediately through
   RB-009 and stop reading later ticks in that window.
4. Add an oracle-diagnostic adapter for RB-007 observed unlock/re-hedge labels
   and fixed-delay baseline timing. Keep labels in a separate path; prove by
   injection tests that changing labels cannot change autonomous outcomes.
   Emit only bounded timing bands and aggregate side-by-side comparison rows,
   using RB-011's earliest-unused same-cycle labels and inclusive `exact`,
   `0-1s`, `2-6s`, `7-30s`, `>30s` bands.
5. Add aggregate validation and deterministic writer checks: one terminal
   outcome per window (`eligible = hold + action + censor`), no action from
   censored/terminal/hedged states, finite bounded metrics, complete fold x
   clock x bootstrap x policy row coverage, privacy allowlist, source digest
   checks, canonical JSON serialization, contained ignored CLI run root, and
   byte-identical reruns.
6. Add synthetic tests for both directions, first-tick boundary, hold/action/
   censor precedence, missing/non-finite features, duplicate/out-of-order and
   gap handling, action legality, duplicate/post-action rejection, oracle
   invariance, baseline timing bands, aggregate tampering, privacy, and M5
   complete matrix-row coverage, canonical writer/CLI containment, privacy,
   and M5 firewall isolation.
7. Run focused RB-012 tests, the full RETRO suite, `check_privacy.py`,
   `compileall`, and `git diff --check` using workspace basetemp paths. Ask
   an independent reviewer in a fresh session; remediate every confirmed
   P0-P3 finding and obtain a fresh focused re-review.
8. Only after a PASS, have the state recorder update `STATUS.md`, `TASKS.md`,
   and `SESSION_LOG.md`, mark the RB-012 task complete, register RB-013, and
   commit only RB-012 artifacts. Do not mix raw data, M5 changes, or unrelated
   work.

Acceptance: the engine is a deterministic causal one-leg re-hedge policy,
compatible with RB-009/RB-007, with explicit hold/action/censor outcomes and
an oracle-only baseline comparison.
