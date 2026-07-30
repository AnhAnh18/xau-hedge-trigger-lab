# M5-004 Unlock-Cause Development Package

Status: `development_package_frozen_future_external_pending`

## Scope

This package estimates `P(UNLOCK_TO_BUY | an eligible unlock occurred)`.
It is not an occurrence model, P/L model, execution rule, or tradeable-edge claim.
The August primary external block has not been loaded.

## Frozen development package

- Predictor allowlist: 12 raw-directional features.
- Bootstrap: 5000 deterministic interval-cluster draws, seed 5004.
- Fit sessions: 2026-07-20 through 2026-07-23 only.
- 2026-07-24 and 2026-07-27 through 2026-07-29 are descriptive reuse diagnostics only.

## Event accounting

| Width | Role | Buy | Sell | Joint valid | Excluded |
| ---: | --- | ---: | ---: | ---: | ---: |
| 500 ms | development | 715 | 730 | 1445 | 3 |
| 500 ms | internal_reuse | 160 | 137 | 297 | 0 |
| 500 ms | seen_external_reuse_diagnostic | 617 | 667 | 1284 | 5 |
| 1000 ms | development | 714 | 730 | 1444 | 4 |
| 1000 ms | internal_reuse | 160 | 135 | 295 | 2 |
| 1000 ms | seen_external_reuse_diagnostic | 616 | 666 | 1282 | 7 |

## Diagnostic likelihood increments

### 500 ms

- `development`: C-A mean `0.000516` (95% `0.000179`, `0.000839`); C-B mean `0.001073`.
- `internal_reuse`: C-A mean `0.000555` (95% `-0.000159`, `0.001258`); C-B mean `-0.008823`.
- `seen_external_reuse_diagnostic`: C-A mean `0.000788` (95% `0.000413`, `0.001163`); C-B mean `-0.006550`.

### 1000 ms

- `development`: C-A mean `0.000205` (95% `0.000059`, `0.000347`); C-B mean `0.003262`.
- `internal_reuse`: C-A mean `0.000094` (95% `-0.000199`, `0.000389`); C-B mean `-0.006150`.
- `seen_external_reuse_diagnostic`: C-A mean `0.000374` (95% `0.000203`, `0.000552`); C-B mean `-0.002862`.

## Interpretation

All results in this report are development, internal-reuse, or seen-external-reuse diagnostics.
They cannot create an M5-004 verdict. Only a blind accepted 2026-08-03 through
2026-08-07 block can satisfy the registered external gate.

## Validation

- `upstream_provenance_reconciles`: PASS
- `canonical_m2_to_m5_003_outputs_unchanged`: PASS
- `known_internal_event_counts_reconcile`: PASS
- `one_row_per_unlock_event`: PASS
- `predictor_allowlist_exact`: PASS
- `labels_absent_from_predictors`: PASS
- `metadata_absent_from_predictor_allowlist`: PASS
- `development_only_fit_sessions`: PASS
- `internal_reuse_not_loaded_for_fit`: PASS
- `seen_reuse_loaded_only_after_manifest_write`: PASS
- `future_external_not_loaded`: PASS
- `all_prediction_probabilities_finite_and_bounded`: PASS
- `group_key_collision_safe`: PASS
- `no_tradeable_edge_claim`: PASS

Deterministic report hash: `ae517c43ef0884e2e98c6579cc32a34ba3c7f247fb6148e12e1a4d0da9a8a9ca`
