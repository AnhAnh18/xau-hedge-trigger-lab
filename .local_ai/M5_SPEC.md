# M5 Trigger Inference — Locked v1 Specification

Status: M5-000 implemented; modelling has not started.

## Research question

Does causal price/tick information improve transition-timing inference beyond
elapsed tradeable state age?

M5 does not train black-box models, optimize P/L, or modify M2–M4 canonical
outputs.

## Time support

- Tick support is the exact first-to-last timestamp in the registered export.
- Every M2 interval is clipped to tick support.
- Intervals are split at calendar midnight before day-level aggregation.
- Consecutive-tick gaps strictly greater than 60 seconds are market breaks.
- The full open interval between the two observed ticks is excluded with
  `exclusion_reason=market_break_no_tick_coverage`.
- State age uses a tradeable clock: elapsed wall time minus market-break
  overlap.
- Gaps of 60 seconds or less remain ordinary risk time.
- Zero-duration M2 intervals remain in accounting but cannot create risk bins.
- Source-interval membership, terminal-event count, and tradeable seconds are
  reported separately.

The current shared boundary fixture is interval `13321`: it crosses midnight
and contains the only market break longer than 60 seconds. Interval `12074` is
left-truncated by the beginning of tick coverage.

## Cohorts and anchors

- Primary risk-bin width: 1 second.
- Sensitivity risk-bin width: 500 milliseconds.
- A positive 1-second bin ends at `reported_time`; its causal price anchor is
  therefore `reported_time - 1 second`.
- The offset from the M4 `matched_timestamp` anchor must be measured and
  published. M4 and M5 effects are not compared as if they shared an anchor.
- Full observed coverage is descriptive (`A_all`).
- All A/B/C headline comparisons use common server hours 12:00–24:00 on
  identical bins (`A_common`).
- Development remains 2026-07-23 and holdout remains 2026-07-24 for the pilot.
  These two dates are not treated as equivalent full sessions.

## Endpoint structure

- `ONE_BUY -> REHEDGE_SELL` and `ONE_SELL -> REHEDGE_BUY` use separate
  occurrence datasets.
- `HEDGED_1X1` models unlock occurrence.
- Unlock direction is estimated only as
  `P(unlock cause | unlock occurred)`. It is not an independent second hazard
  multiplied back into occurrence.
- Competing endpoints are retained as a correctness/censoring requirement.
  They are not promoted into a separate modelling workstream when absent from
  the tick-window cohort.
- `following_event_type` is a label and must never enter a predictor allowlist.

## Model ladder and predictor budget

- A_all: descriptive full-range state-age baseline.
- A_common: state-age baseline on common server-hour support.
- B: pre-registered causal price predictors without state age.
- C: the union of A_common and B on exactly the same bins.

The primary price allowlist is limited to 10–12 predictors. It must include:

- side-appropriate H2 boundary touch at 2 seconds;
- side-appropriate H2 boundary touch at 5 seconds;
- absolute mid-price displacement from state start at bin start.

The state-start reference is the last observed mid at or before the state
transition. If that reference is unavailable because of left truncation, the
displacement feature is invalid rather than imputed.

The remaining predictors must be selected and registered before M5-003. The
132-column M4 matrix cannot be imported wholesale.

## Inference

- Effective replication is counted by `interval_id`, not by risk-bin count.
- Headline statistics are paired per-interval log-likelihood increments
  `C - A_common` and `C - B`.
- Bootstrap clusters are `interval_id`.
- Standalone log loss, calibration, event rank, and top-decile capture are
  descriptive diagnostics only.
- A model verdict requires adjacent-window/sensitivity coherence and external
  temporal validation.

## Additional-data gate

The first three contiguous full broker sessions after the current export are
pre-registered as 2026-07-27, 2026-07-28, and 2026-07-29. Each requires XAUUSD
ticks and an MT5 report covering its lifecycle events.

No validation date may be substituted after viewing model results. A
substitution caused by unavailable/corrupt source data requires a dated
manifest amendment made before the replacement result is inspected.

M5-002 may run as a pilot if these files are unavailable, but M5 cannot close.

## M5-000 gate

- Roadmap and milestone numbering agree.
- Timezone status is recorded without overstating certainty.
- Legacy and canonical risk-time totals reconcile explicitly.
- Cross-midnight, left-truncation, zero-duration, and market-break behavior has
  regression coverage.
- Audit output is deterministic and privacy-safe.
- No model is fit.
