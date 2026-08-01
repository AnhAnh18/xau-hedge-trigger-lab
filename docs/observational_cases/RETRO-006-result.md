# RETRO-006 Result: Historical One-Leg Case

Status: descriptive result; independent review PASS; RETRO-006 complete.

## Provenance

Report manifest digest: `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`.
Tick manifest digest: `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`.
Aggregate result digest: `a97ede3f9a4ab975ffc45f1c87b7cecad5d7e9246cd17b3182331b3cc64fc48b`.
The source objects remain quarantine-only and are not M5 inputs.

## Observed

- The preselected `2026-07-01` `buy` one-leg interval
  is uniquely reconstructed for `560` seconds, with
  the registered opposite-side re-hedge transition at its boundary.
- No continuation opposite-side re-hedge occurs inside the selected interval.
- The selected window contains `3` order rows and
  their comments are blank; no journal was authorized or inspected.
- Both registered clock candidates support the report-boundary alignment, so
  the clock status is `ambiguous_multiple_supported_mappings` rather than a unique mapping.

## Interpretation

- **Observed:** this preselected case shows a finite one-leg interval followed
  by the registered opposite-side re-hedge, with no continuation opposite-side
  re-hedge before the interval ends.
- **Compatible:** this sequence is compatible with a state-dependent rotation
  that waits before re-hedging; it does not establish why it waits.
- **Unresolved:** because UTC+2 and UTC+3 both support the tick boundaries, the
  adverse-excursion band is not accepted as a single result. The trigger,
  manual intervention, profitability, ownership, and historical broker clock
  remain unresolved.

No journal, cache, screenshot, M1 object, XLSX/PNG companion, or additional
source was inspected. This is descriptive RETRO evidence only and does not
modify, fit, evaluate, or gate any M5 artifact.
