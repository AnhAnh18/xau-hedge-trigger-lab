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

Decision: Use `UTC+03:00` as the inferred server timezone for the observed
July 2026 tick window. Propagate that inference to reports from the same MT5
account server in the June/July 2026 summer period, while marking it as
high-confidence but not formally or globally confirmed.

Reason: The only tick gap longer than 60 seconds occurs around server midnight
to 01:00, and the highest tick-count hours are 16–18 server time. These
independent observations are consistent with UTC+3 for this window.

Consequences: Session context may use server clock under this recorded
assumption. No year-round DST rule may be inferred without additional data or
broker confirmation.

## D-008 — Use canonical tradeable time and common-hour support in M5

Date: 2026-07-26
Status: Accepted

Decision: Clip M2 intervals to merged tick coverage, split them at midnight,
exclude full consecutive-tick gaps longer than 60 seconds, and pause state age
inside those gaps. Until recurrence is observed across sessions, classify a
gap as `unknown_coverage_gap`, not as a scheduled market closure.

All A/B/C headline comparisons use identical bins restricted to server hours
12–23, the coverage support shared by development and holdout. This aligns
coverage but does not align base rates: the corrected common-hour development
/ holdout target-density ratio is 2.100x.

Preserve zero-duration intervals for accounting only and exclude them from the
primary risk-bin estimand. Exclude left-truncated intervals from primary
inference relative to merged coverage. Append a synthetic right-censored state
tail from the final M2 event to tick coverage end without modifying M2.

Reason: Start-date duration aggregation assigns after-midnight time to the
wrong day and counts a 3,720.501-second maintenance break as actionable risk.
The current development day also lacks server hours 01–11, which prevents a
full-day comparison with holdout. Aligning hours cannot remove real between-day
rate variation or the day-of-week confound.

Consequences: Legacy totals remain published for reconciliation, but they are
not model exposure. Risk-bin generation must use canonical fragments and the
tradeable state-age clock. M5 v1 primary conclusions apply only to 12:00–24:00
server time and cannot be generalized to the Asian session.

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

Primary external inference remains fixed to server hours 12:00–24:00. A
full-session analysis on the same three dates is pre-registered as secondary;
it cannot override the primary verdict.

## D-010 — Use paired and conditional M5 timing comparisons

Date: 2026-07-26
Status: Accepted

Decision: Keep paired per-interval likelihood increments `C - A_common` and
`C - B` as headline statistics and add a within-interval conditional timing
statistic as co-primary. The conditional statistic includes intervals with
exactly one representable event and cancels the interval intercept.

Occurrence hazard remains the occurrence model; the conditional statistic is
not multiplied back into occurrence and does not include censored intervals.

Raw holdout calibration is descriptive. Post-hoc intercept recalibration may
only diagnose whether failure is intercept-only or also affects slope. It must
be labelled as using holdout labels and cannot affect a verdict or gate.

Reason: Common-hour support still has a 2.100x development/holdout base-rate
difference. Paired likelihood deltas are less sensitive than standalone
calibration but are not algebraically invariant to an intercept shift.

Consequences: Final M5 inference reports both co-primary timing comparisons and
waits for pre-registered external sessions. Neither post-hoc recalibration nor
standalone calibration can promote a result.

## D-011 — Amend M5-002 support and age buckets before fitting

Date: 2026-07-26
Status: Accepted before M5-002 fitting

Decision: Keep internal and retrospective tick cohorts as separate support
domains and define left truncation relative to each cohort. Never append the
retrospective export to the canonical M2-M4 `ticks.parquet`. Lay complete risk
bins on the wall-clock grid inside tradeable fragments and evaluate paused
tradeable state age at bin start.

Amend the age grid around the M2-observed six-second unlock boundary to include
`[5,6)`, `[6,8)`, and `[8,10)`. Keep Jeffreys smoothing as the primary finite
estimate, publish unsmoothed rates and alpha sensitivity, and do not hard-code
the early unlock hazard to zero because M2 contains one sub-six-second
exception.

For M5-002 timing inference, use the within-interval conditional statistic as
primary and cause-specific occurrence likelihood as secondary. Preserve their
different estimands. Supplemental sessions describe per-session base-hazard
variation only and must leave the internal fitted-parameter hash unchanged.

Reason: M2 durations show 6,275 of 6,276 unlocks at or beyond six seconds,
whereas roughly one third of re-hedges occur earlier. The original `[5,10)`
bucket obscures that boundary. Separate cohort support also preserves M2-M4
reproducibility and removes ambiguity around the 43,320-second inter-export
gap.

Consequences: This is a dated pre-fit amendment based only on canonical M2
durations. It does not use price data, held-out model performance, or M5-002
fit results. Final M5 external validation remains unchanged.

## D-012 — Retire outcome-truncated conditional inference for M5-002

Date: 2026-07-26
Status: Accepted post-fit remediation; supersedes D-010/D-011 only for the
M5-002 age-only verdict

Decision: Use paired cause-specific occurrence likelihood `A_age - A_const` as
the primary M5-002 statistic. Withdraw the two re-hedge timing-rejected
verdicts. Retain the old within-interval calculation only as a non-inferential
degeneracy audit, and defer any conditional timing design to M5-003
pre-registration.

Reason: M2 intervals end at their observed event and the target is always the
last representable bin. For an age-only model, the proposed risk set is
therefore determined by the outcome and the statistic is a function of
interval duration and the fitted age curve. Even a holdout-label oracle remains
below the uniform null for all three endpoints.

Consequences: The internal occurrence result supports the approximate unlock
timer floor and weaker re-hedge age effects, but remains base-rate-sensitive
and externally unvalidated. The 500-millisecond width is discretization
sensitivity, not independent replication. M5-003 does not start in this
remediation.

## D-013 — Lock M5-003 development scope and price-increment estimand

Date: 2026-07-26
Status: Accepted before M5-003 feature construction or fitting; model-baseline
clauses superseded by D-014

Decision: Pool retrospective 2026-07-20..22 with internal 2026-07-23 for
development only. Freeze 2026-07-24 out of preprocessing, CV, fitting,
selection, and calibration. Treat it as an internal reuse diagnostic, not
independent price confirmation. Preserve 2026-07-27..29 as the only external
gate.

Condition unlock occurrence on tradeable state age at bin start being at least
five seconds. Use endpoint-specific 12-feature allowlists, frozen M5-002
A_common as C's unit-coefficient offset, and one-second `C - A_common` as the
single headline comparison per endpoint.

Reason: Pooling the four development dates raises known target counts to 699,
687, and 1,448 without spending the external gate. Conditioning unlock after
the timer floor removes 3,115 zero-event internal-development bins so A and B
receive the same structural information. The 24 July price labels were already
inspected in M4 and cannot honestly be called untouched.

Consequences: Supplemental dates may train B/C but can never validate or gate.
All fitting choices are locked before price construction. Null price findings
are mergeable, and no result may be promoted to a tradeable-edge claim.

## D-014 — Correct M5-003 age grid and require independent re-review

Date: 2026-07-26
Status: Accepted before M5-003 price-feature construction or fitting;
supersedes D-013 only for the age grid and model-baseline comparison

Decision: Fit `A_dev` on the exact 11-bucket M5-002 grid, including `[5,6)`,
`[6,8)`, and `[8,10)`. Unlock's age-at-start floor therefore retains seven
buckets, not five. Keep `A_common` frozen for provenance, use development-fit
`A_dev` as the headline baseline, and compare `C_dev - A_dev` with no free
intercept in `C_dev`.

Reason: The merged M5-003 preregistration incorrectly listed nine buckets
while simultaneously requiring the exact M5-002 grid. Source code, the
committed M5-002 report, and fitted parameter hash all prove that M5-002 uses
11 buckets. A nine-bucket `A_dev` would make the registered shape-transport
diagnostic incompatible with `A_common` and would obscure the already locked
six-second boundary.

Consequences: This correction was made before any M5-003 price fit and changes
no M5-002 output. Because one developer is implementing the pipeline, the
completed Draft PR requires an independent Claude re-review covering this
correction, cohort accounting, leakage controls, frozen hashes, comparisons,
and verdict language before merge.

## D-015 — Add a session-adjusted M5-003 baseline after independent review

Date: 2026-07-27
Status: Accepted review-driven remediation before external evaluation;
supersedes D-014 only for the M5-003 headline baseline and price comparison

Decision: Preserve `A_dev` and the old `C_dev - A_dev` result for audit, but
replace it as headline with `C_session - A_session`. Define `A_session` as the
fixed `A_dev` logit plus three unpenalized one-hot/no-intercept server-time
effects on `[12,16)`, `[16,20)`, and `[20,24)`. Define `C_session` as the fixed
`A_session` offset plus the full price allowlist with no free intercept. Select
its lambda anew using the existing development-only GroupKFold protocol.

Move unlock range-width features from `boundary` to
`volatility_liquidity`. Add a reduced `C_shape` model using motion and true
boundary features only; it reuses the selected `C_session` lambda and is an
external secondary diagnostic without an independent verdict. LOSO must refit
`A_dev`, all session effects, preprocessing, selection, and price models.

Reason: Independent review showed that deterministic time-of-day context was
available to the price package but absent from the age baseline. Comparing the
old price model against a newly fitted session baseline without refitting the
price model was invalid. A two-dummy/no-intercept prototype also accidentally
fixed the first block effect at zero, so the exact three-effect
parameterization is part of the contract.

Consequences: Development and 2026-07-24 remain diagnostic and cannot create
a verdict. The server UTC+3 mapping is still an unconfirmed D-007 inference.
Only unseen 2026-07-27..29 data may gate the amended headline. A fresh
independent Claude re-review is required because this remediation was
implemented by the same developer after the prior review.
