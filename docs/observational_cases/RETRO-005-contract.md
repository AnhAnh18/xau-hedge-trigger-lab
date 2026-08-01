# RETRO-005: Historical One-Leg Case

Status: owner-authorized; source receipt accepted; independent review PASS;
RETRO-005 complete.

## Purpose

Describe one preselected historical one-leg interval from the RETRO-003
stratified inventory. This case is descriptive only and cannot change M5
contracts, models, thresholds, evaluations, or gates.

## Exact scope

- Server interval: inclusive `2026-03-03 23:55:47` through
  `2026-03-04 01:03:00`.
- Selected target date: `2026-03-03`; selected side:
  `buy`; inventory duration band: `3600_to_14400_seconds`.
- Report alias: `report-005.html`.
- Tick alias: `XAUUSD_ticks_2026-02-28_to_2026-03-07.csv`.
- Registered clock candidates: UTC+2 and UTC+3. A tick metric is accepted
  only when exactly one candidate supports both report boundaries; otherwise
  the clock result and price-derived metric are unresolved.

No journal, terminal log, support cache, screenshot, M1 object, XLSX/PNG
companion, or other source is in scope.

## Questions

1. Is the selected one-leg interval and its following opposite-side re-hedge
   uniquely reconstructable?
2. Which registered clock candidate, if any, supports the tick window and
   report-boundary alignment?
3. What aggregate quote-quality, coarse adverse-excursion, and continuation
   indicators are observed without inferring a trigger or manual action?

## Safeguards and acceptance

- Verify both source objects against the accepted RETRO-003 manifests before
  parsing, including quarantine-root, exact parent/name/suffix, and SHA-256.
- Stream ticks and retain aggregate metrics only; never print or commit rows,
  prices, tickets, or detailed timelines.
- Keep journal/manual-intervention status unresolved because no journal is in
  scope.
- Preserve the M5 information firewall and obtain a fresh independent review
  before marking this case complete.

## Provenance

Report manifest digest: `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`.
Tick manifest digest: `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`.
