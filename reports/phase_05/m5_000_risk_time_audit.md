# M5-000 Risk-Time Audit

- Status: `pilot_accounting_only`
- Tick coverage: 2026-07-23T12:00:00.046000 to 2026-07-24T23:56:57.758000
- Source intervals touching coverage: 2,096
- Positive-duration intervals: 2,062
- Deterministic audit SHA-256: `c1cc7c9596e68e7d547756ddf89d6f4a00dfdd0d5122295ec4effdb8f0eb6571`

## Why the earlier counts differ

The legacy calculation assigns each interval's entire un-clipped duration to its start date. It therefore assigns the after-midnight part of a cross-midnight interval to the prior day and counts the maintenance break as risk time.

| Day | Intervals | Legacy seconds | Event density |
| --- | ---: | ---: | ---: |
| 2026-07-23 | 1,248 | 47,501.000 | 2.627% |
| 2026-07-24 | 848 | 81,911.000 | 1.035% |

## Canonical full-coverage accounting

Intervals are clipped to observed tick coverage, split at midnight, and stripped of detected market-break time.

| Day | Interval-day memberships | Eligible events | Raw seconds | Break seconds | Tradeable seconds | Target density |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-07-23 | 1,248 | 1,226 | 43,199.954 | 120.101 | 43,079.853 | 2.846% |
| 2026-07-24 | 849 | 836 | 85,899.000 | 3,600.400 | 82,298.600 | 1.016% |

## Comparable cohort: server hours 12-23

All later A/B/C headline comparisons must use this common server-hour support. Full-range results remain descriptive.

| Day | Interval-day memberships | Eligible events | Tradeable seconds | Target density |
| --- | ---: | ---: | ---: | ---: |
| 2026-07-23 | 1,248 | 1,226 | 43,079.853 | 2.846% |
| 2026-07-24 | 594 | 585 | 42,699.000 | 1.370% |

## Market-break accounting

- `2026-07-23T23:57:59.899000` to `2026-07-24T01:00:00.400000`: 3,720.501 seconds excluded (`market_break_no_tick_coverage`).

## Boundary cases

- Left-truncated interval IDs: 12074
- Right-censored interval IDs: none
- Cross-midnight interval IDs: 13321
- Market-break intersection interval IDs: 13321
- Zero-duration intervals in coverage: 34

## Timezone decision

- Server timezone: `UTC+03:00`.
- Status: high-confidence inference for the July 2026 data window, not a globally confirmed broker/DST rule.
- Highest tick-count server hours: 17, 16, 18.

## Gate

M5-000 defines accounting and acquisition prerequisites only. No model verdict is allowed from this report, and M5 cannot close without pre-registered additional tick sessions.
