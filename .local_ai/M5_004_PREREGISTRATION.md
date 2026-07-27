# M5-004 Unlock-Cause Preregistration

Status: Registered on 2026-07-27 before any M5-004 feature build or model fit.
This document is stacked on independently reviewed Draft PR #8 and remains
implementation-blocked until this preregistration receives separate approval.

Machine-readable contract: `data/m5_004_preregistration.json`.

## Question and estimand

M5-004 asks a single conditional question:

```text
P(UNLOCK_TO_BUY | an eligible unlock occurred)
```

`UNLOCK_TO_BUY` is encoded as one and `UNLOCK_TO_SELL` as zero. The unit is an
observed unlock event, represented by the terminal target bin of an eligible
`unlock_occurrence` interval. Non-event risk bins, right-censored intervals,
competing endpoints, re-hedges, and additional-position events are not
negative cause examples.

This is a cause split conditional on occurrence. It is not a fourth occurrence
hazard, does not estimate when an unlock occurs, and cannot be multiplied by an
occurrence model to make a trading rule in M5-004.

## Upstream dependency and immutability

The preregistration is tied to the current M5-003 Draft PR #8 head
`7434505e9e6fcff7d8c427a51943ea6b571c3328` and these deterministic hashes:

| Input | SHA-256 |
| --- | --- |
| M5-003 preregistration | `4da95ca8b787e201a77f03fcfe1bf40145752bb967d4d847325349c528f50616` |
| M5-003 report | `9b6cc69feea7fd031c039a7af7f6cf8900c6fcc21cd952f6eb1a4ea5d6824eb1` |
| M5-003 frozen manifest | `da2f9e0c66bdf8e51a349bc77db67fc3bbd1f8dc100d359890ac7ee54b14e747` |
| M5-003 feature-audit dataframe | `44183dbf388a9dc86344d3beaea480f0db3242488c66afa937ddef0475ce78b4` |
| M5-003 joint-valid dataframe | `69deadc6a6d2ed45ff12c15ef7659a73cf09ace74d27b496938dd057569800f2` |
| M5-002 risk-bin dataframe | `62f0f0fa4f961b699461c2c3ba935c460d853b4553142130187c503fb4698520` |

M2 through M5-003 outputs are immutable. If review of PR #8 changes any locked
hash, this contract must receive a dated pre-fit amendment and fresh review.
No M5-004 fit may be inspected before that amendment. Text hashes use
canonical UTF-8/LF; binary and dataframe hashes keep their existing contracts.

### Dated upstream-hash amendment — 2026-07-27

PR #8 added the review-driven `A_session`/`C_session` occurrence baseline and
then applied the accepted independent-review follow-ups: an external
two-of-three session-consistency gate and stricter interpretation limits. No
M5-003 model was refit, no M5-004 feature was built, and no cause model was fit
before this amendment. The M5-003 feature-audit and joint-valid dataframe
hashes stayed unchanged, so the M5-004 event support and conditional cause
estimand are unchanged. The M5-004 model design therefore remains locked as
written; only its upstream provenance hashes advance.

## Event construction and accounting

Start from M5-003 candidate rows and select exactly one row per unlock event:

- `endpoint == unlock_occurrence`;
- `target_label == 1`;
- `following_event_type` is exactly `UNLOCK_TO_BUY` or `UNLOCK_TO_SELL`;
- the terminal bin and all 12 M5-004 predictors are jointly valid;
- tradeable state age at bin start is at least five seconds;
- the row belongs to the registered common-hour cohort and is not a
  cross-split interval.

The audit must reconcile all target unlock events into included and excluded
rows by first exclusion reason. Duplicate `(cohort_id, interval_id,
bin_width_ms)` event rows are fatal. Any other target cause is fatal rather
than silently dropped.

Known pre-fit audit expectations from already-inspected internal labels are:

| Width | Role | Buy | Sell | Total |
| ---: | --- | ---: | ---: | ---: |
| 1,000 ms | development 2026-07-20..23 | 714 | 730 | 1,444 |
| 1,000 ms | internal reuse 2026-07-24 | 160 | 135 | 295 |
| 500 ms | development 2026-07-20..23 | 715 | 730 | 1,445 |
| 500 ms | internal reuse 2026-07-24 | 160 | 137 | 297 |

These counts verify construction only. They cannot select features, tune a
model, or create a verdict.

## Causal anchors and windows

The primary anchor is the one-second terminal bin start, equal to
`reported_time - 1 second`. All predictors use ticks at or before that anchor.
The 500-millisecond analysis moves the anchor to `reported_time - 500 ms` and
is timing sensitivity, not independent replication or simple discretization.

The report time has one-second resolution, so the primary anchor may be about
one to two seconds before the true action. Sub-second trigger behavior is not
identified. M4 `matched_timestamp` results are prior exploratory evidence and
must not replace either registered anchor.

Lookbacks are half-open at their left boundary and include the last tick at or
before the anchor. A window crossing an excluded coverage gap is invalid.
Prior-boundary features use `[t-2w, t-w)` for the boundary and `[t-w, t)` for
strictly pre-anchor touches. Current/event/post-action ticks never enter a
predictor.

## Predictor allowlist

All price calculations use mid. Bid/Ask and spread remain audit diagnostics.
The primary model has exactly these 12 directional predictors:

| Feature | Definition at anchor `t` |
| --- | --- |
| `mid_change_2s` | last mid at/before `t` minus first mid in `[t-2s,t]` |
| `mid_change_5s` | last mid at/before `t` minus first mid in `[t-5s,t]` |
| `tick_imbalance_2s` | `(upticks-downticks)/(tick transitions)` on 2 s |
| `tick_imbalance_5s` | `(upticks-downticks)/(tick transitions)` on 5 s |
| `range_position_2s` | `(mid_t-low)/(high-low)` on 2 s; 0.5 if flat |
| `range_position_5s` | same on 5 s |
| `range_position_10s` | same on 10 s |
| `prior_upper_boundary_touch_2s` | prior 2 s upper boundary touched before `t` |
| `prior_lower_boundary_touch_2s` | prior 2 s lower boundary touched before `t` |
| `prior_upper_boundary_touch_5s` | prior 5 s upper boundary touched before `t` |
| `prior_lower_boundary_touch_5s` | prior 5 s lower boundary touched before `t` |
| `state_start_displacement` | `mid_t` minus last observed mid at/before state start |

Positive values are always upward price movement; no label-dependent sign
normalization is allowed. P/L, side-survival labels, entry lineage, volume,
ticket IDs, timestamps, event/cause labels, M4 controls, and post-action data
are forbidden predictors. Spread and the M4 price-unit effect relative to
spread are reported only as limitations.

## Joint validity and outputs

One joint-valid event cohort is used for all A/B/C comparisons. A sample is
excluded if any allowlisted feature is invalid. No model-specific complete
case subsets and no imputation are allowed.

Local outputs, if implementation is separately authorized, are split into:

- `m5_004_unlock_cause_audit.parquet`: IDs, anchors, cause label, validity,
  first exclusion reason, and diagnostics;
- `m5_004_unlock_cause_predictors.parquet`: generated sample key plus exactly
  the 12 predictors;
- `m5_004_unlock_cause_targets.parquet`: generated sample key and binary
  target;
- `m5_004_unlock_cause_predictions.parquet`: local prediction audit.

The generated sample key is never in the predictor allowlist. Committed
outputs are aggregate Markdown/JSON and deterministic hashes only.

## Cohort roles

- Development: common hours on 2026-07-20, 21, 22, and 23. These labels are
  already known and may fit models but cannot validate them.
- Internal reuse: common hours on 2026-07-24. It is excluded from every fit,
  transform, selection, and calibration step and produces diagnostics only.
- External: the pre-registered 2026-07-27, 28, and 29 sessions. They remain
  untouched until the M5-004 manifest is frozen and are the only verdict gate.

The retrospective cohort and M4 H3 result can never validate M5-004. No
external file may be loaded before the full-development parameters and hashes
are frozen.

## Models and preprocessing

All models are unweighted binary Bernoulli models on identical event rows:

- `A_const_cause`: Jeffreys-smoothed development class prior.
- `A_age_cause`: exact floor-eligible M5-002 age buckets `[5,6)`, `[6,8)`,
  `[8,10)`, `[10,20)`, `[20,30)`, `[30,60)`, and `[60,+inf)`, with
  Jeffreys `alpha=0.5` for `P(UNLOCK_TO_BUY | unlock, age bucket)`.
- `B_price_cause`: unpenalized intercept plus exactly the 12 price features.
- `C_age_price_cause`: fixed `logit(A_age_cause)` unit-coefficient offset plus
  the 12 price features; it has no free intercept.

An active evaluation age bucket with zero training events is a hard stop. No
adaptive merge, frozen-prior fallback, or holdout-informed repair is allowed.

Continuous predictors are standardized with development-training means and
population standard deviations. Binary touch indicators are left as 0/1.
Zero-variance continuous columns receive scale one. Every CV fold refits age
probabilities and preprocessing on training intervals only.

## Selection and diagnostics

`B_price_cause` and `C_age_price_cause` use L2 regularization on price
coefficients only, with fixed grid:

```text
0.0001, 0.001, 0.01, 0.1, 1, 10
```

Selection uses deterministic five-fold GroupKFold on
`cohort_id:interval_id`, mean validation log likelihood per event, and the
one-standard-error rule choosing the strongest eligible penalty. The two
models select penalties independently. No class weighting, oversampling,
threshold tuning, feature selection, or black-box boosting is allowed.

A four-session leave-one-session-out development diagnostic refits every
training-derived quantity. It cannot select the final model or create a
verdict. AUC, Brier score, calibration, accuracy, and confusion matrices are
descriptive only; the classification threshold is fixed at 0.5 and is not a
trading threshold.

## Inference, ablations, and decision rule

The one registered headline is the external one-second paired event-level log
likelihood increment:

```text
C_age_price_cause - A_age_cause
```

The secondary comparison is `C_age_price_cause - B_price_cause`. Report the
mean paired increment and a deterministic 5,000-draw bootstrap over source
intervals (`seed=5004`), plus separate results for each external session. The
bootstrap is conditional on observed sessions and does not estimate the
between-session population distribution.

Required full-model ablations reuse the selected full-model penalty:

- `momentum`: both mid changes and both tick imbalances;
- `range_location`: all three range-position features;
- `boundary_side`: all four upper/lower boundary touches;
- `state_path`: state-start displacement.

The four ablations form a Bonferroni family at `alpha/4`. The 500 ms headline
sensitivity is secondary and belongs to a separate one-comparison family. No
coefficient sign is a standalone confirmatory test after joint fitting.

External price information is `supported` only when the one-second headline
mean is positive, its one-sided 95% bootstrap lower bound is above zero, and
at least two of the three external session point estimates are positive. A
positive pooled mean without both gates is `weak/inconclusive`. A pooled
ordinary 95% interval with upper bound at or below zero is `rejected for this
design`. A pooled positive bound with fewer than two positive sessions is
`mixed/inconclusive` rather than supported.

Development, LOSO, M4, and 2026-07-24 results receive no verdict. A supported
cause classifier would still not prove an occurrence trigger, profitability,
execution feasibility, or a tradeable edge.

## Implementation gate

M5-004 implementation is not authorized by this preregistration branch. A
separate authorization may be given only after PR #8 and this contract are
reviewed. Implementation may merge with supported, null, mixed,
inconclusive, or rejected external findings if:

- upstream hashes and one-row-per-unlock accounting reconcile;
- A/B/C use identical joint-valid event rows;
- cause labels and all metadata are absent from the predictor allowlist;
- development-only preprocessing, GroupKFold, and parameter freezing are
  proven by tests;
- internal reuse and external data are absent from fitting and selection;
- required ablations, per-session results, and multiplicity are published;
- determinism, CI, and privacy gates pass;
- no occurrence, P/L, or tradeable-edge claim is made.
