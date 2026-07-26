# Session Log

## 2026-07-25 — M0 bootstrap

- Initialized repository documentation and directory layout.
- Added privacy-first Git ignore rules for raw financial data.
- Recorded the first executable task: normalize trade reports and ticks.

## 2026-07-26 — M5-000 support lock

- Marked the merged M4 state at commit `a49daad`.
- Reconciled legacy start-date duration accounting with canonical calendar
  tradeable time.
- Locked midnight splitting, maintenance-break exclusion, common server-hour
  support, and window-scoped UTC+3 inference.
- Pre-registered three contiguous external validation sessions.
- Stopped before risk-bin generation or model fitting.

## 2026-07-26 — M5-000 review remediation

- Added the 318.758-second synthetic right-censored final-state tail without
  changing M2 output.
- Excluded left-truncated and zero-duration cases from the primary risk-bin
  estimand while preserving complete accounting.
- Separated eligible-state exposure from all-state audit exposure.
- Classified the current long gap as unknown pending recurrence evidence.
- Pre-registered a co-primary within-interval timing statistic and a secondary
  full-session external analysis.
- Kept M5-002 out of scope.

## 2026-07-26 — M5-001 acquisition preparation

- Added an executable pre-registration for the 2026-07-27 through 2026-07-29
  external sessions without changing the locked dates or analysis windows.
- Added a privacy-safe tick/report intake validator with checksums, generated
  file aliases, per-session coverage checks, duplicate preservation, and
  recurring-gap classification.
- Added plan-only and generated-data dry-run modes; no private fixture or raw
  export is committed.
- Documented that untouched historical full-tick data is technically valid,
  but changing the locked dates requires a dated amendment before inspection.
- Stopped before M5-002 model construction.

## 2026-07-26 — retrospective supplemental tick intake

- Registered 2026-07-20 through 2026-07-22 as a non-gating retrospective
  supplemental cohort before reading its tick export.
- Validated all three sessions and the existing 2026-07-19 through 2026-07-25
  report coverage with the privacy-safe intake validator.
- Kept the result separate from the pre-registered 2026-07-27 through
  2026-07-29 primary external-validation gate and did not start M5-002.

## 2026-07-26 — M5-002 state-age hazard pilot

- Recorded and pushed the bucket/support amendment before the first fit.
- Kept internal and supplemental ticks in separate cohort tables and protected
  the exact M2-M4 canonical tick export in the dataset builder.
- Built complete wall-clock 1-second and 500-millisecond risk bins with paused
  tradeable state age, cohort-relative truncation, terminal competing-bin
  censoring, and cross-split exclusion.
- Fit endpoint-specific constant and amended state-age bucket baselines on
  internal development common hours only.
- Proved supplemental isolation with identical fitted-parameter hashes and
  reproduced the aggregate report hash on two complete runs.
- Confirmed the approximate six-second unlock floor while retaining the single
  month-wide exception and avoiding a hard-zero model assumption.
- Found that state age improves secondary occurrence likelihood but not frozen
  holdout conditional timing; M5 remains open pending external data.

## 2026-07-26 — M5-002 conditional-statistic remediation

- Reproduced the holdout-label oracle result showing that the outcome-truncated
  within-interval calculation cannot score an age-only model.
- Promoted paired cause-specific occurrence likelihood to the bounded pilot
  primary and withdrew the two timing-rejected verdicts.
- Added the explicit M5-000 tradeable-to-primary-to-bin accounting bridge and
  documented the known-age scope of `A_all`.
- Reclassified 500-millisecond results as discretization sensitivity and pinned
  the supplemental tick input by SHA-256.
- Kept M5-003 and all M2-M4 canonical outputs out of scope.
