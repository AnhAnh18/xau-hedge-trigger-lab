# RETRO-BOT-003 Sequential Multi-Cycle Result

Status: descriptive RETRO evidence; synthetic sequential accounting only; no M5 input or verdict.

Aggregate digest: `0f803aad89838a45e31e4589897d7019f65c4fc7e888d7d5dfa8c02671cd9831`.

| Clock | Policy | Total | Eligible | Action | Marked | Censored | Overlap | Invalid | Loss | Flat | Gain |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `utc_plus_2` | `first_available_tick` | 189 | 189 | 176 | 176 | 13 | 0 | 0 | 87 | 0 | 89 |
| `utc_plus_2` | `wait_300_seconds` | 189 | 189 | 174 | 174 | 15 | 0 | 0 | 103 | 1 | 70 |
| `utc_plus_2` | `wait_900_seconds` | 189 | 189 | 18 | 18 | 171 | 0 | 0 | 5 | 0 | 13 |
| `utc_plus_2` | `wait_3600_seconds` | 189 | 189 | 8 | 8 | 181 | 0 | 0 | 3 | 0 | 5 |
| `utc_plus_3` | `first_available_tick` | 189 | 189 | 186 | 186 | 3 | 0 | 0 | 95 | 0 | 91 |
| `utc_plus_3` | `wait_300_seconds` | 189 | 189 | 184 | 184 | 5 | 0 | 0 | 95 | 0 | 89 |
| `utc_plus_3` | `wait_900_seconds` | 189 | 189 | 20 | 20 | 169 | 0 | 0 | 10 | 0 | 10 |
| `utc_plus_3` | `wait_3600_seconds` | 189 | 189 | 8 | 8 | 181 | 0 | 0 | 5 | 0 | 3 |
| `eu_dst_2025_2026` | `first_available_tick` | 189 | 189 | 186 | 186 | 3 | 0 | 0 | 94 | 0 | 92 |
| `eu_dst_2025_2026` | `wait_300_seconds` | 189 | 189 | 184 | 184 | 5 | 0 | 0 | 93 | 0 | 91 |
| `eu_dst_2025_2026` | `wait_900_seconds` | 189 | 189 | 20 | 20 | 169 | 0 | 0 | 10 | 0 | 10 |
| `eu_dst_2025_2026` | `wait_3600_seconds` | 189 | 189 | 8 | 8 | 181 | 0 | 0 | 4 | 0 | 4 |

All locked policies and clocks are reported side by side. Overlapping or invalidly ordered cycles are excluded from action/mark accounting; no policy, clock, profitability, ownership, or live-execution claim is made.
