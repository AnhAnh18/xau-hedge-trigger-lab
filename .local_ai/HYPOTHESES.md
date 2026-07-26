# Hypotheses

## H-001 — Re-hedge at rolling boundaries

Status: Tested — confounded/inconclusive

Prediction:

- Sell re-entry occurs near the upper edge of a recent mid-price range.
- Buy re-entry occurs near the lower edge.

Pre-registered windows: 2 s, 5 s, 10 s, 30 s, and 60 s.

Primary population: positives with at least 7 seconds of pre-transition
state age and eligible control risk time. The pooled all-positive result is
descriptive only. Results must also be reported in the fixed state-age strata
0–6 s, 7–10 s, 10–30 s, 30–60 s, and >60 s.

The model-ready state-age predictor is clipped to `[0, 60]` seconds. The raw
lineage-derived value remains available only in the audit output.

Acceptance: At least two adjacent holdout windows must have paired
positive-event cluster-bootstrap intervals above zero. A pooled result cannot
override a null result in the control-supported population.

## H-002 — Re-hedge after a prior-boundary touch and retracement

Status: Tested — inconclusive

Prediction:

- Before a sell re-entry, price touches or breaks a prior upper boundary and
  then retraces before the event.
- Before a buy re-entry, price touches or breaks a prior lower boundary and
  then bounces before the event.

Pre-registered sequence windows: 1 s, 2 s, and 5 s.

For each sequence window `w`, calculate the prior boundary only from
`[t-2w, t-w)`. Test the causal sequence on `[t-w, t]`: the side-appropriate
boundary must be touched before `t`, followed by a non-zero retracement or
bounce before `t`. Report boundary-touch, post-touch retracement, and the joint
sequence separately.

Direction is pre-registered: positives are expected to have a higher
side-appropriate boundary-touch rate than matched controls. Retracement
fractions are upper-tail winsorized at the development control-supported
risk-set p99 separately for each pre-registered window. The resulting caps are
applied unchanged to holdout; holdout data never refits a cap.

Acceptance: H2 must not be the arithmetic complement of H1. The joint sequence
requires coherent evidence in at least two adjacent holdout windows.

## H-003 — Unlock direction follows signed momentum

Status: Tested — supported but timing-sensitive

Prediction:

- Unlock-to-Buy is associated with positive pre-event mid-price momentum.
- Unlock-to-Sell is associated with negative pre-event mid-price momentum.

Pre-registered windows: 500 ms, 1 s, and 2 s.

Acceptance: At least two adjacent holdout windows must have paired
positive-event cluster-bootstrap intervals above zero. Report the effect in
price units relative to the median spread and do not interpret the association
as a standalone tradeable edge.
