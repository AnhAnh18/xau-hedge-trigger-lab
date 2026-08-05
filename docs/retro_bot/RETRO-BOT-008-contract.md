# RETRO-BOT-008: One-Leg Re-Hedge Trigger Contract

Status: owner-authorized follow-on to RB-011 on 2026-08-03; RETRO-only and
outside all M5 inputs, models, evaluations, thresholds, and gates.

## Purpose

Define the causal engine that decides whether a policy-controlled one-leg
state emits the opposite-side conceptual action. This milestone removes the
RB-003/RB-007 observed-unlock plus fixed-delay oracle from the autonomous
decision path. It produces an offline policy event, never a broker order.

## Locked source and scope

The source boundary, aliases, hashes, folds, clock scenarios, bootstrap rows,
and censor rules are inherited unchanged from RB-008. No new source, August
M5 block, journal, credential, `.ex5`, live API, or private raw path may be
opened. Only causal fields permitted by RB-010 may reach this engine:
autonomous RB-009 state/side and the RB-010 feature snapshot at the current
decision tick. Observed unlock, close, re-hedge, terminal, P/L, ticket,
comment, or future-mark fields are labels/diagnostics only.

## State and action semantics

The engine is eligible only in `ONE_BUY` or `ONE_SELL`:

| Policy state | Conceptual opposite action | Next state |
| --- | --- | --- |
| `ONE_BUY` | `OPEN_SELL` | `HEDGED` |
| `ONE_SELL` | `OPEN_BUY` | `HEDGED` |

`HEDGED`, `TERMINAL`, and `CENSORED` produce no re-hedge action. The action
quantity is the RB-009 abstract fixed `1.0`. A state epoch may emit at most
one accepted action; duplicate, same-time, non-increasing, or post-terminal
actions fail closed and cannot mutate state.

## Decision protocol

At each caller-provided valid tick in chronological order, the engine builds
the RB-010 snapshot using only history at or before that tick. It evaluates a
frozen trigger rule set. If the rule set does not match, the outcome is
`hold`. If it matches and the state/action mapping is legal, the outcome is
`action` and RB-009 applies the transition. If the snapshot is unavailable,
non-finite, out of order, duplicated, beyond a coverage boundary, or otherwise
ambiguous, the outcome is `censored` (with a bounded reason category) and no
action is emitted. RB-008 censor precedence applies exactly once per window:
`clock_unresolved`, `invalid_transition`, `cross_fold_continuation`,
`left_censored_unknown_bootstrap`, `coverage_censored_no_valid_tick`, then
`right_censored_no_terminal`. The first applicable censor is terminal; there
is no retry that can inspect later ticks, sorting repair, or fallback action.

The first eligible tick at or after the RB-009 decision anchor (inclusive) is
evaluated. The caller supplies a `StateSnapshot` and exact `epoch` as
`expected_epoch`; a mismatch is `invalid_transition` before feature
construction. Times are normalized to UTC and same-second collisions
(`floor("s")`) are invalid; no subsecond ordering repairs them. An action is
available only on a valid tick; no interpolation or synthetic tick is
permitted. After a legal match, the engine emits one `PolicyAction` with
`window_epoch=expected_epoch`, applies it immediately through RB-009, and ends
the window without reading later ticks. A continuation wrapper may begin the
next cycle only after RB-009 confirms `HEDGED`.

Each one-leg window has exactly one terminal aggregate outcome: `hold`,
`action`, or `censored`. Per-tick diagnostics remain in memory and do not add
denominator rows.

## Candidate policy and baseline

Candidate rules use only the immutable RB-010 DSL and are frozen before any
holdout inspection. The complete manifest is locked to `always_hold` (empty
rule tuple) and `first_legal_match` (two `always` rules with ids `open_buy`
and `open_sell`, mapping `ONE_SELL -> OPEN_BUY` and `ONE_BUY -> OPEN_SELL`).
No other policy or parameter tuple is admitted. Rule-id order is the
deterministic tie-break; at most one action can be selected at a tick. A
candidate that matches every eligible tick is not sufficient: coverage,
hold/action/censor rates, duplicate/invalid counts, timing tolerance, state
safety, and minimum support are reported.

The RB-007 observed-unlock/fixed-delay replay is retained as a descriptive
baseline comparison only. Its observed event may define an oracle label and a
timing reference, but it cannot feed candidate features, state, trigger
selection, or action execution. Baseline and candidate rows are shown side by
side without selecting a winner and without paper P/L or profitability
selection.

## Retained outputs and privacy

Retain only aggregate counts and bounded categorical bands: complete rows for
every registered RB-008 fold x clock x bootstrap x policy combination,
eligible one-leg windows, hold/action/censor counts, action-side counts,
invalid/duplicate counts, timing tolerance bands against the separately
labeled baseline, minimum-support flags, and a self-digest. Missing or
duplicate matrix rows fail closed. Do not retain raw rows, prices,
detailed timelines, exact timestamps, tickets, account identifiers, source
paths, credentials, journals, or private quarantine names.

## Acceptance and stop conditions

- Synthetic causal tests cover both directions, hold, action, censoring,
  first-tick eligibility, missing/duplicate/out-of-order ticks, gaps,
  terminal/hedged ineligibility, and state conservation.
- RB-007 baseline comparison is label-only and cannot alter autonomous output;
  candidate and baseline aggregates are deterministic and privacy-safe.
- Two clean runs are byte-identical; RB-008/RB-010 digests and the M5 firewall
  remain unchanged; focused/full tests, privacy, compile, and diff checks pass.
- Stop on any lookahead, oracle mutation, invalid transition leak, action on a
  censored state, privacy failure, or M5 firewall failure.
- Independent review and fresh re-review must report `PASS` with no P0-P3
  finding before state recording or commit.

This contract establishes behavioral replay compatibility only. It does not
identify the original trigger, prove profitability, attribute manual versus
automated action, establish broker ownership, or authorize live execution.

Implementation defaults: the only policy ids are `always_hold` and
`first_legal_match`, with immutable direction mappings `ONE_BUY -> OPEN_SELL`
and `ONE_SELL -> OPEN_BUY`. The denominator is one terminal outcome per
one-leg window; an accepted action or first censor closes the window. RB-008
censor precedence is inherited unchanged, same-second timestamps are rejected
without sorting, and accepted actions are applied through RB-009 immediately
with no post-action tick reads.
