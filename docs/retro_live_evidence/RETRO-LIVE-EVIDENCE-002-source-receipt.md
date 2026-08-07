# RETRO-LIVE-EVIDENCE-002 Source Receipt

Status: owner-authorized in the current task on 2026-08-06 and metadata-
validated before source parsing.

- Authorization: `E002-HIST-SUMMER-20260806`
- Scope: bounded actionful capture only; execution surface disabled
- Source set: all nine report aliases `report-001.html` through
  `report-009.html` plus the 14 weekly tick aliases from `2026-04-25` through
  `2026-08-01`, exactly as pinned by the accepted RETRO-003 manifests
- Parent report manifest SHA-256:
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`
- Parent tick manifest SHA-256:
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`
- Canonical population: `[2026-04-30T21:00:00.000000Z,
  2026-07-30T21:00:00.000000Z)` under `UTC+3-summer`
- Allowed projection: report `position_id`, `symbol`, `side`, `volume`,
  `open_time`, `close_time` fields for in-memory deduplication, and tick
  `time_utc`, `bid`, `ask`; no such source rows are retained
- Parser: `e002-hist-redactor-2`; canonicalization: `e002-c14n-2`
- Retention: redacted aggregates and digests only, deadline
  `2026-08-13T12:00:00.000000Z`
- Receipt digest:
  `ce95e862518a16b896670fd98ac87a1d4cada8f21fb3eeaf4eb93c686d8b9fd2`

The machine-readable exact alias/hash/byte receipt is
`RETRO-LIVE-EVIDENCE-002-source-receipt.json`. Raw rows, credentials, private
paths, source expansion, M5 inputs, and execution surfaces remain forbidden.
