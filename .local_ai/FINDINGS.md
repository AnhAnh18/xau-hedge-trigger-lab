# Findings

## F-001 — Alternating hedge state machine

Status: Confirmed  
Confidence: 95%

Evidence:

- One-month MT5 trade reports
- Position and deal ordering

Finding: The strategy generally alternates between ONE_BUY / ONE_SELL and HEDGED with one Buy and one Sell. When a side is closed, the next order generally restores that same side.
