# RETRO-LIVE-EVIDENCE-002 Authorization Template

This document is intentionally unfilled. It is a request/checklist, not an
authorization and not a source receipt. E-002 must not open or hash any source
until every field below is completed and independently reviewed.

## Owner decision

- `authorization_id`: `<unique case id>`
- `owner_approval_utc`: `<RFC3339 timestamp>`
- `scope`: `bounded-actionful-capture-only`
- `retention_deadline_utc`: `<RFC3339 timestamp>`
- `new_sources_authorized`: `<true|false>`
- `m5_inputs_models_thresholds_gates_untouched`: `<true>`
- `execution_surface_authorized`: `<false>`

## Exact source receipt

For each source object, provide an opaque alias only; never record a private
path, credential, account number, ticket, terminal cache, or `.ex5` artifact.

- `source_aliases`: `<opaque aliases>`
- `object_types`: `<tick/report/observation>`
- `sha256_by_alias`: `<64-hex digest per alias>`
- `byte_count_by_alias`: `<positive integer per alias>`
- `population_utc_half_open`: `[<start>, <end>)`
- `source_timezone_code`: `<declared broker timezone or explicit ambiguous>`
- `allowed_fields_by_alias`: `<exact allowlist>`
- `canonicalization_version`: `<version>`
- `parser_version`: `<version>`
- `retention`: `redacted-aggregates-and-digests-only`
- `source_receipt_sha256`: `<digest over this receipt without this field>`

## Required allowlist

Ticks may contain only canonical UTC timestamp, bid, and ask fields. Reports or
observations may contain only the redacted lifecycle/action/state fields needed
to form E-002 cycle aggregates. Raw rows are parsed in memory and are never
printed, committed, or placed in an M5 manifest.

## Gate and blindness acknowledgements

- The frozen E-001 gate digest is unchanged.
- Development, validation, and holdout windows are chronological and disjoint.
- Holdout labels and outcomes remain unopened until structural intake passes.
- Missing/ambiguous timezone, hash/window/field mismatch, oracle leakage,
  privacy exposure, M5 contamination, or source expansion is a hard stop.
