# RETRO-BOT-020 Revised Implementation Plan

Status: actionable plan; owner authorization and the exact source receipt were
accepted on 2026-08-06. Implementation remains RETRO-only and independent of
M5.

## 1. Freeze governance before source access

1. Preserve `RETRO-BOT-020-contract.md` as the scope and claims authority.
2. Create an RB-020 authorization record naming the exact RH-002 report and
   tick aliases, their accepted manifest hashes, population
   `[2025-11-01, 2026-07-31)`, allowed fields, deterministic timezone/clock
   interpretation, and retention period. The authorization must explicitly
   permit bounded in-memory parsing for RB-020 only.
3. Copy the exact aliases and hashes into
   `RETRO-BOT-020-source-receipt.md`; verify every file before opening it and
   write a receipt digest. A missing/mismatched hash, path, alias, window,
   field, or retention value is a hard stop. No historical parsing occurs
   before this receipt is accepted.
4. Add a machine-readable source manifest and contract validator. Reject
   credentials, journals/deals/fees/swaps/profits, terminal caches, `.ex5`,
   August M5 data, private paths, and any source outside the receipt.

## 2. Define the causal reconstruction protocol

1. Define a canonical event clock and ordering: source timestamp, normalized
   broker/session clock, tick sequence, and report event sequence. Resolve
   ties deterministically; ambiguous or missing ordering is censored/fail
   closed rather than inferred.
2. Define bootstrap explicitly: pre-window inventory is `unknown` unless a
   receipt-backed initial state exists; unknown bootstrap cannot create an
   autonomous action. Record `bootstrap_supported` and censoring counts.
3. Define lifecycle states and legal transitions for flat, opening, hedged,
   one-leg, closing, and terminal/censored cycles. Enforce same-timestamp
   ordering, duplicate-event rejection, no same-tick double action, and
   fail-closed invalid transitions.
4. Define the decision cutoff and latency policy. Features may use only ticks
   at or before the cutoff; an action executes at cutoff plus declared latency
   using the first eligible Bid/Ask quote. Missing/stale quotes are censored.
5. Define conservative marking separately from policy decisions. Mark only
   with a quote at or before the mark horizon, select the conservative side,
   and classify stale/no-quote marks explicitly.
6. Reuse RB-019/RB-014 Decimal fixed8 parsing, Bid/Ask signs, per-leg
   quantity conservation, uneven/partial-leg semantics, and synthetic fee,
   spread, slippage, latency, and margin scenarios. Accounting is downstream
   diagnostics and cannot control candidate selection.

## 3. Synthetic fixtures and typed isolation

1. Add typed schemas for `AutonomousInput`, `OracleDiagnosticInput`,
   `DecisionRecord`, `CycleRecord`, `AccountingRecord`, and redacted aggregate.
   Autonomous types must not contain observed action, outcome, future mark,
   or oracle label fields.
2. Implement separate autonomous and oracle-diagnostic modules and APIs.
   Oracle labels are read-only diagnostics for compatibility/error analysis;
   they cannot enter autonomous features, state, actions, thresholds,
   candidate ranking, accounting controls, or fold selection.
3. Add mutation tests that inject oracle fields through mappings, object
   copies, serialization, and nested payloads and prove autonomous execution
   rejects or ignores them. Add tests for future-tick/lookahead leakage,
   same-tick double action, bootstrap ambiguity, latency, stale marking,
   invalid transitions, uneven quantities, and conservation.

## 4. Freeze candidate vocabulary and folds

1. Freeze a small interpretable candidate vocabulary before any outcome is
   opened: state age, causal price increments/excursion, quote side/spread,
   tick gap/rate, session context, and autonomous position-side context.
   No unrestricted search or holdout-informed feature generation is allowed.
2. Declare chronological folds and aliases in a preregistered config: one or
   more development folds for rule construction, an optional structural
   validation fold for protocol checks only, and one untouched final holdout.
   Folds are report/time based, never random or overlapping.
3. Freeze candidate definitions, thresholds, parser/schema versions, cost
   scenarios, and result taxonomy before opening the holdout. The holdout is
   a one-shot replay; no retuning, recalibration, candidate dropping, or
   post-hoc threshold change may use its labels or metrics.

## 5. Implement and expose bounded tooling

1. Implement the causal replay engine under a dedicated RB-020 module without
   modifying M5 code or manifests.
2. Add stdin-only CLI stages with named artifacts, for example:
   `scripts/run_retro_bot_020.py validate-source`, `replay-autonomous`,
   `replay-oracle-diagnostic`, `walk-forward`, `paper-account`, and
   `verify-aggregate`. Commands must reject filesystem paths in payloads,
   duplicate keys, non-finite values, trailing bytes, unknown fields, and raw
   input echo; output is canonical fixed-schema JSON only.
3. Add schema, source-firewall, M5-firewall, deterministic digest, and
   subprocess tests. Include two runs from the same authorized archive and
   two synthetic actionful runs; compare aggregate and accounting digests.

## 6. Evaluation and result taxonomy

Report only redacted aggregates: direction/timing bands, state safety,
coverage, censoring, duplicate-action rate, bootstrap support, oracle
compatibility, accounting conservation, and synthetic cost-scenario bands.
Use result values exactly as defined by the contract:

- `package-ready`: all causal, isolation, holdout, accounting, privacy, and
  determinism gates pass; this is not a profitability or clone claim.
- `behaviorally-compatible-accounting-inconclusive`: causal compatibility is
  observed but accounting/support is insufficient for a supported candidate.
- `no-supported-candidate`: no frozen candidate clears the declared gates.

Paper P/L, oracle agreement, or historical fit alone may never establish
profitability, broker ownership, live suitability, or a clone.

## 7. Independent workflow and acceptance gates

1. Run the independent plan critic; its response must begin with
   `RECOMMENDED_IMPLEMENTATION_PROFILE: build` or `complex`.
2. A separate plan reviser writes this complete revised plan before code.
3. Implement, then run a fresh independent review (P0-P3 findings only).
   Fix every confirmed finding and obtain a fresh independent re-review with
   the same review profile; reviewers never edit files.
4. Run focused tests, full regression, `compileall`, `git diff --check`,
   privacy scanner, M5/source/path firewall checks, and deterministic
   subprocess reruns. Validate aggregate schemas and receipt hashes.
5. Write `RETRO-BOT-020-result.md` and a closeout receipt containing only
   redacted aggregates, schema/version, source/aggregate/accounting digests,
   fold and taxonomy status, and stop conditions encountered.
6. Update `.local_ai/STATUS.md`, `.local_ai/TASKS.md`, and
   `.local_ai/SESSION_LOG.md` only after fresh review `PASS` and all gates.
   Stage only RB-020 artifacts and state records; preserve unrelated user
   changes. Commit with `retro-bot-020:` prefix and push the active feature
   branch. Do not merge or alter M5 artifacts.

## Mandatory stop conditions

Stop immediately on missing authorization/receipt, source tamper or
expansion, clock ambiguity, lookahead/oracle leakage, bootstrap insufficiency,
stale/no-quote execution beyond policy, schema/privacy/path exposure,
nondeterminism, M5 contamination, unsupported claims, or any request for
live/demo execution. Transient implementation fields are allowed only through
an explicit allowlist, must be excluded from canonical output and hashes, and
must not contain raw rows, tickets, credentials, paths, or detailed timelines.
