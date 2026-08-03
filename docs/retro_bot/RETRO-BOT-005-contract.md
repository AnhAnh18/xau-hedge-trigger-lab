# RETRO-BOT-005: Causal Lifecycle and State Engine

Status: owner-authorized follow-on to RB-008 on 2026-08-03; not an M5 task.

## Purpose

Define the autonomous lifecycle state machine used by later RETRO-BOT
milestones. It must advance only from a locked bootstrap seed and
bot-generated causal actions. Observed unlock, close, and re-hedge events are
labels for diagnostics and may not mutate `policy_state`.

## Scope

Use only the RB-008 configuration and its verified source boundary. The
`fixed_warmup_seed` scenario starts in `HEDGED`; the `left_censored` scenario
remains censored and cannot emit autonomous actions. No raw source expansion,
fitting, threshold tuning, paper P/L, live API, credentials, journal, or
`.ex5` access is allowed.

## States and actions

The finite state set is:

- `HEDGED`;
- `ONE_BUY`;
- `ONE_SELL`;
- `TERMINAL`;
- `CENSORED`.

The only autonomous action kinds are `CLOSE_BUY`, `CLOSE_SELL`,
`OPEN_BUY`, `OPEN_SELL`, and `TERMINATE`. An action has a strictly increasing
causal tick/event time, a direction, and a source tag of `policy`; oracle
labels use a separate source tag and are never accepted by the policy-state
transition function.

Allowed transitions are locked as follows:

| Current | Action | Next |
| --- | --- | --- |
| `HEDGED` | `CLOSE_BUY` | `ONE_SELL` |
| `HEDGED` | `CLOSE_SELL` | `ONE_BUY` |
| `ONE_BUY` | `OPEN_SELL` | `HEDGED` |
| `ONE_SELL` | `OPEN_BUY` | `HEDGED` |
| `HEDGED`, `ONE_BUY`, or `ONE_SELL` | `TERMINATE` | `TERMINAL` |

Any opposite, duplicate, same-side, non-increasing, post-terminal, censored,
or
unregistered action is rejected as `invalid_transition`. No transition may
be repaired by sorting or by reading a future observed event.

## Bootstrap and censoring

`fixed_warmup_seed` accepts one immutable conceptual seed snapshot:
`state=HEDGED`, `anchor=window_start`, `quantity=1.0`, and
`first_decision_tick=the first causal tick at or after window_start`. It has no
broker position identity and is explicitly assumption-dependent. The first
decision tick is eligible. `left_censored` initializes as `CENSORED` and
rejects all policy actions until a future contract provides a verified
bootstrap snapshot. A missing/ambiguous bootstrap, invalid clock, or coverage
gap remains censored; censored states emit no action and cannot contribute
accounting.

Autonomous inputs and oracle labels use different dataclasses and functions.
The reducer accepts only policy actions; an observed unlock, close, re-hedge,
or terminal label cannot be passed to it. Changing oracle labels must leave
autonomous output unchanged.

Policy action input order is authoritative and must already be chronological;
no sorting is performed. Policy action times must be strictly increasing.
Same-second competing actions, duplicate idempotency keys
`(window_epoch, decision_time, action_kind)`, and reordered source rows are
rejected as `invalid_transition`; no incidental sorting or future tick may
repair them.

At window end, an explicit `TERMINATE` enters `TERMINAL`. Missing final ticks,
coverage loss, or an observed terminal label without a policy action remain
`CENSORED`; they do not become autonomous terminal transitions. A continuation
crossing an RB-008 fold is `cross_fold_continuation`, while a continuation
within one fold preserves state across midnight.

For RB-007 integration, `CLOSE_BUY` maps to conceptual `sell` only when the
next state is `ONE_SELL`; `CLOSE_SELL` maps to `buy`/`ONE_BUY`; `OPEN_BUY`
maps to `buy`/`HEDGED`; and `OPEN_SELL` maps to `sell`/`HEDGED`. `TERMINATE`
and every censored/invalid outcome carry no action side and no mark. The seed
quantity is abstract fixed quantity `1.0`; transitions conserve one active
conceptual leg and imply no broker margin or P/L.

## Retained outputs and claims

The engine retains only aggregate transition counts, invalid/censored counts,
state/action category counts, and a self-digest. It must not retain raw rows,
prices, timestamps, tickets, paths, account identifiers, or detailed traces.
The result is descriptive state-machine validation, not trigger
identification, profitability, broker attribution, or live readiness.

## Acceptance and stop conditions

- Synthetic fixtures cover every allowed transition, every prohibited action,
  duplicate/non-increasing time, post-terminal input, bootstrap censoring,
  cross-midnight ordering, and oracle-label rejection.
- State conservation holds: every accepted action has exactly one prior state
  and one next state; invalid/censored actions never alter state.
- Two clean runs are byte-identical and the aggregate schema is privacy-safe.
- RB-008 config/source digests and the M5 firewall remain locked.
- Independent review and fresh re-review return PASS with no P0-P3 finding.

Stop on any lookahead, oracle mutation, invalid transition leak, privacy
failure, or M5 firewall failure.
