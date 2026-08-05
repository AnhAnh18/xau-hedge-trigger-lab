# RETRO-HIST-004 Result

Status: accepted after independent implementation re-review PASS on
2026-08-05. This is aggregate-only descriptive accounting over the inherited
RH-002 archive. It is outside M5 inputs, fitting, model selection, thresholds,
profitability claims, and live/demo execution.

## Scope

- Population: `[2025-11-01 00:00:00, 2026-07-31 00:00:00)` server time.
- Sources: the exact RH-002 report and tick manifests; no source expansion.
- Scenarios: `zero_cost`, `fixed_fee`, `per_lot_fee`, `spread_slippage`,
  `latency_slippage`.
- Governance digests: contract `f3a20298cea7e01844f6a349906ea92ab9dd494cd8a3fd5a48820a562dbcb1bc`;
  source receipt `3611ee393cb00d71f4d1d05d546ab7c999d4e16de389ef012a1e7d7589f1e7f3`.

## Finding

Both authorized archive runs were byte-identical:

- Aggregate digest: `43ad1e09a59e78bbf2777e76d6b94f67cb7d98fe2824281e65e223c8f7b2d2b9`.
- File SHA-256: `2fd7c8f634dc320b31f7d8ab6ae2de36b58ae957a99da44f9f688e3f7fbec469`.
- File size: 5,706 bytes.
- Bootstrap state: `FLAT` for both UTC+2 and UTC+3 clock scenarios.
- Policy actions: zero across all six inherited RH-003 candidates and both clocks.
- Accounting outcome: `no_action` in every synthetic cost scenario; all quantity
  and accounting totals are zero.

This is a descriptive `FLAT/no_action` historical result. It does not establish
trigger correctness, profitability, broker ownership, or a tradeable edge.

## Validation

- Focused RH-004 tests: 26 passed.
- Full regression suite: 411 passed; 2 pre-existing warnings.
- `compileall`: passed.
- Scoped `git diff --check`: passed.
- Independent RH-004 re-review: `VERDICT: PASS`, no P0-P3 findings.
- Aggregate schema/self-digest validation: passed.

The generated aggregate remains in the ignored private report directory and is
not an M5 input or committed artifact.
