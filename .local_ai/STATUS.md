# Current Status

## Current phase

M5 — Trigger Inference (M5-002 pilot complete; external validation pending)

## Completed

- The bot uses a hedging account.
- The usual state is one position or one Buy plus one Sell.
- After closing one leg, the bot generally reopens the same side.
- The resulting advantage occurs during one-sided exposure.
- Repository bootstrapped
- Initial project memory committed
- One month of MT5 reports and XAUUSD ticks documented in the manifest
- Canonical MT5 report and tick parsers
- Dataset validation and anonymized fixtures
- Per-report financial reconciliation
- Trade/tick overlap inventory validation
- Lifecycle/state reconstruction with exception accounting
- M2 event accounting and boundary validation
- M3 deterministic event–tick alignment for the observed tick window
- M4 v1 causal trigger-dataset implementation
- Deterministic matched risk-set controls without candidate replacement
- H1/H2/H3 paired and cluster-bootstrap reports
- Separate M4 audit and reviewed model-feature outputs
- Complete pre-transition state age from M2 lineage
- Control-supported H1 inference and causal sequence-based H2
- Development-only winsorization for H2 retracement
- Reviewed model transforms and pre-registered H2 direction/windows
- M4 merged to `main` through PR #2
- M4 release marker created at commit `a49daad`
- M5 roadmap/specification aligned before modelling
- Canonical tradeable-risk-time accounting
- Explicit midnight split and maintenance-break exclusion
- Common-hour development/holdout cohort locked to server hours 12–23
- UTC+3 recorded as a window-scoped high-confidence inference
- Three external validation sessions pre-registered
- Synthetic right-censored tail through tick coverage end
- Explicit zero-duration and left-truncation estimand exclusions
- Unknown-gap taxonomy with multi-day regression coverage
- Co-primary within-interval conditional timing statistic pre-registered
- Secondary full-session external analysis pre-registered
- Machine-readable M5 acquisition plan and privacy-safe intake validator
- Deterministic synthetic acquisition dry run and recurring-gap audit
- Retrospective supplemental 2026-07-20 through 2026-07-22 intake validated
- Separate internal/supplemental causal risk-bin cohorts at 1s and 500ms
- Development-only constant and state-age bucket hazard baselines
- 5,000-draw interval-cluster bootstrap for occurrence and conditional timing
- Supplemental parameter-isolation hash and M2-M4 canonical tick protection
- M5-002 aggregate report and deterministic local-output hashes

## Current data

- 4 MT5 weekly trade reports
- 2 local XAUUSD tick exports covering 2026-07-20 to 2026-07-24
- Approximately one month of trade history

## Current focus

M5-002 is a bounded state-age-only pilot. Internal risk support reconciles
exactly at both widths; interval `13321` is excluded from both primary splits,
and cohort-relative left truncation remains `12074` internally and `8294`
supplementally. Canonical M2-M4 ticks and fitted parameters are unchanged by
supplemental data.

Frozen holdout conditional timing is worse than uniform for both re-hedge
endpoints and inconclusive for unlock. Secondary occurrence likelihood improves
for all endpoints, demonstrating that occurrence and timing are different
estimands. The approximate six-second unlock floor is confirmed with one
month-wide exception and no sub-six-second unlock in the five July 20–24
calendar sessions.

## Next executable task

M5-001 — acquire the pre-registered 2026-07-27 through 2026-07-29 XAUUSD tick
sessions and a trade report covering their lifecycle events. Raw files remain
outside Git. The intake code is ready; real acquisition remains pending.

The registered retrospective supplemental 2026-07-20 through 2026-07-22
cohort now supplies common-hour per-session descriptive rates only. It is
non-gating and does not replace the pre-registered external sessions.

## Current blockers

- Pre-registered external tick/report sessions are not yet available
- Server timezone is inferred as UTC+3 for the current window but is not
  formally or globally confirmed
- MT5 report event time has only second-level resolution
- The 0–6 second structural control-support gap is tracked in issue #3
- Thirty-four zero-duration re-hedges are outside the complete-risk-bin
  estimand and remain linked to issue #3
- Development/holdout/external dates are perfectly confounded by day of week
