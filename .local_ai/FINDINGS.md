# Findings

## F-001 — Alternating hedge state machine

Status: Confirmed
Confidence: 95%

Evidence:

- One-month MT5 trade reports
- Position and deal ordering

Finding: The strategy generally alternates between ONE_BUY / ONE_SELL and HEDGED with one Buy and one Sell. When a side is closed, the next order generally restores that same side.

## F-002 — Alternating hedge loop dominates the observed lifecycle

Status: Confirmed
Confidence: High

Evidence:

- 7,086 unique position lifecycles
- 6,276 classified unlock events
- 6,277 classified re-hedge events
- Multi-position and unbalanced states retained as explicit categories

Finding: The dominant observed behavior alternates between an equal-sided hedge and one-sided exposure. The one-event re-hedge difference is explained by the report boundary: the reconstructed timeline ends with a re-hedge.

Limitations: 630 same-second events have ambiguous order at report resolution and require tick-based analysis for possible disambiguation.

## F-003 — Legacy day-level risk accounting is not calendar-causal

Status: Confirmed
Confidence: High

Evidence:

- 2,096 M2 intervals touch observed tick coverage.
- Legacy start-date accounting reports 47,501 seconds on 2026-07-23 and
  81,911 seconds on 2026-07-24.
- Interval 13321 crosses midnight and contains the only observed coverage gap longer than
  60 seconds: 3,720.501 seconds.

Finding: Grouping full interval duration by start date moves after-midnight
exposure into the prior day and treats an unobserved coverage gap as actionable
risk. M5 must use clipped, midnight-split, gap-excluded tradeable time.

## F-004 — Current development and holdout coverage is asymmetric

Status: Confirmed
Confidence: High

Evidence:

- Development tick coverage begins just after server time 12:00.
- Holdout includes server hours 01–23.
- Canonical common-hour support is server time 12:00–24:00.

Finding: Full-day development/holdout model comparison is not supported by the
current data. Restricting both dates to common hours aligns coverage support
but does not align behavior: after right-censor and left-truncation handling,
the development target density remains 2.100x holdout. Primary M5 v1 inference
is fixed to server hours 12:00–24:00 and does not generalize to the Asian
session.

Limitation: Development is Thursday, holdout is Friday, and pre-registered
external validation is Monday through Wednesday. Day of week is perfectly
confounded with the split.

## F-005 — M2 event-to-event intervals omit the final observed state tail

Status: Confirmed
Confidence: High

Evidence:

- Final lifecycle event: 2026-07-24 23:51:39.
- State after the final event: `HEDGED_1X1`.
- Tick coverage ends at 2026-07-24 23:56:57.758.
- Unrepresented observed tail: 318.758 seconds.

Finding: Canonical M2 correctly stops intervals at the final event, but M5 risk
support must append an explicitly synthetic right-censored interval through
tick coverage end. The tail contributes exposure and no terminal or competing
event.

## F-006 — Zero-duration re-hedges are outside the risk-bin estimand

Status: Confirmed
Confidence: High

Evidence:

- 34 zero-duration intervals occur in tick coverage.
- All 34 terminate in a re-hedge target; 30 occur in common hours.

Finding: These events are real but cannot occupy a complete 1-second or
500-millisecond causal risk bin. They remain in accounting and are excluded
from primary M5 inference under the structural support limitation tracked in
issue #3.

## F-007 — Unlock has an approximate six-second dwell floor

Status: Confirmed as an approximate floor
Confidence: High

Evidence:

- 6,275 of 6,276 M2 `HEDGED_1X1` intervals ending in unlock last at least six
  seconds; the sole exception lasts one second.
- `ONE_BUY -> REHEDGE_SELL` has 32.555% of events below six seconds.
- `ONE_SELL -> REHEDGE_BUY` has 30.820% of events below six seconds.
- 333 hedged competing additional-position endpoints exist; 154 (46.246%)
  occur below six seconds, so cause-specific censoring is age-dependent.

Finding: Unlock behavior is consistent with an approximately
six-second minimum hedged dwell, while re-hedge behavior has no comparable
floor. The single month-wide exception is retained, so this is not claimed as
an absolute structural zero.

M5-002 verification: All five July 20–24 calendar sessions contain zero unlock
events below six seconds in M2. The month-wide one-second exception remains
published. On the causal bin contract, events occurring at six seconds are
represented by the `[5,6)` predictor-at-bin-start bucket, so that bucket is
correctly non-zero; `[0,5)` remains zero-event in internal development.

## F-008 — State age improves internal holdout occurrence likelihood

Status: Internal pilot complete; external validation pending
Confidence: Moderate

Evidence:

- At both 1-second and 500-millisecond widths, frozen development age buckets
  improve primary cause-specific occurrence likelihood over the constant
  baseline for all three endpoints.
- A holdout-label oracle for the old conditional calculation remains negative
  for all endpoints (`-0.320249`, `-0.430092`, and `-0.060804` at one second).
  It therefore cannot score age-only timing quality.
- Results are stable across smoothing alpha 0.0, 0.5, and 1.0.

Finding: State age improves whether-transition-occurs likelihood within
observed risk support. The strongest interpretable component is transport of
the approximate unlock timer floor. The former within-interval conditional
verdicts are withdrawn because each event-to-event interval ends at its
outcome, making the age-only candidate risk set outcome-truncated.

Limitation: This is an internal Thursday-to-Friday pilot. It makes no
tradeable-edge claim, occurrence likelihood remains base-rate-sensitive, and
M5 cannot close before the pre-registered 2026-07-27 through 2026-07-29
external evaluation.

## F-009 — Session context explains part, but not all, of the internal package increment

Status: Review-remediated internal diagnostic; independent re-review and
external validation pending
Confidence: Preliminary

Evidence at the one-second 2026-07-24 internal-reuse diagnostic:

| Endpoint | A_session−A_dev | C_session−A_session | C_shape−A_session |
| --- | ---: | ---: | ---: |
| rehedge_buy_occurrence | 0.065349 | 0.081396 | 0.009696 |
| rehedge_sell_occurrence | 0.132032 | 0.039308 | 0.030655 |
| unlock_occurrence | 0.148346 | 0.080685 | 0.036852 |

The ordinary 95% interval for the rehedge-sell residual full-price increment
crosses zero (`-0.011776` to `0.091948`). The two other full-package intervals
are positive internally. Required ablations remain correlated-group
diagnostics and are not additive or causal decompositions.

Finding: Under the amended model ladder, session-block transport exceeds the
residual full-price increment for two of three endpoints on the single
internal-reuse session. The residual price package does not disappear, but it
cannot be interpreted as pure price action: it may still encode market regime,
operating schedule, volatility, liquidity, and state path. The reduced shape
diagnostic is materially smaller than the full package for buy and unlock.

Limitation: These values motivated and were produced by a review-driven
internal remediation. They cannot support, reject, or validate an endpoint.
The server timezone is inferred rather than confirmed, a fresh Claude review
is required before merge, and only the frozen 2026-07-27..29 evaluation may
create the M5-003 headline verdicts. No result establishes a tradeable edge.
