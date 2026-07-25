# Current Status

## Current phase

M2 — State Reconstruction

## Completed

- The bot uses a hedging account.
- The usual state is one position or one Buy plus one Sell.
- After closing one leg, the bot generally reopens the same side.
- The resulting advantage occurs during one-sided exposure.
- Repository bootstrapped
- Initial project memory committed
- One month of MT5 reports and XAUUSD ticks documented in the manifest
- Canonical MT5 report and tick parsers
- Dataset validation and anonymized fixtures
- Per-report financial reconciliation
- Trade/tick overlap inventory validation

## Current data

- 4 MT5 weekly trade reports
- 1 XAUUSD tick file covering 2026-07-23 to 2026-07-24
- Approximately one month of trade history

## Current focus

Reconstruct chronological hedge position states from normalized Positions and Deals.

## Next executable task

Reconstruct hedge position states and classify unlock/re-hedge events from normalized Deals and Positions.

## Current blockers

- Server timezone not formally confirmed
- MT5 report event time has only second-level resolution
