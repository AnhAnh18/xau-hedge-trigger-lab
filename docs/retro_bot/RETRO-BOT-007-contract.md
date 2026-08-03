# RETRO-BOT-007: Unlock/Close Candidate Engine Contract

Status: owner-authorized follow-on to RB-010 on 2026-08-03; RETRO only and
outside every M5 input, model, evaluation, threshold, and gate.

## Purpose and claim boundary

RB-011 defines a deterministic candidate engine for the `HEDGED` state. At
each eligible causal tick it may hold or emit one conceptual close/unlock
candidate (`CLOSE_BUY` or `CLOSE_SELL`). The engine is a research replay
component, not a broker-order adapter and not a claim that the original bot,
an EA, or a human operator has been reproduced.

The observed unlock/close stream is an `oracle-diagnostic` benchmark only. It
may supply labels and timing comparisons after the policy output is frozen;
it can never mutate autonomous state, features, candidate configuration, or
action timing. `autonomous` mode receives only RB-009 state and RB-010 causal
features/ticks.

## Locked source and population boundary

Use exactly the RB-008 population and configuration, inherited unchanged:

- RB-008 config SHA-256:
  `26fec4baa2b8e2680cc17afaad299bbbb00afba32810865ac60bf28eb2e49ebf`;
- report manifest SHA-256:
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`;
- tick manifest SHA-256:
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`.

The deterministic windows, report/session/case folds, bootstrap policies,
clock scenarios, and censor rules are those frozen by RB-008. No new raw
source, August M5 block, journal, credential, `.ex5`, ticket/account field,
or private path is admitted. Any source expansion needs a new owner contract
and receipt.

## Decision semantics

1. The caller supplies an RB-009 autonomous state snapshot, its monotone
   `state_epoch`, and an ordered prefix of valid ticks. The prefix is strictly
   chronological and contains no tick later than `decision_time`; RB-010
   validation is reused unchanged. A stale or mismatched epoch is reported as
   `invalid_transition` and cannot emit an action.
2. A decision is eligible only while state is `HEDGED`, after the RB-009
   bootstrap anchor and at an available tick. `ONE_BUY`, `ONE_SELL`,
   `TERMINAL`, and `CENSORED` produce no candidate and are counted separately
   as `noneligible_terminal`, `noneligible_one_leg`, or
   `noneligible_censored` (never as a policy action).
3. The engine evaluates an immutable, explicitly ordered tuple of RB-010
   `TriggerRule` objects. Rules are deterministic and may contain at most
   three AND clauses. The first matching legal rule in ascending `rule_id`
   order wins; no matching rule means `hold`.
4. A matching rule must name exactly one legal close action for `HEDGED`.
   `CLOSE_BUY` means the buy leg is closed and the conceptual next state is
   `ONE_SELL`; `CLOSE_SELL` means the sell leg is closed and the next state is
   `ONE_BUY`. Candidate quantity is the RB-009 fixed abstract `1.0`.
5. At most one action may be emitted per decision tick. Duplicate ticks,
   same-second competing decisions, non-increasing decision times, malformed
   rules, and illegal transitions fail closed as `invalid_transition`; a
   malformed rule invalidates the whole policy and is never skipped. They
   never emit an action. Missing/non-finite features yield `feature_missing`
   and never default to an action.
6. Once a candidate is emitted, the caller must apply it through RB-009 before
   any later lifecycle decision. RB-011 never reads an observed close/unlock to
   repair, suppress, or advance policy state.

## Candidate policies and calibration

Candidate policy configuration is frozen before evaluation. Any fitting or
calibration is restricted to the declared chronological development folds from
RB-008; it may select only among predeclared rule tuples and timing parameters
from the RB-010 finite grid. No paper P/L, holdout outcome, or observed future
event may be used for selection. A baseline `always_hold` rule and a
predeclared `first_legal_match` policy are the complete locked policy manifest;
no other policy ids or parameter tuples are admitted. Exploratory coverage and
timing summaries are reported but are non-blocking. Minimum support is one
accepted action for each direction; insufficient support yields
`inconclusive`, never a forced winner. A policy that acts on every eligible
tick/cycle is not acceptable solely because it maximizes coverage.

## Oracle benchmark separation

For `oracle-diagnostic` mode, observed unlock/close events are materialized in
a separate label object keyed only by anonymized window/cycle identity and
second-resolution time. For each policy action, matching consumes the earliest
unused label for the same anonymized cycle whose timestamp difference falls in
the first applicable inclusive band (`exact`, `0-1s`, `2-6s`, `7-30s`, `>30s`);
labels are never reused, and unmatched labels/actions are counted explicitly.
The benchmark reports aggregate timing tolerance bands and directional
agreement against frozen policy output. Oracle labels
cannot enter feature snapshots, RB-009 transitions, rule fitting, policy
selection, or paper accounting. Autonomous and oracle runs must have separate
digests and schemas so accidental mixing fails validation.

## Retained aggregate outputs

Only aggregate, privacy-safe fields may be retained: fixed schema/version;
allowlisted anonymized case ids (`^[A-Za-z0-9_-]{1,64}$`); inherited
source/config digests; mode and policy id; eligible, hold, action,
feature-missing, invalid, censored, noneligible, and duplicate counts;
directional action counts; oracle match, direction-mismatch, duplicate-label,
and unmatched counts; timing-band counts; minimum-support and exploratory gate
statuses; and a canonical aggregate SHA-256. The aggregate must carry the
literal `M5_FIREWALL_ATTESTATION_V1` field and reject any key/value outside the
allowlist. No prices, raw rows, detailed timelines, tickets, account
identifiers, credentials, or filesystem paths may be printed, written, or
committed.

## Predeclared gates and stop conditions

The candidate passes only if all are true on the registered development and
evaluation summaries: source and M5-firewall attestations verify; action
direction is legal; no lookahead or oracle mutation is detected; state/action
conservation holds; duplicate and invalid-action rates are zero (or explicitly
reported); and each direction has at least one accepted action. Coverage and
timing gates are exploratory, reported, and non-blocking. Hold, action,
censor, and noneligible rates must all be reported. With insufficient support,
the result is `inconclusive`, never a forced winner.

Stop immediately on any source digest mismatch, future tick/feature, oracle
state mutation, illegal transition, privacy leak, M5-manifest contamination,
or failed deterministic rerun.

## Required validation

Synthetic tests must cover HEDGED close-buy/close-sell direction mapping,
hold/no-match, non-HEDGED and censored states, first-match rule ordering,
duplicate/non-increasing decision ticks, feature-missing and invalid rules,
one-action-per-tick, stale epoch rejection, malformed-policy fail-closed,
oracle/policy isolation and earliest-unused inclusive-band matching,
timing-band aggregation, minimum-support gates, digest/schema/firewall
validation, and two byte-identical runs.
Run focused RB-011 tests, the full suite, privacy checker, `py_compile`,
`git diff --check`, and an independent review followed by a fresh
re-review. No RB-011 artifact may alter M5 state or frozen M5 inputs.
