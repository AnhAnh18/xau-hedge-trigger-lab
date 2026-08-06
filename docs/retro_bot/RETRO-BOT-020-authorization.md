# RETRO-BOT-020 Authorization Record

Status: accepted by owner on 2026-08-06 for the exact bounded scope below.
No source object was opened before this authorization was recorded.

## Proposed authorization

Authorize bounded in-memory RB-020 parsing of exactly the accepted RH-002
archive for autonomous historical reconstruction and oracle diagnostics only.

- Report run: `retro-003-history-screening-20260801/run-20260801T160000`.
- Tick run: `mt5-ticks-20260801/run-20260801T061208`.
- Report manifest SHA-256:
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`.
- Tick manifest SHA-256:
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`.
- Population: `[2025-11-01 00:00:00, 2026-07-31 00:00:00)` server time.
- Retention: in-memory parsing only; retain redacted aggregates and receipt
  digests, never raw rows or detailed timelines.

## Exact aliases

Reports: `report-001.html` through `report-009.html`.

Ticks:

`XAUUSD_ticks_2025-11-01_to_2025-11-08.csv`,
`XAUUSD_ticks_2025-11-08_to_2025-11-15.csv`,
`XAUUSD_ticks_2025-11-15_to_2025-11-22.csv`,
`XAUUSD_ticks_2025-11-22_to_2025-11-29.csv`,
`XAUUSD_ticks_2025-11-29_to_2025-12-06.csv`,
`XAUUSD_ticks_2025-12-06_to_2025-12-13.csv`,
`XAUUSD_ticks_2025-12-13_to_2025-12-20.csv`,
`XAUUSD_ticks_2025-12-20_to_2025-12-27.csv`,
`XAUUSD_ticks_2025-12-27_to_2026-01-03.csv`,
`XAUUSD_ticks_2026-01-03_to_2026-01-10.csv`,
`XAUUSD_ticks_2026-01-10_to_2026-01-17.csv`,
`XAUUSD_ticks_2026-01-17_to_2026-01-24.csv`,
`XAUUSD_ticks_2026-01-24_to_2026-01-31.csv`,
`XAUUSD_ticks_2026-01-31_to_2026-02-07.csv`,
`XAUUSD_ticks_2026-02-07_to_2026-02-14.csv`,
`XAUUSD_ticks_2026-02-14_to_2026-02-21.csv`,
`XAUUSD_ticks_2026-02-21_to_2026-02-28.csv`,
`XAUUSD_ticks_2026-02-28_to_2026-03-07.csv`,
`XAUUSD_ticks_2026-03-07_to_2026-03-14.csv`,
`XAUUSD_ticks_2026-03-14_to_2026-03-21.csv`,
`XAUUSD_ticks_2026-03-21_to_2026-03-28.csv`,
`XAUUSD_ticks_2026-03-28_to_2026-04-04.csv`,
`XAUUSD_ticks_2026-04-04_to_2026-04-11.csv`,
`XAUUSD_ticks_2026-04-11_to_2026-04-18.csv`,
`XAUUSD_ticks_2026-04-18_to_2026-04-25.csv`,
`XAUUSD_ticks_2026-04-25_to_2026-05-02.csv`,
`XAUUSD_ticks_2026-05-02_to_2026-05-09.csv`,
`XAUUSD_ticks_2026-05-09_to_2026-05-16.csv`,
`XAUUSD_ticks_2026-05-16_to_2026-05-23.csv`,
`XAUUSD_ticks_2026-05-23_to_2026-05-30.csv`,
`XAUUSD_ticks_2026-05-30_to_2026-06-06.csv`,
`XAUUSD_ticks_2026-06-06_to_2026-06-13.csv`,
`XAUUSD_ticks_2026-06-13_to_2026-06-20.csv`,
`XAUUSD_ticks_2026-06-20_to_2026-06-27.csv`,
`XAUUSD_ticks_2026-06-27_to_2026-07-04.csv`,
`XAUUSD_ticks_2026-07-04_to_2026-07-11.csv`,
`XAUUSD_ticks_2026-07-11_to_2026-07-18.csv`,
`XAUUSD_ticks_2026-07-18_to_2026-07-25.csv`,
`XAUUSD_ticks_2026-07-25_to_2026-08-01.csv`.

## Allowed fields

- Reports: `positions` and `open_positions` lifecycle fields needed for
  symbol, side, quantity, open/close time, and conservative state labels.
- Ticks: `time_utc`, `bid`, and `ask` only.

No deals, orders, commission, fee, swap, profit, journal, credential,
terminal-cache, `.ex5`, August-M5, or live/demo field is authorized.

## Firewall

RB-020 remains outside every M5 input, model, threshold, evaluation, gate, and
frozen artifact. Oracle labels are diagnostics only and cannot control
autonomous state, features, actions, accounting, or candidate selection.

The owner acceptance above is the authorization to open only the listed
objects under the stated in-memory and redacted-output restrictions.
