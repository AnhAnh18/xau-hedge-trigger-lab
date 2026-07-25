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
