# RETRO-BOT-003 Sequential Multi-Cycle Receipt

Status: accepted; source objects remain quarantine-only.

Authorization: owner-authorized RETRO follow-on to RETRO-BOT-002, 2026-08-02.

## Exact input binding

- Base configuration: `RETRO-BOT-001-config.json`, digest
  `b420d9d014c2cac67461eda9603a200b2a48d0ad1fa0299baaf1c8cdeded5c52`.
- Report object set: 9 registered aliases, manifest digest
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`.
- Tick object set: 39 registered aliases, manifest digest
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`.
- The runner verified the locked aliases, hashes, path containment, suffixes,
  and accepted manifests before parsing; no new source was introduced.

## Run and reproducibility record

- Two fresh sequential aggregates were written as direct children of the
  ignored RETRO-BOT-003 multi-cycle run root.
- Both aggregates passed schema/digest validation, were byte-identical, and
  produced digest
  `0f803aad89838a45e31e4589897d7019f65c4fc7e888d7d5dfa8c02671cd9831`.
- The tracked result was generated only from the first validated aggregate.
- The population contains 189 chronological eligible cycles for every
  policy/clock row; no overlap or invalid-order cycle occurred in this run.

No raw rows, prices, timestamps, interval identifiers, cycle identifiers,
traces, tickets, credentials, or source paths are retained in tracked
artifacts. The result is sequential synthetic accounting only and is not an
M5 input, model, evaluation, threshold, gate, profitability claim, or
live-execution bot.

Validation: focused RB-007/RB-006 tests passed 17; full suite passed 225; the
privacy checker, py_compile, diff check, and independent final review passed
with no P0-P3 findings.
