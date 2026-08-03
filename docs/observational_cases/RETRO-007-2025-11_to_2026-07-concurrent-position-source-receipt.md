# RETRO-007 Source Receipt

Status: accepted by owner authorization in the current task on 2026-08-03.

RETRO-007 reuses, without expansion, the hash-verified RETRO-003 source set:

- parent receipt: `RETRO-003-2025-11_to_2026-07-history-screening-receipt.md`;
- report manifest SHA-256:
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`;
- tick manifest SHA-256:
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`;
- exact report aliases: `report-001.html` through `report-009.html`;
- exact tick aliases: the 39 aliases in the parent receipt, with no additions,
  substitutions, or deletions;
- deterministic server population: `[2025-11-01 00:00:00,
  2026-07-31 00:00:00)`;
- retention: project close or earlier owner revocation.

The receipt permits only in-memory parsing and aggregate anonymized output.
It does not authorize journals, terminal logs, support caches, screenshots,
M1 objects, XLSX/PNG companions, credentials, private paths, raw-row output,
or any M5 input. `raw_rows_printed=false` and
`m5_firewall=M5_FIREWALL_ATTESTATION_V1` are mandatory result attestations.
