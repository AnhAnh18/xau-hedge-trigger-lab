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

## D-006 — Bound M4 model transforms before merge

Date: 2026-07-26
Status: Accepted

Decision: Keep `sample_id` and raw pre-transition state age in the audit output
only. The model-ready state-age predictor is clipped to `[0, 60]` seconds.

H2 retracement fractions are upper-tail winsorized at the p99 estimated
separately for each pre-registered window from development,
control-supported re-hedge risk-set samples. Those development caps are applied
unchanged to holdout. The expected H2-touch direction is positive: event
samples should touch the side-appropriate prior boundary more often than their
matched controls.

Reason: Arbitrary IDs are not predictors, the raw state-age tail is too sparse
for an unconstrained numeric effect, and unbounded normalized retracement is
dominated by a small number of near-zero prior ranges.

## D-007 — Treat UTC+3 as a window-scoped timezone inference

Date: 2026-07-26
Status: Accepted

Decision: Use `UTC+03:00` as the inferred server timezone for the July 2026
dataset window. Mark it as high-confidence but not formally or globally
confirmed.

Reason: The only tick gap longer than 60 seconds occurs around server midnight
to 01:00, and the highest tick-count hours are 16–18 server time. These
independent observations are consistent with UTC+3 for this window.

Consequences: Session context may use server clock under this recorded
assumption. No year-round DST rule may be inferred without additional data or
broker confirmation.

## D-008 — Use canonical tradeable time and common-hour support in M5

Date: 2026-07-26
Status: Accepted

Decision: Clip M2 intervals to exact tick coverage, split them at midnight,
exclude full consecutive-tick gaps longer than 60 seconds, and pause state age
inside those gaps. Preserve zero-duration intervals for accounting only.

All A/B/C headline comparisons use identical bins restricted to server hours
12–23, the support shared by development and holdout. Full-range results are
descriptive only.

Reason: Start-date duration aggregation assigns after-midnight time to the
wrong day and counts a 3,720.501-second maintenance break as actionable risk.
The current development day also lacks server hours 01–11, which prevents a
fair full-day comparison with holdout.

Consequences: Legacy totals remain published for reconciliation, but they are
not model exposure. Risk-bin generation must use the canonical fragments and
tradeable state-age clock.

## D-009 — Pre-register external M5 sessions before modelling

Date: 2026-07-26
Status: Accepted

Decision: Register 2026-07-27 through 2026-07-29 as the first external
validation sessions. Require full XAUUSD ticks plus a trade report covering
their lifecycle events.

Reason: The current data contains one partial and one near-full tick session.
Selecting validation dates after seeing model results would create avoidable
selection bias.

Consequences: M5 may produce a clearly labelled pilot before acquisition, but
the milestone cannot close. Any replacement date requires a dated manifest
amendment before replacement results are inspected.
