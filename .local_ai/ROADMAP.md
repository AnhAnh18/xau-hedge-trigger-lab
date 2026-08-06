# Roadmap

## North star

Reconstruct the XAUUSD strategy at three distinct levels:

1. Structural clone — reproduce hedge-state management.
2. Behavioral clone — reproduce transition direction, timing, and price.
3. Economic clone — preserve any edge after spread, slippage, latency, and risk.

Passing one level does not imply that the next level is feasible.

## M0 — Project Bootstrap ✅

Deliverable: reproducible project structure, project memory, privacy policy,
CI, and branch/test/merge workflow.

Gate: the project can continue across sessions without relying on chat history.

## M1 — Data Foundation ✅

Deliverable: canonical MT5 report and tick parsers, normalized local tables,
per-report reconciliation, anonymized fixtures, CI, and privacy checks.

Gate: parsing is reproducible, financial totals reconcile, and no raw financial
data is tracked.

## M2 — State Reconstruction ✅

Deliverable: unique position lifecycles, chronological state intervals,
transition classifications, and explicit exception accounting.

Gate: inventory is conserved and every lifecycle event is classified or
retained as an exception.

## M3 — Event–Tick Alignment ✅

Deliverable: reported events aligned to broker ticks with separate time/price
errors and match-quality accounting.

Gate: all events in tick coverage are resolved or explicitly unmatched; no
ambiguous event is forced into the primary cohort.

## M4 — Causal Trigger Dataset and Baseline Hypotheses ✅

Deliverable: causal positive/control samples, separate audit/model outputs,
lineage-safe state age, and paired H1/H2/H3 reports.

Gate: deterministic sampling, no future leakage, explicit support/validity,
causal sensitivity, and honest hypothesis verdicts.

## M5 — Trigger Inference 🚧

Question: does price/tick information add predictive signal beyond elapsed
tradeable state age?

Work packages:

- M5-000: lock time support, timezone status, cohort comparability, parameter
  budget, and external-session acquisition protocol.
- M5-001: acquire and register additional contiguous tick/report sessions.
- M5-002: build state-age-only discrete-time hazard baselines.
- M5-003: add the pre-registered price predictor set and compare paired
  per-interval likelihood increments.
- M5-004: model unlock cause conditional on an unlock occurring.
- M5-005: run external temporal validation.

Gate:

- Risk bins use tradeable time and exclude recorded coverage gaps.
- M5 appends explicit right-censored state tails through merged tick coverage;
  censored tails never create terminal or competing events.
- Left-truncated and zero-duration cases remain fully accounted but outside the
  complete-risk-bin primary estimand.
- A/B/C headline comparisons use identical bins on common server-hour support.
- ONE_BUY and ONE_SELL re-hedge processes are evaluated separately.
- Unlock direction is a conditional cause split, not an independent hazard.
- Price predictors are explicitly pre-registered and capped at 10–12 primary
  predictors.
- Headline inference reports both `C - A_common` and `C - B`, clustered by
  `interval_id`.
- M5-002 uses cause-specific occurrence likelihood as primary. Any
  within-interval conditional timing statistic for M5-003 requires a new
  pre-registered risk-set design; the outcome-truncated age-only version is
  non-inferential.
- Results survive pre-registered additional tick sessions. The current
  partial-plus-one-session dataset may produce a pilot only and cannot close M5.

## M6 — Behavioral Baseline

Deliverable: first interpretable rule-based strategy that maps HEDGED and
one-sided states to candidate transitions without profit optimization.

Gate: direction, transition type, timing, price, and one-sided-duration
similarity improve materially over simple baselines on untouched data.

## M7 — Tick Replay Backtester

Deliverable: deterministic no-lookahead replay with Bid/Ask execution, spread,
latency, slippage, commission/swap, P/L, and side-by-side original/clone events.

Gate: behavioral similarity survives small execution perturbations and all
execution/accounting invariants pass.

## M8 — Out-of-Sample and Regime Validation

Deliverable: walk-forward evaluation over additional trend, range, volatility,
news, rollover, and end-of-week regimes.

Gate: parameters remain stable and behavior is not driven by one day, regime,
or a few outliers.

## M9 — Shadow Observer

Deliverable: read-only live observer logging real state, original events, clone
signals, feature snapshots, and timing differences.

Gate: one to two weeks of stable observation confirms historical behavior,
feed/timezone assumptions, latency, and event ordering.

## M10 — EA Prototype

Deliverable: modular demo/paper EA with StateManager, UnlockTrigger,
RehedgeTrigger, ExecutionManager, RiskManager, and Logger.

Gate: hard risk limits, emergency flattening, deterministic logs, real-tick
testing, and demo validation pass before any live consideration.

## M11 — Feasibility Decision

Possible outcomes:

- Behavioral clone is feasible: continue validating the EA.
- The original cannot be cloned, but an independent robust rule exists: split
  it into a separate strategy-research project.
- Available MT5/tick data cannot identify the trigger: stop rather than overfit.

## RETRO-LIVE-EVIDENCE - independent evidence lane

- E-001 governance and gate freeze: complete; synthetic-only, no source or
  execution authorization.
- E-002 synthetic intake scaffold: complete; actual actionful capture remains
  pending a new owner authorization and exact source receipt.
- E-003 behavioral fidelity and E-004 untouched holdout/robustness synthetic
  scaffolds: complete and independently re-reviewed PASS; real source capture
  remains locked behind a new owner authorization and exact source receipts.
- E-005 shadow observer and E-006 demo/canary readiness remain locked behind
  prior gates and are not implemented.
