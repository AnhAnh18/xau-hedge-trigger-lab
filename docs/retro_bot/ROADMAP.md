# RETRO-BOT Roadmap

RETRO-BOT is a research lane that may run alongside M5 but cannot alter it.
It starts with an explainable, replay-only one-sided re-hedge surrogate. It
does not create a live strategy or declare that the original bot is cloned.

## RB-001 -- Governance and Firewall

Deliverable: the frozen RETRO-BOT-001 contract, an independent roadmap, source
receipt references, and an executable M5-reference firewall check.

Gate: scope excludes August M5 blocks and the `.ex5` binary; raw access is
receipt-gated; no RETRO-BOT artifact occurs in frozen M5 inputs.

Commit: `retro-bot: define isolated replay contract`.

## RB-002 -- Clock and Replay Inputs

Deliverable: typed clock-scenario configuration, verified source adapters, and
synthetic report/tick fixtures. The adapter must stream ticks and expose only
the first admissible tick timestamp, never persist tick rows.

Gate: UTC+2, UTC+3, and EET/EEST-style DST transitions work across
cross-midnight and transition fixtures; path/hash failures fail closed.

Commit: `retro-bot: add verified replay inputs and clock scenarios`.

## RB-003 -- Deterministic Re-Hedge Surrogate

Deliverable: a no-lookahead state machine and the four predeclared fixed-delay
policies. It consumes observed deterministic unlocks only and emits conceptual
opposite-side candidate actions, not broker orders.

Gate: direction is mechanically correct, actions occur only at/after the
delay on an available tick, gaps are explicit, and policy configuration is
immutable after a run starts.

Commit: `retro-bot: add deterministic rehedge replay policies`.

## RB-004 -- Aggregate Evaluator

Deliverable: policy/clock comparison against observed re-hedges, an ignored
canonical aggregate artifact, and a tracked redacted report generator.

Gate: no detailed timelines or prices are retained; aggregate reruns are
byte-identical; metrics expose no P/L or model-selection verdict.

Commit: `retro-bot: add aggregate behavioral evaluator`.

## RB-005 -- Historical Run and Independent Closeout

Deliverable: a registered historical run over the fixed population, a bounded
aggregate result, independent review, and state recording only if the verdict
passes.

Gate: source receipts verify, M5 remains blind and unchanged, all targeted and
full tests pass, and an independent reviewer finds no P0-P3 issue.

Commit: `retro-bot: publish historical replay aggregate`.

## Beyond V1

Price-sensitive trigger candidates, execution accounting, shadow observation,
and a demo/paper EA are separate follow-on contracts. They cannot be inferred
from a v1 fixed-delay replay and must not be silently added to this roadmap.

## RB-006 -- Bounded Paper Accounting

Deliverable: locked RETRO-BOT-002 contract, stream-only synthetic paper accounting harness, CLI, redacted result writer, and ignored paper-run root.

Gate: fixed quantity-1.0 opposite-side actions use bid/ask semantics and mark only at the observed re-hedge anchor; outputs are privacy-safe, reproducible, and never used for fitting, selection, M5 evaluation, or live orders.

## RB-007 -- Sequential Multi-Cycle Wrapper

Deliverable: locked RETRO-BOT-003 contract, chronological multi-cycle wrapper
over RB-006 outcomes, fail-closed overlap/invalid-order accounting, CLI,
redacted result writer, synthetic tests, and ignored multi-cycle run root.

Gate: cycles remain in caller-provided chronological order; malformed or
overlapping cycles cannot contribute actions, marks, or return bands; all
registered clock/policy rows report aggregate counts side by side. No new
source, `.ex5`, August/M5 data, live API, fitting, or policy selection is
allowed, and historical raw replay requires a separate owner decision.

## RETRO-BOT V2 -- Historical Paper Bot Roadmap (Proposed)

The V2 objective is an offline historical paper bot: it must consume only
information available at each decision time, reconstruct its own lifecycle,
emit conceptual actions, and produce a reproducible paper-accounting report
on a temporally held-out historical population. This is a research bot, not a
claim that the original strategy has been cloned.

The V2 finish line is deliberately bounded:

- The bot can replay a frozen historical population without using observed
  future unlock/re-hedge events as inputs.
- The bot has an explicit lifecycle, trigger, execution, and accounting model.
- Evaluation is chronological, reproducible, and reports uncertainty,
  censoring, and coverage limitations.
- All RETRO artifacts remain outside M5 inputs, models, evaluations,
  thresholds, and gates.

The final implementation must expose two explicitly separated modes:

- `autonomous`: decisions use only causal state and tick history; observed
  unlock/re-hedge events are unavailable to the decision path.
- `oracle-diagnostic`: observed events may be read only for labels, baseline
  comparison, and error analysis; it is never presented as bot performance.

It does not promise original-trigger identification, profitability, broker
ownership, manual-versus-EA attribution, live execution, or EA equivalence.
Those require separate evidence and authorization.

Before RB-008 is registered, this roadmap itself is the `RB-PLAN` gate:
the dependency graph, claim limits, stop conditions, and source boundary must
receive independent plan critique and re-review. No implementation milestone
starts from this proposal alone.

### Phase A -- Remove the replay oracle

#### RB-008 -- Evidence and Temporal Population Freeze

Deliverable: a RETRO-only data contract over the currently accepted 9 report
and 39 tick objects, with coverage, gaps, timestamp resolution, clock/DST
scenarios, censoring rules, report/session/case-level temporal folds, and an
explicit initial-state/bootstrap policy for every replay window.

Gate: hashes, aliases, paths, suffixes, and source receipts verify before any
source is opened; folds are chronological and never split correlated
intervals at random; the 2026-08 M5 blocks and any `.ex5`, journal, or new
source remain excluded. The contract must explicitly decide whether the
current population is sufficient for a descriptive holdout or whether a
larger RETRO-only archive is needed. Source expansion requires a new owner
authorization and receipt. A window without a receipt-pinned pre-window
position snapshot must use a declared fixed/warm-up seed or be marked
censored; its first observed event cannot be used to bootstrap state.

#### RB-009 -- Lifecycle and State Engine

Deliverable: a causal finite-state simulator for hedged, one-buy, one-sell,
re-hedge, terminal, and censored states, including cross-midnight windows,
missing ticks, second-level report timestamps, and invalid transitions. The
implementation keeps separate `policy_state` and `oracle_labels` paths: the
autonomous state changes only from bot-generated actions and causal inputs;
observed unlock, re-hedge, and close events are labels and diagnostics only.
The initial state is accepted only from the RB-008 bootstrap policy; if that
policy cannot establish a state, the window is censored rather than seeded
from the first observed report event.

Gate: synthetic transition and invariant tests prove no lookahead, no
duplicate action, correct direction mapping, deterministic ordering, and
fail-closed behavior for ambiguity or insufficient coverage.

#### RB-010 -- Causal Feature and Trigger Contract

Deliverable: a frozen, small, interpretable candidate vocabulary whose values
use only an explicit allowlist of history available at or before the decision
tick: state age, price increments/excursions, quote side/spread, tick
rate/gaps, session context, and autonomous position-side context.

Gate: candidate configuration and thresholds are immutable per run; a
lookahead scanner rejects post-action fields, observed unlock/re-hedge labels,
future marks, and unrestricted feature searches; missing-data policy is
explicit and aggregate-only outputs are retained.

#### RB-011 -- Unlock/Close Candidate Engine

Deliverable: deterministic candidate policies that decide whether and when a
hedged state produces a close/unlock event. The observed unlock path remains
an explicitly labeled benchmark only, never an autonomous input.

Gate: candidates are fit or calibrated only on declared development folds;
actions are causal, directional, and available-tick constrained; behavioral
coverage, hold/action/censor rates, false/duplicate-action rates, timing
tolerance bands, state-safety invariants, and minimum support thresholds are
predeclared. A candidate that acts on every eligible tick/cycle cannot pass
merely by maximizing coverage, and selection never uses paper P/L.

#### RB-012 -- One-Leg Re-Hedge Trigger Engine

Deliverable: deterministic candidate policies that decide whether and when a
one-leg state emits the opposite-side conceptual action, replacing the
RB-003/RB-007 observed-unlock plus fixed-delay oracle. Hold, action, and
censor outcomes must all be represented.

Gate: chronological replay is compatible with RB-009 and RB-007; no observed
future re-hedge, post-action price, or hidden label can affect a decision;
synthetic causal tests and an RB-007 baseline comparison pass.

### Phase B -- Validate the historical bot

#### RB-013 -- Walk-Forward Historical Evaluation

Deliverable: a preregistered temporal evaluation over the locked 2025-11
through 2026-07 population, using report/session/case-level train, development,
and untouched holdout folds. Candidate results are shown side by side.

Gate: no random interval split, holdout inspection, or post-hoc threshold
tuning; candidate freeze and tie rules are explicit; hold/action/censor,
false/duplicate-action, timing-band, state-safety, coverage, and minimum
support gates are evaluated before any candidate can be called supported. With
only a small number of independent historical units, an inconclusive result
is allowed and no winner or generalization claim is forced.

#### RB-014 -- End-to-End Historical Paper Bot

Deliverable: one offline CLI that composes the RB-009 through RB-012
autonomous policy engines with the RB-013 evaluation protocol, RB-006 paper
accounting, and the RB-007 sequential wrapper. The baseline is fixed quantity
`1.0`, Buy-at-Ask/Sell-at-Bid, conservative marking, and explicit scenario
parameters for any fee, spread, slippage, latency, or margin assumption.

Gate: state transitions, actions, marks, and accounting identities are
validated; the bot never calls MT5, sends orders, reads credentials, or
retains raw rows; two clean runs produce the same aggregate digest.

#### RB-015 -- Robustness, Stress, and Ablation

Deliverable: a locked stress matrix covering UTC+2/UTC+3/DST, timestamp
ambiguity, tick gaps/order, quote quality, spread/slippage/latency scenarios,
coverage/censoring, regime/session/side slices, and predeclared feature
ablations or parameter perturbations.

Gate: stress cases fail closed where required and report conservative bands;
no post-test tuning or cherry-picking is allowed; results remain descriptive
and outside M5.

### Phase C -- Freeze and close out

#### RB-016 -- Offline Bot Packaging and Freeze

Deliverable: versioned strategy configuration, self-hashed manifest, replay and
paper CLI, redacted result schema, run receipt, state snapshot format, and
known-limitations documentation. A clean-checkout run must be reproducible
with synthetic fixtures or externally mounted, hash-verified RETRO sources;
raw quarantine data are not expected in Git.

Gate: privacy, M5-firewall, `py_compile`, focused/full tests, and deterministic
rerun checks pass; no raw rows, credentials, private paths, journals, `.ex5`,
or live execution surfaces are packaged.

#### RB-017 -- Independent Historical Closeout

Deliverable: fresh holdout replay, redacted aggregate report, independent
review in a separate session, fixes for every confirmed in-scope P0-P3
finding, a focused re-review, and state recording only after a PASS verdict.

Gate: the final report states exactly what historical compatibility was shown
and what remains unresolved; two independent runs are byte-identical; the
milestone is committed without changing M5 state or frozen artifacts.

An optional future RB-018 may cover new-source or external/shadow validation,
but it requires a new owner decision, contract, source receipt, and review.
It is not implied by V2 and does not authorize live MT5 orders or `.ex5`
analysis.

### V2 terminal outcomes

The closeout is allowed to end in any of these predeclared outcomes:

- `package-ready`: a causal candidate passes replay, holdout, accounting,
  anti-overtrigger, support, and robustness gates and is suitable for
  offline/demo paper use.
- `behaviorally-compatible-accounting-inconclusive`: behavior is compatible
  within the registered bands, but spread, slippage, fees, margin, or coverage
  prevent a reliable accounting conclusion.
- `no-supported-candidate`: no candidate clears the causal or holdout gates,
  or the data are insufficient; the lane stops without additional tuning.

None of these outcomes means the original trigger was identified or that a
live strategy is profitable.

### Required workflow for every V2 milestone

1. Read the durable project state and the active RETRO contract.
2. Write and lock the milestone contract/preregistration and source boundary.
3. Run an independent plan critic in a fresh session; its response must begin
   with `RECOMMENDED_IMPLEMENTATION_PROFILE: build` or `complex`.
4. Have a plan reviser write the complete actionable plan artifact.
5. Implement only that revised plan and run focused validation.
6. Run an independent reviewer in a separate session from implementation and
   fixes; report findings as P0-P3 only.
7. Fix confirmed findings, then run a fresh independent re-review.
8. Re-run privacy/firewall, `py_compile`, focused/full tests, and deterministic
   aggregate checks.
9. Let the state recorder update `STATUS.md`, `TASKS.md`, and
   `SESSION_LOG.md` only when the verdict supports completion.
10. Commit one milestone; do not mix raw data, M5 changes, or unrelated work.

Each milestone contract must also pin: exact source aliases and hashes;
deterministic time/case windows; allowed in-memory fields; no-lookahead rules;
privacy-safe output schema; acceptance tests; stop conditions; the M5 firewall
assertion; and the required review/re-review artifacts.

RB-001 through RB-007 remain immutable baselines. RB-008 onward is proposed
roadmap scope until each milestone receives its own owner authorization and
locked contract.
