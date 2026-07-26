# M5-003 Causal Price-Increment Preregistration

Status: Registered on 2026-07-26; implementation and fitting have not started.

Machine-readable contract:
`data/m5_003_preregistration.json`.

## Scope

M5-003 asks whether causal price information improves endpoint-specific
occurrence likelihood beyond the frozen M5-002 state-age baseline.

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

Within each endpoint and split, A, B, and C must use exactly the same bin IDs.
There is no imputation and no model-specific complete-case cohort.

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

This excludes 3,115 internal-development bins with zero target events and
removes the structural timer-floor information from the A-versus-B
comparison. An unlock interval ending before age five is outside this
conditional estimand; it is audited as `unlock_before_floor_excluded`, never
relabeled as a negative or censored observation. Frozen A_common probabilities
are subsetted without refitting or renormalization.

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
gate, or promote B/C. Their inclusion in development cannot be reconsidered
after a price result is seen.

The 2026-07-24 session is excluded from preprocessing, feature selection,
cross-validation, regularization selection, fitting, and calibration. It is a
locked internal reuse diagnostic, not untouched price confirmation: M4 already
inspected its price hypotheses and labels.

Only the pre-registered 2026-07-27..29 sessions can satisfy the external gate.
They remain untouched until all M5-003 transformations, coefficients,
regularization values, feature groups, and decision rules are frozen.

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

Any invalid allowlisted feature removes that bin from all A/B/C comparisons for
that endpoint. The audit must report bin and target counts by cohort, date,
split, endpoint, reason, and target label. Overlapping reasons are reported
both in a reason matrix and in a deterministic first-reason waterfall.

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

## Models

All models are endpoint-specific discrete-time Bernoulli hazards.

- `A_common`: exact frozen M5-002 state-age probability. It is never refit.
- `B`: unweighted logistic hazard with an unpenalized intercept and exactly the
  endpoint price allowlist. State age is forbidden.
- `C`: frozen `logit(A_common)` as a unit-coefficient offset plus exactly the
  endpoint price allowlist. The offset has no free coefficient and C has no
  free intercept, preventing an intercept-only update from being called price
  information.

No class weighting, interaction search, nonlinear tree/boosting model, or
automatic feature selection is allowed.

## Development-only preprocessing and regularization

Every cross-validation split is `GroupKFold(n_splits=5)` grouped by
`interval_id`. Rows are sorted deterministically before splitting. The
cross-validation group is identical to the inference/bootstrap cluster.

Within each training fold:

- continuous and binary features are centered by the training-fold mean and
  divided by the training-fold standard deviation;
- a zero standard deviation is replaced by one without dropping the feature;
- validation-fold values never affect transformations;
- no imputation is performed.

After selecting regularization, transformations are refit once on all
development rows and frozen.

B and C use L2 regularization on price coefficients only:

```text
lambda ∈ {0.0001, 0.001, 0.01, 0.1, 1, 10}
```

The CV score is mean per-interval Bernoulli log likelihood: bin log
likelihoods are summed within interval, then averaged across intervals. Select
the largest lambda within one standard error of the best mean score. Ties
therefore choose stronger regularization. B and C select lambda separately by
endpoint. No random search or post-holdout retuning is permitted.

## Inference and multiplicity

For interval `i` and model `M`, define:

```text
LL_i(M) = sum of Bernoulli bin log likelihoods in interval i
```

All model comparisons are paired by interval. Bootstrap 5,000 deterministic
draws of `interval_id` clusters with seed base 5003.

The single headline comparison for each endpoint is:

```text
C - A_common at the one-second anchor
```

The three endpoint headlines form one family. Family-wise alpha is 0.05 using
Bonferroni simultaneous one-sided cluster-bootstrap lower bounds
(`alpha/3 = 0.0166667` per endpoint). Ordinary 95% intervals are also
published but cannot create a supported verdict.

Required secondary families are:

- `C - B`, three endpoints, Bonferroni `alpha/3`;
- four C feature-group ablations per endpoint, 12 comparisons, Bonferroni
  `alpha/12`;
- 500 ms anchor `C - A_common`, three endpoints, Bonferroni `alpha/3`,
  non-gating.

Calibration, coefficients, event rank, and individual features are descriptive
only and receive no inferential verdict.

## Required ablations

Refit C after removing exactly one registered group:

- re-hedge: `motion`, `boundary`, `state_path`,
  `volatility_liquidity`;
- unlock: `magnitude_motion`, `boundary_magnitude`, `state_path`,
  `volatility_liquidity`.

Each reduced model uses the full C model's selected lambda. Hyperparameters are
not reselected. The paired metric is `full C - ablated C`.

## Decision rules

For an endpoint, internal evidence that price adds information requires:

1. mean `C - A_common > 0`; and
2. its family-wise one-sided lower bound is greater than zero.

If the mean is positive but the family-wise bound is not, the result is
`weak/inconclusive`. If the entire ordinary 95% interval is non-positive, the
price increment is `rejected for this design`. None of these labels is a
tradeable-edge statement.

The future external verdict applies the same frozen one-second comparison and
family-wise rule to 2026-07-27..29. Internal 24 July and retrospective
20–22 July cannot satisfy that gate.

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
- A/B/C use identical endpoint-specific bins;
- unlock floor conditioning and all exclusions reconcile;
- development-only preprocessing, GroupKFold, and frozen A hashes are proven;
- every registered comparison, ablation, and multiplicity family is reported;
- retrospective, internal-reuse, and external roles remain separated;
- tests, privacy, determinism, and CI pass;
- no P/L optimization or tradeable-edge conclusion appears.

Null price findings are valid research results and do not block merge.
