# RETRO-HIST-003 Contract

Status: bounded RH-003 causal trigger and observed-sizing milestone under the
owner-authorized RETRO-HIST goal. RH-003 reuses the accepted RH-002 source
receipt without expanding the source boundary or reopening the closed
RETRO-BOT synthetic/shadow lane.

## Objective

Define and evaluate a small, frozen vocabulary of causal trigger candidates
over the archived XAUUSD lifecycle. The engine emits only policy decisions from
causal state and tick prefixes. Observed future lifecycle labels and observed
future quantities remain oracle diagnostics and can never affect a decision or
quantity. RH-003 is descriptive and does not claim a selected trigger,
profitability, broker ownership, or a tradeable edge.

## Source boundary

Reuse exactly the RH-002 report/tick receipt, manifests, aliases, opaque run
labels, and population `[2025-11-01 00:00:00, 2026-07-31 00:00:00)`. Verify every
object before opening it. Read only the RH-002 report fields and tick columns;
stream ticks in memory and retain aggregate counts only. No new source,
August M5 data, journal, cache, credential, `.ex5`, private path, or live/MT5
surface is allowed.

## Causal clock and feature rules

- Evaluate both fixed clock scenarios `utc_plus_2` and `utc_plus_3`. A naive
  server timestamp maps to UTC as `utc = server - offset` because the broker
  server clock is UTC plus the scenario offset. This is a diagnostic clock
  scenario, not a DST claim.
- A tick prefix is valid only when timestamps are UTC, strictly increasing,
  finite, positive, and `ask >= bid`; every tick at or before the decision time
  is causal and a future or malformed tick fails closed. Equal timestamps are
  retained in source order but make that feature window unsupported; they are
  never silently collapsed.
- Decisions occur once per valid tick timestamp. A policy can emit at most one
  action for a tick and must advance its state epoch before another action.
  The action time must be strictly greater than the previous policy action
  time. A tick exactly at the decision time is included; a tick after it is not.
- Let `mid=(bid+ask)/2`, `point=0.01`, `anchor` be the latest tick with
  `time <= decision-60s`, and `W` be all valid ticks in the inclusive interval
  `[anchor, decision]`. Then
  `price_increment_points=(mid_last-mid_anchor)/point`,
  `buy_adverse_excursion_points=max(0,(mid_anchor-min(mid_W))/point)`,
  `sell_adverse_excursion_points=max(0,(max(mid_W)-mid_anchor)/point)`,
  `spread_points=(ask_last-bid_last)/point`,
  `tick_count_60s=count(W where time >= decision-60s)`, and
  `quote_gap_seconds=max(decision-time_last, consecutive_tick_gaps within W)`.
  Decimal arithmetic is used until aggregate formatting. A missing anchor,
  duplicate timestamp, `quote_gap_seconds > 6`, or any invalid row in `W`
  yields `support_status=unsupported`; exactly 6 seconds is supported.
- The feature clock, state timestamp, and decision timestamp are retained only
  as aggregate support/timing bands; raw timestamps and prices are never
  printed or committed.

## Frozen candidate vocabulary

The candidate IDs and thresholds are fixed before historical evaluation:

- `hold_only` - never emits an action.
- `close_buy_increment_ge_0` - in a hedged state, close Buy when
  `price_increment_points >= 0`.
- `close_sell_increment_le_0` - in a hedged state, close Sell when
  `price_increment_points <= 0`.
- `close_buy_adverse_ge_10` - in a hedged state, close Buy when
  `buy_adverse_excursion_points >= 10`.
- `close_sell_adverse_ge_10` - in a hedged state, close Sell when
  `sell_adverse_excursion_points >= 10`.
- `rehedge_mirror_active_leg` - in a one-leg state, open the opposite side
  when the causal support gate passes.

No candidate is selected, tuned, or ranked by P/L in RH-003. Illegal state
transitions, multi-position states, and censored states are non-actionable.
Each candidate ID has an independent replay and state epoch; outcomes from
different candidate IDs are never combined or suppressed. Within one candidate
replay, close evaluation precedes re-hedge evaluation and at most one action is
emitted per unique tick timestamp. Candidate IDs are sorted only for aggregate
serialization and deterministic action-digest framing.

## Bootstrap and policy path

The policy path is not initialized from future observed labels. At the lower
population boundary it uses only the RH-002 carry-in snapshot: positions open
before `START_SERVER` and still active at `START_SERVER`, with their exact
fixed8 quantities. Bootstrap precedence is ordered: any censored/ambiguous
record is `CENSORED`; otherwise any active count >= 2 that is not exactly one
Buy and one Sell is `MULTI_POSITION` (including a two-position same-side
snapshot); otherwise no active position is `FLAT`; otherwise exactly one active
Buy or Sell is `ONE_BUY` or `ONE_SELL`; otherwise exactly one active leg per
side is `HEDGED_1X1` or `UNBALANCED_HEDGE` by exact quantity equality.
Only
`HEDGED_1X1`, `UNBALANCED_HEDGE`, `ONE_BUY`, and `ONE_SELL` can emit actions.
Every candidate seed has `epoch=0` and no prior action time; the first valid
tick is eligible subject to support. Each candidate ID owns an independent
policy state and epoch. Candidate
outcomes are never combined into one shared replay. Subsequent policy state
changes come only from that candidate's own actions. Observed events never
mutate any policy state.

## Quantity rule

Every emitted action uses `mirror_active_leg`: a close uses the currently active
quantity on that side, and a one-leg re-hedge opens the opposite side with the
currently active quantity. Quantities are Decimal fixed8 values. Future
observed lots are recorded only in oracle diagnostics and never size policy
actions.

## Oracle isolation and output

An oracle label is `(event kind, side, quantity, observed time)` and is mapped
to UTC as `server - offset` before matching. For each clock and candidate,
labels are drawn from the half-open horizon `[action_time, action_time+30s)`;
the nearest unused label is chosen by `(delta_ns, event_kind_rank, side,
position_id)` after policy actions are consumed in `(decision_time_ns,
action_id)` order. Timing bins are exactly `exact`, `0-1s`, `2-6s`, `7-30s`,
and `unmatched`; direction and quantity matches are counted independently.
`CLOSE` precedes `OPEN` and `buy` precedes `sell`; equal-time labels use the
RH-002 position-id tie key. Adding, removing, reordering, or changing oracle
labels or future quantities must leave the policy decision and action digest
byte-identical. For each candidate/clock pair, the internal action digest is
SHA-256 over the ordered compact JSON action records with exactly the fields
`candidate_id`, `clock_id`, `epoch`, `decision_time_ns`, `kind`, `side`, and
`quantity_fixed8`, using `ensure_ascii=true`, compact separators, insertion
order, and no oracle fields; an empty replay hashes the empty byte string.
`action_id` is the lowercase SHA-256 hex digest of the same seven fields in
the same canonical framing and is used for action ordering at equal nanosecond
times.

The top-level aggregate insertion order is `schema_version`, `case_id`,
`source_validation`, `report_manifest_sha256`, `tick_manifest_sha256`,
`population`, `clocks`, `candidate_ids`, `support_counts`, `outcome_counts`,
`action_counts`, `quantity_bands`, `oracle_diagnostics`, `action_digests`,
`m5_firewall`, `claims`, and `aggregate_sha256`. `schema_version` is integer
`1`, `case_id` is exactly `RETRO-HIST-003`, `population` has exactly
`start_server`, `end_server_exclusive`, `report_alias_count`,
`tick_alias_count`, and `tick_clock_scenarios`, and `candidate_ids` and clock
keys use the order declared in this contract. The fixed aggregate dimensions
are candidate x clock x state x outcome for
`hold/action/unsupported/noneligible/censored/invalid`, candidate x clock x action
side for `CLOSE_BUY/CLOSE_SELL/OPEN_BUY/OPEN_SELL`, candidate x clock x fixed
quantity band for `0.01000000`, `0.02000000`, `0.05000000`, `0.10000000`,
`0.20000000`, `0.30000000`, `1.00000000`, and `other`, plus fixed support
reason map `supported`, `empty_prefix`, `no_anchor`, `duplicate_timestamp`,
`invalid_row`, `quote_gap`, and `state_ineligible`, plus fixed oracle maps with the timing
bins above and `direction_match`, `direction_mismatch`, `quantity_match`,
`quantity_mismatch`, `duplicate_label`, and `unmatched_label`. All keys are
fixed and all values are strict non-negative integers. `source_validation` is
the exact string `accepted_hash_verified_RETRO003_manifest_runs_all_objects`;
`clocks` has exactly `utc_plus_2` and `utc_plus_3`, each with source counter
keys `valid_rows`, `invalid_rows`, `duplicate_timestamps`, `out_of_order`,
`crossed_quotes`, `envelope_excluded_rows`, and `bootstrap_state`;
`support_counts` is candidate x clock x state x support-reason; `outcome_counts`
is candidate x clock x state x outcome; `action_counts` is candidate x clock x
action-kind; `quantity_bands` is candidate x clock x quantity-band; and
`oracle_diagnostics` is candidate x clock with exactly the timing,
direction, quantity, duplicate-label, and unmatched-label keys named above.
`m5_firewall` is exactly `M5_FIREWALL_ATTESTATION_V1`, and `claims` has only
the strict booleans `oracle_used_for_policy`, `raw_rows_printed`, and
`pnl_or_model_selection`, all false. The aggregate contains source digests,
per-clock source counters, these counts, the M5 firewall attestation, and a
self-digest. The self-digest hashes UTF-8 bytes of the compact canonical JSON
aggregate with insertion order, `ensure_ascii=true`, `allow_nan=false`, and no
trailing newline, omitting only `aggregate_sha256`. It
contains no raw rows, IDs, timestamps, prices, tickets, comments, private
paths, credentials, or P/L/model-selection fields. `raw_rows_printed=false`
is mandatory.

## Acceptance gates

Synthetic tests must cover causal prefix/lookahead rejection, quote/order/gap
support gates, frozen candidate legality, Decimal quantity conservation,
oracle-label and future-lot isolation, clock separation, deterministic schema
and digest validation, and the recursive M5/privacy firewall. Focused and full
regression suites, compileall, diff checks, two deterministic historical runs,
and a fresh independent review must pass before commit/push.

Stop on source/hash/path failure, lookahead or oracle contamination, quantity
substitution, unsupported transition, raw/privacy leak, M5 access, or any
request for profitability, tuning, or live execution.
