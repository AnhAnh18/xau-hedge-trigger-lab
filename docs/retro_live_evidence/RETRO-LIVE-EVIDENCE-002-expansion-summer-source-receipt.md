# RETRO-LIVE-EVIDENCE-002 Summer Expansion Source Receipt

Status: owner-authorized metadata-only expansion in the current task on
2026-08-07. This receipt was generated from the accepted RETRO-003 receipt
metadata; no raw source object was opened or hashed for this expansion.

- Authorization: `E002-EXP-SUMMER-20260807`
- Parent report manifest SHA-256: `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`
- Parent tick manifest SHA-256: `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`
- Source objects: 9 report aliases and 3 tick aliases
- Tick aliases: `XAUUSD_ticks_2026-04-04_to_2026-04-11.csv`, `XAUUSD_ticks_2026-04-11_to_2026-04-18.csv`, `XAUUSD_ticks_2026-04-18_to_2026-04-25.csv`
- Registered server-time window: [2026-04-04 00:00, 2026-04-25 00:00) server time under UTC+3.
- Canonical UTC window: `[2026-04-03T21:00:00.000000Z, 2026-04-24T21:00:00.000000Z)`
- Source timezone code: `UTC+3-summer`
- Boundary treatment: The interval from the winter cutoff through 2026-04-04 00:00 server time is intentionally censored; this receipt starts after the transition boundary under UTC+3.
- Allowed projection: report `position_id`, `symbol`, `side`, `volume`, `open_time`, `close_time`; tick `time_utc`, `bid`, `ask`
- Parser: `e002-expansion-redactor-1`; canonicalization: `e002-expansion-c14n-1`
- Retention: redacted aggregates and digests only, deadline `2026-08-21T12:00:00.000000Z`
- Execution surface: disabled; M5 inputs, models, thresholds, and gates untouched
- Receipt SHA-256: `3a59c1af6e80f490829adef004cf84925c269db124a57ef8c1b8cc16bbba13d8`

The JSON receipt contains the exact per-alias SHA-256 and byte-count metadata.
It is a metadata-only authorization envelope and does not authorize source
expansion beyond the listed aliases or the registered half-open window.
