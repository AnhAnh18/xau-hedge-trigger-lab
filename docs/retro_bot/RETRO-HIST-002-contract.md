# RETRO-HIST-002 Contract

Status: owner-authorized bounded RETRO-HIST lifecycle/adapter milestone,
opened after RH-001 on 2026-08-03. This is a new contract and does not reopen
RB-008 through RB-019.

## Objective

Provide a hash-verified stream adapter and deterministic lifecycle engine for
the retained XAUUSD population. The engine reconstructs observed lifecycle
labels for diagnostics while exposing a separate causal state/action path for
later autonomous replay. RH-002 does not select a trigger, claim
profitability, or use observed future events as autonomous inputs.

## Source boundary

Use exactly the RH-001 receipt and its parent RETRO-003 objects: nine report
aliases, 39 tick aliases, the pinned manifest digests, and the server population
`[2025-11-01 00:00:00, 2026-07-31 00:00:00)`. The adapter resolves only the
receipt's opaque run labels below the fixed quarantine root. No source,
August M5 data, journal, cache, credential, `.ex5`, or live/MT5 surface may be
added.

RH-002 reads report `positions` and `open_positions` fields already allowed by
RH-001. Every report and tick object hash in the two manifests must be checked
before parsing or streaming. Its tick adapter reads only `time_utc`, `bid`,
and `ask` from CSV chunks, validates them, and yields one typed quote at a
time; raw ticks are never retained or printed.

## Lifecycle semantics

- Quantity parsing, identity deduplication, close precedence, conflict
  handling, and population boundaries inherit RH-001 exactly. A quantity or
  side/open-time disagreement for one position ID is unsupported partial-close
  semantics in RH-002: the ID is retained only as a conservative censored
  interval marker and contributes no definite event. RH-002 never infers a
  partial fill from snapshot differences; the marker exists solely so the
  affected lifecycle state is explicitly `CENSORED` rather than silently
  omitted.
- Closed intervals produce observed `OPEN` and `CLOSE` labels. Carry-in
  positions bootstrap the observed state at the population start; they do not
  create an artificial in-window open event. Open-ended positions are
  right-censored and cannot create a completed close label.
- Intervals are `[open_time, close_time)`. Open at the end boundary and close
  at the start boundary are excluded; carry-in requires `open_time < start` and
  `close_time > start`. At equal timestamps, labels sort by
  `(time, close-before-open, side buy-before-sell, position_id)`; collisions
  are counted as diagnostics but do not change this deterministic order.
- Observed labels update only the `oracle_state`. The `policy_state` changes
  only when an explicit causal action is supplied by a later policy engine.
  Removing or changing oracle labels must leave policy state and actions
  unchanged.
- Allowed aggregate state labels are `FLAT`, `ONE_BUY`, `ONE_SELL`,
  `HEDGED_1X1`, `UNBALANCED_HEDGE`, `MULTI_POSITION`, and `CENSORED`.
  `CENSORED` takes precedence whenever an unresolved conflict or unsupported
  partial-close record affects the current interval; otherwise classification
  is based on active leg count and exact fixed8 quantity equality.

## Tick time and quote rules

- Report timestamps are naive broker-server timestamps and are not converted in
  RH-002. Tick timestamps are parsed as timezone-aware UTC values from
  `time_utc`.
- Coverage is reported under the fixed `utc_plus_2` and `utc_plus_3` scenarios.
  The accepted tick envelope is the half-open union
  `[start_server - 3h - 60s, end_server - 2h + 60s)`; no tick outside this
  envelope is used. A later contract must define any exact event-to-tick clock
  mapping.
- `ask >= bid` is valid; NaN, non-finite, non-positive, crossed, malformed,
  or invalid-time rows are rejected and counted. Equal timestamps are accepted
  and counted as duplicates; any timestamp decrease across aliases/chunks is a
  fatal source-order failure.

## Causal policy API

The policy path uses typed `PolicyState` and explicit `CausalAction` records:
`action_id`, `time_ns`, `side`, `quantity_fixed8`, and `kind`. Actions must be
strictly increasing by `(time_ns, action_id)`, positive fixed8 quantity, and a
valid state transition; duplicate or invalid actions fail closed without a
partial state update. RH-002 initializes the policy path from a declared FLAT
seed and emits no actions. `OracleLabel` records are separate diagnostics and
are never accepted by the policy API. A label-removal/toggle test must prove
policy state and action output are byte-identical.

## Output and gates

Retain only fixed-schema aggregate state/event counts, ambiguity/conflict/
censor counts, tick coverage bands, source digests, deterministic fingerprints,
`raw_rows_printed=false`, and `M5_FIREWALL_ATTESTATION_V1`. No raw rows,
position IDs, timestamps, prices, tickets, comments, private paths,
credentials, or detailed timelines may be printed or committed.

Acceptance requires synthetic lifecycle/action-isolation tests, tick validation
tests, source manifest/path tamper tests, focused and full regression suites,
compile/privacy/firewall checks, deterministic aggregate reruns, independent
review, fix cycles, and a fresh re-review with `VERDICT: PASS`.

Stop on authorization/hash/path failure, invalid quantity or timestamp
semantics, lookahead/oracle contamination, state conservation failure,
out-of-order/crossed/non-finite quotes, raw/privacy leak, M5 access, or any
request for trigger selection, profitability, or live execution.
