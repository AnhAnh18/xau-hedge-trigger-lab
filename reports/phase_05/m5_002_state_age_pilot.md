# M5-002 State-Age Hazard Pilot

- Status: `pilot_complete_external_pending`
- Internal fitted-parameter hash: `4a84542d6cfb25ac91c9702100f2294585c82e28c37928c0aef2a67b40558d89`
- Deterministic report SHA-256: `03f41d7e3838960a23aca5eb001add0f74a1eb285396f97b8228fdbf446781fb`
- External gate satisfied: **no**
- Price predictors/P&L optimization/tradeable-edge claim: **none**

## Contract and data isolation

- Internal 2026-07-23..24 and supplemental 2026-07-20..22 use separate support cohorts.
- The canonical M2-M4 `ticks.parquet` was not rebuilt or extended.
- Bins use complete wall-clock grid cells; state age uses the paused tradeable clock at bin start.
- Supplemental rows do not enter fitting; parameter hashes are equal with and without supplemental input.

## Support reconciliation

| Cohort | Width | Eligible seconds | Representable seconds | Dropped partial seconds | Delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| internal_2026_07_23_24 | 1000 ms | 125,503.257 | 125,501.000 | 2.257 | 0.000000 |
| supplemental_2026_07_20_22 | 1000 ms | 247,978.582 | 247,975.000 | 3.582 | 0.000000 |
| internal_2026_07_23_24 | 500 ms | 125,503.257 | 125,502.500 | 0.757 | 0.000000 |
| supplemental_2026_07_20_22 | 500 ms | 247,978.582 | 247,977.500 | 1.082 | 0.000000 |

## Development-only age buckets (1-second primary)

Zero-event buckets have observed exposure and therefore are not called prior-only. Jeffreys smoothing remains finite; raw event and exposure counts are shown.

| Endpoint | Bucket | Exposure bins | Events | Jeffreys p | Zero dev events |
| --- | --- | ---: | ---: | ---: | --- |
| rehedge_buy_occurrence | age_0_1 | 300 | 21 | 0.07142857 | false |
| rehedge_buy_occurrence | age_1_2 | 279 | 35 | 0.12678571 | false |
| rehedge_buy_occurrence | age_2_3 | 244 | 23 | 0.09591837 | false |
| rehedge_buy_occurrence | age_3_5 | 412 | 50 | 0.12227603 | false |
| rehedge_buy_occurrence | age_5_6 | 171 | 15 | 0.09011628 | false |
| rehedge_buy_occurrence | age_6_8 | 300 | 26 | 0.08803987 | false |
| rehedge_buy_occurrence | age_8_10 | 258 | 11 | 0.04440154 | false |
| rehedge_buy_occurrence | age_10_20 | 898 | 49 | 0.05506118 | false |
| rehedge_buy_occurrence | age_20_30 | 542 | 28 | 0.05248619 | false |
| rehedge_buy_occurrence | age_30_60 | 935 | 22 | 0.02403846 | false |
| rehedge_buy_occurrence | age_60_inf | 2,440 | 20 | 0.00839820 | false |
| rehedge_sell_occurrence | age_0_1 | 302 | 28 | 0.09405941 | false |
| rehedge_sell_occurrence | age_1_2 | 274 | 21 | 0.07818182 | false |
| rehedge_sell_occurrence | age_2_3 | 253 | 18 | 0.07283465 | false |
| rehedge_sell_occurrence | age_3_5 | 448 | 39 | 0.08797327 | false |
| rehedge_sell_occurrence | age_5_6 | 196 | 15 | 0.07868020 | false |
| rehedge_sell_occurrence | age_6_8 | 347 | 23 | 0.06752874 | false |
| rehedge_sell_occurrence | age_8_10 | 307 | 23 | 0.07629870 | false |
| rehedge_sell_occurrence | age_10_20 | 976 | 67 | 0.06908905 | false |
| rehedge_sell_occurrence | age_20_30 | 574 | 18 | 0.03217391 | false |
| rehedge_sell_occurrence | age_30_60 | 1,196 | 20 | 0.01712615 | false |
| rehedge_sell_occurrence | age_60_inf | 2,402 | 30 | 0.01269247 | false |
| unlock_occurrence | age_0_1 | 623 | 0 | 0.00080128 | true |
| unlock_occurrence | age_1_2 | 623 | 0 | 0.00080128 | true |
| unlock_occurrence | age_2_3 | 623 | 0 | 0.00080128 | true |
| unlock_occurrence | age_3_5 | 1,246 | 0 | 0.00040096 | true |
| unlock_occurrence | age_5_6 | 623 | 143 | 0.22996795 | false |
| unlock_occurrence | age_6_8 | 877 | 113 | 0.12927107 | false |
| unlock_occurrence | age_8_10 | 708 | 48 | 0.06840621 | false |
| unlock_occurrence | age_10_20 | 2,639 | 105 | 0.03996212 | false |
| unlock_occurrence | age_20_30 | 1,910 | 42 | 0.02223967 | false |
| unlock_occurrence | age_30_60 | 3,973 | 63 | 0.01597886 | false |
| unlock_occurrence | age_60_inf | 12,514 | 109 | 0.00874950 | false |

## Frozen holdout timing inference

### 1000 ms bins

- `rehedge_buy_occurrence`: conditional-vs-uniform mean -0.392998 (95% CI -0.471518, -0.315270; 133 intervals); secondary occurrence LL mean 0.447988 (95% CI 0.035086, 0.982834).
- `rehedge_sell_occurrence`: conditional-vs-uniform mean -0.251292 (95% CI -0.311112, -0.197270; 155 intervals); secondary occurrence LL mean 0.775089 (95% CI 0.389391, 1.251455).
- `unlock_occurrence`: conditional-vs-uniform mean -0.032687 (95% CI -0.136489, 0.070205; 297 intervals); secondary occurrence LL mean 1.278197 (95% CI 0.925843, 1.717464).
### 500 ms bins

- `rehedge_buy_occurrence`: conditional-vs-uniform mean -0.380200 (95% CI -0.458832, -0.303578; 133 intervals); secondary occurrence LL mean 0.443227 (95% CI 0.041013, 0.953890).
- `rehedge_sell_occurrence`: conditional-vs-uniform mean -0.244546 (95% CI -0.301054, -0.192273; 155 intervals); secondary occurrence LL mean 0.762190 (95% CI 0.374648, 1.230396).
- `unlock_occurrence`: conditional-vs-uniform mean 0.001764 (95% CI -0.100377, 0.102775; 297 intervals); secondary occurrence LL mean 1.267057 (95% CI 0.908458, 1.695941).

## Smoothing sensitivity

| Width | Alpha | Endpoint | Conditional mean |
| ---: | ---: | --- | ---: |
| 1000 ms | 0.0 | rehedge_buy_occurrence | -0.395005 |
| 1000 ms | 0.0 | rehedge_sell_occurrence | -0.251248 |
| 1000 ms | 0.0 | unlock_occurrence | -0.029564 |
| 1000 ms | 0.5 | rehedge_buy_occurrence | -0.392998 |
| 1000 ms | 0.5 | rehedge_sell_occurrence | -0.251292 |
| 1000 ms | 0.5 | unlock_occurrence | -0.032687 |
| 1000 ms | 1.0 | rehedge_buy_occurrence | -0.391112 |
| 1000 ms | 1.0 | rehedge_sell_occurrence | -0.251365 |
| 1000 ms | 1.0 | unlock_occurrence | -0.035762 |
| 500 ms | 0.0 | rehedge_buy_occurrence | -0.381951 |
| 500 ms | 0.0 | rehedge_sell_occurrence | -0.244311 |
| 500 ms | 0.0 | unlock_occurrence | 0.005524 |
| 500 ms | 0.5 | rehedge_buy_occurrence | -0.380200 |
| 500 ms | 0.5 | rehedge_sell_occurrence | -0.244546 |
| 500 ms | 0.5 | unlock_occurrence | 0.001764 |
| 500 ms | 1.0 | rehedge_buy_occurrence | -0.378569 |
| 500 ms | 1.0 | rehedge_sell_occurrence | -0.244810 |
| 500 ms | 1.0 | unlock_occurrence | -0.001936 |

## F-007 timer-floor verification

The M2 month-wide data contain one sub-six-second unlock, so the pattern is reported as an approximate dwell floor rather than an absolute structural zero.

| Endpoint | Events | Under 6s | Percent |
| --- | ---: | ---: | ---: |
| unlock_occurrence | 6,276 | 1 | 0.016% |
| rehedge_sell_occurrence | 3,253 | 1,059 | 32.555% |
| rehedge_buy_occurrence | 3,024 | 932 | 30.820% |

## Supplemental named deliverable: per-session base hazard

These are descriptive common-hour weekday/session rates. Supplemental days do not fit, validate, or promote the internal pilot. One session per weekday cannot identify a weekday effect.

| Date | Weekday | Endpoint | Risk seconds | Events | Events/1000s | Role |
| --- | --- | --- | ---: | ---: | ---: | --- |
| 2026-07-20 | Monday | rehedge_buy_occurrence | 7,359 | 147 | 19.975540 | retrospective_supplemental_non_gating |
| 2026-07-20 | Monday | rehedge_sell_occurrence | 5,938 | 130 | 21.892893 | retrospective_supplemental_non_gating |
| 2026-07-20 | Monday | unlock_occurrence | 29,782 | 300 | 10.073199 | retrospective_supplemental_non_gating |
| 2026-07-21 | Tuesday | rehedge_buy_occurrence | 8,524 | 111 | 13.022055 | retrospective_supplemental_non_gating |
| 2026-07-21 | Tuesday | rehedge_sell_occurrence | 7,621 | 130 | 17.058129 | retrospective_supplemental_non_gating |
| 2026-07-21 | Tuesday | unlock_occurrence | 26,934 | 252 | 9.356204 | retrospective_supplemental_non_gating |
| 2026-07-22 | Wednesday | rehedge_buy_occurrence | 10,095 | 141 | 13.967311 | retrospective_supplemental_non_gating |
| 2026-07-22 | Wednesday | rehedge_sell_occurrence | 5,536 | 125 | 22.579480 | retrospective_supplemental_non_gating |
| 2026-07-22 | Wednesday | unlock_occurrence | 27,448 | 273 | 9.946080 | retrospective_supplemental_non_gating |
| 2026-07-23 | Thursday | rehedge_buy_occurrence | 9,251 | 300 | 32.428927 | internal |
| 2026-07-23 | Thursday | rehedge_sell_occurrence | 7,275 | 302 | 41.512027 | internal |
| 2026-07-23 | Thursday | unlock_occurrence | 26,359 | 623 | 23.635191 | internal |
| 2026-07-24 | Friday | rehedge_buy_occurrence | 5,169 | 133 | 25.730315 | internal |
| 2026-07-24 | Friday | rehedge_sell_occurrence | 6,568 | 155 | 23.599269 | internal |
| 2026-07-24 | Friday | unlock_occurrence | 31,280 | 297 | 9.494885 | internal |

## Pilot interpretation

- `rehedge_buy_occurrence`: `internal_timing_rejected_external_pending`.
- `rehedge_sell_occurrence`: `internal_timing_rejected_external_pending`.
- `unlock_occurrence`: `inconclusive_external_pending`.

Conditional timing is primary for M5-002. Cause-specific occurrence likelihood is secondary and answers a different, base-rate-sensitive question. Neither result closes M5.

## Explicit deferrals

- M4 matched-timestamp anchor offset: deferred until price-feature work.
- Unlock direction P(cause | occurrence): deferred.
- External temporal validation: pending 2026-07-27..29 acquisition.

## Validation gates

- `support_seconds_reconcile`: PASS
- `no_nonpositive_bins`: PASS
- `no_gap_crossing_bins`: PASS
- `no_cross_split_primary_bins`: PASS
- `target_only_at_last_representable_bin`: PASS
- `competing_bins_are_zero_label`: PASS
- `canonical_ticks_unchanged`: PASS
- `supplemental_fit_isolation`: PASS
- `predictor_allowlist_has_no_forbidden_fields`: PASS
- `design_matrix_matches_allowlist`: PASS
