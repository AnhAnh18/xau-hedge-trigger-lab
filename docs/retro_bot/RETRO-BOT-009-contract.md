# RETRO-BOT-009: Walk-Forward Historical Evaluation Contract

Canonical milestone mapping: this artifact is the `RB-013` walk-forward
evaluation milestone (the repository filenames retain the historical
`RETRO-BOT-009` sequence). Implementations, tests, receipts, and state
records must use `RB-013` as the canonical id and must not create a second
milestone id.

Status: owner-authorized follow-on to RB-012 on 2026-08-03; RETRO-only and
outside every M5 input, model, evaluation, threshold, and gate.

## Purpose and claim boundary

RB-013 evaluates the frozen autonomous candidate policies on the locked
2025-11 through 2026-07 historical population. It is a chronological,
aggregate-only compatibility evaluation, not a search for a profitable
strategy and not evidence that the original bot, an EA, or a human operator
has been reproduced. The observed unlock/close/re-hedge stream is available
only as a separately labeled oracle diagnostic and never as an autonomous
feature, state transition, calibration input, or selection criterion.

The evaluation may end as `package-ready`, `tie_inconclusive`,
`inconclusive`, or `no-supported-candidate`. Status precedence is:
`no-supported-candidate` when every candidate fails a mandatory safety gate;
`inconclusive` when required independent-unit or side support is unavailable;
`tie_inconclusive` when two or more candidates clear every gate; and
`package-ready` only when exactly one candidate clears every gate. RB-013 does
not perform paper accounting, so the V2
`behaviorally-compatible-accounting-inconclusive` outcome is deferred to
RB-014/RB-017. No candidate is ranked by a performance statistic.

## Locked source and population boundary

The evaluator inherits RB-008 without expansion:

- configuration SHA-256: `26fec4baa2b8e2680cc17afaad299bbbb00afba32810865ac60bf28eb2e49ebf`;
- report manifest SHA-256: `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`;
- tick manifest SHA-256: `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`.

The half-open population is `[2025-11-01 00:00:00,
2026-07-31 00:00:00)` in registered server time. The nine report aliases,
three clock scenarios, two bootstrap rows, censor precedence, and fold
assignment are exactly those in RB-008. No August M5 block, RETRO-001/002
source, journal, credential, account field, `.ex5`, XLSX companion, or new
raw source is admitted. A digest, alias, date-range, suffix, or path failure
fails closed before source opening.

The two bootstrap rows are deterministic views over the same locked source
boundary (fixed-seed replay and left-censored replay), not candidate-specific
resampling choices. Every candidate sees the same view; bootstrap order and
randomness cannot affect selection or tie resolution.

## Temporal walk-forward protocol

Report/session/case units are the split units. No interval, cycle, or tick is
randomly split, and a continuation crossing a fold boundary is excluded by
the RB-008 censor rule. The fixed chronological roles are:

| Role | Units | Permitted use |
| --- | --- | --- |
| `development` | reports 001--005 | exploratory protocol checks only; no calibration |
| `validation` | reports 006--007 | one predeclared protocol-readiness check; no holdout inspection |
| `holdout` | reports 008--009 | untouched final evaluation, executed once after freeze |

The candidate manifest, feature vocabulary, rule tuples, thresholds,
missing-data policy, timing bands, gate thresholds, tie rules, and output
schema are frozen before validation or holdout outcomes are opened. The four
registered tuples are replayed unchanged; RB-013 performs no calibration or
selection from development outcomes. Development is retained only for
exploratory protocol checks and gate accounting. Validation is a single blind
structural-readiness intake: only source/config digests, schema, fold
membership, matrix coverage, and censor/clock structural status may be
opened. Candidate action, hold, side, oracle, timing, and false-action values
remain sealed until the final replay. Validation may not tune thresholds, add
candidates, drop candidates, or inspect holdout results.

The exact expanding prefix is chronological by report alias: for each report
in validation, the available prefix is reports 001--005 plus earlier
validation reports; for each report in holdout, it is reports 001--007 plus
the earlier holdout report. No decision may read a tick, label, or state event
whose report belongs to a later fold. A lifecycle continuation that crosses a
fold boundary is excluded once, using the RB-008 censor precedence. Each fold
is replayed in causal order and no random interval split is permitted.

The holdout has one sealed historical replay after the structural intake and
freeze. Determinism is established with two synthetic fixture runs; an
optional second historical replay may be generated only as a sealed digest
check and must not open or feed any result back into the protocol.

## Candidate and baseline set

Evaluate every policy tuple in the locked RB-011 and RB-012 manifests side by
side. A tuple is the Cartesian product
`(close_policy_id, rehedge_policy_id)`; its canonical id is
`<close_policy_id>__<rehedge_policy_id>`. Only the registered policy ids
`always_hold` and `first_legal_match` are admitted for either component, so
the four combinations are complete and no hidden composition is allowed.
Candidate configuration is immutable before validation intake and after the
run starts. The RB-007 fixed-delay replay remains a descriptive baseline row,
and observed events remain labels only. No development, validation, or
holdout outcome, paper P/L, accounting result, or profitability statistic may
select or rank a candidate; only the predeclared safety and support gates
determine the terminal status.

If more than one candidate clears all support and safety gates, report
`tie_inconclusive` and retain all rows. A deterministic lexical `candidate_id`
order is used only for serialization and reproducible diagnostics; it is not
a performance tie-break. If no candidate clears the gates, report
`no-supported-candidate`; if minimum support is unavailable, report
`inconclusive`.

## Predeclared gates and metrics

Every fold x clock x bootstrap x candidate row has separate close-component
and re-hedge-component counters. For each component, eligible terminal
windows conserve `hold + action + censor`; per-tick `invalid_transition`,
`feature_missing`, and duplicate counts are reported separately and force the
component to `censor` rather than being silently dropped. The combined
lifecycle may not emit a same-tick close then re-hedge: a re-hedge window
starts only on a later valid tick after RB-009 accepts the close transition.
A close censor terminates that lifecycle window under RB-008 precedence; no
re-hedge decision is attempted after a terminal censor. A re-hedge censor is
terminal for its one-leg window and cannot be retried on later ticks.

The minimum-support gate is checked independently for each component,
fold, clock, bootstrap, and side: at least two independent report units in a
non-empty fold, at least two eligible `ONE_BUY` and two eligible `ONE_SELL`
windows, and at least one accepted action in each direction for a candidate
component. An empty fold or missing side is marked `support_unavailable` and
cannot be called supported; it yields `inconclusive` unless another
mandatory safety gate already yields `no-supported-candidate`.

The following are mandatory safety gates: source and firewall attestation,
no lookahead/oracle mutation, legal state transitions, zero unaccounted
duplicates or invalid actions, finite aggregate values, complete matrix
coverage, and privacy validation. Coverage, hold/action/censor proportions,
and false-action counts are reported descriptively. Oracle diagnostics use the
RB-011 one-to-one, earliest-unused, non-negative delta matcher and the
inclusive timing bands (`exact`, `0-1s`, `2-6s`, `7-30s`, `>30s`); unmatched
actions, direction mismatches, duplicate labels, and unmatched labels are
distinct counts. No coverage-maximizing policy passes merely by acting on
every eligible tick.

## Retained outputs and privacy

Retain two canonical redacted aggregates: an autonomous aggregate containing
only lifecycle/component accounting and safety fields, and a separate oracle
diagnostic aggregate containing label-match and timing fields. They have
distinct schemas, allowlists, and digests; the autonomous verifier rejects
oracle keys and the oracle verifier rejects autonomous state-mutating fields.
Each aggregate contains schema/version, inherited source digests,
fold/clock/bootstrap/candidate ids, bounded counts and bands,
minimum-support and gate statuses, terminal outcome, and aggregate SHA-256.
Anonymized ids must match `^[A-Za-z0-9_-]{1,64}$`. Include the literal
`M5_FIREWALL_ATTESTATION_V1`. Never retain or print raw rows, prices, exact
timestamps, detailed timelines, tickets, credentials, private paths,
journals, or account identifiers. Candidate and oracle diagnostics have
separate schemas/digests so accidental mixing fails closed.

Canonical output is UTF-8 JSON with fixed key order and matrix rows sorted by
fold, clock, bootstrap, candidate, and component. Reject NaN, infinity,
negative zero, unbounded integers, unknown keys, and duplicate matrix rows.
The self-digest is computed after removing only its own digest field. Writers
must stay under the ignored run root, and validation errors must not include
source paths or raw values.

## Acceptance and stop conditions

- Synthetic tests prove chronological fold assignment and exact expanding
  prefixes, candidate freeze, structural-only validation intake, sealed
  holdout, no-lookahead decisions, no same-tick double action, oracle
  isolation, separate-schema rejection, component conservation, support
  gates, deterministic tie/status precedence, bootstrap repeatability, and
  complete rows.
- Two clean synthetic runs produce byte-identical aggregates and the sealed
  historical replay emits a single accepted digest; privacy, M5 firewall,
  `py_compile`, focused/full tests, and `git diff --check` pass.
- Stop immediately on source tamper, holdout inspection/tuning, future data,
  oracle mutation, illegal transition, privacy leak, incomplete matrix, or
  M5 contamination. Source expansion requires a new owner decision, receipt,
  and contract.
- Independent plan critique, implementation review, remediation, and fresh
  re-review must return `PASS` with no P0-P3 finding before state recording,
  commit, or push.

This contract does not identify the original trigger, establish profitability,
attribute manual versus automated action, or authorize live execution.
