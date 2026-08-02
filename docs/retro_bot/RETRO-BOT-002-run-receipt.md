# RETRO-BOT-002 Historical Paper-Backtest Receipt

Status: accepted; source objects remain quarantine-only.

Authorization: owner-authorized RETRO follow-on to RETRO-BOT-001, 2026-08-02.

## Exact input binding

- Base configuration: `RETRO-BOT-001-config.json`, digest
  `b420d9d014c2cac67461eda9603a200b2a48d0ad1fa0299baaf1c8cdeded5c52`.
- Report object set: 9 registered aliases, manifest digest
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`.
- Tick object set: 39 registered aliases, manifest digest
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`.
- The runner verified the locked aliases, path containment, suffixes, hashes,
  and accepted manifests before parsing; no new source was introduced.

## Run and reproducibility record

- After the cross-chunk/path ordering remediation, two fresh paper aggregates
  were written as direct children of the ignored RETRO-BOT-002 paper-run root.
- Both aggregates passed schema/digest validation, were byte-identical, and
  produced digest
  `4f40faae72bb4cd32df8ea5b24fcea9238912f77c3b0ca0bbd69deba088148f6`.
- The tracked result was generated only from the first validated aggregate.
- The population contains 189 eligible intervals for every policy/clock row;
  quantity is the fixed synthetic 1.0 and costs are fixed at none.

No raw rows, prices, timestamps, interval identifiers, traces, tickets,
credentials, or source paths are retained in tracked artifacts. The result is
descriptive synthetic accounting only and is not an M5 input, model,
evaluation, threshold, gate, profitability claim, or live-execution bot.

Validation: focused RETRO-BOT-002 tests passed 8; full suite passed 216; the
privacy checker, py_compile, diff check, and independent post-remediation
RB-006 review passed with no P0-P3 findings.
