# RETRO-BOT-014: Offline Lane Terminal Seal Contract

Canonical milestone: `RB-018`. This is a RETRO-only synthetic/shadow seal
that runs after the RB-017 independent historical closeout. It consumes only
two redacted RB-017 reports and their non-sensitive run receipts. It adds no
raw source, no historical replay, no candidate selection, no model fitting,
and no external or live validation. A successful seal closes the offline
RETRO-BOT lane; it does not reopen the roadmap for tuning or source expansion.

The RB-017 contract and report schema are assumed to remain locked. RB-018
cannot start until RB-017 has a PASS verdict, a focused re-review after any
fixes, and durable state recording. This contract and its registration
artifact are locked before implementation.

## Owner decision and assumptions

The owner has authorized the bounded synthetic/shadow extension in the current
roadmap-completion request. The authorization token is
`RB018_SYNTHETIC_SHADOW_AUTHORIZED`; the lane terminates with a descriptive,
accounting-inconclusive result. This token authorizes no fresh history,
external validation, `.ex5` inspection, profitability claim, or live/demo
execution. Any such expansion requires a separate owner decision, source
receipt, and contract.

## Exact input boundary

The `seal` stage accepts exactly one JSON object with ordered keys:

```text
schema_version:int=1,
case_id:str="RB-018",
runs:[run_a,run_b],
gate_attestation:object
```

`runs` has exactly two entries, in order `run_a`, then `run_b`. Each entry has
the ordered keys:

```text
run_id:str in {"run_a","run_b"},
report:valid RB-017 report object,
stdout_sha256:64hex,
process_receipt:{schema_version:int=1,runner_id:str="RB017_CLOSEOUT_PROCESS_V1",
execution_nonce:64hex},
run_receipt_sha256:64hex
```

`stdout_sha256` is SHA-256 of the exact UTF-8 bytes emitted by the frozen
RB-017 `closeout` CLI: canonical report JSON followed by one LF byte. The
canonical JSON rules are UTF-8, `ensure_ascii=true`, separators `(",", ":")`,
`sort_keys=false`, finite values, and listed insertion order. The run receipt
digest is over the run entry with `run_receipt_sha256` omitted, using the same
canonical rules. `process_receipt` is an explicit operator-supplied
process-boundary receipt: distinct 64-hex nonces are required, but this lane
does not claim that a nonce cryptographically proves process independence.
No command line, path, environment, or raw output is retained.

`gate_attestation` has exactly these ordered keys and fixed values:

```text
schema_version:int=1,
owner_authorization:str="RB018_SYNTHETIC_SHADOW_AUTHORIZED",
registration_sha256:64hex="a66b085509e14729b5acdf1e39a0c823a74770b7406251a141d454de3f02b6b9",
rb017_prerequisite_sha256:64hex="3a51a2de0898652c4c58d599508a89894d0a7ecb9cb0d178e9d0d5efa69a5c4b",
rb017_validator_sha256:64hex="0329ddfd59e70be9e76c73a99f60c64726747a3453b5f30f40219f8c9757d7d4",
rb017_review_verdict:str="PASS",
rb017_rereview_verdict:str="PASS",
focused_tests_passed:bool=True,
full_tests_passed:bool=True,
privacy_passed:bool=True,
compile_passed:bool=True,
diff_check_passed:bool=True,
m5_firewall_passed:bool=True,
source_expansion:bool=False,
m5_modified:bool=False,
live_execution:bool=False,
attestation_sha256:64hex
```

The attestation digest omits only `attestation_sha256`. The registration and
prerequisite digests pin the owner decision and redacted RB-017 closeout
receipt; the validator digest pins the inherited RB-017 module bytes. The
remaining gate values are procedural evidence supplied after the independent
RB-017 review; RB-018 does not infer a review verdict from report contents.

The `verify-seal` stage accepts the same object with one optional final key,
`receipt`, containing the exact output of `seal`. Unknown keys, duplicate
JSON keys, reordered keys, non-finite numbers, and malformed nested objects
are rejected before any input is echoed.

## Exact output schema

`seal` emits one redacted terminal receipt with ordered keys:

```text
schema_version:int=1,
case_id:str="RB-018",
rb017_report_sha256:64hex,
rb017_package_sha256:64hex,
rb017_holdout_fixture_sha256:64hex,
rb017_holdout_aggregate_sha256:64hex,
run_receipt_sha256s:[64hex,64hex],
gate_attestation_sha256:64hex,
run_count:int=2,
byte_identical:bool=True,
review_verdict:str="PASS",
terminal_status:str="offline-lane-closed-synthetic-shadow-only",
historical_conclusion:str="behaviorally-compatible-accounting-inconclusive",
selection_performed:bool=False,
new_sources_used:bool=False,
m5_inputs_used:bool=False,
live_execution:bool=False,
shown:[str,...],
unresolved:[str,...],
m5_firewall:str="M5_FIREWALL_ATTESTATION_V1",
receipt_sha256:64hex
```

`shown` is exactly, in order:

```text
rb017_report_integrity,
rb017_two_run_determinism_receipts,
rb017_independent_review_pass,
offline_boundary_intact,
terminal_receipt_self_digest
```

`unresolved` is exactly, in order:

```text
synthetic_shadow_only,
no_new_historical_evidence,
no_candidate_selection,
no_profitability,
original_trigger_unidentified,
no_live_execution,
model_scope_unchanged
```

The receipt digest omits only `receipt_sha256` and uses the repository
canonical JSON rules: UTF-8, `ensure_ascii=true`, separators `(',', ':')`,
`sort_keys=false`, finite values, and the listed insertion order. No output
contains raw rows, quotes, returns, paths, credentials, private identifiers,
journals, tickets, `.ex5` content, network or subprocess controls, M5 fields
other than the exact firewall token, or live-order surfaces.

## Deterministic checks and firewall

The implementation must perform these checks in this order:

1. Parse one finite JSON value with duplicate-key rejection and no trailing
   bytes. Recursively scan the entire parsed tree for privacy/M5/live hazards
   before semantic validation; this structural scan never echoes input.
2. The scan rejects path-like values, raw-row aliases, credentials,
   journal/ticket/`.ex5` aliases, MT5/network/subprocess names, and live-order
   controls. It allows only the exact fixed schema keys/literals
   `m5_firewall`, `m5_firewall_passed=true`, `m5_modified=false`,
   `live_execution=false`, `source_expansion=false`, and RB-017 registered
   `raw_historical_scope`/`no_live_execution` literals. Unknown keys are
   still scanned and then rejected by schema validation.
3. Validate the exact ordered stage schema, then validate both RB-017 reports
   with the locked RB-017 validator, including
   field order, fixed literals, inherited source digests, and report
   self-digests. A report from any case other than `RB-017` is invalid.
4. Require distinct run ids and process nonces, recompute both run receipt
   digests, and require each `stdout_sha256` to match canonical report bytes
   plus one LF. Require canonical byte equality of the two reports and equal
   RB-017 package, fixture, aggregate, and report digests.
5. Validate every fixed gate-attestation literal, registration/prerequisite/
   validator digest, and its self-digest. Any
   false gate, missing owner authorization, source expansion, M5 modification,
   or live-execution flag stops the seal.
6. Build the fixed terminal receipt, recompute its self-digest, validate the
   complete output schema, and emit only the receipt. `verify-seal` recomputes
   the receipt and, when supplied, compares the optional receipt byte-for-byte.

Malformed input, tampering, failed gates, or firewall hits exit `2` with the
fixed non-sensitive message `RB-018 input rejected` and never echo input.
The process writes no input or run receipt to disk; callers may retain the
redacted input externally so `verify-seal` can recompute provenance. The
terminal receipt self-digest verifies only the receipt itself, not an input
that is no longer supplied.

## Stop conditions and terminal meaning

Stop before sealing when RB-017 is not independently PASS-reviewed, the two
reports differ, any digest or fixed literal fails, the owner authorization is
absent, a privacy/M5/live firewall check fails, or any required validation
command fails. Do not tune a candidate, inspect a holdout, add a source, or
change M5 state to make a stop condition pass. A P0/P1 finding, failed focused
re-review, or unresolved privacy/M5 finding blocks closeout; no durable state
file may be updated in that case.

`offline-lane-closed-synthetic-shadow-only` is a terminal process status, not
a performance result. The inherited
`behaviorally-compatible-accounting-inconclusive` conclusion is permanent for
this lane. It cannot become `package-ready`, `no-supported-candidate`, a
profitability claim, an original-trigger claim, or a live/demo authorization.
Any later evidence requires a separately authorized roadmap milestone.

## Acceptance tests

Implementation is accepted only when all of the following pass:

- valid RB-017 reports with two distinct run receipts produce the exact output
  schema, fixed literals, and terminal status above;
- two clean subprocess `seal` runs over identical input are byte-identical,
  and `verify-seal` accepts both a recomputed receipt and an identical supplied
  receipt, emitting exactly `{"stage":"verify-seal","verified":true}`;
- whitespace-only JSON changes remain equivalent, while duplicate keys,
  unknown keys, wrong key order, non-finite values, and malformed nesting fail
  closed with exit `2` and no input echo;
- changing any RB-017 report field, inherited digest, run id, stdout digest,
  run receipt digest, or gate-attestation field is rejected;
- one report differing from the other, a third/missing run, or a report with a
  non-RB-017 case id is rejected;
- recursive fixtures containing raw/private paths, credentials, journals,
  tickets, `.ex5`, MT5/network/subprocess/live aliases, or non-firewall M5
  values are rejected and never printed;
- static checks show no import or call surface for MT5, network, subprocess,
  credentials, journals, `.ex5`, or live execution;
- focused RB-018 tests, the isolated full suite, privacy scan, `py_compile`,
  and `git diff --check` pass; and
- a fresh independent review and focused re-review report PASS with no P0-P3
  findings before any state recording or milestone commit.

All malformed-input tests assert empty stdout and exact stderr
`RB-018 input rejected` followed by one LF, including duplicate keys, unknown
keys, wrong order, non-finite values, trailing bytes, deep nesting, firewall
hits, and digest tampering. The tests pin golden canonical preimages for
stdout, run receipts, attestation, and receipt digests, and verify the frozen
RB-017 validator hash.

RB-018 remains descriptive and outside every M5 input, model, evaluation,
threshold, and gate. The state recorder may update durable state only after
all acceptance tests and the independent review workflow pass.
