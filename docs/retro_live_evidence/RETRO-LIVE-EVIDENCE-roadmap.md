# RETRO-LIVE-EVIDENCE Roadmap

Status: active, fail-closed; independent of M5 and closed RB-020. No live
orders are authorized by this roadmap.

## Current lane state

- E-001 contract, source boundary, gate registry, privacy firewall, and
  holdout protocol are frozen and independently reviewed.
- E-002 receipt-bound historical captures are complete for the currently
  authorized population. The original summer and winter/summer-transition
  expansion results remain `insufficient-actionful-coverage`; Monday-gap is
  absent and the variable-lot minimum is unmet (`1/6`).
- E-003 and E-004 are implemented and independently reviewed as synthetic,
  fail-closed scaffolds. Real fidelity comparison and untouched-holdout
  consumption have not started because E-002 is insufficient.
- E-005 and E-006 are implemented and independently reviewed as synthetic,
  read-only/safety scaffolds. No realtime observer, broker connector, demo,
  canary, or live execution surface exists.
- A new source/window requires a new case-specific owner authorization,
  exact aliases and hashes, UTC window, retention deadline, and receipt. No
  threshold may be relaxed to bypass the current stop condition.

## E-001 — Evidence contract and source boundary

Lock owner authorization, exact source aliases/hashes, timezone policy,
retention, preregistered gates, privacy/M5 firewall, and stop conditions.

## E-002 — Actionful capture and intake

Collect bounded tick/report/observation blocks with hashes and redacted intake
receipts. Target at least 30 actionful cycles spanning normal hedge,
one-leg recovery, Monday gaps, variable lots, both directions, and wide spreads.
No raw rows are retained in reports.

## E-003 — Behavioral fidelity evidence

Compare autonomous replay with observed labels on untouched blocks for state,
direction, ordering, timing, duplicate actions, lot sizing, coverage, and
censoring. A candidate cannot advance if coverage is insufficient.

## E-004 — Untouched holdout and robustness

Open a sealed holdout once. Evaluate registered candidates across seasonal
clock regimes, gaps, spread/slippage perturbations, missing quotes, and lot
variation. No holdout-informed tuning is permitted.

## E-005 — Shadow observer

Run a read-only realtime observer with no order API. Compare clone decisions to
the contemporaneous source, record latency/reconnect/state-recovery behavior,
and stop on unsafe divergence.

## E-006 — Demo/canary readiness decision

Build and test an execution adapter only after E-001–E-005 pass. Demo comes
before canary; hard limits, emergency flattening, idempotency, reconnect
recovery, and operator stop controls are mandatory. This roadmap does not
authorize live trading.
