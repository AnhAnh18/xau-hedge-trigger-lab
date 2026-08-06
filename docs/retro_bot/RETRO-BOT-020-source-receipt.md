# RETRO-BOT-020 Source Receipt

Status: accepted on 2026-08-06 under the owner authorization in
`RETRO-BOT-020-authorization.md`.

This receipt inherits exactly the RH-002 archive:

- report run `retro-003-history-screening-20260801/run-20260801T160000`;
- tick run `mt5-ticks-20260801/run-20260801T061208`;
- report manifest SHA-256
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`;
- tick manifest SHA-256
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`;
- reports `report-001.html` through `report-009.html`;
- the exact 39 tick aliases enumerated in the authorization record;
- population `[2025-11-01 00:00:00, 2026-07-31 00:00:00)` server time.

Allowed fields are report `positions`/`open_positions` lifecycle fields needed
for symbol, side, quantity, open/close time and state labels, plus tick
`time_utc`, `bid`, and `ask`. Parsing is bounded in memory; only redacted
aggregates and receipt digests may be retained.

No journal, deals, fees, swaps, profits, credentials, terminal cache, `.ex5`,
August M5 data, or live/demo surface is in scope. Every alias, path and object
hash must verify before opening; any mismatch is a hard stop.
