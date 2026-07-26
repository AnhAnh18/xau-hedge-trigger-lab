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

## D-004 — Keep M4 v1 causal and lineage-safe

Date: 2026-07-26
Status: Accepted

Decision: Build M4 v1 features only from ticks, state intervals, and aligned
events at `matched_time`. Keep `matched_time ± 500 ms` in sensitivity reports
only. Use deterministic matched risk-set controls without replacement, with
separate validity flags for every feature window.

Reason: Position lineage is not yet strong enough to reproduce entry distance,
surviving-leg state, floating P/L, or preceding unlock loss without assumptions.

Consequences: Those four feature families are deferred to M4-004. M4 remains
open because the +500 ms sensitivity reverses H1/H2, even though the causal
dataset and baseline hypothesis reports are reproducible.

## D-005 — Remediate M4 anchors, support, and causal sensitivity

Date: 2026-07-26
Status: Accepted

Decision: Price features remain anchored at `matched_timestamp`.
Pre-transition state bookkeeping uses the exact M2 interval ending at the
event, with `reported_time` as the fallback anchor. Audit metadata and reviewed
model predictors are written to separate outputs.

H1 primary inference is restricted to the control-supported population with
at least seven seconds of pre-transition state age. H2 uses a disjoint prior
boundary window followed by a causal touch-and-retracement sequence.

The causal sensitivity gate compares `matched_time - 500 ms` with
`matched_time`. Positive shifts of +250, +500, and +1000 ms are post-action
diagnostics only and cannot affect model features, headline verdicts, or merge
gates.

Reason: The first M4 implementation mixed price and state time bases, allowed
sampling metadata into the model-ready table, and implemented H2 as the exact
complement of H1. Positive timestamp shifts measure post-action response rather
than pre-action causal robustness.

Consequences: This decision supersedes the sensitivity-gate consequence in
D-004. Inconclusive hypotheses may be reported honestly; they are not promoted
to supported by descriptive or post-action results.
