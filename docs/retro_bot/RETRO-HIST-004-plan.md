# RETRO-HIST-004 Revised Plan

Status: revised after independent plan critique on 2026-08-05. This is a
bounded RETRO-HIST accounting milestone. It does not reopen the closed
RETRO-BOT lane, change RH-001 through RH-003, or authorize M5 or live
execution.

## Objective

Run an observed-lot paper-accounting replay over the accepted, hash-verified
RH-002 archive. Reconcile the already reconstructed historical state/action
stream with typed Bid/Ask cash flows, latency-aware quote selection,
conservative marking, fixed Decimal costs, and exact per-leg quantity
conservation. The result is descriptive accounting only. Policy decisions,
candidate selection, threshold changes, model fitting, M5 inputs, and live or
demo execution are out of scope.

The historical run must preserve the observed bootstrap and report a
`FLAT`/`no_action` outcome when the inherited RH-002/RH-003 replay emits no
action. That outcome is an accounting observation, not evidence of
profitability, trigger correctness, or broker ownership.

## Authorized source boundary

Use exactly the accepted RH-002 source receipt and its parent RETRO-003
objects:

- `docs/retro_bot/RETRO-HIST-002-source-receipt.md` and its authorization;
- report aliases `report-001.html` through `report-009.html`;
- the exact 39 tick aliases and opaque run labels in the receipt;
- report manifest SHA-256
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`;
- tick manifest SHA-256
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`;
- server population `[2025-11-01 00:00:00, 2026-07-31 00:00:00)`.

Every manifest object and path must be verified before parsing. Resolve only
receipt-pinned opaque run labels below the fixed quarantine root. No source
expansion, new time window, August M5 block, journal, terminal cache,
credential, private path, `.ex5`, or MT5/live surface is permitted. A change
requires a new owner authorization, contract, and accepted source receipt;
the implementation must stop before opening data when any boundary or digest
check fails.

## Required governance artifacts

Before implementation, create and lock:

- `docs/retro_bot/RETRO-HIST-004-contract.md`, with this plan's source
  boundary, accounting equations, quote/latency rules, costs, output schema,
  and firewall claims;
- `docs/retro_bot/RETRO-HIST-004-source-receipt.md`, inheriting the exact
  RH-002 receipt, aliases, hashes, run labels, quarantine boundary, and
  population without expansion;
- the owner authorization/amendment if the repository workflow requires a
  separately named RH-004 authorization. It must reference only the RH-002
  archive and observed-lot accounting.

The contract and receipt are immutable inputs to implementation and must be
hash-pinned in the final aggregate and process receipt.

## Implementation artifacts and boundaries

Implement only the following new or directly scoped artifacts:

- `src/xau_trigger/retro_hist_004.py`: typed stream accounting reducer;
- `scripts/analyze_retro_hist_004_accounting.py`: stdin-only or pinned-label
  CLI with no raw-file/path arguments;
- `tests/test_retro_hist_004.py`: focused synthetic and schema/firewall tests;
- ignored aggregate and run receipts under
  `reports/private/retro-hist-004/` (never commit raw data or detailed
  timelines);
- the contract and source receipt named above.

Reuse RH-002's verified adapter and RH-003's already frozen causal stream only
as library inputs. Do not alter their policy rules, candidate vocabulary,
state transitions, source manifests, or historical outputs. The accounting
layer must be removable without changing policy actions or action digests.
No accounting value may feed policy state, feature computation, action
quantity, candidate ranking, threshold choice, or any M5 artifact.

## Fixed accounting semantics

### Numeric and quantity rules

- Parse Bid, Ask, prices, quantities, fees, slippage, and latency costs as
  `Decimal`; never route through binary float.
- Serialize monetary/price values at declared fixed8 precision (or the
  contract's explicitly declared currency precision), with integer fixed8
  quantity units for equality and conservation checks.
- Reject non-finite, malformed, non-positive, over-precision, or negative
  quantities unless a contract-declared fee/cost field permits a negative
  cash-flow sign. Fail closed and count a semantic-invalid cycle without
  retaining raw fields.
- Preserve every observed initial and event lot exactly. Uneven Buy/Sell legs,
  partial closes, and partial opens are represented as typed quantities; no
  `0.3` replacement, interpolation, rounding, or normalization is allowed.
- For each leg and cycle, enforce
  `opening_qty - closing_qty = ending_qty` in fixed8 units. A close cannot
  exceed the active quantity; an invalid or unresolved partial-leg transition
  is censored/invalid and never silently repaired. Aggregate conservation
  failures are fatal to the run.

### Bid/Ask direction and cash-flow signs

- A Buy opens at Ask and closes at Bid; a Sell opens at Bid and closes at Ask.
- Opening cash flow is negative and closing cash flow is positive under the
  paper-accounting convention; the contract must state the exact signed
  formulas and side labels.
- Validate `Ask >= Bid`, finite positive quotes, and fixed quote precision.
  Crossed/invalid quotes are rejected, counted, and cannot be used for
  execution or marking.
- Synthetic golden vectors must cover both sides, opening and closing signs,
  unequal lots, and exact Decimal arithmetic.

### Latency quote selection

- For an action at causal decision time `t`, select the first valid quote at
  or after `t + latency` within the declared bounded horizon; do not use a
  future quote beyond the horizon or a quote before the latency target.
- If no qualifying quote exists, mark the fill unsupported/censored and do not
  invent a price. Equal timestamps and duplicate rows follow RH-002 ordering;
  a duplicate/ambiguous latency quote is a deterministic unsupported outcome,
  not an arbitrary pick.
- The selected quote is retained only as an aggregate latency band and
  selection-status counter. Raw timestamp, price, ticket, and path data never
  appear in output.

### Conservative marking

- Mark open inventory at the adverse executable side: Buy inventory at Bid and
  Sell inventory at Ask. Use the last valid causal quote at or before the mark
  time; never use a future quote or midpoint to improve P/L.
- Missing, crossed, stale, or out-of-envelope marks produce a conservative
  `mark_unsupported`/censored accounting status and zero fabricated proceeds.
- Marking is descriptive and must not alter policy state, action eligibility,
  oracle matching, or any candidate outcome.

### Costs and scenarios

- Predeclare a finite synthetic cost matrix in the RH-004 contract before any
  archive run. At minimum include `zero_cost`, `fixed_fee`, `per_lot_fee`,
  `spread_slippage`, and `latency_slippage` scenarios with exact Decimal
  parameters and a canonical scenario fingerprint.
- Charge initial and event costs at the declared side/quantity basis; never
  tune costs from historical P/L. Scenario IDs, parameters, and fingerprints
  are fixed and included in the redacted aggregate.
- Cost arithmetic must conserve currency signs and be independently testable;
  a cost scenario cannot change whether an action is emitted.

## Policy/accounting isolation

Run policy/state/action replay first, then feed its typed actions and observed
lot schedule to a separate accounting reducer. The reducer receives no oracle
labels, future lots, P/L-derived features, or scenario-dependent controls.
Mutation tests must show that removing, reordering, or changing accounting
inputs leaves policy state, action records, and action digests byte-identical;
changing a cost scenario may change only accounting fields. A policy action
cannot be synthesized solely to make accounting complete.

The historical bootstrap and outcome vocabulary is fixed: `FLAT`, `ONE_BUY`,
`ONE_SELL`, `HEDGED_1X1`, `UNBALANCED_HEDGE`, `MULTI_POSITION`, and
`CENSORED`, with outcomes `no_action`, `accounted_action`, `unsupported`,
`invalid`, and `censored`. The inherited historical RH-003 result must remain
observable as `FLAT` plus `no_action` when no policy action is emitted.

## Redacted output schema and firewall

The aggregate is fixed-schema canonical JSON with insertion order and a
self-digest. It must include only:

`schema_version`, `case_id`, `source_validation`, `report_manifest_sha256`,
`tick_manifest_sha256`, `population`, `scenario_ids`, `bootstrap_state`,
`state_counts`, `action_counts`, `accounting_counts`, `quantity_bands`,
`latency_bands`, `cost_fingerprints`, `conservation`, `policy_action_digests`,
`accounting_digests`, `m5_firewall`, `claims`, and `aggregate_sha256`.

All dimensions, enum values, integer types, Decimal/fixed8 string formats,
and false firewall claims are declared in the contract. Required claims are
`oracle_used_for_policy=false`, `raw_rows_printed=false`,
`pnl_or_model_selection=false`, and
`live_execution=false`; `m5_firewall` is exactly
`M5_FIREWALL_ATTESTATION_V1`. Reject unknown keys, duplicate keys, non-finite
values, trailing bytes, raw identifiers, timestamps, prices, tickets,
comments, credentials, private paths, and any nested privacy violation.

The aggregate is descriptive only. No report, action timeline, raw quote,
position ID, or detailed P/L row may be retained, printed, committed, or
placed in an M5 manifest.

## Tests and acceptance gates

Add synthetic tests for:

1. Decimal/fixed8 parsing, precision rejection, and exact quantity
   conservation for uneven initial, open, close, and partial-leg quantities;
2. Bid/Ask side signs for Buy/Sell opens and closes, crossed/non-finite quote
   rejection, and conservative adverse marking;
3. latency target/horizon selection, duplicate/equal-time quotes, no-quote
   censoring, and no-lookahead behavior;
4. each predeclared cost scenario, scenario fingerprint stability, and proof
   that costs cannot alter policy actions;
5. policy/accounting/oracle isolation, including future-lot and accounting
   mutation tests;
6. historical `FLAT`/`no_action`, legal action transitions, invalid partial
   closes, censored marks, and aggregate conservation failure;
7. canonical schema, self-digest, strict types, recursive privacy/M5 firewall,
   manifest/path/hash tampering, and stdin-only CLI restrictions.

Run the focused RH-004 tests, the full regression suite, compileall,
privacy/firewall checks, and `git diff --check`. Execute two fresh authorized
archive runs from clean processes; their redacted aggregate bytes, scenario
fingerprints, policy digests, and accounting digests must match exactly.
Run an independent P0-P3 implementation review in a separate session, fix all
confirmed findings, and obtain a fresh re-review with `VERDICT: PASS`.

## Acceptance criteria

The milestone is accepted only when:

- contract, receipt, authorization, and all source hashes/path constraints
  verify before source access;
- observed quantities, Bid/Ask signs, latency selection, marking, costs, and
  per-leg conservation match the frozen equations;
- policy action/state digests are unchanged by accounting, oracle, future-lot,
  or scenario mutations;
- the historical run reports the inherited `FLAT`/`no_action` result when
  applicable and does not claim profitability or a supported trigger;
- both archive runs are byte-identical and all focused/full/privacy/firewall
  gates pass;
- independent review and fresh re-review pass with no P0/P1/P2/P3 findings;
- the milestone is committed with the RH-004 prefix and durable state is
  updated only after the final review verdict.

## Risks and stop conditions

Stop immediately on missing/changed authorization, hash or path failure,
source expansion, malformed or ambiguous quotes, Decimal/fixed8 drift,
quantity-conservation failure, latency lookahead, non-conservative marking,
policy/accounting contamination, raw/privacy leak, nondeterministic reruns,
M5 access, live/demo execution, or any request to tune costs, select a policy,
fit a model, or make a profitability claim. Such a stop requires a new owner
decision and receipt; do not repair by inference or by broadening the source.

## Closeout and state updates

After independent `PASS`, commit only the RH-004 contract, receipt,
implementation, tests, and non-sensitive documentation. Do not commit ignored
aggregates or raw archives. Push the milestone commit, then update
`.local_ai/STATUS.md`, `.local_ai/TASKS.md`, and `.local_ai/SESSION_LOG.md`
with the exact verdict, commands, two-run digest evidence, and the permanent
RETRO-only/M5-firewall conclusion. Do not mark the task complete while any
P0/P1 finding, failed gate, unresolved conservation/privacy issue, or owner
decision remains.
