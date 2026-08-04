# RETRO-HIST-003 Plan

Status: revised after independent plan critique on 2026-08-04. RH-003 reuses
the RH-002 source receipt and remains descriptive RETRO only.

## Artifacts

- `docs/retro_bot/RETRO-HIST-003-contract.md`
- `docs/retro_bot/RETRO-HIST-003-source-receipt.md`
- `src/xau_trigger/retro_hist_003.py`
- `scripts/analyze_retro_hist_003_trigger.py`
- `tests/test_retro_hist_003.py`
- ignored aggregate `reports/private/retro-hist-003/trigger-aggregate.json`

## Revised implementation

1. Reuse RH-002 manifest verification and typed Decimal quantity semantics;
   refuse any alias, path, digest, or source-boundary change. Pin the inherited
   RH-001 goal authorization and lower-boundary carry-in bootstrap in the
   result receipt.
2. Implement the typed causal state/action reducer. Derive the exact
   lower-boundary carry-in precedence (`CENSORED`, same-side/multi-position,
   `FLAT`, one-leg, or 1x1/unbalanced) and give each candidate an independent
   policy state. Enforce fixed8 quantity conservation, state epochs, strict
   action times, legal close states, and `mirror_active_leg` sizing.
3. Implement UTC = server - offset for both clocks and a stream-only feature
   cursor. Parse Bid/Ask from raw CSV tokens with Decimal (never pandas float),
   compare integer nanosecond timestamps, and freeze exact Decimal mid/point
   equations (including quote gaps within the causal window W), inclusive
   60-second anchor/window, exact-6-second support
   boundary, duplicate-window handling, invalid-row fail-closed behavior, and
   one decision per unique valid tick timestamp. When duplicate rows share a
   timestamp, retain both for the source counter and window flag, emit exactly
   one `unsupported/duplicate_timestamp` decision for that timestamp, and
   attribute a cross-alias duplicate to the later alias without resetting the
   global order cursor.
4. Implement the six frozen candidate policies with independent state/epoch
   replays and one action per unique tick. Close rules run before re-hedge
   rules within the same policy; candidate IDs are never cross-suppressed or
   selected by accounting and are sorted only for deterministic serialization.
5. Implement a separate one-to-one oracle matcher after policy replay. Map
   observed server timestamps per clock, use a half-open 30-second horizon,
   consume actions deterministically, and expose only fixed timing,
   direction, and quantity diagnostic keys. Mutation tests must show oracle
   labels and future lots cannot alter any independent policy state, action, or
   action digest.
6. Implement a hash-verified historical analyzer that streams the exact 39
   tick aliases once, runs both clock states and all six candidates, starts
   from the lower-boundary carry-in only, and retains only bounded aggregate
   counters plus incremental action digests. No raw timeline is written.
7. Add synthetic golden vectors for bootstrap, feature equations, exact 60/6
   second boundaries, duplicate/crossed/nonfinite rows, candidate coactivation,
   repeated ticks, action rejection, uneven lots, oracle matching, alias
   boundaries, nested schema/digest/firewall, and CLI/path tampering. Run
   focused/full suites, compileall, privacy/M5 checks, two real deterministic
   runs, independent review, fix cycles, and fresh re-review before commit.

## Fixed aggregate schema

Top-level order is `schema_version`, `case_id`, `source_validation`,
`report_manifest_sha256`, `tick_manifest_sha256`, `population`, `clocks`,
`candidate_ids`, `support_counts`, `outcome_counts`, `action_counts`,
`quantity_bands`, `oracle_diagnostics`, `action_digests`, `m5_firewall`, `claims`,
`aggregate_sha256`. `schema_version` is integer `1`, `case_id` is exactly
`RETRO-HIST-003`, and `source_validation` is the exact string
`accepted_hash_verified_RETRO003_manifest_runs_all_objects`. `clocks` has
exactly `utc_plus_2` and `utc_plus_3`, each with exactly the integer keys
`valid_rows`, `invalid_rows`, `duplicate_timestamps`, `out_of_order`,
`crossed_quotes`, `envelope_excluded_rows`, and string `bootstrap_state`.
`population` has exactly `start_server`, `end_server_exclusive`,
`report_alias_count`, `tick_alias_count`, and `tick_clock_scenarios`.
`outcome_counts` is candidate x clock x state with the
fixed state set `FLAT`, `ONE_BUY`, `ONE_SELL`, `HEDGED_1X1`,
`UNBALANCED_HEDGE`, `MULTI_POSITION`, `CENSORED` and outcome set
`hold/action/unsupported/noneligible/censored/invalid`. `support_counts` uses
the fixed reasons `supported`, `empty_prefix`, `no_anchor`,
`duplicate_timestamp`, `invalid_row`, `quote_gap`, and `state_ineligible`. `support_counts`
is candidate x clock x state x reason. `action_counts` is candidate x clock
with exactly `CLOSE_BUY`, `CLOSE_SELL`, `OPEN_BUY`, and `OPEN_SELL`;
`quantity_bands` is candidate x clock with exactly the eight bands named in the
contract; `oracle_diagnostics` is candidate x clock with exactly `exact`,
`0-1s`, `2-6s`, `7-30s`, `unmatched`, `direction_match`,
`direction_mismatch`, `quantity_match`, `quantity_mismatch`,
`duplicate_label`, and `unmatched_label`. `action_digests` is candidate x clock
with lowercase 64-hex SHA-256 strings. Each digest hashes UTF-8 bytes formed by
concatenating one compact canonical JSON object per action in order, with a
single LF byte between records and no trailing LF; each object has exactly
`candidate_id`, `clock_id`, `epoch`, `decision_time_ns`, `kind`, `side`, and
`quantity_fixed8`. Empty replays hash empty bytes. `m5_firewall` is exactly
`M5_FIREWALL_ATTESTATION_V1`; `claims` has exactly the strict false booleans
`oracle_used_for_policy`, `raw_rows_printed`, and `pnl_or_model_selection`.
Canonical digest framing omits only `aggregate_sha256`, uses
`ensure_ascii=true`, compact separators, insertion order, and
`allow_nan=false`; the resulting UTF-8 bytes have no trailing newline and the
self-digest omits only `aggregate_sha256`. Unknown keys, NaN, and non-finite
values fail closed; required string and false-boolean fields are validated by
their exact declared types.
