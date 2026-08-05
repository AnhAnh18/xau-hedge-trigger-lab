# RETRO-HIST-001 Revised Plan

Status: revised after independent plan critique on 2026-08-03. This is a
separate historical-reconstruction lineage; it does not modify RB-008 through
RB-019 contracts or reopen the closed synthetic/shadow lane.

## Objective

Build a reproducible historical reconstruction and paper-replay lane for the
XAUUSD hedge-rotation bot. The lane uses observed historical quantities as the
canonical lot schedule, keeps autonomous decisions separate from oracle labels,
and remains descriptive and outside every M5 input, model, evaluation,
threshold, gate, and live/demo execution surface.

## Source boundary

The first bounded population reuses, without expansion, the accepted archived
RETRO-003 objects:

- nine report aliases: `report-001.html` through `report-009.html`;
- the exact 39 tick aliases in the accepted RETRO-003 receipt;
- report manifest SHA-256:
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`;
- tick manifest SHA-256:
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`;
- server population `[2025-11-01 00:00:00, 2026-07-31 00:00:00)`.

The August M5 blocks, `.ex5`, journals, terminal caches, credentials, private
paths, and any new source are excluded. A new source or time window requires a
new owner authorization, contract, and accepted receipt before source access.

## Non-negotiable semantics

- Observed lot quantities are ground truth for historical replay. No global
  replacement with `0.3`, interpolation, or silent normalization is allowed.
- Position snapshots and deal/event records require a declared precedence;
  duplicate IDs, partial fills/closes, conflicting quantities, and unresolved
  timestamps are represented as conflicts/censoring rather than imputed.
- An observed future unlock/re-hedge quantity may be an oracle label, but it
  must never size an autonomous action or enter an autonomous feature.
- Autonomous policy state, causal features, action quantities, and accounting
  are separate from oracle labels and diagnostics. Removing oracle labels must
  leave autonomous actions and the ledger byte-identical.
- Decimal/fixed-point quantity conservation is mandatory. Accounting remains
  descriptive; P/L cannot select a policy or change M5.

## Milestones

### RH-001 -- Governance, receipt, and lot-regime audit

Lock the case contract, source receipt, allowed in-memory fields, quantity
precedence, censor rules, population boundary, privacy schema, and M5 firewall.
Produce only aggregate lot bands by side/censor status, accepted-position
counts, duplicate/conflict/invalid/censor counts, and deterministic
fingerprints. This milestone does not claim to reconstruct an ordered lot
schedule.

Gate: all hashes/aliases/path constraints verify before source open; no raw row,
price, ticket, comment, credential, or private path is retained or printed.

Implementation artifacts: `docs/retro_bot/RETRO-HIST-001-contract.md`,
`docs/retro_bot/RETRO-HIST-001-source-receipt.md`,
`scripts/analyze_retro_hist_001_lots.py`,
`tests/test_retro_hist_001.py`, and the ignored aggregate
`reports/private/retro-hist-001/lot-audit-aggregate.json`.

Fixed aggregate key order: `schema_version`, `case_id`, `source_validation`,
`report_manifest_sha256`, `tick_manifest_sha256`, `population`,
`position_coverage`, `lot_bands`, `m5_firewall`, `claims`,
`aggregate_sha256`. The CLI has no raw-file arguments; it uses only the pinned
run labels and returns a redacted one-line summary.

Focused commands: `uv run pytest -q tests/test_retro_hist_001.py`,
`uv run python -m py_compile scripts/analyze_retro_hist_001_lots.py`,
`uv run python scripts/analyze_retro_hist_001_lots.py`, `git diff --check`,
and a second clean CLI run whose aggregate digest must match byte-for-byte.

### RH-002 -- Historical adapter and causal lifecycle engine

Add a stream-only hash-verified adapter and causal lifecycle reconstruction for
hedged, one-leg, re-hedge, terminal, and censored states. Pin bootstrap,
cross-midnight, clock/DST, second-level collision, gap, and coverage rules.

Gate: synthetic variable-lot, partial-close, concurrent-leg, deduplication,
gap, collision, and censor tests pass; autonomous state does not consume oracle
events.

### RH-003 -- Autonomous trigger and causal sizing contract

Freeze the small candidate vocabulary, causal clock/tick inputs, candidate
thresholds, tie rules, support gates, and a declared quantity rule for new
actions. Keep the observed action path as oracle-diagnostic only.

Gate: no-lookahead and oracle-isolation tests prove that post-action labels,
future marks, or observed future lots cannot alter autonomous decisions.

### RH-004 -- Observed-lot paper accounting

Compose the causal replay with Bid/Ask execution, Decimal fixed-point
quantities, initial uneven legs, per-leg conservation, explicit fee/slippage/
latency/margin scenarios, and conservative marking. Keep raw details out of
the retained result.

Gate: accounting identities, cost fingerprints, invalid-transition handling,
and deterministic replay pass. Currency P/L is descriptive only.

### RH-005 -- Chronological walk-forward evaluation

Use expanding chronological folds over the bounded historical population. Keep
development, validation, and untouched holdout units explicit; do not split
correlated intervals randomly. Report hold/action/censor, timing, safety,
coverage, and support bands before any accounting summary.

Gate: no holdout inspection or post-test tuning; `inconclusive` and
`no-supported-candidate` are valid outcomes.

### RH-006 -- Regime and scale robustness

Predeclare slices for lot regimes, asymmetric legs, session/day, clock/DST,
timestamp ambiguity, quote gaps, and coverage perturbations. Compare actual-lot
replay with normalized scale diagnostics without replacing the canonical run.

Gate: the matrix and tie rules are frozen before results; no cherry-picking or
policy selection from P/L.

### RH-007 -- Independent closeout

Produce a redacted fixed-schema report, recomputed source/provenance
fingerprints, known limitations, independent review, fix cycles, fresh
re-review, state recording, and one milestone commit/push.

Terminal outcomes are descriptive only: `package-ready`,
`behaviorally-compatible-accounting-inconclusive`, `no-supported-candidate`,
or `inconclusive`.

## Required workflow gates

For each milestone: lock its contract; obtain an independent plan critique;
write the revised plan; implement only that scope; run focused and regression
tests, compile/privacy/firewall checks, and `git diff --check`; obtain a fresh
independent P0-P3 review; fix and re-review until `VERDICT: PASS`; then commit
and push with the milestone prefix and update durable state. No milestone may
change M5 artifacts or read the August M5 outputs.

## Stop conditions

Stop on missing or mismatched authorization/receipt, source expansion, hash or
path failure, raw/privacy leak, oracle/lookahead contamination, lot or state
conservation failure, unresolved causal sizing, incomplete support matrix,
M5-surface access, or any request for live execution, `.ex5` analysis, or
profitability claims.
