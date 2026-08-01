# RETRO-002: 2026-07-31 Tick-Source Reconciliation

Status: owner-authorized; source receipt accepted; descriptive analysis
complete; independent review PASS.

## Purpose

Reconcile the original 2026-07-31 tick export with the later MT5 weekly tick
archive used by RETRO-001.  The goal is to explain why the two observations
do not currently agree on the apparent drawdown band, without changing the
RETRO-001 result or making an M5 decision.

## Lane and authorization

This is a new RETRO case authorized by the owner in the current task on
2026-08-01.  It permits bounded, in-memory parsing of only the three exact
source objects below after the source receipt is accepted.  Retention is until
project close or earlier owner revocation.  No journal, adjacent date, report
set, or other tick source is in scope.

RETRO-002 remains outside every M5 input manifest.  It cannot modify M5
contracts, preregistrations, models, thresholds, evaluation, or gates.  Raw
rows, detailed timelines, credentials, and private paths must not be printed
or committed; only aggregate, anonymized results may be retained.

## Source scope

The source receipt must contain these generated aliases and exact hashes:

- `report-002.html`: the daily owner export originally named `3107.html`;
- `ticks-original-002.csv`: the original 2026-07-31 XAUUSD tick export; and
- `ticks-archive-002.csv`: the accepted RETRO-001 weekly archive object that
  spans 2026-07-25 through 2026-08-01.

## Deterministic window and questions

Use inclusive recorded server time `[2026-07-31 16:00:00.000,
2026-07-31 17:21:00.000]` only.  Under the registered window-scoped UTC+3
inference, the corresponding UTC interval is inclusive
`[2026-07-31 13:00:00.000Z, 2026-07-31 14:21:00.000Z]`.  The original export
has no timezone declaration, so it may receive a separate source-clock
diagnostic.  The archive export explicitly declares `time_utc` and must be
evaluated only through the UTC-to-server+3 mapping.  Do not compare a
source-clock diagnostic for the original against a shifted event window in the
archive.

1. Do the original and archived tick sources cover the same event window?
2. Do they differ in timestamp basis, quote availability, duplicate/gap
   structure, or price bands after the fixed conversion?
3. Does the source reconciliation explain the earlier drawdown discrepancy?

The analysis must report source agreement, conflict, or unresolved status. It
must not infer a bot trigger, manual intervention, profitability, or ownership.

## Method and safeguards

1. Verify the three objects against the append-only RETRO-002 manifest before
   parsing; reject any alias, hash, suffix, or source-root mismatch.
2. Stream each tick source and retain only aggregate window metrics.  Do not
   persist raw rows or detailed timelines.
3. Compare coverage, timestamp alignment, quote validity, and coarse price
   bands using identical window and conversion rules.
4. Keep the existing RETRO-001 aggregate and source receipt byte-for-byte
   unchanged.
5. Publish only an aggregate result note with source manifest and result
   hashes, limitations, and an explicit M5 firewall statement.

## Acceptance criteria

- All three source objects are hash-verified and quarantined append-only.
- No raw rows or detailed timeline is printed, committed, or added to M5.
- Each question is labeled `observed`, `compatible`, or `unresolved`.
- RETRO-001 artifacts and all frozen M5 artifacts remain unchanged.
- A fresh independent review reports no P0-P3 finding before this case is
  marked complete.
