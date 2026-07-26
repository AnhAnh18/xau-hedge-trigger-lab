# M5-003 Causal Price-Increment Preregistration

Status: Registered on 2026-07-26; implementation and fitting have not started.

Machine-readable contract:
`data/m5_003_preregistration.json`.

## Scope

M5-003 asks whether causal price information improves endpoint-specific
occurrence likelihood beyond a state-age baseline fit mechanically on the
registered M5-003 development cohort. The frozen M5-002 baseline remains an
immutable provenance and transport reference, not the price-increment
headline baseline.

This document authorizes no feature build or model fit. M2 through M5-002
canonical outputs are immutable. P/L, entry lineage, black-box boosting,
post-action ticks, and tradeable-edge claims remain out of scope.

## Immutable M5-002 input

M5-003 must stop before feature construction if any of these hashes differ:

| Input | SHA-256 |
| --- | --- |
| M5-002 report | `80a1a8c680e7ddd7eb0a9e8ed8813f5f69c025d3b62b292eba30b05a92401365` |
| Risk-bin dataframe | `62f0f0fa4f961b699461c2c3ba935c460d853b4553142130187c503fb4698520` |
| Interval-audit dataframe | `18effcaa1d169fa7ad0f029eceb61a00c4470ebf2d3c492a004efce9ed286cd2` |
| Internal tick dataframe | `42baf883f837986e8cfb28f6bb1632fad9caead934a5d059f197a81511d898ac` |
| Supplemental tick source | `d0f27a2090ad84db810c8d5ed5b2b1907743ba084684bc3aa1fdd46983ba5fa4` |
| A_common, 1 second | `4a84542d6cfb25ac91c9702100f2294585c82e28c37928c0aef2a67b40558d89` |
| A_common, 500 ms | `b04035e4a631276c3ec196eddc32a66cf7f5debd6779f61967d94ffdfc047f73` |

The base row is an M5-002 complete risk bin. Eligible rows must:

- be in `HEDGED_1X1`, `ONE_BUY`, or `ONE_SELL`;
- have known tradeable state age;
- fall in server hours `[12:00, 24:00)`;
- not be left-truncated or cross a development/holdout boundary;
- not cross an excluded coverage gap;
- have every endpoint-allowlisted price feature valid.

M5-002 labels and censoring are inherited unchanged: a terminal competing bin
is retained with `target_label=0` and risk ends after that bin. M5-003 cannot
relabel or regenerate endpoint outcomes.

Within each endpoint and split, `A_common`, `A_level`, `A_dev`, B, and `C_dev`
must use exactly the same evaluation bin IDs. There is no imputation and no
model-specific complete-case cohort.

Future external bins are built into a separately named immutable artifact with
the same M5-002 bin/support contract. They are never appended to or used to
rewrite the hashed M5-002 risk-bin file.

## Endpoint estimands

Re-hedge endpoints use their full eligible known-age cohort.

Unlock occurrence is conditional on surviving in `HEDGED_1X1` until tradeable
state age five seconds:

```text
state_age_seconds at bin start >= 5
```

This excludes 3,115 2026-07-23 internal-development bins with zero target
events and removes the structural timer-floor information from the A-versus-B
comparison. An unlock interval ending before age five is outside this
conditional estimand; it is audited as `unlock_before_floor_excluded`, never
relabeled as a negative or censored observation. Frozen A_common probabilities
are subsetted without refitting or renormalization. `A_dev` is fit separately
on this same floor-conditioned cohort.

## Cohort roles and dated development decision

The development cohort is fixed before any M5-003 price fit:

```text
2026-07-20..22 retrospective supplemental
+ 2026-07-23 internal development
```

Known development target counts are:

| Endpoint | Events |
| --- | ---: |
| rehedge_buy_occurrence | 699 |
| rehedge_sell_occurrence | 687 |
| unlock_occurrence | 1,448 |

The retrospective sessions increase training coverage but can never validate,
gate, or promote B/`C_dev`. Their inclusion in development cannot be
reconsidered after a price result is seen.

The 2026-07-24 session is excluded from preprocessing, feature selection,
cross-validation, regularization selection, fitting, and calibration. It is a
locked internal reuse diagnostic, not untouched price confirmation: M4 already
inspected its price hypotheses and labels.

Only the pre-registered 2026-07-27..29 sessions can satisfy the external gate.
They remain untouched until all M5-003 transformations, coefficients,
regularization values, feature groups, and decision rules are frozen.

### Dated amendment after baseline review

On 2026-07-26, before any price model was fit, development-only state-age
rates and shapes were inspected while reviewing this preregistration. That
review established that the 2026-07-23 `A_common` level differs from pooled
2026-07-20..23 development and that re-hedge age-hazard shape also varies by
session. A free level intercept alone cannot prevent price features correlated
with state age from absorbing this shape mismatch.

The headline baseline is therefore amended from `A_common` to the mechanically
specified `A_dev` below. This inspection means development and 2026-07-24 may
produce diagnostics only; neither can produce a confirmatory supported,
rejected, or absent-price verdict. No price coefficient, price likelihood, or
external label was inspected to make this amendment.

## Price anchors and causal windows

The primary M5-003 bin width is one second. For a positive ending at reported
time `T`, the price anchor is bin start `T - 1 second`. Because the report time
has one-second resolution, this anchor is approximately one to two seconds
before the true action. Sub-second triggers are not observable under the
primary contract.

Primary price lookbacks are 2, 5, and 10 seconds. No sub-second price window
enters the allowlist.

The 500 ms risk-bin analysis is secondary and separately fit from development.
Its anchor moves to `T - 500 ms`; it is an anchor-sensitivity estimand, not the
M5-002-style discretization sensitivity. It cannot override the one-second
headline. It uses the frozen 500 ms A_common hash listed above.

For rolling window `w`, only ticks in `[anchor-w, anchor]` are used. The last
tick at or before the anchor is the current quote. A rolling window requires
at least two ticks.

For H2 touch window `w`, the prior boundary uses `[anchor-2w, anchor-w)` and
the sequence uses `[anchor-w, anchor]`. Each subwindow requires at least two
ticks. A touch at the anchor is not a pre-anchor touch. A lookback intersecting
any excluded gap is invalid even if enough endpoint ticks are present.

## Endpoint sign contract

The re-hedge side sign is:

```text
rehedge_sell_occurrence: +1
rehedge_buy_occurrence:  -1
```

Multiplying directional motion by this sign makes positive values point toward
the expected re-entry boundary. Sell uses the upper boundary and Buy uses the
lower boundary.

Unlock occurrence has no side. It uses only magnitude/either-boundary
features. Unlock direction belongs to deferred
`P(cause | unlock occurred)` and cannot enter M5-003 occurrence predictors.
No directional split percentage is used to justify this rule; the canonical
M4 unlock counts are 320 and 294, and neither assigns a side to the combined
occurrence process.

## Exact feature allowlists

### Re-hedge endpoints

1. `signed_mid_change_2s`
2. `signed_mid_change_5s`
3. `signed_tick_imbalance_2s`
4. `signed_tick_imbalance_5s`
5. `side_boundary_proximity_2s`
6. `side_boundary_proximity_5s`
7. `side_prior_boundary_touch_2s`
8. `side_prior_boundary_touch_5s`
9. `realized_volatility_10s`
10. `spread_at_anchor`
11. `absolute_state_start_displacement`
12. `signed_state_start_displacement`

### Unlock occurrence

1. `absolute_mid_change_2s`
2. `absolute_mid_change_5s`
3. `absolute_tick_imbalance_2s`
4. `absolute_tick_imbalance_5s`
5. `range_width_2s`
6. `range_width_5s`
7. `range_width_10s`
8. `either_prior_boundary_touch_2s`
9. `either_prior_boundary_touch_5s`
10. `realized_volatility_10s`
11. `spread_at_anchor`
12. `absolute_state_start_displacement`

No other M4 column may enter the model matrix. In particular, the M4
retracement fraction is excluded: its holdout finding was inconclusive and its
normalization becomes undefined when the prior range is zero. This decision is
made before M5-003 fitting.

`spread_at_anchor` is deliberately retained as a low-variance microstructure
control; its scale and variance must be published and L2 may shrink it.
Absolute and signed state-start displacement are also deliberately retained
together for re-hedge: the signed term represents direction while the absolute
term permits a V-shaped magnitude contribution. They are not treated as
duplicate linear predictors.

## Feature definitions

Let `m_0` and `m_1` be the first and last mid in a rolling window, `s` the
re-hedge sign, and `d_j = m_j - m_{j-1}`.

- Mid change: `m_1 - m_0`; signed re-hedge change multiplies this by `s`;
  unlock takes its absolute value.
- Tick imbalance:
  `(count(d_j>0) - count(d_j<0)) / count(d_j)`. Re-hedge multiplies by `s`;
  unlock takes the absolute value.
- Range width: `max(mid) - min(mid)`.
- Boundary proximity: `(m_1-low)/(high-low)` for Sell and
  `(high-m_1)/(high-low)` for Buy. A zero-width range is assigned the
  pre-defined neutral value `0.5`; this is part of the feature definition, not
  missing-value imputation.
- Prior-boundary touch: sequence mid reaches or breaks the prior upper
  boundary for Sell or prior lower boundary for Buy strictly before the
  anchor. Unlock uses the logical OR of upper and lower touches.
- Realized volatility: `sqrt(sum(d_j^2))`.
- Spread: canonical forward-filled Ask minus Bid at the last tick at or before
  the anchor.
- State-start reference: last observed mid at or before the M2 interval start,
  provided no excluded gap lies between that tick and the start. Displacement
  is current mid minus reference mid; absolute and signed variants follow
  their names.

## Missingness and exclusion accounting

A feature is invalid when:

- its full window precedes cohort tick support;
- a required rolling, prior, or sequence subwindow lacks its minimum ticks;
- its lookback crosses an excluded coverage gap;
- its state-start reference is unavailable or separated by a gap;
- its current canonical Bid/Ask snapshot is unavailable.

Any invalid allowlisted feature removes that bin from every model comparison
for that endpoint. The audit must report bin and target counts by cohort,
date, split, endpoint, reason, and target label. Overlapping reasons are
reported both in a reason matrix and in a deterministic first-reason
waterfall.

The known internal generic-window precheck is:

```text
2s + 5s + 10s windows:       501 bins, 0 targets removed
adding a 500ms price window: 9,924 bins, 48 targets removed in total
```

These counts justify excluding sub-second price windows from the primary
allowlist. They are not the final joint-valid count: H2 disjoint subwindows and
the state-start reference can add exclusions. The implementation must publish
and reconcile the final count before any fit; it must not hard-code 501 as the
final cohort attrition.

A full-allowlist pre-fit support audit measured 937 removed bins and 3 removed
targets across the current internal one-second primary support. These are
expected audit values, not a substitute for implementation accounting. The
implementation must recompute them, report endpoint-specific counts, and stop
if the aggregate values do not reconcile.

## Models

All models are endpoint-specific discrete-time Bernoulli hazards.

- `A_common`: exact frozen M5-002 state-age probability. It is never refit and
  remains the provenance baseline.
- `A_level`: frozen `logit(A_common)` plus one unpenalized intercept fitted on
  development. It measures level transport only and is non-inferential.
- `A_dev`: empirical state-age hazard refit on the exact endpoint-specific,
  joint-valid M5-003 development bins with the same registered age grid and
  Jeffreys smoothing `alpha=0.5` as M5-002:
  `[0,1)`, `[1,2)`, `[2,3)`, `[3,5)`, `[5,10)`, `[10,20)`, `[20,30)`,
  `[30,60)`, and `[60,+inf)`. Unlock primary inference uses only the five
  floor-eligible buckets beginning at age five. The grid and smoothing are
  fixed; there is no bucket or smoothing selection.
- `B`: unweighted logistic hazard with an unpenalized intercept and exactly the
  endpoint price allowlist. State age is forbidden.
- `C_dev`: fixed `logit(A_dev)` as a unit-coefficient offset plus exactly the
  endpoint price allowlist. The offset has no free coefficient and `C_dev` has
  no free intercept. This prevents either level or age-shape repair from being
  called price information.

No class weighting, interaction search, nonlinear tree/boosting model, or
automatic feature selection is allowed.

Every active evaluation bucket must have positive exposure in the
corresponding training fold. A zero-exposure training bucket stops the run
before price fitting; adaptive bucket merging, `A_common` fallback, and
holdout-informed repair are forbidden.

## Development-only preprocessing and regularization

Every cross-validation split is `GroupKFold(n_splits=5)` grouped by
`interval_id`. Rows are sorted deterministically before splitting. The
cross-validation group is identical to the inference/bootstrap cluster.

Within each training fold:

- `A_dev` is fit only from training-fold interval clusters and its validation
  probabilities use those training-fold bucket parameters;
- continuous and binary features are centered by the training-fold mean and
  divided by the training-fold standard deviation;
- a zero standard deviation is replaced by one without dropping the feature;
- validation-fold values never affect transformations;
- no imputation is performed.

After selecting regularization, `A_dev`, transformations, and price models are
refit once on all development rows and frozen before 2026-07-24 is loaded for
evaluation.

B and `C_dev` use L2 regularization on price coefficients only:

```text
lambda ∈ {0.0001, 0.001, 0.01, 0.1, 1, 10}
```

The CV score is mean per-interval Bernoulli log likelihood: bin log
likelihoods are summed within interval, then averaged across intervals. Select
the largest lambda within one standard error of the best mean score. Ties
therefore choose stronger regularization. B and `C_dev` select lambda
separately by endpoint. No random search or post-holdout retuning is permitted.

The frozen model manifest must hash the development cohort and joint-valid row
IDs, `A_dev` bucket parameters, every model intercept that exists,
preprocessing parameters, selected lambdas, price coefficients, allowlists,
and model contracts. These hashes must be identical whether 2026-07-24 is
available or absent.

Because four development sessions cannot identify between-session variance,
the implementation must also run a four-fold leave-one-session-out diagnostic.
Each fold refits `A_dev`, preprocessing, lambda selection, B, and `C_dev`
without the held-out session. Lambda selection is nested GroupKFold using only
the remaining training-session intervals. This diagnostic reports the session
spread of `C_dev - A_dev`; it cannot select a model, alter the frozen
full-development fit, or create a verdict.

## Inference and multiplicity

For interval `i` and model `M`, define:

```text
LL_i(M) = sum of Bernoulli bin log likelihoods in interval i
```

All model comparisons are paired by interval. Bootstrap 5,000 deterministic
draws of `interval_id` clusters with seed base 5003.

The single headline comparison for each endpoint is:

```text
C_dev - A_dev at the one-second anchor
```

The three endpoint headlines form one family. Family-wise alpha is 0.05 using
Bonferroni simultaneous one-sided cluster-bootstrap lower bounds
(`alpha/3 = 0.0166667` per endpoint). Ordinary 95% intervals are also
published but cannot create a supported verdict.

Required secondary families are:

- `C_dev - B`, three endpoints, Bonferroni `alpha/3`;
- four `C_dev` feature-group ablations per endpoint, 12 comparisons, Bonferroni
  `alpha/12`;
- 500 ms anchor `C_dev - A_dev`, three endpoints, Bonferroni `alpha/3`,
  non-gating.

Calibration, coefficients, event rank, and individual features are descriptive
only and receive no inferential verdict.

`A_level - A_common` (level transport) and `A_dev - A_level` (shape transport)
must also be published, but are descriptive diagnostics outside every
multiplicity family. Effect magnitudes must not be compared across unlock and
re-hedge endpoints because their estimands, timer-floor support, and base rates
differ.

The interval-cluster bootstrap is conditional on the observed sessions and
does not estimate between-session population variance. Development
leave-one-session-out and external per-session results must be published
alongside pooled results.

## Required ablations

Refit `C_dev` after removing exactly one registered group:

- re-hedge: `motion`, `boundary`, `state_path`,
  `volatility_liquidity`;
- unlock: `magnitude_motion`, `boundary_magnitude`, `state_path`,
  `volatility_liquidity`.

Each reduced model uses the full `C_dev` model's selected lambda.
Hyperparameters are not reselected. The paired metric is
`full C_dev - ablated C_dev`.

## Decision rules

Development and 2026-07-24 produce diagnostics only. Before external
evaluation, report status is:

```text
pipeline_frozen_external_pending_zero_validated_price_results
```

Only 2026-07-27..29 may produce an endpoint verdict. External evidence that
price adds information requires:

1. mean `C_dev - A_dev > 0`; and
2. its family-wise one-sided lower bound is greater than zero.

If the mean is positive but the family-wise bound is not, the result is
`weak/inconclusive`. If the entire ordinary 95% interval is non-positive, the
price increment is `rejected for this design`. None of these labels is a
tradeable-edge statement or evidence about broader session populations.
Retrospective development and internal reuse diagnostics cannot satisfy or
change this gate.

The observed 2.1x development/holdout base-rate difference is expected to
attenuate richer-model paired increments by roughly 7% in the existing
intercept-shift diagnostic. This is a relative diagnostic, not `0.07`
log-likelihood units and not a decision margin. The exact diagnostic method
and estimate must be published. M5-003 may reproduce it only as a
development-label stress test using the fixed intercept shift `-log(2.1)`;
holdout-label recalibration is forbidden even as a diagnostic. A null of
approximately that relative magnitude is not evidence of absence.

## Future outputs and merge gate

Implementation, when separately authorized, may create local:

- `m5_003_feature_audit.parquet`;
- `m5_003_joint_valid_design_matrix.parquet`;
- `m5_003_predictions.parquet`.

Committed outputs will be aggregate Markdown/JSON reports and deterministic
hashes only.

An M5-003 implementation may merge with supported, null, inconclusive, or
rejected price findings if:

- immutable hashes match and M2–M5-002 outputs are unchanged;
- `A_common`/`A_level`/`A_dev`/B/`C_dev` use identical endpoint-specific
  evaluation bins;
- unlock floor conditioning and all exclusions reconcile;
- development-only `A_dev`, preprocessing, GroupKFold, leave-one-session-out
  diagnostics, and frozen model hashes are proven;
- parameter hashes are unchanged by the presence or absence of 2026-07-24;
- every registered comparison, ablation, and multiplicity family is reported;
- retrospective, internal-reuse, and external roles remain separated;
- tests, privacy, determinism, and CI pass;
- no P/L optimization or tradeable-edge conclusion appears.

Null price findings are valid research results and do not block merge.
