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
- Interval 13321 crosses midnight and contains the only tick gap longer than
  60 seconds: 3,720.501 seconds.

Finding: Grouping full interval duration by start date moves after-midnight
exposure into the prior day and treats the maintenance break as actionable
risk. M5 must use clipped, midnight-split, break-excluded tradeable time.

## F-004 — Current development and holdout coverage is asymmetric

Status: Confirmed
Confidence: High

Evidence:

- Development tick coverage begins just after server time 12:00.
- Holdout includes server hours 01–23.
- Canonical common-hour support is server time 12:00–24:00.

Finding: Full-day development/holdout model comparison is not supported by the
current data. Full-range summaries are descriptive; primary comparisons must
use common hours until pre-registered external sessions are acquired.
