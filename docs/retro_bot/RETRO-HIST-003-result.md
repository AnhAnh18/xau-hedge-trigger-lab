# RETRO-HIST-003 Result

Status: completed after independent implementation re-review (`PASS`). This
report is aggregate-only and remains outside M5 inputs, model selection,
future validation, thresholds, and live execution.

## Scope

- Population: `[2025-11-01 00:00:00, 2026-07-31 00:00:00)` in broker-server time.
- Sources: the nine owner-authorized report aliases and 39 tick aliases pinned
  by the inherited RH-002 receipt; no source expansion was used.
- Clock scenarios: `utc_plus_2` and `utc_plus_3`.
- Frozen policies: six independent candidates, including hold-only, four
  close rules, and mirror-active-leg re-hedging.

Observed lifecycle labels and quantities were used only by the separate oracle
diagnostic path. They did not initialize, size, select, or mutate policy
replays.

## Reproducibility

Two full archive replays were run with the same accepted manifests. The
aggregate passed the RH-003 schema and self-digest validator. The final
aggregate has:

- aggregate digest: `95311f30fe6c2ce7e2c37503d51900787182285631feb1ab89c5530ceddd4369`
- file SHA-256: `2c1683b83ebdb652f81d9343bda74b2ed8d453906bc6734192c4812ce81c2057`
- size: `27603` bytes
- result framing: compact canonical JSON with no trailing newline

The two runs were byte-identical: both produced the aggregate and file hashes
listed above.

## Aggregate observations

- Lower-boundary bootstrap state is `FLAT` for both clocks.
- All six policy candidates emitted zero actions in both clock scenarios;
  action digests are therefore the SHA-256 of empty bytes.
- Valid tick rows: `101383707` for UTC+2 and `101357062` for UTC+3.
- Duplicate timestamps: `24` in each clock scenario; no out-of-order or
  crossed-quote rows were accepted.
- Envelope-excluded rows: `656091` for UTC+2 and `682736` for UTC+3. The
  difference reflects the one-hour start-window shift, not a strategy result.
- Oracle labels remained unmatched because no policy action was emitted; this
  is a diagnostic count, not evidence of trigger failure or success.

## Interpretation boundary

RH-003 demonstrates that the causal state/feature/action machinery can replay
the accepted archive deterministically while preserving observed lot sizes as
oracle-only ground truth. Because the registered lower-boundary state is flat,
this run does not identify a close trigger, re-hedge trigger, profitability,
manual intervention, broker ownership, or a tradeable edge. A future RH
milestone would need a separately authorized non-flat case or another bounded
source contract; it must not alter M5 inputs or the frozen RETRO-BOT lane.

## Validation

- Focused RH-003 tests: `25 passed`.
- Full regression suite: `385 passed` in the current runtime.
- `python -m compileall -q src tests`: passed.
- Scoped `git diff --check`: passed.
- Independent RH-003 re-review: `VERDICT: PASS`, no P0-P3 findings.
