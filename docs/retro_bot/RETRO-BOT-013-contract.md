# RETRO-BOT-013: Independent Historical Closeout Contract

Canonical milestone: `RB-017`. This is a RETRO-only synthetic/shadow closeout
over a frozen RB-016 package and a separately supplied typed RB-015 fixture. It
does not claim fresh external history, read raw files, access credentials,
journals, tickets, `.ex5`, MT5, network, or any M5 artifact. Because the
holdout is synthetic/shadow, this milestone cannot produce V2 `package-ready`
or `no-supported-candidate` outcomes; it is permanently
`behaviorally-compatible-accounting-inconclusive` and documents that limit.

## Exact input and holdout boundary

Both `closeout` and `verify-closeout` accept exactly one JSON object with
ordered keys `package`, `holdout_fixture`. `package` is a valid RB-016 package.
`holdout_fixture` is a valid RB-015 typed fixture whose four cycles each have
`fold="holdout"`, `causal_window.report_alias="report-008.html"`, and every
decision record has `fold="holdout"`, `future_read=false`, `oracle_used=false`,
and `report_alias="report-008.html"`. `report-009.html` is not used in this
bounded shadow lane. The canonical parsed fixture digest is recorded; raw
cycles are never retained or emitted.

## Exact report schema

Report ordered top-level keys are:

```text
schema_version:int=1, case_id="RB-017", package_id="RB016_PACKAGE_V1",
package_sha256:64hex, package_aggregate_sha256:64hex,
holdout_fixture_sha256:64hex, holdout_aggregate_sha256:64hex,
projection_digest:64hex,
source_manifest_digests:{report_manifest_sha256:64hex,tick_manifest_sha256:64hex},
attestation:{schema_version:int,rb008_config_sha256:64hex,
report_manifest_sha256:64hex,tick_manifest_sha256:64hex,fixture_id:str,
m5_firewall:str},
selection_performed:bool=False, holdout_supported:bool=False,
terminal_status="behaviorally-compatible-accounting-inconclusive",
shown:[str,...], unresolved:[str,...], m5_firewall:str,
report_sha256:64hex
```

`shown` is exactly the ordered list `package_integrity`,
`rb015_projection_integrity`, `holdout_replay_integrity`,
`accounting_bands_only`, `deterministic_replay`. `unresolved` is exactly
`no_candidate_selection`, `synthetic_shadow_holdout`, `raw_historical_scope`,
`profitability`, `live_execution`. The source digest object and attestation
object have the exact key order shown and must equal the inherited RB-015
constants. Report digest omits only `report_sha256` and uses RB-016 canonical
JSON rules. Unknown keys, duplicate keys, changed references, non-Boolean
flags, and bad 64-hex values fail closed.

## Verification and gates

`closeout` validates the package, replays the holdout through RB-015, checks the
fold/alias rules above, and emits only the redacted report. `verify-closeout`
receives the same package+fixture input, recomputes the report and all package,
fixture, aggregate, provenance, and self-digests, and compares the supplied
report only if an optional third top-level key `report` is present; otherwise
it verifies the freshly recomputed report. It emits exactly
`{"stage":"verify-closeout","verified":true}` on exit `0`. Malformed input
or tampering exits `2` with fixed `RB-017 input rejected` and no input echo.

Two identical typed inputs produce byte-identical UTF-8 JSON. No report field
contains raw rows, quote values, returns, paths, credentials, private keys,
journals, tickets, `.ex5`, M5 fields, or live-execution surfaces.

RB-017 is complete only after focused/full tests, privacy, compile, diff,
determinism, independent review, remediation, fresh re-review, and durable
state recording. It is descriptive evidence and not an M5 gate or live-order
authorization.
