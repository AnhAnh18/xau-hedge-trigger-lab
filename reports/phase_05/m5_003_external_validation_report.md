# M5-003 External Validation

Status: `external_evaluation_complete_with_qualitative_exposure_disclosed`

This is a prospective frozen-model evaluation with disclosed
qualitative exposure. It is not analyst-blinded and makes no
standalone tradeable-edge claim.

## Acquisition

- Status: `PASS_WITH_REPLICATED_SOURCE_QUOTE_GAP`
- Registered sessions: 2026-07-27, 2026-07-28, 2026-07-29
- Replicated source quote gap: 2026-07-27 18:08:35.303 to 18:10:21.660
- Gap interpolation: forbidden

## One-second event accounting

| Endpoint | Lifecycle events | Representable targets | Common/floor targets | Joint-valid targets |
| --- | ---: | ---: | ---: | ---: |
| rehedge_buy_occurrence | 868 | 812 | 622 | 620 |
| rehedge_sell_occurrence | 837 | 785 | 581 | 574 |
| unlock_occurrence | 1,705 | 1,702 | 1,289 | 1,282 |

## One-second headline

| Endpoint | Bins | Targets | Mean C_session-A_session | CI95 | Family low | Positive sessions | Verdict |
| --- | ---: | ---: | ---: | --- | ---: | ---: | --- |
| rehedge_buy_occurrence | 22,163 | 620 | +0.231269 | [+0.199141, +0.265559] | +0.195982 | 3/3 | **supported** |
| rehedge_sell_occurrence | 19,389 | 574 | +0.166665 | [+0.134550, +0.198017] | +0.131774 | 2/3 | **supported** |
| unlock_occurrence | 79,578 | 1,282 | +0.221639 | [+0.194634, +0.248726] | +0.191840 | 2/3 | **supported** |

## Per-session headline means

### rehedge_buy_occurrence

| Session | Intervals | Mean |
| --- | ---: | ---: |
| 2026-07-27 | 224 | +0.082535 |
| 2026-07-28 | 67 | +0.040161 |
| 2026-07-29 | 334 | +0.369355 |

### rehedge_sell_occurrence

| Session | Intervals | Mean |
| --- | ---: | ---: |
| 2026-07-27 | 213 | +0.080872 |
| 2026-07-28 | 93 | -0.019134 |
| 2026-07-29 | 275 | +0.295949 |

### unlock_occurrence

| Session | Intervals | Mean |
| --- | ---: | ---: |
| 2026-07-27 | 437 | +0.049742 |
| 2026-07-28 | 166 | -0.078614 |
| 2026-07-29 | 683 | +0.404598 |

## Interpretation limits

- The 500 ms results are causal-anchor sensitivity only.
- `C_shape` and ablations are descriptive and non-causal.
- Likelihood increments are not scale-free across endpoints or sessions.
- Events inside excluded quote gaps remain in lifecycle accounting but
  cannot receive forced tick features.
- Re-hedge results are positive against A_session but negative against
  price-only B; the combined architecture remains ambiguous.
- Session 2026-07-29 contributes most of the pooled gain, while
  2026-07-28 is negative for two endpoints.
- M5-003 is externally evaluated; M5 remains open for M5-004.
- Independent re-review is required before merge.

## Validation gates

- `frozen_manifest_hash_reconciles`: PASS
- `canonical_M2_through_M5_003_files_unchanged`: PASS
- `amendment_precedes_external_features_and_predictions`: PASS
- `exact_registered_sessions_present`: PASS
- `external_rows_never_entered_fit`: PASS
- `all_predictions_match_joint_valid_design_rows`: PASS
- `replicated_quote_gap_excluded_without_interpolation`: PASS
- `report_financial_reconciliation`: PASS
- `position_inventory_conservation`: PASS
- `predictor_allowlist_unchanged`: PASS
- `tradeable_edge_claim_absent`: PASS
- `event_stage_accounting_is_monotonic`: PASS
