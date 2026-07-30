# Current Status

## Current phase

M5 — Trigger Inference (M5-003 external evaluation complete; M5-004
pre-registered without fit)

## Completed

- M0–M4 canonical parsing, lifecycle reconstruction, event/tick alignment,
  causal trigger sampling, and bounded hypothesis tests
- M5-000 causal risk-time contract and acquisition protocol
- M5-001 retrospective and prospective intake validation
- M5-002 state-age occurrence pilot and conditional-statistic remediation
- M5-003 causal price-increment preregistration
- Development-only feature preprocessing, GroupKFold regularization, frozen
  A/B/C models, required ablations, and deterministic reports
- Independent review and session-baseline remediation before external data
- Prospective external acquisition for 2026-07-27 through 2026-07-29
- Pre-prediction external intake amendment disclosing qualitative screenshot
  exposure and a replicated 106.357-second source quote gap
- Frozen-model external evaluation at one second plus 500 ms anchor sensitivity
- M5-004 conditional unlock-cause preregistration only; no cause model fit

## Current data

- 5 local MT5 trade reports, including the external evaluation period
- Separate local XAUUSD tick exports for 2026-07-20 through 2026-07-29
- Raw reports, ticks, screenshots, and account data remain outside Git

## Current finding

The registered one-second external headline `C_session - A_session` passes its
locked gate for all three endpoints:

| Endpoint | Mean paired LL increment | Familywise lower bound | Positive sessions | Verdict |
| --- | ---: | ---: | ---: | --- |
| Re-hedge Buy | +0.231269 | +0.195982 | 3/3 | supported |
| Re-hedge Sell | +0.166665 | +0.131774 | 2/3 | supported |
| Unlock occurrence | +0.221639 | +0.191840 | 2/3 | supported |

This supports the narrow claim that the frozen price-feature package adds
occurrence information beyond the frozen age/session baseline on the registered
external sessions. It does not establish a tradeable edge, causal trigger,
profitability, or broker-owned behavior.

Interpretation remains constrained:

- the pooled gain is concentrated in 2026-07-29;
- 2026-07-28 is negative for two endpoints;
- both re-hedge combined models beat `A_session` but underperform price-only
  `B`, leaving the architecture unresolved;
- the external sessions were not fully analyst-blinded because selected
  screenshots from 2026-07-27 and 2026-07-28 were seen;
- a replicated quote gap is excluded without interpolation, while affected
  lifecycle events remain accounted for.

## Next executable task

Obtain independent review of the M5-003 external evaluator, event accounting,
frozen-model proof, and interpretation. The external-validation branch must
remain unmerged until that review is accepted.

After review, decide whether to authorize M5-004 implementation. Before any
M5-004 fit, add a dated provenance amendment because the same external
sessions have now been qualitatively observed and used for M5-003 evaluation.

## Current blockers

- Independent re-review is required before merging the M5-003 external result
- M5-004 implementation and fitting are not yet authorized
- The 2026-07-27 through 2026-07-29 sessions cannot be treated as
  analyst-blinded for later M5-004 validation without a new provenance decision
- Server timezone remains a window-scoped UTC+3 inference
- MT5 report event time has only second-level resolution
- The 0–6 second structural support limitation remains tracked in issue #3
- Development/internal/external dates remain confounded with weekday
