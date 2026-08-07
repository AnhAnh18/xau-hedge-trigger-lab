# RETRO-LIVE-EVIDENCE E-002 Plan

Status: draft pending independent critique. Owner authorization was granted in
the current task on 2026-08-06; this plan remains bounded to the existing
hash-verified RETRO-003 report/tick archive and does not authorize execution.

## Objective

Create a case-specific E-002 source receipt, verify its metadata without
opening source rows, then run a bounded aggregate-only actionful intake. The
intake must emit only redacted cycle/checkpoint aggregates and digests. It may
not retain or print raw rows, detailed timelines, credentials, private paths,
M5 artifacts, or execution requests.

## Source boundary

Use exactly the nine report aliases and 39 weekly tick aliases already pinned
by the accepted RETRO-003 receipt and manifests. No XLSX/PNG companions,
journals, caches, `.ex5`, credentials, August M5 inputs, or neighboring files
are in scope. Verify every object hash and byte count before parsing. The
population is `[2025-11-01T00:00:00.000000Z,
2026-07-31T00:00:00.000000Z)`; server-clock ambiguity is represented by the
registered `ambiguous-censor` policy and unresolved boundaries are censored.

## Workflow

1. Produce a metadata-only owner authorization/source receipt with opaque
   aliases, exact hashes and byte counts, allowed canonical fields, parser and
   canonicalization versions, retention deadline, and self-digest.
2. Validate the receipt through the stdin-only validator before any source
   parser is opened.
3. Verify the inherited report/tick manifests and stream the bounded sources
   through the existing aggregate-only lifecycle/tick adapters. Convert only
   accepted lifecycle checkpoints into the E-002 redacted cycle schema.
4. Run the frozen E-002 gate aggregation, determinism rerun, schema/privacy/
   M5 firewall checks, and focused tests. If actionful coverage is below the
   frozen target, return `insufficient-actionful-coverage` without lowering
   thresholds or using the result for model selection.
5. Obtain an independent implementation review and fresh re-review. Fix only
   confirmed P0-P3 findings, then record state only if the final verdict is
   PASS.

## Acceptance

- Receipt validator accepts only the exact metadata envelope and all source
  object hashes/bytes match the inherited manifests.
- Raw rows and credentials never appear in stdout, logs, tracked reports, or
  M5 manifests; `raw_rows_printed=false` and the RETRO-only firewall hold.
- Two independent canonical runs are byte-identical or the result is HOLD.
- E-002 emits a frozen taxonomy result only; it does not imply profitability,
  clone fidelity, demo readiness, canary readiness, or live suitability.
