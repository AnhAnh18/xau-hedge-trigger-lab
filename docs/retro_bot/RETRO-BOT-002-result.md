# RETRO-BOT-002 Paper Backtest Result

Status: descriptive RETRO evidence; synthetic accounting only; no M5 input or verdict.

Aggregate digest: `4f40faae72bb4cd32df8ea5b24fcea9238912f77c3b0ca0bbd69deba088148f6`.

| Clock | Policy | Eligible | Marked | Mark-censored | Delay-censored | No-tick-censored | Clock-unresolved | Loss | Flat | Gain |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `utc_plus_2` | `first_available_tick` | 189 | 176 | 0 | 0 | 13 | 0 | 87 | 0 | 89 |
| `utc_plus_2` | `wait_300_seconds` | 189 | 174 | 0 | 2 | 13 | 0 | 103 | 1 | 70 |
| `utc_plus_2` | `wait_900_seconds` | 189 | 18 | 0 | 169 | 2 | 0 | 5 | 0 | 13 |
| `utc_plus_2` | `wait_3600_seconds` | 189 | 8 | 0 | 181 | 0 | 0 | 3 | 0 | 5 |
| `utc_plus_3` | `first_available_tick` | 189 | 186 | 0 | 0 | 3 | 0 | 95 | 0 | 91 |
| `utc_plus_3` | `wait_300_seconds` | 189 | 184 | 0 | 2 | 3 | 0 | 95 | 0 | 89 |
| `utc_plus_3` | `wait_900_seconds` | 189 | 20 | 0 | 169 | 0 | 0 | 10 | 0 | 10 |
| `utc_plus_3` | `wait_3600_seconds` | 189 | 8 | 0 | 181 | 0 | 0 | 5 | 0 | 3 |
| `eu_dst_2025_2026` | `first_available_tick` | 189 | 186 | 0 | 0 | 3 | 0 | 94 | 0 | 92 |
| `eu_dst_2025_2026` | `wait_300_seconds` | 189 | 184 | 0 | 2 | 3 | 0 | 93 | 0 | 91 |
| `eu_dst_2025_2026` | `wait_900_seconds` | 189 | 20 | 0 | 169 | 0 | 0 | 10 | 0 | 10 |
| `eu_dst_2025_2026` | `wait_3600_seconds` | 189 | 8 | 0 | 181 | 0 | 0 | 4 | 0 | 4 |

Accounting is fixed at quantity 1.0: buys execute at ask and mark at bid; sells execute at bid and mark at ask at the observed re-hedge anchor. No policy or clock is selected, and no profitability or live-execution claim is made.
