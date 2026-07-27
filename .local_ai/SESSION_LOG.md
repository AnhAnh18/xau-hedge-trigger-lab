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

## 2026-07-26 — M5-003 preregistration only

- Locked immutable M5-002 hashes and an exact common joint-valid bin rule.
- Chose 2026-07-20..23 as pooled development before any price feature fit;
  retrospective dates remain permanently non-validating and non-gating.
- Recorded that 2026-07-24 is internal reuse, not untouched price
  confirmation, because M4 already inspected its price hypotheses.
- Conditioned unlock occurrence after the five-second timer floor and locked
  separate sign-normalized re-hedge and magnitude-only unlock allowlists.
- Fixed GroupKFold by interval, development-only preprocessing, L2 selection,
  paired interval inference, multiplicity families, and required ablations.
- Added a machine-readable null-permitting merge contract. No M5-003 feature
  construction or model fitting was performed.

## 2026-07-26 — M5-003 implementation authorization and grid correction

- Merged M5-002 and the M5-003 preregistration in stacked order.
- Detected that the preregistration listed nine age buckets while the frozen
  M5-002 source, report, and parameter hash use 11.
- Received explicit authorization to restore `[5,6)`, `[6,8)`, and `[8,10)`
  before any M5-003 price fit; unlock now has seven floor-eligible buckets.
- Added a blocking independent Claude re-review requirement because the
  implementation is being produced by one developer.

## 2026-07-26 — M5-003 causal price-increment implementation

- Built causal endpoint-specific price features at one-second and
  500-millisecond anchors with strict gap-aware joint-window validity.
- Reproduced the pre-registered one-second attrition audit: 937 bins and three
  targets; reproduced the 3,115-bin, zero-target unlock timer-floor exclusion.
- Fit A_dev, B, and no-intercept C_dev using development-only interval
  GroupKFold, deterministic one-standard-error regularization, required
  ablations, and 5,000-draw interval bootstrap diagnostics.
- Reconstructed and verified immutable M5-002 in-memory hashes without
  changing any M2-M5-002 canonical output.
- Froze the model manifest before evaluating the 2026-07-24 internal-reuse
  session and reproduced all six generated outputs byte-for-byte on rerun.
- Published internal reuse and leave-one-session-out results as diagnostics
  only, with no price verdict and no tradeable-edge claim.
- Left the implementation PR in draft pending independent Claude re-review;
  the 2026-07-27..29 external-validation gate remains open.

## 2026-07-27 — M5-003 CI portability remediation

- GitHub CI exposed that raw text-byte hashes differed between Windows CRLF
  and Linux LF checkouts even though the preregistration content was identical.
- Canonicalized preregistration text hashes to UTF-8 with LF newlines while
  preserving raw-byte hashing for binary data and private tick checksums.
- Kept Draft PR #8 blocked on the same independent Claude re-review gate.

## 2026-07-27 — M5-003 session-baseline remediation

- Independently reproduced the review concern that the price package encoded
  deterministic time-of-day context absent from `A_dev`.
- Identified that the reviewer prototype used two dummies without an
  intercept, silently fixing `[12,16)` to zero; locked three explicit block
  effects instead.
- Added development-only `A_session`, no-intercept `C_session`, fold-local
  session fitting, nested lambda reselection, and full LOSO refits.
- Repartitioned unlock range widths into volatility/liquidity and added the
  review-driven `C_shape` diagnostic without an independent verdict.
- Published all registered comparison, ablation, multiplicity, anchor, and
  base-rate-stress tables in Markdown and JSON.
- Preserved all M2–M5-002 canonical outputs and kept external 2026-07-27..29
  data absent.
- Kept Draft PR #8 blocked pending a fresh independent Claude re-review of
  this single-developer remediation.

## 2026-07-27 — M5-003 independent review accepted

- Claude independently reproduced all three `A_session - A_dev` and
  `C_session - A_session` values and accepted the remediation engineering.
- Added the requested two-of-three positive external-session consistency gate.
- Recorded that likelihood increments are not scale-free across endpoints or
  sessions and kept ablation interpretation conditional and non-causal.
- Required no feature/model refit; deterministic rebuild, hashes, tests,
  privacy, and stacked M5-004 provenance are refreshed before merge.
