# M5 Trigger Inference — Locked v1 Specification

Status: M5-002 state-age pilot implemented; external validation pending.

## Research question

Does causal price/tick information improve transition-timing inference beyond
elapsed tradeable state age?

M5 does not train black-box models, optimize P/L, or modify M2–M4 canonical
outputs.

## Time support

- Tick support is the exact first-to-last timestamp in each named cohort.
- Tick files may be merged only within the same named cohort. Internal
  2026-07-23..24, retrospective supplemental 2026-07-20..22, and later
  external cohorts remain separate support domains.
- The supplemental export must never be concatenated into the M2-M4 canonical
  `data/interim/ticks.parquet`; it is parsed into a separately named local
  M5 table so the M2-M4 coverage contract remains reproducible.
- Every M2 interval is clipped to tick support.
- Intervals are split at calendar midnight before day-level aggregation.
- Consecutive-tick gaps strictly greater than 60 seconds are excluded coverage
  gaps.
- The full open interval between the two observed ticks is excluded with
  `exclusion_reason=unknown_coverage_gap` until recurrence across sessions
  supports a scheduled-market-closure classification.
- A gap may become `scheduled_market_closed` only after the same server-clock
  pattern recurs across multiple registered sessions. D-007 alone is not
  sufficient evidence.
- State age uses a tradeable clock: elapsed wall time minus excluded-gap
  overlap.
- Gaps of 60 seconds or less remain ordinary risk time.
- Zero-duration M2 intervals remain in accounting but cannot create risk bins.
- Because M2 intervals are event-to-event, M5 appends an explicitly synthetic
  right-censored interval from the final event's `state_after` to merged tick
  coverage end. It has no terminal event or competing endpoint.
- Left truncation is defined against cohort-level merged tick coverage, not
  against each file and not across distinct cohorts.
  A left-truncated interval remains in audit accounting but is excluded from
  primary inference; its state age is neither reset to zero nor assumed fully
  tradeable before coverage.
- Source-interval membership, terminal-event count, and tradeable seconds are
  reported separately.

The current internal-cohort boundary fixture is interval `13321`: it crosses
midnight and contains the internal coverage gap longer than 60 seconds.
Interval `12074` is left-truncated by the beginning of the internal cohort.
Interval `8294` is the corresponding left-truncation fixture for the
supplemental cohort. The synthetic internal-cohort
right-censored tail is `HEDGED_1X1` from 23:51:39 to 23:56:57.758.

Primary M5 v1 estimates transition timing only for
`HEDGED_1X1`, `ONE_BUY`, and `ONE_SELL` intervals containing at least one
complete causal bin. The 34 zero-duration re-hedge events, including 30 in
common hours, are excluded from that estimand and remain explicitly linked to
issue #3.

## Cohorts and anchors

- Primary risk-bin width: 1 second.
- Sensitivity risk-bin width: 500 milliseconds.
- A positive 1-second bin ends at `reported_time`; its causal price anchor is
  therefore `reported_time - 1 second`.
- The offset from the M4 `matched_timestamp` anchor must be measured and
  published. M4 and M5 effects are not compared as if they shared an anchor.
- Known-age eligible observed coverage is descriptive (`A_all`). Left-truncated
  intervals remain in audit but cannot enter a state-age model because true
  age is unknown.
- All A/B/C headline comparisons use common server hours 12:00–24:00 on
  identical bins (`A_common`).
- The 12:00–24:00 primary window is fixed for M5 v1, including external
  validation. It is not re-derived when new data arrive.
- A full-session analysis on the pre-registered 2026-07-27 through 2026-07-29
  sessions is pre-registered as secondary. It measures transportability beyond
  the London/NY-focused primary estimand and cannot override its verdict.
- Development remains 2026-07-23 and holdout remains 2026-07-24 for the pilot.
  These two dates are not treated as equivalent full sessions.
- After canonical censoring and left-truncation handling, the development /
  holdout common-hour target-density ratio is 2.100x. Common hours align
  coverage support, not base rates.
- In holdout, the 12:00–24:00 target density is 2.145x the 01:00–12:00
  density. M5 v1 conclusions therefore do not generalize to the Asian session.
- Day of week is perfectly confounded with the split: development is Thursday,
  holdout is Friday, and external validation is Monday through Wednesday.

## Endpoint structure

- `ONE_BUY -> REHEDGE_SELL` and `ONE_SELL -> REHEDGE_BUY` use separate
  occurrence datasets.
- `HEDGED_1X1` models unlock occurrence.
- Unlock direction is estimated only as
  `P(unlock cause | unlock occurred)`. It is not an independent second hazard
  multiplied back into occurrence.
- Competing endpoints are retained as a correctness/censoring requirement.
  They are not promoted into a separate modelling workstream when absent from
  the tick-window cohort.
- `following_event_type` is a label and must never enter a predictor allowlist.

## Model ladder and predictor budget

- A_all: descriptive known-age eligible state-age baseline.
- A_common: state-age baseline on common server-hour support.
- B: pre-registered causal price predictors without state age.
- C: the union of A_common and B on exactly the same bins.

The primary price allowlist is limited to 10–12 predictors. It must include:

- side-appropriate H2 boundary touch at 2 seconds;
- side-appropriate H2 boundary touch at 5 seconds;
- absolute mid-price displacement from state start at bin start.

The state-start reference is the last observed mid at or before the state
transition. If that reference is unavailable because of left truncation, the
displacement feature is invalid rather than imputed.

The remaining predictors must be selected and registered before M5-003. The
132-column M4 matrix cannot be imported wholesale.

## Inference

- Effective replication is counted by `interval_id`, not by risk-bin count.
- Headline statistics are paired per-interval log-likelihood increments
  `C - A_common` and `C - B`.
- Paired likelihood increments are still mildly sensitive to base-rate shift.
- Cause-specific occurrence likelihood is primary for the M5-002 age-only
  pilot.
- The previously proposed within-interval conditional statistic is
  non-inferential for age-only models: each event-to-event interval ends at
  its observed outcome, so its candidate risk set is outcome-truncated and the
  target is always the final bin. It cannot produce an M5-002 verdict.
- Any M5-003 conditional timing comparison requires a separately
  pre-registered risk-set/control-time design. Adding a price predictor alone
  does not automatically validate the old statistic.
- Bootstrap clusters are `interval_id`.
- Standalone log loss, raw calibration, event rank, and top-decile capture are
  descriptive diagnostics only.
- Calibration is first reported without holdout refitting. A post-hoc
  holdout-intercept recalibration may diagnose intercept-only versus slope
  failure, but it must be labelled as using holdout labels and cannot affect a
  verdict, likelihood headline, or merge gate.
- The 500-millisecond width is a discretization sensitivity on the same risk
  support, not independent replication. External temporal validation remains
  required.

## Additional-data gate

The first three contiguous full broker sessions after the current export are
pre-registered as 2026-07-27, 2026-07-28, and 2026-07-29. Each requires XAUUSD
ticks and an MT5 report covering its lifecycle events.

No validation date may be substituted after viewing model results. A
substitution caused by unavailable/corrupt source data requires a dated
manifest amendment made before the replacement result is inspected.

The requirement is untouched, pre-registered temporal data, not future data
as such. Previously uninspected historical full-tick sessions may be registered
by a dated amendment before their validation/model result is read. They do not
silently replace the locked 2026-07-27 through 2026-07-29 primary external
sessions, and no date may be chosen based on a favorable result.

The 2026-07-20 through 2026-07-22 XAUUSD export is registered as a
retrospective supplemental cohort before its tick contents are read. It may
test intake completeness, improve descriptive/support accounting, and support
clearly labelled pilot diagnostics. It is non-gating and cannot replace or
promote the primary 2026-07-27 through 2026-07-29 external-validation result.

M5-002 may run as a pilot if these files are unavailable, but M5 cannot close.
Primary external evaluation remains fixed to 12:00–24:00. The full-session
analysis on all three dates is secondary and was registered before acquisition.

## M5-000 gate

- Roadmap and milestone numbering agree.
- Timezone status is recorded without overstating certainty.
- Legacy and canonical risk-time totals reconcile explicitly.
- Cross-midnight, left/right-censoring, zero-duration, unknown coverage-gap,
  eligible-state filtering, and multi-day/weekend behavior has regression
  coverage.
- Audit output is deterministic and privacy-safe.
- No model is fit.

## M5-001 acquisition preparation

- `data/m5_acquisition_plan.json` is the executable source of locked dates,
  session bounds, report requirements, analysis windows, gap policy, and
  privacy rules.
- `scripts/validate_m5_acquisition.py --plan-only` validates registration
  without reading private data.
- `scripts/validate_m5_acquisition.py --dry-run` validates the complete intake
  path with generated anonymized inputs.
- The live validator records SHA-256 checksums and generated aliases, checks
  per-session tick bounds and report event coverage, preserves duplicate
  timestamps, and reports gaps without retuning the threshold.
- M5-002 remains blocked until real registered inputs pass this validator or
  is explicitly run as a labelled non-closing pilot under this specification.

## M5-002 pre-fit amendment — 2026-07-26

The support and bucket choices in this amendment were recorded before fitting
any M5-002 hazard model. Their evidence source is the already-published M2
event-to-event duration table, not tick predictors, holdout model performance,
or an M5 fit. The pilot-estimand subsection below incorporates the dated
post-fit D-012 remediation after the original conditional statistic was shown
to be non-inferential for an outcome-truncated age-only risk set.

### Scope and data isolation

- M5-002 is a bounded state-age-only pilot. It does not add price predictors,
  optimize P/L, alter M2-M4 outputs, or make a tradeable-edge claim.
- Parsing the 2026-07-20..22 raw tick export into a separately named local M5
  cohort table is in scope. Rebuilding or extending the canonical M2-M4
  `ticks.parquet` is forbidden.
- Canonical support, gaps, midnight fragments, left truncation, and synthetic
  right censoring reuse `risk_time.py`; bin construction and modelling live in
  separate M5 modules.

### Risk-bin clock and terminal contract

- Primary bins are one second; sensitivity bins are 500 milliseconds.
- Bins are half-open `[bin_start, bin_end)` wall-clock grid cells laid inside
  each tradeable fragment. Only complete cells are representable.
- Tradeable state age is a covariate evaluated at `bin_start`; it subtracts
  excluded-gap overlap and is not itself the bin grid.
- A target event belongs to the complete bin whose `bin_end` equals its
  second-resolution `reported_time`. Predictors are evaluated at bin start.
- Competing terminal bins are retained with `target_label=0`, an explicit
  competing event type and censor reason; all later bins are absent.
- Cross-development/holdout intervals are audit-only and excluded from both
  primary splits. Left-truncated and zero-duration intervals remain in audit
  accounting but not model inference.

### Pre-registered state-age buckets

M2 contains 6,276 hedged intervals ending in unlock. Exactly one has duration
below six seconds; the five available tick sessions each have zero such
events. This is evidence for an approximate six-second timer floor, not proof
of an absolute zero-probability law.

The amended bucket grid is:

`[0,1), [1,2), [2,3), [3,5), [5,6), [6,8), [8,10), [10,20),
[20,30), [30,60), [60,+inf)`.

The primary empirical fit retains Jeffreys smoothing (`alpha=0.5`) so a rare
exception cannot create infinite held-out loss. Raw unsmoothed rates are
published, structural-zero candidates are marked explicitly, and smoothing
sensitivity is reported for `alpha in {0.0, 0.5, 1.0}`. No bucket is forced to
zero by assumption.

### Pilot estimands and deliverables

- Cause-specific occurrence likelihood `A_age - A_const` is primary. It
  represents target, censored, and competing-endpoint risk intervals and
  remains sensitive to base-rate shift.
- The old within-interval conditional event-bin calculation is retained only
  as a degeneracy audit. A holdout-label oracle still falls below its uniform
  null, proving that it does not score age-only model quality. It affects no
  verdict or merge gate and is deferred to M5-003 risk-set redesign.
- Fitted parameters use development internal common-hours only. Their
  deterministic hash must be unchanged whether supplemental inputs are
  present or absent.
- The supplemental cohort's named deliverable is descriptive per-session base
  hazard variation across 2026-07-20..24. It may diagnose weekday variation
  behind the 2.100x development/holdout ratio but cannot alter the internal
  fit, pilot verdict, or external gate.
- M4 `matched_timestamp` anchor-offset measurement is explicitly deferred to
  price-feature work because M5-002 has no price anchor.
- Unlock direction `P(cause | occurrence)` is explicitly deferred; M5-002
  models unlock occurrence only.
- M5-002 may report `pilot_complete_external_pending`, but M5 remains open
  until the 2026-07-27..29 external cohort is acquired and evaluated.

## M5-003 preregistration and implementation amendment — 2026-07-26

M5-003 implementation and price fitting were explicitly authorized after the
preregistration review. The complete locked contract is:

- `.local_ai/M5_003_PREREGISTRATION.md`;
- `data/m5_003_preregistration.json`.

The preregistration locks immutable M5-002 hashes, endpoint-specific causal
feature allowlists, unlock conditioning at state age five seconds,
development-only GroupKFold and preprocessing, frozen A_common parameters,
the exact 11-bucket A_dev grid, fixed L2 selection, paired interval inference,
required ablations, multiplicity families, and a null-permitting merge gate.

Retrospective 2026-07-20..22 joins development but can never validate or gate.
The 2026-07-24 session remains excluded from fitting and tuning but is an
internal reuse diagnostic rather than untouched price confirmation because M4
already inspected its price hypotheses. Only 2026-07-27..29 can satisfy the
external gate.

For M5-003, the earlier generic allowance for post-hoc holdout-intercept
recalibration is superseded: holdout labels cannot be used for calibration,
including diagnostics. Base-rate attenuation is evaluated only with the fixed
development-label stress test registered in the M5-003 contract.

The implementation is frozen with status
`pipeline_frozen_external_pending_zero_validated_price_results`. Development
and 2026-07-24 internal-reuse outputs are diagnostics only and cannot create a
price verdict. Because this is a single-developer implementation and the
preregistration required a post-merge nine-versus-11 bucket correction, an
independent Claude re-review is a blocking merge gate. Only 2026-07-27..29 can
satisfy the external validation gate; no tradeable-edge claim is permitted.

## M5-003 session-baseline remediation — 2026-07-27

Independent review found that the full price package encoded deterministic
server-time context absent from `A_dev`. Before any registered external data
was loaded, the headline was amended to `C_session - A_session` using fixed
server blocks `[12,16)`, `[16,20)`, and `[20,24)`. `A_session` represents all
three unpenalized block effects explicitly; `C_session` has no free intercept
and reselects regularization with the unchanged development-only GroupKFold
protocol. The old `C_dev - A_dev` result remains a superseded diagnostic.

Unlock range-width features are classified as volatility/liquidity rather
than boundary shape. A reduced `C_shape` model is review-driven and
descriptive only; it cannot create an independent verdict or override the
full-package headline. LOSO refits the age baseline, all session effects,
preprocessing, regularization, and price models. The D-007 UTC+3 server mapping
remains inferred, all internal results remain non-gating, and a fresh
independent Claude re-review is required after this remediation.

That review independently reproduced the session model and accepted the
engineering result. Its final bounded follow-up adds a two-of-three positive
external-session consistency gate to the pooled familywise rule. Likelihood
increment magnitudes are explicitly non-comparable across sessions and
endpoints. Internal ablations may describe small unique conditional value for
motion/boundary versus larger state-path and volatility/liquidity drops, but
cannot establish a causal source or absence of price-shape information.

## M5-004 conditional unlock-cause preregistration — 2026-07-27

M5-004 is registered before any cause-feature implementation or fit. Its exact
contract is:

- `.local_ai/M5_004_PREREGISTRATION.md`;
- `data/m5_004_preregistration.json`.

The estimand is event-level `P(UNLOCK_TO_BUY | eligible unlock occurred)`, not
another occurrence hazard. Non-event risk bins, censored intervals, and
competing endpoints cannot be cause negatives. The one-second headline uses a
fixed state-age cause offset plus exactly 12 directional price features; the
500-millisecond anchor is timing sensitivity.

The contract is stacked on Draft PR #8. Any upstream review change requires a
dated pre-fit hash amendment. Development and internal reuse cannot create a
verdict; only the frozen 2026-07-27..29 evaluation can. Implementation and
fitting require separate authorization after review.

## M5-003 external evaluation — 2026-07-30

The registered 2026-07-27 through 2026-07-29 cohort is now acquired and
evaluated with the frozen M5-003 manifest. A dated amendment was committed
before external feature construction or prediction:

- `.local_ai/M5_003_EXTERNAL_AMENDMENT.md`;
- `data/m5_003_external_amendment.json`.

The amendment changes neither model nor gate. It discloses that selected
operational screenshots from 2026-07-27 and 2026-07-28 were seen and classifies
one independently replicated 106.357-second source quote gap. Gap time and
crossing lookback windows are excluded without interpolation; reported events
remain in lifecycle and accounting.

The one-second `C_session - A_session` headline passes the locked pooled
familywise and two-of-three positive-session rules for all three endpoints.
The 500-millisecond output remains causal-anchor sensitivity. These are
occurrence-likelihood model comparisons only. They do not authorize a
tradeable-edge, profitability, causal-trigger, or broker-ownership claim.

Independent review is required before merge. M5-004 remains a separate,
unimplemented estimand and requires a provenance amendment before fitting
because these external sessions are no longer untouched for later research.
