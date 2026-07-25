# Decision Log

## D-001 — Use behavioral fidelity before profitability

Decision: Evaluate reconstructed triggers first by event direction, timing, and price similarity, not net profit.

Reason: A profitable backtest may result from overfitting while behaving differently from the original strategy.

## D-002 — Raw financial data stays outside Git

Date: 2026-07-25
Status: Accepted

Decision: Store raw MT5 reports and broker tick exports locally under `data/raw/` and exclude them from Git. Track manifests, schemas, checksums, parsing code, and anonymized aggregates.

Reason: Reports contain personally identifying and financial information; tick files are also unsuitable for normal source control.
