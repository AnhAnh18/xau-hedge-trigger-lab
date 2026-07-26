# M5-003 causal price-increment implementation

Status: `pipeline_frozen_external_pending_zero_validated_price_results`

This is a frozen engineering result, not a validated trading edge.
Development and 2026-07-24 are diagnostic only; the registered
2026-07-27..29 external sessions are still unavailable.

## Contract and correction

- M5-002 inputs and A_common hashes matched the preregistration.
- A_dev uses the exact 11-bucket M5-002 grid, including `[5,6)`,
  `[6,8)`, and `[8,10)`; seven buckets remain after the unlock floor.
- `C_dev` has no free intercept; the headline is `C_dev - A_dev`.
- Independent Claude re-review is required before merge.

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

## Internal reuse diagnostics — no verdict

- `rehedge_buy_occurrence`: C_dev−A_dev mean 0.101650 (95% CI 0.047208, 0.157467); C_dev−B mean 0.040581. Diagnostic only.
- `rehedge_sell_occurrence`: C_dev−A_dev mean 0.067622 (95% CI 0.010000, 0.125649); C_dev−B mean 0.262040. Diagnostic only.
- `unlock_occurrence`: C_dev−A_dev mean 0.154393 (95% CI 0.110721, 0.199265); C_dev−B mean 0.174826. Diagnostic only.

## Session stability

Leave-one-session-out refits A_dev, preprocessing, lambda selection,
B, and C_dev using only the remaining sessions. It is diagnostic and
does not estimate between-session population variance.

| Held session | Endpoint | Bins | Targets | C_dev−A_dev |
| --- | --- | ---: | ---: | ---: |
| 2026-07-20 | rehedge_buy_occurrence | 7,063 | 147 | 0.062151 |
| 2026-07-20 | rehedge_sell_occurrence | 5,580 | 129 | 0.161530 |
| 2026-07-20 | unlock_occurrence | 28,013 | 299 | 0.092107 |
| 2026-07-21 | rehedge_buy_occurrence | 8,066 | 111 | 0.111019 |
| 2026-07-21 | rehedge_sell_occurrence | 7,599 | 130 | 0.032602 |
| 2026-07-21 | unlock_occurrence | 25,154 | 250 | 0.006749 |
| 2026-07-22 | rehedge_buy_occurrence | 9,983 | 140 | 0.091282 |
| 2026-07-22 | rehedge_sell_occurrence | 5,528 | 125 | 0.090186 |
| 2026-07-22 | unlock_occurrence | 25,894 | 273 | 0.019866 |
| 2026-07-23 | rehedge_buy_occurrence | 6,764 | 300 | 0.191054 |
| 2026-07-23 | rehedge_sell_occurrence | 7,265 | 302 | 0.108028 |
| 2026-07-23 | unlock_occurrence | 23,173 | 622 | 0.171791 |

## Validation gates

- `canonical_M2_through_M5_002_files_unchanged`: PASS
- `all_joint_valid_model_rows_have_finite_allowlisted_features`: PASS
- `predictor_allowlists_exclude_identifiers_labels_and_timestamps`: PASS
- `A_common_A_level_A_dev_B_C_dev_use_identical_rows`: PASS
- `development_contains_only_registered_sessions`: PASS
- `internal_reuse_not_in_development_fit_hash`: PASS
- `all_C_dev_models_have_no_free_intercept`: PASS
- `all_A_dev_models_use_eleven_buckets`: PASS
- `full_allowlist_internal_audit_reconciles_937_bins_3_targets`: PASS
- `external_sessions_absent_and_not_substituted`: PASS

## Remaining gates

- `independent_re_review_pending`: blocking merge until Claude review.
- `external_2026_07_27_29_pending`: M5 remains open.
- No supported/rejected price verdict is issued from development or
  internal reuse data.
- No P/L optimization or tradeable-edge claim was made.
