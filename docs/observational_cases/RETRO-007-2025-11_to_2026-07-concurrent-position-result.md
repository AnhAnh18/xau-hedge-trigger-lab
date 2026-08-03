# RETRO-007 Result

Status: completed after independent review on 2026-08-03.

## Redacted aggregate finding

- Population: server dates `2025-11-01` through `2026-07-30` inclusive.
- `max_total_active`: 7.
- `max_buy_active`: 4.
- `max_sell_active`: 5.
- Definite positive-duration episodes with total active positions above 2: 8,768.
- Definite positive-duration episodes with at least 2 Buy and 2 Sell: 5,422.
- Definite calendar-day segments with at least 2 Buy and 2 Sell: 7,564.
- Possible same-second upper-bound episodes: 23,509 total-above-2 and 1,883 with 2 Buy + 2 Sell.
- Monday segments above 2: 3,894; non-Monday segments above 2: 19,613.
- Fixed post-gap windows with positive-duration multi-position overlap: 18 under both UTC+2 and UTC+3 mappings.

The result supports that the historical population contains periods with more
than one Buy and one Sell, including a 2 Buy + 2 Sell pattern. It does not
identify the cause, prove that a quote gap caused a new pair, establish manual
intervention, or establish broker ownership. The 2026-08-03 observation is
outside this case and was not inspected.

## Validation

- Source manifests were hash-verified against the owner-authorized RETRO-003
  receipt; no source expansion occurred.
- Synthetic checks covered close-only events, four-position overlap,
  Sunday-to-Monday splitting, and clipped gap windows.
- Aggregate self-digest:
  `1bf1dba84b4a14f1f9b56bbfc711a104e94a8912a02cabc5a4a7bb94c42ac36a`.
- Independent review verdict: PASS, no P0-P3 findings.
- `raw_rows_printed=false`; the output remains outside every M5 manifest.
