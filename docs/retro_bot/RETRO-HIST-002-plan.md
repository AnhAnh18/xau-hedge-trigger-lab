# RETRO-HIST-002 Plan

Status: draft for independent plan critique. RH-002 depends on the completed
RH-001 contract, source receipt, aggregate lot baseline, and fixed Decimal
quantity semantics.

## Artifacts

- `docs/retro_bot/RETRO-HIST-002-contract.md`
- `docs/retro_bot/RETRO-HIST-002-source-receipt.md`
- `src/xau_trigger/retro_hist_002.py`
- `scripts/analyze_retro_hist_002_lifecycle.py`
- `tests/test_retro_hist_002.py`
- ignored aggregate `reports/private/retro-hist-002/lifecycle-aggregate.json`

## Implementation

1. Verify the RH-001 source receipt, exact manifest digests, opaque run labels,
   alias sets, and fixed half-open population before opening any source. Hash
   every report/tick object before parsing or streaming; any object mismatch
   fails closed.
2. Implement typed Decimal position/event records and a stream-only tick
   adapter with chunked CSV reads, the declared UTC+2/UTC+3 union envelope,
   positive finite Bid/Ask checks, `ask >= bid` acceptance, duplicate counting,
   global out-of-order failure, object hashing, and aggregate coverage bands.
3. Implement observed lifecycle reconstruction with carry-in bootstrap,
   half-open interval OPEN/CLOSE labels, explicit equal-time tie key,
   unsupported-partial-close censoring, state classification precedence,
   conflict/censor handling, and aggregate-only output.
4. Implement a separate `PolicyState`/`CausalAction` API with fixed FLAT seed,
   strict action ordering/idempotence/quantity validation, and no partial
   updates. Oracle labels may be recorded for diagnostics but cannot mutate
   policy state, action quantities, or any future ledger.
5. Add synthetic fixtures for uneven lots, unsupported partial-close
   conflicts, carry-in/boundary intervals, concurrent positions, same-second
   collisions/tie ordering, gaps, duplicate/out-of-order/crossed/non-finite
   quotes, object alias/digest tampering, and oracle-label
   removal/toggling.
6. Run RH-002 focused tests, the full suite, compileall, privacy/M5 firewall,
   diff checks, and two deterministic aggregate runs. Obtain an independent
   implementation review and fresh re-review before commit/push.

## Fixed aggregate schema

Top-level order is: `schema_version`, `case_id`, `source_validation`,
`report_manifest_sha256`, `tick_manifest_sha256`, `population`,
`event_coverage`, `state_counts`, `transition_counts`, `tick_coverage`,
`m5_firewall`, `claims`, `aggregate_sha256`.

Nested schemas are also fixed. `event_coverage` keys are
`reports_parsed`, `accepted_position_ids`, `open_events`, `close_events`,
`duplicate_labels`, `collision_timestamps`, `conflicting_position_ids`,
`invalid_rows`, `censored_position_ids`; `state_counts` has `oracle` and
`policy`, each with the seven state labels in contract order;
`transition_counts` has `oracle` and `policy`, each a fixed 7-by-7 state matrix;
`tick_coverage` keys are `valid_rows`, `invalid_rows`, `duplicate_timestamps`,
`out_of_order`, `crossed_quotes`, `envelope_excluded_rows`, and
`files_hash_verified`; all counts are non-negative integers and all missing
categories are emitted as zero.

No policy candidate, threshold, P/L metric, or model-selection result is
retained by RH-002.
