# RETRO-BOT-004 Implementation Plan

Status: revised after independent plan critique; implementation has not
started.

## Working profile

Use the complex profile for source-boundary, fold, bootstrap, privacy, and
firewall logic. Use a balanced implementation model for code and a low-cost
deterministic model for reruns and formatting. The independent reviewer and
re-review must run in separate sessions from implementation and fixes.

## Plan

1. Add a machine-readable RB-008 configuration that pins the RB-001 config
   digest, receipt digests, the exact three temporal folds, both immutable
   bootstrap scenarios (`left_censored` and fixed `HEDGED` seed with zero
   warm-up), clock ids, censor classes, and minimum-support stop conditions.
2. Add immutable parsers/validators for the configuration and accepted source
   receipts. Verify aliases, manifest hashes, path containment, suffixes, and
   partial-file rejection before opening any raw object. Reuse existing
   RB-001 adapters instead of duplicating raw parsing.
3. Add deterministic fold assignment by the pinned report date ranges and
   report/session/case unit. Permit a verified weekly tick object to serve
   multiple folds only through strict in-memory half-open time masks. Reject
   duplicate/ambiguous report ownership, cross-fold intervals, overlapping
   continuations, and random assignment.
4. Add an explicit bootstrap validator. Produce both the mandatory
   `left_censored` evidence row and the assumption-dependent fixed `HEDGED`
   seed row. The former never becomes autonomous-eligible; the latter is
   fixed before parsing and is never changed from observed events. Keep oracle
   labels outside the future policy-state path.
5. Add clock and boundary audit helpers for UTC+2, UTC+3, and the pinned
   EET/EEST-style transitions at `01:00:00Z` on 2025-03-30 (2 -> 3),
   2025-10-26 (3 -> 2), 2026-03-29 (2 -> 3), and 2026-10-25 (3 -> 2).
   Preserve half-open windows and classify unresolved
   transitions, second-level ambiguity, missing tick coverage, invalid
   transitions, cross-fold continuation, and right censoring without silently
   repairing input order. Apply the contract's fixed censor precedence.
6. Build an aggregate-only population manifest/result writer. Retain only
   digests, fold/bootstrap/censor counts, clock ids, schema version, and the
   canonical result digest. Reject raw-like keys, private paths, timestamps,
   prices, tickets, and identifiers in outputs and logs.
7. Add synthetic tests for manifest/config tampering, pinned report dates,
   fold determinism/disjointness, a weekly tick object crossing a fold,
   cross-midnight grouping, bootstrap absence, DST transitions,
   second-resolution collisions, tick gaps, both bootstrap rows,
   censor precedence/conservation, minimum-support stop, privacy, the M5
   firewall, and byte-identical reruns.
8. Run focused RB-008 tests, `py_compile`, `uv run --offline python
   scripts/check_privacy.py`, the pinned firewall/contract scan,
   `git diff --check`, and the isolated full suite. Run historical source
   inventory only through the locked manifest; do not inspect new raw sources.
9. Submit the implementation to an independent reviewer. Fix every confirmed
   in-scope P0-P3 finding, run a fresh re-review, and regenerate the aggregate
   twice before state recording.

## Acceptance

RB-008 is complete only if all contract gates pass, both bootstrap rows are
reported, the population sufficiency decision is explicit per row, the
aggregate is privacy-safe and byte-identical across two runs, and the
independent re-review returns PASS. A fixed-seed insufficiency records
`insufficient_population` and blocks RB-009; the left-censored row remains a
required evidence result. Neither outcome permits source expansion or
threshold tuning.
