# RETRO-LIVE-EVIDENCE Roadmap

Status: proposed; independent of M5 and closed RB-020. No live orders are
authorized by this roadmap.

## E-001 — Evidence contract and source boundary

Lock owner authorization, exact source aliases/hashes, timezone policy,
retention, preregistered gates, privacy/M5 firewall, and stop conditions.

## E-002 — Actionful capture and intake

Collect bounded tick/report/observation blocks with hashes and redacted intake
receipts. Target at least 20–30 actionful cycles spanning normal hedge,
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
