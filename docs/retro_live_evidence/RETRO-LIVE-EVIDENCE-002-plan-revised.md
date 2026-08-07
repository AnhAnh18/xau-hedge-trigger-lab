# RETRO-LIVE-EVIDENCE E-002 Revised Plan

Status: actionable after independent critique; implementation is bounded to a
new E-002 authorization over existing RETRO-003 objects. No live, demo, canary,
M5, or RB-020 surface is authorized.

## 1. Frozen source scope

Use all nine report aliases `report-001.html` through `report-009.html` to
establish a conservative carry-in state, but retain and aggregate only events
inside the summer block. Use the 14 tick aliases from
`XAUUSD_ticks_2026-04-25_to_2026-05-02.csv` through
`XAUUSD_ticks_2026-07-25_to_2026-08-01.csv`. These aliases must match the
accepted RETRO-003 manifests byte-for-byte; no neighboring files or XLSX/PNG
companions are allowed.

The registered server-time window is `[2026-05-01 00:00:00,
2026-07-31 00:00:00)`. For this summer-only block, the canonical E-002 UTC
window is `[2026-04-30T21:00:00.000000Z, 2026-07-30T21:00:00.000000Z)` under
`UTC+3-summer`. Any boundary/tie that cannot be ordered is censored.
Pre-window report rows are used only to determine whether the block starts in
FLAT; they are never emitted as events or retained in the aggregate.

## 2. Receipt before source access

Create a fresh E-002 receipt containing the exact 23 aliases (9 reports and
14 ticks), object types,
source hashes, positive byte counts, canonical field allowlists, parser and
canonicalization versions, a short redacted retention deadline, and a
self-digest. Validate it through the metadata-only stdin validator before the
adapter opens any source object. Pin the parent report/tick manifest digests
inside the redacted provenance but do not treat them as a substitute for the
E-002 receipt digest.

## 3. Source-safe adapter

Implement a separate adapter that verifies the two inherited manifests and
object hashes, reads only report lifecycle fields and tick `time_utc`, `bid`,
`ask`, and emits redacted checkpoint/cycle records. It must not expose raw
rows, position IDs, detailed timestamps, prices, credentials, or paths. Cycle
rules are frozen before parsing: known-FLAT start, verified FLAT close,
one-leg/hedged/gap/variable-lot/wide-spread categories, explicit censoring for
carry-in, right-censored, ambiguous clock, unsupported partial-close, and
same-timestamp ordering ambiguity.

## 4. Intake and gates

Bind the redacted cycles to the receipt digest and frozen E-001 gate digest,
then run the existing E-002 aggregation. Never lower the minimum 30-actionful
and category/direction thresholds after inspection. Return
`insufficient-actionful-coverage` or `HOLD` when coverage, safety,
determinism, privacy, or provenance fails; do not proceed to E-003 if so.

## 5. Validation and review

Run two independent canonical subprocess captures, receipt/manifest tamper
tests, seasonal/half-open boundary tests, oracle/privacy/M5/execution scans,
focused E-002 tests, full regression, compileall, and diff checks. Obtain a
fresh independent review and re-review. Only a final PASS permits updating
state records; no result authorizes profitability, clone status, or live
suitability.
