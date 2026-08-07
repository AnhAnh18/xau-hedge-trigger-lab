# RETRO-LIVE-EVIDENCE-002 Winter Expansion Source Receipt

Status: owner-authorized metadata-only expansion in the current task on
2026-08-07. This receipt was generated from the accepted RETRO-003 receipt
metadata; no raw source object was opened or hashed for this expansion.

- Authorization: `E002-EXP-WINTER-20260807`
- Parent report manifest SHA-256: `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`
- Parent tick manifest SHA-256: `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`
- Source objects: 9 report aliases and 22 tick aliases
- Tick aliases: `XAUUSD_ticks_2025-11-01_to_2025-11-08.csv`, `XAUUSD_ticks_2025-11-08_to_2025-11-15.csv`, `XAUUSD_ticks_2025-11-15_to_2025-11-22.csv`, `XAUUSD_ticks_2025-11-22_to_2025-11-29.csv`, `XAUUSD_ticks_2025-11-29_to_2025-12-06.csv`, `XAUUSD_ticks_2025-12-06_to_2025-12-13.csv`, `XAUUSD_ticks_2025-12-13_to_2025-12-20.csv`, `XAUUSD_ticks_2025-12-20_to_2025-12-27.csv`, `XAUUSD_ticks_2025-12-27_to_2026-01-03.csv`, `XAUUSD_ticks_2026-01-03_to_2026-01-10.csv`, `XAUUSD_ticks_2026-01-10_to_2026-01-17.csv`, `XAUUSD_ticks_2026-01-17_to_2026-01-24.csv`, `XAUUSD_ticks_2026-01-24_to_2026-01-31.csv`, `XAUUSD_ticks_2026-01-31_to_2026-02-07.csv`, `XAUUSD_ticks_2026-02-07_to_2026-02-14.csv`, `XAUUSD_ticks_2026-02-14_to_2026-02-21.csv`, `XAUUSD_ticks_2026-02-21_to_2026-02-28.csv`, `XAUUSD_ticks_2026-02-28_to_2026-03-07.csv`, `XAUUSD_ticks_2026-03-07_to_2026-03-14.csv`, `XAUUSD_ticks_2026-03-14_to_2026-03-21.csv`, `XAUUSD_ticks_2026-03-21_to_2026-03-28.csv`, `XAUUSD_ticks_2026-03-28_to_2026-04-04.csv`
- Registered server-time window: [2025-11-01 00:00, 2026-03-28 00:00) server time under UTC+2.
- Canonical UTC window: `[2025-10-31T22:00:00.000000Z, 2026-03-27T22:00:00.000000Z)`
- Source timezone code: `UTC+2-winter`
- Boundary treatment: The 2026-03-28 through 2026-04-04 alias is bound only as a boundary-support object; the registered window ends before it, so the DST transition interval is censored.
- Allowed projection: report `position_id`, `symbol`, `side`, `volume`, `open_time`, `close_time`; tick `time_utc`, `bid`, `ask`
- Parser: `e002-expansion-redactor-1`; canonicalization: `e002-expansion-c14n-1`
- Retention: redacted aggregates and digests only, deadline `2026-08-21T12:00:00.000000Z`
- Execution surface: disabled; M5 inputs, models, thresholds, and gates untouched
- Receipt SHA-256: `37d3d84e52b43ad4bb318c901df12d42edef278c22fcef8317373bd6c3f9f96d`

The JSON receipt contains the exact per-alias SHA-256 and byte-count metadata.
It is a metadata-only authorization envelope and does not authorize source
expansion beyond the listed aliases or the registered half-open window.
