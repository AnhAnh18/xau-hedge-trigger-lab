# RETRO-BOT-009 Implementation Plan

Canonical milestone: `RB-013` (the `RETRO-BOT-009` filename follows the
historical RETRO-BOT sequence). All implementation modules, tests, receipts,
and state references use `RB-013`; do not introduce a second milestone id.

Status: revised after independent plan critique; implementation authorized.

Locked defaults: inherit the RB-008 source/config digests, nine-report
population, report-level development/validation/holdout folds, three clocks,
two bootstrap rows, censor precedence, and the four-policy Cartesian product
of the RB-011 and RB-012 manifests.
Replay all four tuples unchanged; there is no development calibration or
outcome-based candidate selection. The holdout is opened once only after
candidate/config/schema freeze and a blind structural validation intake. No
random split, post-hoc threshold tuning, paper-P/L selection, or candidate
addition is permitted. Terminal statuses are exactly `package-ready`,
`tie_inconclusive`, `inconclusive`, and `no-supported-candidate`, with the
contract's precedence; the accounting-inconclusive V2 status is deferred to
RB-014/RB-017. Canonical UTF-8 JSON uses fixed key order; candidate ids are
lexical for serialization only, and lexical order never resolves a tie.

1. Add an immutable RB-013 evaluation configuration and typed fold/run
   records. Verify inherited manifests, aliases, date ranges, clock/bootstrap
   rows, fold disjointness, and the M5 firewall before any source is opened.
   Treat the fixed-seed and left-censored bootstrap rows as deterministic views
   over the same source; every candidate receives identical views.
2. Implement chronological walk-forward orchestration over the RB-009
   lifecycle and RB-011/RB-012 autonomous policies. Use the exact report alias
   prefixes: validation report 006/007 sees 001--005 plus earlier validation
   reports; holdout report 008/009 sees 001--007 plus the earlier holdout
   report. Feed only this causal prefix at each decision time; reject
   cross-fold continuations and any future, duplicate, or out-of-order input.
   Keep observed events in an isolated oracle-diagnostic label path.
   Disallow same-tick close/re-hedge: a new one-leg window starts only on a
   later valid tick after RB-009 accepts the close action.
3. Freeze and validate the complete candidate tuple manifest (the four
   canonical close/re-hedge combinations) before validation and holdout
   evaluation. Do not calibrate or select candidates from development;
   replay all four tuples unchanged. Make validation a one-time blind
   structural-readiness check and holdout an untouched single replay with no
   feedback channel.
4. Implement aggregate gate evaluation with separate close and re-hedge
   component counters. For each component enforce terminal conservation
   `hold + action + censor`; report invalid-transition, feature-missing, and
   duplicate counts separately and fail closed rather than dropping them.
   Apply support independently by component/fold/clock/bootstrap/side: two
   independent units in every non-empty fold, two eligible `ONE_BUY` and two
   eligible `ONE_SELL` windows, and one accepted action in each direction.
   Produce per-fold rows side by side, state-safety/no-lookahead/oracle-
   invariance flags, coverage, and bounded false-action summaries. Resolve
   terminal status with the contract's four statuses and no forced winner.
   Use RB-011's one-to-one earliest-unused oracle matcher and inclusive timing
   bands only in the separate oracle aggregate; never copy those fields into
   the autonomous schema.
5. Add canonical redacted autonomous and oracle writers/verifiers with
   distinct schemas, allowlists, and digests. Require complete fold x clock x
   bootstrap x candidate x component matrix, inherited digests,
   `M5_FIREWALL_ATTESTATION_V1`, finite bounded values, fixed UTF-8 key order,
   deterministic row sort, explicit rejection of NaN/infinity/negative zero,
   self-digest excluding only its own field, ignored-run-root containment, and
   no paths/raw values in errors. Never write raw rows or paths. Expose one
   CLI with explicit `validate-config`, `blind-structural-intake`,
   `sealed-holdout-replay`, and `verify-aggregate` stages; a failed earlier
   stage cannot open source data.
6. Add synthetic tests for exact fold prefixes and continuation censoring,
   candidate freeze/holdout immutability, structural-only validation intake,
   no-lookahead and future-tick mutation, same-tick action rejection,
   oracle-label invariance and separate-schema rejection, deterministic
   bootstrap views, support insufficiency, tie/no-winner status precedence,
   component conservation/censoring, matrix completeness, writer tampering,
   privacy, and M5 firewall isolation.
7. Run focused RB-013 tests, the full RETRO suite, `check_privacy.py`,
   `compileall`, `git diff --check`, and two deterministic aggregate runs from
   synthetic fixtures. Perform one sealed historical holdout replay only
   after the blind intake and freeze. Request an independent code review in a
   fresh session;
   remediate all confirmed P0-P3 findings and obtain a fresh re-review.
8. Only after a PASS, let the state recorder update `STATUS.md`, `TASKS.md`,
   and `SESSION_LOG.md`, mark the RB-013 task complete, and commit/push only
   RB-013 artifacts with the milestone prefix. RB-014 registration is a
   separate next milestone action. Do not mix raw
   data, M5 changes, state edits from unrelated work, or generated artifacts.

Acceptance: the evaluator demonstrates a causal, chronological,
holdout-untouched comparison of all locked candidates with explicit
inconclusive/no-winner outcomes and privacy/M5 isolation.
