# Roadmap

## M0 — Project Bootstrap
- Repository structure
- Data privacy rules
- Project documentation
- Initial issues

## M1 — Data Foundation
- Parse MT5 reports
- Parse tick CSV
- Validate time zones and price alignment
- Produce normalized datasets

## M2 — State Reconstruction
- Reconstruct FLAT / ONE_BUY / ONE_SELL / HEDGED
- Classify unlock and re-hedge events
- Validate invariants

## M3 — Trigger Dataset
- Align events to ticks
- Generate features
- Generate negative samples

## M4 — Trigger Hypotheses
- Rolling extreme
- Extreme plus retracement
- Momentum reversal
- P/L threshold
- Hybrid rules

## M5 — Replay Engine
- Tick-by-tick simulation
- Bid/Ask execution
- State similarity metrics

## M6 — Shadow Observer
- Read-only MT5 observer
- Compare predictions with original account

## M7 — EA Prototype
- Modular trigger implementation
- Out-of-sample backtesting
