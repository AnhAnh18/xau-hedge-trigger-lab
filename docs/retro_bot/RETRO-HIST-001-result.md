# RETRO-HIST-001 Result

Status: completed after independent implementation re-review PASS on
2026-08-03.

## Redacted aggregate finding

Population: server dates `2025-11-01` through `2026-07-30` inclusive, using
the exact nine report aliases and receipt-pinned 39 tick aliases. RH-001 reads
only report `positions` and `open_positions` tables; it does not reconstruct an
ordered schedule.

- Accepted position IDs: `125399`.
- Position IDs seen: `125694`.
- Duplicate snapshot rows: `16`.
- Conflicting position IDs: `0`.
- Invalid position rows: `468`.
- Right-censored positions: `0`.
- Outside-population position IDs: `295`.

Observed quantity bands, retained exactly as fixed8 values:

| Side | Closed quantity bands |
| --- | --- |
| Buy | `0.01000000`: 12; `0.02000000`: 13; `0.05000000`: 1,256; `0.10000000`: 54,152; `0.20000000`: 4,381; `0.30000000`: 4,801; `1.00000000`: 2 |
| Sell | `0.01000000`: 10; `0.02000000`: 9; `0.05000000`: 1,097; `0.10000000`: 51,169; `0.20000000`: 3,486; `0.30000000`: 5,010; `1.00000000`: 1 |

The historical lot schedule is therefore not equivalent to a constant `0.3`
lot assumption. RH-001 establishes a distribution baseline only; ordered
per-cycle quantities, partial fills, and causal action sizing remain RH-002/
RH-003 work.

## Validation

- Independent contract re-review: `VERDICT: PASS`.
- Focused RH-001 tests: `5 passed`.
- Full test suite: `342 passed`.
- `compileall` and `git diff --check`: passed.
- Two real archived runs were byte-identical at the aggregate level; aggregate
  self-digest:
  `777ee6e852fd5f0576008ae8d36a49fec309fb8f14141443c07bf9915c40a383`.
- `raw_rows_printed=false`; the aggregate remains outside every M5 manifest.
