# RETRO-HIST-004 Source Receipt

Status: accepted on 2026-08-05 under the owner's explicit RH-004
authorization: use exactly the accepted hash-verified RH-002 archive for
observed-lot paper accounting, with no new source and no M5/live use.

This receipt inherits `docs/retro_bot/RETRO-HIST-002-source-receipt.md` and its
parent RETRO-003 receipt without alteration:

- report manifest SHA-256:
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`
- tick manifest SHA-256:
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`
- report aliases: `report-001.html` through `report-009.html`;
- tick aliases: the exact 39 aliases pinned by the RH-002 receipt;
- population: `[2025-11-01 00:00:00, 2026-07-31 00:00:00)` server time;
- source fields: positions/open_positions lifecycle fields and tick columns
  only, under the inherited hash-verified quarantine boundary.

No deals, commissions, fees, swaps, profits, journals, terminal caches,
credentials, private paths, `.ex5`, August M5 data, or live/demo surface are
authorized. The implementation must verify every manifest object, alias, path,
and digest before opening data and must stop on any mismatch. Retained output is
aggregate-only, redacted, and outside every M5 input manifest.
