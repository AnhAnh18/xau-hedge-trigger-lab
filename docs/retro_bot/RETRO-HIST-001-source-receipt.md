# RETRO-HIST-001 Source Receipt

Status: accepted for the current owner-authorized RETRO-HIST-001 task on
2026-08-03. Retention is until project close or earlier owner revocation.

Owner authorization reference:
`docs/retro_bot/RETRO-HIST-001-authorization.md`; the record cites the
current goal thread
`019fb8a7-dd3d-7b33-b5f4-a221345f41fa`, whose objective explicitly authorizes
the bounded RETRO historical-reconstruction lane and its archived source
boundary.

## Parent receipt and manifests

The source set is inherited without expansion from
`docs/observational_cases/RETRO-003-2025-11_to_2026-07-history-screening-receipt.md`.
The parent receipt pins the exact quarantine run, object aliases, object
hashes, and accepted transfer status.

- report manifest SHA-256:
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`;
- tick manifest SHA-256:
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`;
- report aliases: `report-001.html` through `report-009.html`;
- tick aliases: exactly the 39 aliases listed in the parent receipt, with no
  additions, substitutions, or deletions;
- deterministic server population:
  `[2025-11-01 00:00:00, 2026-07-31 00:00:00)`.

## Quarantine run labels

- report run label: `retro-003-history-screening-20260801/run-20260801T160000`;
- tick run label: `mt5-ticks-20260801/run-20260801T061208`.

The implementation resolves these labels only beneath its fixed quarantine
root. Absolute or user-private paths are not part of the receipt.

## RH-001 access receipt

RH-001 may open only the nine report aliases and only the `positions` and
`open_positions` tables in memory. It must verify both parent manifests and
all report object hashes before parsing. The tick manifest is verified for
boundary integrity but tick objects are not opened in RH-001.

No raw rows, detailed timelines, prices, comments, tickets, credentials,
private paths, journals, terminal caches, `.ex5`, XLSX/PNG companions, August
M5 data, or new source are authorized. Any expansion requires a new owner
decision, contract, and receipt.

Required result attestations are `raw_rows_printed=false` and
`m5_firewall=M5_FIREWALL_ATTESTATION_V1`.
