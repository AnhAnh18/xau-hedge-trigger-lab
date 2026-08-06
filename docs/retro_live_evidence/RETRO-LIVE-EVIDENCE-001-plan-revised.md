# RETRO-LIVE-EVIDENCE E-001 Revised Plan

Status: actionable governance-only plan. E-001 is independent of M5 and the
closed RB-020 lane. It does not authorize historical-source access, realtime
access, demo, canary, order submission, or live execution.

## 1. Objective and hard boundary

Freeze the evidence protocol before any new actionful source is opened. E-001
must produce governance, schema, and synthetic-test artifacts only. It may not
read, print, hash, copy, or retain new raw trading data; it may not inspect M5
outcomes or modify RB-020, M5 manifests, models, thresholds, evaluations,
gates, frozen artifacts, or live/demo code.

The future E-002 population is a bounded observation block supplied under a
new owner authorization. E-001 records the protocol for that authorization,
but does not invent source aliases or claim a source receipt for data not yet
collected. Existing RETRO/RB source receipts remain out of scope unless a new
authorization explicitly names them.

## 2. Required governance artifacts

Create and review all of the following before E-002:

1. `RETRO-LIVE-EVIDENCE-001-contract.md`: scope, claims, stop conditions,
   privacy rules, and the exact gate registry below.
2. `RETRO-LIVE-EVIDENCE-001-authorization.md`: protocol authorization only;
   it must state that no raw source may be opened during E-001 and that E-002
   needs a separate case/population authorization.
3. `RETRO-LIVE-EVIDENCE-001-source-receipt-template.md`: canonical alias,
   object type, UTC window, allowed fields, retention, SHA-256, and receipt
   fields to be completed only after E-002 intake.
4. `RETRO-LIVE-EVIDENCE-001-gates.json`: machine-readable immutable formulas,
   thresholds, denominators, category definitions, and result taxonomy.
5. `RETRO-LIVE-EVIDENCE-001-holdout-protocol.md`: chronological partition,
   input digest, one-shot nonce/receipt, replay rejection, and tamper rules.
6. `RETRO-LIVE-EVIDENCE-001-firewall.md` plus focused tests covering raw-data,
   credential, private-path, M5, and execution-surface exclusion.
7. Independent plan critique, this revised plan, implementation review, and
   fresh re-review receipts.

## 3. Source and observation contract for E-002

E-002 may use only an owner-authorized, hash-verified quarantine receipt. Each
source object receives a generated alias (no private path in output), exact
SHA-256, object type, byte count, and canonicalization version. Allowed raw
fields are restricted to the explicitly authorized tick quote fields and
observation/lifecycle fields; credentials, journals/deals, fees, swaps,
profits, tickets, terminal caches, `.ex5`, and M5 artifacts are forbidden.
The receipt records `[start_utc, end_utc)`, source timezone claim, retention
period, and parser version. Any alias/hash/window/field mismatch is a hard
stop. Raw rows are parsed in memory or in the append-only quarantine procedure
and never appear in retained reports, logs, test output, or commits.

### Deterministic clock

All canonical timestamps are UTC RFC3339 with microseconds and half-open
windows. Source server time is preserved only as a redacted timezone code.
The registered hypotheses are `UTC+2` winter and `UTC+3` summer (DST boundary
is determined by the source date and the declared broker rule); a fixed
`UTC+3` interpretation is not assumed across the whole population. Conversion
is `utc = source_time - offset`, with offsets applied per session date. A
missing/ambiguous offset, second-level tie, or boundary event that cannot be
ordered deterministically is censored and cannot generate an action.

## 4. Actionful population and category definitions

A **cycle** starts at the first observed opening action after a known FLAT
state and ends at a verified FLAT close; an unclosed cycle is `censored`.
An **actionful cycle** has at least one observed open/close/hedge action.
Categories are descriptive and may overlap:

- normal hedge: both opposite legs observed without a gap flag;
- one-leg recovery: exactly one leg remains at a decision checkpoint;
- Monday gap: first eligible quote after a registered weekend gap exceeds the
  preregistered gap threshold of `0.50` XAUUSD price units;
- variable lot: any cycle with two or more distinct positive quantities;
- wide spread: spread above the 95th percentile of the same intake block,
  computed once from ticks and sealed in the intake receipt.

The sufficiency target is at least 30 actionful cycles, including at least 8
normal-hedge, 6 one-leg, 4 Monday-gap, 6 variable-lot, and 4 wide-spread
cycles, at least 10 Buy-direction and 10 Sell-direction observed actions.
Category counts may overlap. If the target is not met, the result is
`insufficient-actionful-coverage`; no threshold may be lowered after intake.

## 5. Immutable gate registry

These definitions and values are frozen when `gates.json` is signed, before
E-002 inspection. The registry stores formula version, numerator, denominator,
exclusions, and threshold; missing denominators produce `not-evaluable`, not a
passing zero.

- `state_parity = matching_state_checkpoints / eligible_state_checkpoints`,
  pass `>= 0.90`.
- `direction_parity = matching_direction_actions / comparable_direction_actions`,
  pass `>= 0.85`.
- `ordering_parity = cycles_with_matching_action_order / comparable_cycles`,
  pass `>= 0.90`.
- `timing_within_band = actions_with_abs_delta_seconds <= 5 /
  comparable_actions`, pass `>= 0.80`; 5 seconds is the report-resolution
  tolerance and is not an inferred strategy delay.
- `lot_parity = quantities_with_abs_delta <= max(0.00000001, 0.01 * observed)
  / comparable_quantities`, pass `>= 0.95`; partial/uneven lots are compared
  per leg and fixed8-rounded before comparison.
- `duplicate_action_rate = duplicate_actions / observed_actions`, pass
  `<= 0.01`.
- `coverage = comparable_checkpoints / eligible_checkpoints`, pass `>= 0.80`;
  `censor_rate = censored_checkpoints / eligible_checkpoints`, pass `<= 0.20`.
- `state_safety` requires zero illegal transitions, negative/created lots,
  same-tick double actions, conservation failures, or future-read flags.
- `robustness_pass_fraction = passing_registered_perturbations /
  registered_perturbations`, pass `>= 0.75` across timezone, gap, spread,
  missing-quote, latency, and lot-variation perturbations.
- `determinism` requires two independent runs to have byte-identical canonical
  aggregate, receipt, and gate digests.

The decision taxonomy is `package-ready`,
`behaviorally-compatible-accounting-inconclusive`,
`insufficient-actionful-coverage`, or `no-supported-candidate`. None implies
profitability, broker ownership, clone status, or live suitability.

## 6. Holdout protocol

Before E-002, register chronological development, validation, and one final
holdout interval with non-overlap and a sealed input digest. Holdout opening
requires a caller-provided nonce bound to the gate-config digest, source
receipt digest, and holdout-input digest. A receipt is append-only and
one-shot: a reused nonce, changed payload, changed config, or second
consumption is rejected. No candidate, threshold, parser, timezone, or cost
change may be made after holdout consumption; any failure yields `HOLD`.

## 7. Oracle isolation and future lanes

Define separate typed `AutonomousInput` and `OracleDiagnosticInput` schemas.
Observed actions/outcomes may be used only to calculate redacted comparison
metrics. Tests must prove oracle fields cannot reach policy features, state
transitions, accounting controls, fold selection, candidate ranking, or gate
thresholds through mappings, copies, serialization, or nested payloads.
E-005 is a future read-only observer with no order API; E-006 is not authorized
by E-001.

## 8. Tests, workflow, and acceptance

Use synthetic fixtures only and add focused tests for valid/invalid schemas,
missing/extra fields, duplicate keys, canonical serialization, hash and alias
mismatch, timezone/DST boundaries, gate immutability, holdout tamper/reuse,
oracle contamination, raw/private-path/M5/order-surface firewall, and a
synthetic end-to-end receipt. Run the exact focused test command, compileall,
`git diff --check`, privacy/M5 scanners, and two deterministic subprocess
runs; record commands and outputs in the review artifacts.

The managed workflow is: independent critic -> revised plan -> implementation
-> fresh independent review -> fixes for every P0-P3 -> fresh re-review ->
state recorder. State files (`.local_ai/STATUS.md`, `TASKS.md`,
`SESSION_LOG.md`) may be updated only after PASS. Preserve unrelated changes;
stage only E-001 artifacts and state records, then commit with
`retro-live-evidence-001:` and push. Any missing authorization, source
expansion, ambiguity, leakage, nondeterminism, privacy/M5 violation, or request
for execution is an immediate stop.
