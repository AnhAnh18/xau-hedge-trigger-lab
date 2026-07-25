# Hypotheses

## H-001 — Re-hedge at rolling extremes

Status: Untested

Prediction:

- Sell re-entry occurs near the upper edge of a recent price range.
- Buy re-entry occurs near the lower edge.

Required data: trade events, millisecond Bid/Ask ticks, and negative samples while the account remains one-sided.

Acceptance: Event samples must differ materially from non-event samples on unseen data.
