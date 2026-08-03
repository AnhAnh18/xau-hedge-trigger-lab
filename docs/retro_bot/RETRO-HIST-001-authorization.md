# RETRO-HIST-001 Authorization Record

Authorization status: accepted for the bounded RH-001 lot-distribution audit
in the owner-authorized RETRO-HIST goal on 2026-08-03.

The owner requested a separate RETRO historical-reconstruction lane while M5
remains independent. This authorization covers only the exact archived
RETRO-003 report/tick object set and the half-open server population pinned in
`RETRO-HIST-001-source-receipt.md`. It authorizes in-memory parsing of the nine
report aliases' `positions` and `open_positions` tables for RH-001 aggregate
output. It does not authorize new sources, August M5 data, deals/orders,
journals, terminal caches, credentials, `.ex5`, live execution, or M5 use.

Retention: project close or earlier owner revocation.

Required attestations: `raw_rows_printed=false` and
`m5_firewall=M5_FIREWALL_ATTESTATION_V1`.
