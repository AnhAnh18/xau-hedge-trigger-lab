# M4 Trigger Dataset Remediation Report

## Gate status

**PASSED**

Only `matched_time` and `matched_time - 500 ms` participate in the causal sensitivity gate. Positive shifts are post-action diagnostics only.

## Positive and control accounting

| Behavior | Positives |
| --- | ---: |
| REHEDGE_SELL | 331 |
| REHEDGE_BUY | 306 |
| UNLOCK_TO_BUY | 320 |
| UNLOCK_TO_SELL | 294 |
| **Total** | **1,251** |

- Controls: 6,233
- Controls per positive: {'0': 4, '3': 1, '5': 1246}
- Positives without sampled controls: 4
- Reused candidates: 0
- Control-supported positives: 980
- Structurally unsupported positives: 271

## Time-anchor contract

- Price and tick features: `matched_timestamp`.
- Pre-transition state bookkeeping: exact M2 interval lineage; `reported_time` is the fallback anchor.
- Positive state ages populated: 1,251/1,251.
- Control state ages populated: 6,233/6,233.

## H1 — rolling boundary

- Headline: **confounded/inconclusive**
- Primary control-supported verdict: **inconclusive**
- Descriptive all-positive verdict: **supported**

| Pre-transition state age | Positives | Supported positives | Holdout 5s diff | CI95 |
| --- | ---: | ---: | ---: | --- |
| 0-6s | 237 | 0 | +0.2533 | [+0.1842, +0.3182] |
| 7-10s | 57 | 57 | +0.0366 | [-0.1305, +0.1967] |
| 10-30s | 148 | 148 | +0.0581 | [-0.0336, +0.1494] |
| 30-60s | 73 | 73 | -0.0228 | [-0.1389, +0.0917] |
| >60s | 122 | 122 | +0.0271 | [-0.0727, +0.1270] |

The all-positive result is descriptive only. It cannot override a null control-supported inference.

## H2 — prior boundary, touch, then retracement

- Joint sequence: **inconclusive**
- Boundary-touch component: **supported**
- Post-touch retracement component: **inconclusive**
- Retracement upper-tail winsorization: development p99; caps {'1000': 7.0000000003534035, '2000': 4.126428571388192, '5000': 2.973416666670874}
- H2 independence audit passed: True

Prior boundaries are calculated on a disjoint window ending before the sequence window. Touch and retracement are published separately.

## H3 — signed momentum

- Headline: **supported**
- Median spread: 0.2300 price units.
- The holdout effect is timing-sensitive, smaller than the median spread, and is not interpreted as a standalone tradeable edge.

| Window | Price-unit effect | Fraction of median spread |
| ---: | ---: | ---: |
| 500 ms | +0.0486 | +0.211 |
| 1000 ms | +0.0621 | +0.270 |
| 2000 ms | +0.0736 | +0.320 |

## Sensitivity

| Shift | Role | H1 | H2 | H3 |
| ---: | --- | --- | --- | --- |
| -500 ms | causal_gate | weak | inconclusive | supported |
| 0 ms | causal_gate | inconclusive | inconclusive | supported |
| 250 ms | post_action_diagnostic_only | rejected | supported | supported |
| 500 ms | post_action_diagnostic_only | rejected | supported | supported |
| 1000 ms | post_action_diagnostic_only | rejected | weak | supported |

Positive shifts do not enter the model matrix, headline hypothesis verdicts, or merge gate.

## Output contracts

- `trigger_samples_audit.parquet`: IDs, anchors, lineage, sampling metadata, alignment diagnostics, and validity flags.
- `trigger_model_features.parquet`: explicit reviewed allowlist only.
- Model predictors: 132.
- Raw state age remains in audit; model state age is clipped at 60 seconds.
- `sample_id` is audit-only and absent from the model matrix.
- Sampling metadata and `time_since_previous_event_seconds` are absent from the model-ready matrix.

Development data on 2026-07-23 begins at 12:00. Holdout data on 2026-07-24 is near-full-day; raw daily counts are not compared as equal-coverage event rates.
