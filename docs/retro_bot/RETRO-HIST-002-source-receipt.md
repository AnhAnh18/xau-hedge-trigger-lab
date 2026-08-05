# RETRO-HIST-002 Source Receipt

Status: accepted for the owner-authorized RH-002 task on 2026-08-03.

RH-002 reuses exactly the RH-001 source receipt and authorization record:

- `docs/retro_bot/RETRO-HIST-001-authorization.md`;
- `docs/retro_bot/RETRO-HIST-001-source-receipt.md`;
- report manifest SHA-256
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`;
- tick manifest SHA-256
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`;
- exact report aliases `report-001.html` through `report-009.html`;
- exact inherited 39 tick aliases and opaque run labels;
- population `[2025-11-01 00:00:00, 2026-07-31 00:00:00)`.

The source boundary is not expanded. RH-002 may stream only the receipt-pinned
report fields and tick columns named in its contract. It must never retain raw
rows or expose source paths in failure output.
