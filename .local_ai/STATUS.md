# Current Status

## Current phase

M1 — Data Foundation

## Completed

- The bot uses a hedging account.
- The usual state is one position or one Buy plus one Sell.
- After closing one leg, the bot generally reopens the same side.
- The resulting advantage occurs during one-sided exposure.
- Repository bootstrapped
- Initial project memory committed
- One month of MT5 reports and XAUUSD ticks documented in the manifest

## Current data

- 4 MT5 weekly trade reports
- 1 XAUUSD tick file covering 2026-07-23 to 2026-07-24
- Approximately one month of trade history

## Current focus

Create a reproducible and validated dataset from MT5 reports and tick data.

## Next executable task

Run `python scripts/audit_data.py` after placing private raw files under `data/raw/`.

## Current blockers

- Server timezone not formally confirmed
- MT5 report event time has only second-level resolution
