# RETRO-BOT-006: Causal Feature and Trigger Contract

Status: owner-authorized follow-on to RB-009 on 2026-08-03; not an M5 task.

## Purpose

Freeze the small causal feature vocabulary and rule operators that later
unlock/re-hedge candidates may use. RB-010 does not fit, select, or evaluate a
candidate and does not read observed future labels in the policy path.

## Allowed feature vocabulary

Only values available at or before the decision tick are allowed:

- `state_age_seconds`;
- `price_increment` and `adverse_excursion` from causal bid/ask history;
- `spread_points` and `tick_rate`;
- `quote_gap_seconds`;
- `session_bucket` and registered clock id;
- autonomous state and side from RB-009.

Feature definitions are fixed: choose the latest valid tick with timestamp
`<= decision_time - 60 seconds` as the lookback anchor. `price_increment` is
current mid minus anchor mid. Over the half-open interval from anchor through
the current tick, `adverse_excursion` is `max(0, anchor_mid - min(mid))` for
`ONE_BUY` and `max(0, max(mid) - anchor_mid)` for `ONE_SELL`;
`spread_points` is `(ask-bid)/0.01` at the current tick; `tick_rate` is valid
ticks in the previous 60 seconds divided by 60; `quote_gap_seconds` is the
elapsed time since the immediately prior valid tick; and `session_bucket` is
UTC-hour buckets `asia` (00-07), `europe` (08-15), and `us` (16-23). The
current tick is included, duplicate/out-of-order ticks are rejected, and
same-time permutations are not repaired.

Observed unlock, close, re-hedge, terminal, future mark, P/L, ticket,
comment, account, journal, and `.ex5` fields are prohibited. Oracle labels may
exist only in a separate diagnostic object.

## Frozen DSL

Operators are `always`, `never`, `ge`, `gt`, `le`, `lt`, and `between`.
The exact numeric parameter grid is `{0, 1, 5, 10, 60, 300, 900, 3600}` in
the feature's declared units; `between` is inclusive on both endpoints.
Categorical domains are `session_bucket={asia,europe,us}`,
`clock_id={utc_plus_2,utc_plus_3,eu_dst_2025_2026}`,
`state={HEDGED,ONE_BUY,ONE_SELL}`, and `side={buy,sell}`. `always` and `never`
are parameterless. Numeric operators cannot target categorical features, and
categorical clauses use only their registered domain values. A rule
has at most 3 clauses, combines them with logical AND, and ties are resolved
by rule id. Configuration is immutable after a run starts; unknown features,
operators, values, or deep mutations fail closed. Missing/non-finite feature
values produce `feature_missing` for the whole snapshot and never a default
action.

`candidate_action` carries an RB-009 action kind and mapped side. `CLOSE_BUY`
and `CLOSE_SELL` are legal only in `HEDGED`; `OPEN_SELL` only in `ONE_BUY`;
`OPEN_BUY` only in `ONE_SELL`. Illegal mappings become `invalid_transition`.

The RB-008 config digest
`26fec4baa2b8e2680cc17afaad299bbbb00afba32810865ac60bf28eb2e49ebf` and
both source manifest digests are inherited unchanged; no new source, raw
path, August/M5 data, or observed event field may enter feature construction.

## Acceptance

Synthetic tests prove feature timestamps are causal, post-decision fields are
rejected, missing data fail closed, the DSL grid is immutable, oracle-label
injection does not change features, and aggregate feature/rule schemas are
privacy-safe. RB-008 digests and the M5 firewall remain locked. No fitting,
threshold selection, profitability, or live execution is permitted.
