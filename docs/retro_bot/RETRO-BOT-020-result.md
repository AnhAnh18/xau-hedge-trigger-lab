# RETRO-BOT-020 Result

Status: descriptive RETRO milestone; no M5 input, model, threshold,
evaluation, gate, live, or profitability claim.

## Outcome

`no-supported-candidate`.

The autonomous and oracle-diagnostic paths are isolated, causal, typed, and
redacted. The registered RH-002 source boundary and object-hash pins validate,
but the synthetic walk-forward acceptance fixture is fully censored in the
holdout (`supported_count=0`, `censor_rate=1.0`). Therefore no candidate is
called supported and no tuning is authorized.

## Evidence

- Walk-forward aggregate digest: `657ee48c8890d284ae3a29625790ca0c1899b9670193cec4c9808dabd1cfda79`.
- Paper-account aggregate digest: `5c9bb4ca863dfd1d35c33a2552964b4f127c01c9d42941fab24dfad245ab83a7`.
- Holdout seal: `89efb5f65f2d4040b63c228eb4489399914756f12c7821386ba5cdaad3de79e0`.
- Holdout consumption receipt: `99b261d3c5c926958784d23c33270b64b6a47c8c17fab235435e63751cf517d8`.
- Full regression: `424 passed` with `--basetemp .rb020-basetemp`.
- Focused RB-020 tests: `13 passed`.
- Privacy/RB focused checks: `15 passed`.
- Two identical CLI walk-forward reruns: byte-identical, SHA-256
  `ebb147570162fbfa95abd18c07e4d0e13729e741674cde4d32307f6737e14c43`.
- Independent final re-review: `PASS`, no P0-P3 findings in scope.

## Boundaries

The source receipt is limited to the accepted RH-002 reports/ticks and
in-memory parsing. Oracle labels remain diagnostics only. Accounting uses
Decimal Bid/Ask semantics and synthetic costs; it does not control policy or
candidate selection. RB-020 remains permanently outside M5 manifests and
execution surfaces.
