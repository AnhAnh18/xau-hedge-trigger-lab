# M5-003 causal price-increment implementation

Status: `pipeline_frozen_external_pending_zero_validated_price_results`

This is a frozen engineering result, not a validated trading edge.
Development and 2026-07-24 are diagnostic only. The registered
2026-07-27..29 external sessions remain unseen and pending.

## Review-driven session remediation

- `A_session = A_dev + server-time block effect` on fixed blocks
  `[12,16)`, `[16,20)`, and `[20,24)`.
- All three block effects are explicit one-hot columns with no intercept;
  no reference block is silently fixed at zero.
- `C_session` uses fixed `logit(A_session)` plus the full price allowlist,
  has no free intercept, and reselects lambda using development-only
  interval GroupKFold.
- `C_dev - A_dev` is retained as a superseded audit diagnostic.
- `C_shape` is review-driven, external-secondary, and cannot create an
  independent verdict.
- D-007 server UTC+3 remains an inference; market-session labels are
  approximate and July-DST dependent.
- Independent Claude re-review reproduced the remediation and accepted
  it subject to the bounded follow-ups now applied.

## Feature accounting

- Full allowlist audit: 937 bins / 3 targets removed — PASS.
- July-23 unlock floor: 3,115 bins / 0 targets removed — PASS.

### Joint-valid one-second cohorts

| Role | Date | Endpoint | Bins | Targets | Intervals |
| --- | --- | --- | ---: | ---: | ---: |
| development | 2026-07-20 | rehedge_buy_occurrence | 7,063 | 147 | 147 |
| development | 2026-07-20 | rehedge_sell_occurrence | 5,580 | 129 | 131 |
| development | 2026-07-20 | unlock_occurrence | 28,013 | 299 | 300 |
| development | 2026-07-21 | rehedge_buy_occurrence | 8,066 | 111 | 111 |
| development | 2026-07-21 | rehedge_sell_occurrence | 7,599 | 130 | 130 |
| development | 2026-07-21 | unlock_occurrence | 25,154 | 250 | 253 |
| development | 2026-07-22 | rehedge_buy_occurrence | 9,983 | 140 | 141 |
| development | 2026-07-22 | rehedge_sell_occurrence | 5,528 | 125 | 125 |
| development | 2026-07-22 | unlock_occurrence | 25,894 | 273 | 274 |
| development | 2026-07-23 | rehedge_buy_occurrence | 6,764 | 300 | 300 |
| development | 2026-07-23 | rehedge_sell_occurrence | 7,265 | 302 | 302 |
| development | 2026-07-23 | unlock_occurrence | 23,173 | 622 | 623 |
| internal_reuse | 2026-07-24 | rehedge_buy_occurrence | 5,136 | 133 | 133 |
| internal_reuse | 2026-07-24 | rehedge_sell_occurrence | 6,464 | 155 | 155 |
| internal_reuse | 2026-07-24 | unlock_occurrence | 29,091 | 295 | 298 |

## One-second paired comparisons — diagnostics only

| Role | Endpoint | C_session−A_session | 95% CI | A_session−A_dev | C_shape−A_session | old C_dev−A_dev |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| development | rehedge_buy_occurrence | 0.104905 | [0.079606, 0.130391] | 0.070269 | 0.021225 | 0.129597 |
| development | rehedge_sell_occurrence | 0.083010 | [0.060819, 0.104509] | 0.050658 | 0.011168 | 0.103028 |
| development | unlock_occurrence | 0.063920 | [0.049382, 0.079130] | 0.068207 | 0.036789 | 0.103529 |
| internal_reuse | rehedge_buy_occurrence | 0.081396 | [0.035256, 0.127356] | 0.065349 | 0.009696 | 0.101650 |
| internal_reuse | rehedge_sell_occurrence | 0.039308 | [-0.011776, 0.091948] | 0.132032 | 0.030655 | 0.067622 |
| internal_reuse | unlock_occurrence | 0.080685 | [0.052650, 0.109254] | 0.148346 | 0.036852 | 0.154393 |

### Required secondary comparison

| Role | Endpoint | C_session−B | 95% CI | Familywise one-sided low |
| --- | --- | ---: | --- | ---: |
| development | rehedge_buy_occurrence | 0.082663 | [0.017031, 0.150362] | 0.010096 |
| development | rehedge_sell_occurrence | 0.083623 | [0.020129, 0.150422] | 0.014226 |
| development | unlock_occurrence | 0.083060 | [0.033317, 0.133236] | 0.029203 |
| internal_reuse | rehedge_buy_occurrence | 0.085676 | [-0.052836, 0.234239] | -0.060883 |
| internal_reuse | rehedge_sell_occurrence | 0.365757 | [0.223638, 0.522839] | 0.215452 |
| internal_reuse | unlock_occurrence | 0.249464 | [0.130381, 0.373940] | 0.121783 |

### Registered one-second ablations

Positive values mean the full `C_session` scored above the model
with that group removed. Correlated-group ablations are not additive
or causal decompositions.

| Role | Endpoint | Removed group | Full−ablated | 95% CI | Familywise one-sided low |
| --- | --- | --- | ---: | --- | ---: |
| development | rehedge_buy_occurrence | motion | 0.000489 | [-0.001340, 0.002524] | -0.001998 |
| development | rehedge_buy_occurrence | boundary | 0.003159 | [0.000200, 0.006121] | -0.000686 |
| development | rehedge_buy_occurrence | state_path | 0.058872 | [0.040263, 0.078166] | 0.034101 |
| development | rehedge_buy_occurrence | volatility_liquidity | 0.037954 | [0.022291, 0.054286] | 0.017997 |
| development | rehedge_sell_occurrence | motion | 0.002409 | [-0.000356, 0.005089] | -0.001334 |
| development | rehedge_sell_occurrence | boundary | 0.000864 | [-0.000783, 0.002422] | -0.001375 |
| development | rehedge_sell_occurrence | state_path | 0.046540 | [0.030130, 0.062978] | 0.023488 |
| development | rehedge_sell_occurrence | volatility_liquidity | 0.038911 | [0.023223, 0.054742] | 0.017781 |
| development | unlock_occurrence | magnitude_motion | 0.000467 | [-0.000252, 0.001158] | -0.000501 |
| development | unlock_occurrence | boundary | 0.000733 | [-0.000616, 0.002041] | -0.001155 |
| development | unlock_occurrence | state_path | 0.011311 | [0.006033, 0.016245] | 0.004459 |
| development | unlock_occurrence | volatility_liquidity | 0.018692 | [0.012115, 0.025320] | 0.009842 |
| internal_reuse | rehedge_buy_occurrence | motion | 0.000057 | [-0.003434, 0.003584] | -0.004574 |
| internal_reuse | rehedge_buy_occurrence | boundary | 0.005927 | [-0.001756, 0.013543] | -0.004373 |
| internal_reuse | rehedge_buy_occurrence | state_path | 0.066036 | [0.026654, 0.104667] | 0.013009 |
| internal_reuse | rehedge_buy_occurrence | volatility_liquidity | 0.013698 | [-0.013109, 0.040815] | -0.022136 |
| internal_reuse | rehedge_sell_occurrence | motion | 0.000093 | [-0.006206, 0.006526] | -0.008190 |
| internal_reuse | rehedge_sell_occurrence | boundary | -0.001355 | [-0.004083, 0.001439] | -0.005155 |
| internal_reuse | rehedge_sell_occurrence | state_path | 0.009388 | [-0.028012, 0.047618] | -0.040637 |
| internal_reuse | rehedge_sell_occurrence | volatility_liquidity | 0.006226 | [-0.029714, 0.039858] | -0.041062 |
| internal_reuse | unlock_occurrence | magnitude_motion | 0.001955 | [0.000384, 0.003547] | -0.000106 |
| internal_reuse | unlock_occurrence | boundary | 0.000417 | [-0.002483, 0.003214] | -0.003650 |
| internal_reuse | unlock_occurrence | state_path | 0.011244 | [0.002115, 0.020896] | -0.000885 |
| internal_reuse | unlock_occurrence | volatility_liquidity | 0.036814 | [0.021382, 0.052244] | 0.016423 |

### 500 ms causal-anchor sensitivity

This moves the anchor to `T−500 ms`; it is not an independent
discretization robustness sample and cannot override one second.

| Role | Endpoint | C_session−A_session | 95% CI |
| --- | --- | ---: | --- |
| development | rehedge_buy_occurrence | 0.149527 | [0.113622, 0.184760] |
| development | rehedge_sell_occurrence | 0.094895 | [0.073199, 0.117379] |
| development | unlock_occurrence | 0.064677 | [0.051194, 0.079066] |
| internal_reuse | rehedge_buy_occurrence | 0.076591 | [0.003343, 0.154856] |
| internal_reuse | rehedge_sell_occurrence | 0.078206 | [0.026598, 0.127362] |
| internal_reuse | unlock_occurrence | 0.078593 | [0.053901, 0.105140] |

## Multiplicity registry

| Family | Comparisons | Per-comparison alpha | Gate role |
| --- | ---: | ---: | --- |
| C_session−A_session at 1 s | 3 | 0.0166667 | external headline |
| C_session−B at 1 s | 3 | 0.0166667 | required secondary |
| C_session leave-one-group-out | 12 | 0.0041667 | required ablation |
| C_session−A_session at 500 ms | 3 | 0.0166667 | non-gating sensitivity |
| C_shape−A_session | 3 | n/a | descriptive, no verdict |

## Fixed base-rate shift stress

The preregistered `-log(2.1)` development-label stress is
non-gating and does not recalibrate internal or external labels.
Its observed direction and magnitude are reported rather than
replaced by the earlier approximate 7% expectation.
Likelihood increments are not scale-free and must not be compared
across endpoints or sessions; their sign is interpreted only for
the observed evaluation distribution.

| Endpoint | Original increment | Shifted increment | Relative change |
| --- | ---: | ---: | ---: |
| rehedge_buy_occurrence | 0.104905 | 0.160098 | 52.612% |
| rehedge_sell_occurrence | 0.083010 | 0.127087 | 53.098% |
| unlock_occurrence | 0.063920 | 0.121808 | 90.564% |

## Leave-one-development-session-out

Every fold refits `A_dev`, all three `A_session` effects,
preprocessing, nested lambda selection, and all price models.
The spread is diagnostic and does not estimate a session-population
variance from only four development sessions.

| Held session | Endpoint | Bins | Targets | A_session−A_dev | C_session−A_session | C_shape−A_session |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2026-07-20 | rehedge_buy_occurrence | 7,063 | 147 | -0.010342 | 0.083854 | 0.001052 |
| 2026-07-20 | rehedge_sell_occurrence | 5,580 | 129 | 0.039827 | 0.060223 | 0.013180 |
| 2026-07-20 | unlock_occurrence | 28,013 | 299 | 0.010235 | 0.085129 | 0.049268 |
| 2026-07-21 | rehedge_buy_occurrence | 8,066 | 111 | 0.070940 | 0.075949 | 0.001460 |
| 2026-07-21 | rehedge_sell_occurrence | 7,599 | 130 | 0.119244 | 0.029152 | -0.003244 |
| 2026-07-21 | unlock_occurrence | 25,154 | 250 | 0.033814 | -0.017142 | -0.001525 |
| 2026-07-22 | rehedge_buy_occurrence | 9,983 | 140 | 0.113417 | 0.082446 | -0.003532 |
| 2026-07-22 | rehedge_sell_occurrence | 5,528 | 125 | 0.008177 | 0.081968 | 0.021045 |
| 2026-07-22 | unlock_occurrence | 25,894 | 273 | 0.048084 | 0.000988 | 0.001127 |
| 2026-07-23 | rehedge_buy_occurrence | 6,764 | 300 | 0.101415 | 0.140130 | 0.045024 |
| 2026-07-23 | rehedge_sell_occurrence | 7,265 | 302 | 0.054584 | 0.079328 | -0.010312 |
| 2026-07-23 | unlock_occurrence | 23,173 | 622 | 0.111689 | 0.136645 | 0.050464 |

## Interpretation boundary

On the single 2026-07-24 internal-reuse session, the session-block
increment exceeded the residual full-price increment for two of three
endpoints. Rehedge-sell had the smallest residual price increment and
its ordinary 95% interval crossed zero. These are internal diagnostics,
not endpoint verdicts or causal decompositions. Time-of-day may proxy
market regime, operating schedule, or execution behavior.
Across both internal roles, motion and boundary groups have little
unique incremental value conditional on correlated features, while
state-path and volatility/liquidity ablations are larger. This does
not prove a causal source or establish that price-shape information
is absent; external validation remains required.

## External decision rule

An endpoint is supported only if the pooled mean is positive, its
Bonferroni familywise one-sided lower bound is above zero, and at least two of the three registered external-session means are positive.
A positive pooled bound with fewer than two positive sessions is
`mixed/inconclusive`. All three external sessions must be present.

## Validation and remaining gates

- `canonical_M2_through_M5_002_files_unchanged`: PASS
- `all_joint_valid_model_rows_have_finite_allowlisted_features`: PASS
- `predictor_allowlists_exclude_identifiers_labels_and_timestamps`: PASS
- `all_baselines_and_price_models_use_identical_rows`: PASS
- `development_contains_only_registered_sessions`: PASS
- `internal_reuse_not_in_development_fit_hash`: PASS
- `all_C_dev_models_have_no_free_intercept`: PASS
- `all_C_session_and_C_shape_models_have_no_free_intercept`: PASS
- `all_A_session_models_use_three_explicit_blocks`: PASS
- `all_A_dev_models_use_eleven_buckets`: PASS
- `full_allowlist_internal_audit_reconciles_937_bins_3_targets`: PASS
- `external_sessions_absent_and_not_substituted`: PASS
- `independent_re_review_accepted_followups_applied`: PASS.
- `external_2026_07_27_29_pending`: M5 remains open.
- No supported/rejected result is issued from development or internal reuse.
- No P/L optimization or tradeable-edge claim was made.
