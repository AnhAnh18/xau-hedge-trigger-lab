# RETRO-BOT-012: Offline Bot Packaging and Freeze Contract

Canonical milestone: `RB-016`. This is a RETRO-only packaging freeze over the
locked RB-015/RB-014 synthetic typed-replay boundary. It adds no source data,
does not select or tune a candidate, and cannot alter any M5 input, model,
evaluation, threshold, or gate.

## Locked provenance and input boundary

The package id is `RB016_PACKAGE_V1`. RB-014 provenance is the explicit digest
`3621048bc7ca84d4be0717b0599cc1bfed5d8d565f5502f20543873aeabfde44`, computed
from the ordered JSON array `["RB-014",1,RB008_CONFIG_SHA256,
REPORT_MANIFEST_SHA256,TICK_MANIFEST_SHA256]` with the inherited literal
values. The manifest also repeats the RB-015 projection digest
`4b3f9a2bd98b3827641cafa7807c6b929a2e212243c7a340cb51c97da1c701c3`, fixture
id `synthetic_rb015_base_cycle_v1`, RB-008 config digest, both source-manifest
digests, and all three fixed RB-015 cost fingerprints:

- `zero`: `94e0bdfde7445b7fbb442ffefefe6cdf972b1f524b60d6c637b6e97200acc1e2`;
- `spread_slippage`: `8b5544bbbcbc7b76247c95d152b2a9d1cef77f99e96123a64b86e01baddcc71b`;
- `latency_margin`: `682392bd46841d8de5bc777993df3bb39c563ce844fc27b92f2a5a7056f8d312`.

RB-016 accepts any owner-authorized typed RB-015 fixture with that locked
fixture id; it is not a new historical source and is not a checked-in raw
archive. The fixture digest is over its parsed canonical JSON representation,
not transport whitespace. `package-replay` accepts exactly one JSON object on
stdin; `validate-config` accepts no stdin; `verify-receipt` accepts one package
artifact object. Duplicate JSON keys are rejected before parsing.

## Canonicalization and manifest

Every digest uses UTF-8 JSON with `ensure_ascii=true`, separators `(',', ':')`,
`sort_keys=false`, the listed insertion order, finite values only, no floats
where a fixed decimal string is specified, and no duplicate keys. Hashes omit
only their own final digest field, so no digest cycle exists.

Manifest ordered keys and types are exactly:

```text
schema_version:int=1, package_id:str, projection_version:str,
projection_digest:64hex, fixture_id:str, rb014_schema_version:int=1,
rb014_provenance_sha256:64hex, rb008_config_sha256:64hex,
source_manifest_digests:{report_manifest_sha256:64hex,tick_manifest_sha256:64hex},
cost_scenarios:[{scenario_id:str,fee_per_unit:str,slippage_points:str,
latency_seconds:int,margin_per_unit:str,fingerprint:64hex}],
m5_firewall:str, live_execution:bool=False, manifest_sha256:64hex
```

The manifest cost list is ordered `zero`, `spread_slippage`,
`latency_margin`; fixed decimal fields have exactly eight fractional digits.
Unknown keys, reordered keys, changed inherited fields, non-finite values,
`live_execution != false`, or a bad self-digest are rejected.

## State, aggregate, and receipt schemas

The state snapshot is initial state from the `all` RB-015 slice, before replay.
It must be `HEDGED`, epoch `0`, quantity `1.0`, and have no seen action keys;
its `last_time` is a UTC ISO timestamp or `null`. Ordered state keys are:
`schema_version`, `state`, `epoch`, `last_time`, `quantity`, `seen_keys`,
`state_sha256`. Each seen key is `[window_epoch:int,time_ns:int,kind:str]`;
the self-digest omits `state_sha256`. The snapshot is embedded in the package
artifact, so `verify-receipt` can recompute its digest without hidden input.

The package artifact ordered top-level keys are:

```text
schema_version, case_id="RB-016", package_id, manifest, rb015_aggregate,
state_snapshot, receipt, package_sha256
```

`rb015_aggregate` is the complete redacted RB-015 aggregate, validated against
its locked 40-row schema and digest; it contains no raw cycles, quote values,
returns, paths, credentials, journals, tickets, `.ex5`, or M5 fields.

The receipt ordered keys are:

```text
schema_version, package_id, manifest_sha256, fixture_id, fixture_sha256,
rb015_aggregate_sha256, state_snapshot_sha256,
terminal_status="descriptive-only-no-selection", live_execution=False,
receipt_sha256
```

The receipt digest omits only `receipt_sha256`; the package digest omits only
`package_sha256`. Verification recomputes all nested digests and checks the
full inherited RB-015 aggregate provenance, not just its top-level id.

## CLI, privacy, and acceptance

`validate-config` exits `0` and emits the manifest only. `package-replay` exits
`0` and emits one package artifact; `verify-receipt` exits `0` and emits
`{"stage":"verify-receipt","verified":true}`. Malformed input exits `2`
with a fixed non-sensitive error and no input echo. Runtime/static tests prove
no MT5, network, credentials, subprocess, journal, ticket, `.ex5`, or live
execution surface is imported or called. Recursive exact allowlists reject
unknown nested keys, path-like/private aliases, M5 references, duplicate keys,
and non-Boolean `live_execution`.

Known limitations are documented in `docs/retro_bot/RETRO-BOT-012-known-limitations.md`:
synthetic typed replay only, descriptive/no-selection semantics, censoring and
second-level timestamps, inferred timezone windows, no profitability claim,
and no MT5/live execution.

RB-016 is complete only after focused/full tests, privacy, compile, diff,
two byte-identical CLI runs, an independent review, remediation, and a fresh
independent re-review. Any source expansion or live/M5 coupling stops the
milestone and requires a new owner decision.
