# Decision Log

## D-001 — Use behavioral fidelity before profitability

Decision: Evaluate reconstructed triggers first by event direction, timing, and price similarity, not net profit.

Reason: A profitable backtest may result from overfitting while behaving differently from the original strategy.

## D-002 — Raw financial data stays outside Git

Date: 2026-07-25
Status: Accepted

Decision: Store raw MT5 reports and broker tick exports locally under `data/raw/` and exclude them from Git. Track manifests, schemas, checksums, parsing code, and anonymized aggregates.

Reason: Reports contain personally identifying and financial information; tick files are also unsuitable for normal source control.

## D-003 — Rewrite repository history to remove real account identifier

Date: 2026-07-25
Status: Accepted

Decision: Rewrite all published repository history to replace the real MT5 account identifier with `SOURCE_ACCOUNT_ID`.

Reason: The repository is early-stage and public; rewriting now keeps the anonymization policy consistent.

Consequences: Published commit hashes change, existing clones must be discarded or reset carefully, and old branches must not be merged back.
