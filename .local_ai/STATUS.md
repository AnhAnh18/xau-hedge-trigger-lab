# Current Status

## Current phase

M5 — Trigger Inference (M5-004 development package frozen; fresh August
external evaluation pending)

## Completed

- M0–M4 canonical parsing, lifecycle reconstruction, event/tick alignment,
  causal trigger sampling, and bounded hypothesis tests
- M5-000 causal risk-time and acquisition contracts
- M5-002 state-age occurrence pilot and conditional-statistic remediation
- M5-003 causal price-increment implementation and independent review
- Frozen M5-003 external evaluation on 2026-07-27 through 2026-07-29
- M5-003 PR #10 squash-merged to `main` at `bd4715d`
- M5-004 conditional unlock-cause base preregistration
- M5-004 provenance amendment assigning 2026-07-27 through 2026-07-29
  permanently to seen external reuse diagnostics
- Fresh M5-004 primary and fallback external blocks registered before
  implementation, fitting, acquisition, or inspection
- M5-004 event-level directional feature builder and A/B/C cause models
- Frozen development-only M5-004 model manifest
- Internal 2026-07-24 and seen-external-reuse 2026-07-27 through 2026-07-29
  diagnostics, with no verdict

## Current finding

M5-003 found that its frozen price package added external occurrence
information beyond the age/session baseline on all three registered endpoints.
This remains a model-comparison finding only, not a causal-trigger,
profitability, broker-ownership, or tradeable-edge result.

M5-004 asks a different question:

```text
P(UNLOCK_TO_BUY | an eligible unlock occurred)
```

Its development package is now implemented and frozen. Diagnostic results
show very small positive `C_age_price_cause - A_age_cause` increments, while
`C_age_price_cause - B_price_cause` is negative on both 2026-07-24 and the
seen 2026-07-27 through 2026-07-29 reuse block. These are non-gating
diagnostics and do not establish external support.

## Effective M5-004 cohorts

- Development: 2026-07-20 through 2026-07-23
- Internal reuse diagnostic: 2026-07-24
- Seen external reuse diagnostic: 2026-07-27 through 2026-07-29
- Primary untouched external gate: 2026-08-03 through 2026-08-07
- Structural fallback block: 2026-08-10 through 2026-08-14

The development package is frozen. The primary and fallback dates must still
remain outcome-blind until their registered structural intake is complete.
Do not inspect or discuss unlock directions, class balance, predictions,
charts, or performance summaries before the intake gate.

## Next executable task

Obtain independent Claude re-review of the single-developer M5-004
implementation. After approval, merge the frozen package. Acquire the
registered 2026-08-03 through 2026-08-07 report/ticks only after the block is
complete, run the blind structural intake, and evaluate once if accepted.

## Current blockers

- M5-004 implementation requires independent re-review before merge
- Future external labels and model outputs must remain uninspected until the
  blind structural intake passes
- Server timezone remains a window-scoped UTC+3 inference
- MT5 report event time has only second-level resolution
- The 0–6 second structural support limitation remains tracked in issue #3
