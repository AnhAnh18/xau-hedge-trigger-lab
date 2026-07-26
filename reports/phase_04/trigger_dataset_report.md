# M4 Trigger Dataset Report

## Gate status

**NOT PASSED** — timestamp sensitivity changes the H1/H2 conclusions at +500 ms.

The implementation is reproducible, but M4 must not be closed while this sensitivity gate is unresolved.

## Positive accounting

| Behavior | Count |
| --- | ---: |
| REHEDGE_SELL | 331 |
| REHEDGE_BUY | 306 |
| UNLOCK_TO_BUY | 320 |
| UNLOCK_TO_SELL | 294 |
| **Total** | **1,251** |

## Matched controls

- Controls: 6,233
- Positives without a control: 4
- Controls per positive: {'0': 4, '3': 1, '5': 1246}
- Reused control candidates: 0
- True events protected by exclusion zones: 2,096
- Sampling is deterministic, without global candidate replacement, and uses the same date, hour, state, opportunity direction, and 0.3 volume.
- Every control is outside the ±3 second exclusion zone of every aligned true event. Short risk sets are not forced to meet the quota.

## Window validity

| Sample | 500 ms | 1 s | 2 s | 5 s | 10 s | 30 s | 60 s |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| positive | 1,240 | 1,247 | 1,250 | 1,251 | 1,251 | 1,251 | 1,251 |
| control | 6,140 | 6,216 | 6,232 | 6,231 | 6,231 | 6,230 | 6,226 |

Samples remain in the dataset when a long window is unavailable; each analysis filters only on its own validity flag.

## Hypothesis conclusions at matched_time

- H1: **supported**
- H2: **rejected**
- H3: **supported**

H1 separates most clearly at 5–60 seconds. H2 is rejected over those same windows. H3 has short-horizon support at 0.5–2 seconds, while longer windows are inconclusive.

## Timestamp sensitivity

| Shift | H1 | H2 | H3 |
| ---: | --- | --- | --- |
| -500 ms | supported | rejected | weak |
| 0 ms | supported | rejected | supported |
| 500 ms | rejected | supported | supported |

The +500 ms reversal is report-only evidence of timing fragility. No +500 ms value is present in `trigger_features.parquet` or used for rule discovery.

## Coverage and inference constraints

- 2026-07-23 is development data and begins at 12:00.
- 2026-07-24 is holdout data and is near-full-day.
- Raw daily event counts or rates are not compared as if coverage were equal.
- Statistics use matched differences and positive-event cluster bootstrap; controls in one risk set are not treated as independent.
- Control ratios are not interpreted as absolute event probabilities.
- `entry_gap`, surviving-entry distance, floating P/L, and preceding unlock loss are excluded pending position lineage.
