# RETRO-HIST-002 Result

Status: completed after fresh independent implementation re-review PASS on
2026-08-04.

## Redacted aggregate finding

Population: server timestamps `[2025-11-01 00:00:00, 2026-07-31 00:00:00)`
using the exact nine report aliases and 39 receipt-pinned tick aliases. All
source objects were hash-verified before parsing or streaming.

- Accepted position IDs: `125399`.
- Position IDs seen: `125694`.
- Duplicate snapshot rows: `16`.
- Conflicting position IDs: `0`.
- Invalid position rows: `468`.
- Right-censored positions: `0`.
- Observed OPEN labels: `125399`.
- Observed CLOSE labels: `125397`.
- Same-timestamp collision buckets: `27397`.
- Observed state counts: `FLAT 3829`, `ONE_BUY 52109`, `ONE_SELL 55463`,
  `HEDGED_1X1 111061`, `UNBALANCED_HEDGE 5`, `MULTI_POSITION 28330`,
  `CENSORED 0`.

Tick adapter coverage across the accepted UTC envelope:

- Valid rows: `101,384,194`.
- Envelope-excluded rows: `655604`.
- Duplicate timestamps: `24`.
- Invalid, crossed, and out-of-order rows: `0` each.

RH-002 retains unsupported snapshot conflicts as conservative `CENSORED`
interval markers and never emits a definite OPEN/CLOSE event for them. The
real registered population has no conflicting IDs, so the aggregate remains
unchanged from the pre-remediation baseline; synthetic gates cover the
conflict path. Oracle labels remain diagnostics only, and the policy path emits
zero actions from its declared FLAT seed.

## Validation

- Independent plan re-review: `VERDICT: PASS`.
- Focused RH-002 suite: `18 passed`.
- Full regression suite: `360 passed`.
- `python -m compileall -q src tests`: passed.
- `git diff --check`: passed.
- Two real archived runs were byte-identical at the aggregate level; aggregate
  self-digest:
  `8392949ab28491953301d10fbcfe3efab8dab5b08354b68803e53a85c2e34db9`.
- Fresh independent implementation re-review: `VERDICT: PASS`, no P0-P3
  findings.
- `raw_rows_printed=false`; RH-002 remains outside every M5 input, model,
  evaluation, threshold, and live-execution path.
