# Current Status

## Current phase

M4 — Trigger Dataset (bounded remediation)

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
- Separate M4 audit and reviewed model-feature outputs
- Complete pre-transition state age from M2 lineage
- Control-supported H1 inference and causal sequence-based H2

## Current data

- 4 MT5 weekly trade reports
- 1 XAUUSD tick file covering 2026-07-23 to 2026-07-24
- Approximately one month of trade history

## Current focus

Validate the remediated M4 artifact and Draft PR #2. H1 is
confounded/inconclusive on the control-supported population, H2 is
inconclusive, and H3 is supported but timing-sensitive and smaller than spread.

## Next executable task

Pass deterministic rebuild, CI, privacy, and code-review gates before deciding
whether Draft PR #2 is ready to merge.

## Current blockers

- Server timezone not formally confirmed
- MT5 report event time has only second-level resolution
