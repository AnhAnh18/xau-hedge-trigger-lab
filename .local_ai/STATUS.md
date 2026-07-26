# Current Status

## Current phase

M4 — Trigger Dataset (gate review)

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
- Lifecycle/state reconstruction with exception accounting
- M2 event accounting and boundary validation
- M3 deterministic event–tick alignment for the observed tick window
- M4 v1 causal trigger-dataset implementation
- Deterministic matched risk-set controls without candidate replacement
- H1/H2/H3 paired and cluster-bootstrap reports

## Current data

- 4 MT5 weekly trade reports
- 1 XAUUSD tick file covering 2026-07-23 to 2026-07-24
- Approximately one month of trade history

## Current focus

Resolve the timestamp-sensitivity gate. At `matched_time`, H1 is supported,
H2 is rejected, and H3 is supported; at `matched_time + 500 ms`, H1/H2 reverse.

## Next executable task

Determine whether the +500 ms reversal reflects post-action price response or a
remaining alignment ambiguity before closing M4 and starting M5.

## Current blockers

- Server timezone not formally confirmed
- MT5 report event time has only second-level resolution
- M4 sensitivity conclusions are not stable at `matched_time + 500 ms`
