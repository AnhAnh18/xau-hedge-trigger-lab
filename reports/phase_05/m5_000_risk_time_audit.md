# M5-000 Risk-Time Audit

- Status: `pilot_accounting_only`
- Tick coverage: 2026-07-23T12:00:00.046000 to 2026-07-24T23:56:57.758000
- M2 intervals touching coverage: 2,096
- Synthetic right-censored tails: 1
- Positive-duration intervals: 2,063
- Deterministic audit SHA-256: `0b1d4d9ae9ea948c1e3fdba25afb6295b4834b6117819e8207b5375dbe117862`

## Why the earlier counts differ

The legacy calculation assigns each interval's entire un-clipped duration to its start date. It therefore assigns the after-midnight part of a cross-midnight interval to the prior day and counts the maintenance break as risk time.

| Day | Intervals | Legacy seconds | Event density |
| --- | ---: | ---: | ---: |
| 2026-07-23 | 1,248 | 47,501.000 | 2.627% |
| 2026-07-24 | 848 | 81,911.000 | 1.035% |

## Canonical full-coverage accounting

Intervals are clipped to observed tick coverage, split at midnight, and stripped of excluded coverage-gap time.

| Day | Interval-day memberships | Target events | Raw seconds | Gap seconds | Tradeable seconds | Primary risk seconds | Target density |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-07-23 | 1,248 | 1,225 | 43,199.954 | 120.101 | 43,079.853 | 42,885.899 | 2.856% |
| 2026-07-24 | 850 | 836 | 86,217.758 | 3,600.400 | 82,617.358 | 82,617.358 | 1.012% |

## Comparable cohort: server hours 12-23

All later A/B/C headline comparisons must use this common server-hour support. Full-range results remain descriptive.

| Day | Interval-day memberships | Target events | Tradeable seconds | Primary risk seconds | Target density |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2026-07-23 | 1,248 | 1,225 | 43,079.853 | 42,885.899 | 2.856% |
| 2026-07-24 | 595 | 585 | 43,017.758 | 43,017.758 | 1.360% |

## Cohort comparability warning

- Development / holdout common-hour density ratio: **2.100x**.
- Holdout 12–24 / 01–12 density ratio: **2.145x**.
- Common hours align observed coverage, but they do not align base rates or remove the Thursday/Friday/day-of-week confound.
- Primary M5 v1 inference remains fixed to server hours 12–24. A full-session analysis on the external dates is pre-registered as secondary.

## Coverage-gap accounting

- `2026-07-23T23:57:59.899000` to `2026-07-24T01:00:00.400000`: 3,720.501 seconds excluded (`unknown_coverage_gap`).

## Boundary cases

- Left-truncated interval IDs: 12074
- Right-censored interval IDs: m5-tail-14170
- Cross-midnight interval IDs: 13321
- Coverage-gap intersection interval IDs: 13321
- Right-censored tail seconds: 318.758
- Zero-duration intervals in coverage: 34
- Left-truncated intervals are retained in audit accounting but excluded from primary inference.

## Primary estimand

- Transition timing in eligible states with at least one complete causal risk bin on merged tick coverage.
- Zero-duration target events excluded (full/common): 34 / 30.
- The structural zero/early-state support limitation remains tracked in issue #3.

## Timezone decision

- Server timezone: `UTC+03:00`.
- Status: high-confidence inference for the July 2026 data window, not a globally confirmed broker/DST rule.
- Highest tick-count server hours: 17, 16, 18.

## Gate

M5-000 defines accounting and acquisition prerequisites only. No model verdict is allowed from this report, and M5 cannot close without pre-registered additional tick sessions.
