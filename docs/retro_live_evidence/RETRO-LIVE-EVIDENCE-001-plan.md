# RETRO-LIVE-EVIDENCE E-001 Plan

## Objective

Freeze the evidence protocol before collecting or inspecting any new
actionful source. E-001 produces governance artifacts only; it must not send
orders, inspect M5 outcomes, or modify RB-020.

## Scope

- Define the exact observation objects and allowed fields.
- Define source aliases, hashes, population windows, and timezone handling.
- Define redacted evidence schemas and retention.
- Pre-register fidelity, coverage, holdout, shadow, and safety gates.
- Define stop conditions and the owner decision required to open E-002.

## Proposed evidence gates

The final numeric thresholds are frozen in the owner-approved contract before
E-002. The gate families are: actionful sample count, state parity, direction
parity, ordering parity, timing bands, lot parity, duplicate-action rate,
coverage/censoring, state safety, robustness, and deterministic replay.

## Privacy and M5 firewall

Only generated aliases, manifest/object hashes, redacted counts, aggregate
digests, and bounded diagnostic bands may be retained. Raw rows, credentials,
private paths, journals/deals/fees/profits, `.ex5`, and M5 inputs/outcomes are
out of scope. Oracle observations cannot control policy, accounting, or
candidate selection.

## Acceptance

E-001 is complete only when the contract, authorization, source receipt,
machine-readable gate schema, independent plan review/revision, and focused
schema/firewall tests all pass. No E-002 source may be opened before that
point.
