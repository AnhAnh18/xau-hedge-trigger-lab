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
- Consecutive-tick gaps strictly greater than 60 seconds are excluded coverage
  gaps.
- The full open interval between the two observed ticks is excluded with
  `exclusion_reason=unknown_coverage_gap` until recurrence across sessions
  supports a scheduled-market-closure classification.
- A gap may become `scheduled_market_closed` only after the same server-clock
  pattern recurs across multiple registered sessions. D-007 alone is not
  sufficient evidence.
- State age uses a tradeable clock: elapsed wall time minus excluded-gap
  overlap.
- Gaps of 60 seconds or less remain ordinary risk time.
- Zero-duration M2 intervals remain in accounting but cannot create risk bins.
- Because M2 intervals are event-to-event, M5 appends an explicitly synthetic
  right-censored interval from the final event's `state_after` to merged tick
  coverage end. It has no terminal event or competing endpoint.
- Left truncation is defined against merged tick coverage, not each tick file.
  A left-truncated interval remains in audit accounting but is excluded from
  primary inference; its state age is neither reset to zero nor assumed fully
  tradeable before coverage.
- Source-interval membership, terminal-event count, and tradeable seconds are
  reported separately.

The current shared boundary fixture is interval `13321`: it crosses midnight
and contains the only coverage gap longer than 60 seconds. Interval `12074` is
left-truncated by the beginning of merged tick coverage. The synthetic
right-censored tail is `HEDGED_1X1` from 23:51:39 to 23:56:57.758.

Primary M5 v1 estimates transition timing only for
`HEDGED_1X1`, `ONE_BUY`, and `ONE_SELL` intervals containing at least one
complete causal bin. The 34 zero-duration re-hedge events, including 30 in
common hours, are excluded from that estimand and remain explicitly linked to
issue #3.

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
- The 12:00–24:00 primary window is fixed for M5 v1, including external
  validation. It is not re-derived when new data arrive.
- A full-session analysis on the pre-registered 2026-07-27 through 2026-07-29
  sessions is pre-registered as secondary. It measures transportability beyond
  the London/NY-focused primary estimand and cannot override its verdict.
- Development remains 2026-07-23 and holdout remains 2026-07-24 for the pilot.
  These two dates are not treated as equivalent full sessions.
- After canonical censoring and left-truncation handling, the development /
  holdout common-hour target-density ratio is 2.100x. Common hours align
  coverage support, not base rates.
- In holdout, the 12:00–24:00 target density is 2.145x the 01:00–12:00
  density. M5 v1 conclusions therefore do not generalize to the Asian session.
- Day of week is perfectly confounded with the split: development is Thursday,
  holdout is Friday, and external validation is Monday through Wednesday.

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
- Paired likelihood increments are still mildly sensitive to base-rate shift.
  A within-interval conditional statistic, conditioned on an interval having
  exactly one representable event, is co-primary for the timing comparison
  because the interval intercept cancels algebraically.
- For interval `i`, the conditional event-bin probability is
  `exp(eta_event_bin) / sum(exp(eta_bin))` over its representable bins.
- The occurrence hazard remains primary for occurrence; the conditional
  statistic is not an occurrence model and excludes censored/no-event
  intervals by construction.
- Bootstrap clusters are `interval_id`.
- Standalone log loss, raw calibration, event rank, and top-decile capture are
  descriptive diagnostics only.
- Calibration is first reported without holdout refitting. A post-hoc
  holdout-intercept recalibration may diagnose intercept-only versus slope
  failure, but it must be labelled as using holdout labels and cannot affect a
  verdict, likelihood headline, or merge gate.
- A model verdict requires adjacent-window/sensitivity coherence and external
  temporal validation.

## Additional-data gate

The first three contiguous full broker sessions after the current export are
pre-registered as 2026-07-27, 2026-07-28, and 2026-07-29. Each requires XAUUSD
ticks and an MT5 report covering its lifecycle events.

No validation date may be substituted after viewing model results. A
substitution caused by unavailable/corrupt source data requires a dated
manifest amendment made before the replacement result is inspected.

The requirement is untouched, pre-registered temporal data, not future data
as such. Previously uninspected historical full-tick sessions may be registered
by a dated amendment before their validation/model result is read. They do not
silently replace the locked 2026-07-27 through 2026-07-29 primary external
sessions, and no date may be chosen based on a favorable result.

M5-002 may run as a pilot if these files are unavailable, but M5 cannot close.
Primary external evaluation remains fixed to 12:00–24:00. The full-session
analysis on all three dates is secondary and was registered before acquisition.

## M5-000 gate

- Roadmap and milestone numbering agree.
- Timezone status is recorded without overstating certainty.
- Legacy and canonical risk-time totals reconcile explicitly.
- Cross-midnight, left/right-censoring, zero-duration, unknown coverage-gap,
  eligible-state filtering, and multi-day/weekend behavior has regression
  coverage.
- Audit output is deterministic and privacy-safe.
- No model is fit.

## M5-001 acquisition preparation

- `data/m5_acquisition_plan.json` is the executable source of locked dates,
  session bounds, report requirements, analysis windows, gap policy, and
  privacy rules.
- `scripts/validate_m5_acquisition.py --plan-only` validates registration
  without reading private data.
- `scripts/validate_m5_acquisition.py --dry-run` validates the complete intake
  path with generated anonymized inputs.
- The live validator records SHA-256 checksums and generated aliases, checks
  per-session tick bounds and report event coverage, preserves duplicate
  timestamps, and reports gaps without retuning the threshold.
- M5-002 remains blocked until real registered inputs pass this validator or
  is explicitly run as a labelled non-closing pilot under this specification.
