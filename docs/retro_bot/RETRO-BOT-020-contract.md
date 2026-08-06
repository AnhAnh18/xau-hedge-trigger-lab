# RETRO-BOT-020 Contract

Status: owner-authorized on 2026-08-06; implementation is confined to the
accepted RB-020 authorization and source receipt. M5 remains untouched.

## Objective

Build an offline historical-reconstruction research bot with two isolated
paths:

- `autonomous`: decisions use only causal state and tick history available at
  the decision time;
- `oracle-diagnostic`: observed lifecycle/actions may be read only as labels,
  baseline comparisons, and error analysis.

The oracle path must never feed autonomous features, state, actions,
thresholds, candidate selection, or accounting controls.

## Independence and claims

RB-020 is RETRO-only. It must not modify or populate any M5 input manifest,
model, threshold, evaluation, gate, preregistration, frozen artifact, or
external-data intake. It must not inspect the registered August M5 outcomes,
read credentials or `.ex5`, call MT5, send orders, or claim a clone,
profitability, broker ownership, or live suitability.

Permitted claims are limited to causal replay behavior, observed-label
compatibility, timing/direction bands, state safety, coverage, censoring, and
paper-accounting diagnostics.

## Source boundary

The proposed first source is exactly the accepted RH-002 report/tick archive:
the 9 report aliases, 39 tick aliases, inherited manifest hashes, and
population `[2025-11-01, 2026-07-31)`. No source expansion is authorized by
this draft. Any source access requires a separate owner authorization naming
RB-020, the exact aliases/hashes/window, allowed fields, and retention period.

Until that authorization and receipt are accepted, only synthetic fixtures and
existing redacted artifacts may be read.

## Required behavior

- Reconstruct an explicit autonomous lifecycle with declared bootstrap,
  hedged/one-leg/terminal/censored states, and fail-closed ambiguity handling.
- Use a frozen, interpretable causal feature/rule vocabulary; no future ticks,
  observed actions, post-action marks, or unrestricted search.
- Evaluate chronologically with development/holdout separation and no
  post-hoc threshold tuning.
- Keep paper accounting separate from policy state and use conservative
  Bid/Ask semantics with synthetic cost scenarios only.
- Emit fixed-schema redacted aggregates only; never retain raw rows, tickets,
  paths, credentials, detailed timelines, or private identifiers.

## Acceptance gates

The milestone is complete only after a revised plan, implementation tests,
independent review and fresh re-review PASS, privacy/M5 firewall checks,
compileall, full regression, deterministic reruns, and a redacted result that
states whether the outcome is `package-ready`,
`behaviorally-compatible-accounting-inconclusive`, or
`no-supported-candidate`.

No candidate may be called supported from paper P/L. An inconclusive result is
valid and stops tuning.
