# RETRO-HIST-001 Contract

Status: owner-authorized bounded RETRO historical lot-regime audit, opened in
the current task on 2026-08-03. This contract is a new RETRO-HIST lineage; it
does not reopen or modify RB-008 through RB-019.

## Question

What lot quantities are actually present in the retained historical XAUUSD
position population? RH-001 produces a redacted lot-distribution baseline for
later RETRO replay; it does not retain an ordered per-cycle lot schedule. The
ordered schedule and action sizing are deferred to RH-002/RH-003 contracts. This
case does not infer a trigger, profitability, broker ownership, manual
intervention, or live readiness.

## Exact source boundary

This case uses only the accepted RETRO-003 quarantine objects, without source
expansion:

- report aliases `report-001.html` through `report-009.html`;
- the exact 39 tick aliases pinned by the RETRO-003 source receipt;
- report manifest SHA-256
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`;
- tick manifest SHA-256
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`;
- server population `[2025-11-01 00:00:00, 2026-07-31 00:00:00)`.

RH-001 reads report `positions` and `open_positions` tables only. The tick
objects are receipt-pinned and manifest-verified but are not opened by this
milestone; tick use belongs to a later contract. Deals, orders, journals,
terminal caches, XLSX/PNG companions, `.ex5`, August M5 data, credentials, and
any new source are out of scope.

## Lot ground truth and censoring

- The only quantity source field is `volume` from `positions` and
  `open_positions`. The only identity fields are `position_id`, `symbol`,
  `side`, `open_time`, and `close_time`.
- Side is accepted only after Unicode-free ASCII case folding to `buy` or
  `sell`; symbol is accepted only after ASCII case folding to `xauusd`.
- A quantity is accepted only when `Decimal(str(value))` is finite, strictly
  positive, no greater than `1000.00000000`, and exactly representable at eight
  decimal places without rounding. It is serialized as an exact eight-place
  fixed string. Zero, negative, non-finite, malformed, or over-bound values are
  invalid and counted, never repaired.
- A position snapshot is identified by `position_id`. All rows for an ID must
  have the same normalized side, fixed8 quantity, and open time. Equal rows
  are deduplicated. A row with a missing close time does not conflict with a
  row that has the single unique non-missing close time; the non-missing close
  is authoritative. More than one distinct non-missing close time, or any
  disagreement in side, quantity, or open time, is a conflict and excluded.
- A closed position overlaps the population when
  `open_time < end_exclusive` and `close_time > start_inclusive`. A position
  with no close time overlaps when `open_time < end_exclusive`; it is
  right-censored. Positions with missing open time or no positive overlap are
  excluded from population counts. Carry-in positions are included when their
  interval overlaps the start boundary.
- `open_positions` without a close time are right-censored. They are counted in
  coverage and lot-band statistics with a censor flag, but never treated as
  completed intervals or an inferred future action.
- RH-001 does not infer partial fills or a future action quantity from a later
  observed event. Those semantics require RH-002/RH-003 contracts.
- No historical quantity is replaced with `0.3`, normalized, interpolated, or
  imputed. Normalized scale summaries, if later requested, are secondary
  diagnostics only.

## Allowed output

Only aggregate counts and fixed bands may be retained: source digests, coverage
status, quantity bands by side and censor status, duplicate / conflict /
invalid / censor counts, deterministic fingerprints, `raw_rows_printed=false`,
and `M5_FIREWALL_ATTESTATION_V1`. No raw rows,
timestamps, prices, comments, tickets, private paths, credentials, or detailed
position timelines may be printed or committed. The aggregate remains outside
all M5 manifests.

## Acceptance and stop conditions

Acceptance requires hash/run-label/alias validation, Decimal quantity
conservation for every retained aggregate bucket, a fixed output key order,
byte-identical reruns, focused synthetic tests, compile/privacy/firewall
checks, `git diff --check`, and an independent review with `VERDICT: PASS`.

Stop on missing or mismatched authorization/receipt, source expansion, hash or
path failure, raw/privacy leak, M5 access, unsupported quantity semantics, or
any attempt to use RH-001 output for fitting, threshold selection, M5
evaluation, profitability claims, or live execution.
