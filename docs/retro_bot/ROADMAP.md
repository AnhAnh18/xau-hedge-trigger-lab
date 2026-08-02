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
