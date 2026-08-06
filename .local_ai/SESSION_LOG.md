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

## 2026-07-27 — M5-004 unlock-cause preregistration

- Started a separate stacked branch without changing Draft PR #8.
- Defined unlock direction as one event-level conditional cause split rather
  than an additional occurrence hazard.
- Locked one-second and 500-millisecond anchors, a 12-feature directional
  allowlist, state-age cause baseline, development-only GroupKFold, required
  ablations, and an external-only verdict rule.
- Recorded known internal event accounting for audit only and prohibited it
  from creating a verdict.
- Stopped before cause-feature construction or model fitting; implementation
  requires review and separate authorization.

## 2026-07-30 — M5-003 registered external evaluation

- Validated separate tick exports for 2026-07-27, 2026-07-28, and 2026-07-29
  plus the covering MT5 report; raw inputs remain ignored and untracked.
- Registered a pre-prediction amendment disclosing selected screenshot
  exposure and a replicated 106.357-second source quote gap.
- Reconstructed the external lifecycle independently and evaluated the frozen
  M5-003 manifest without refitting preprocessing, regularization, calibration,
  or model parameters.
- Excluded quote-gap time and any crossing price windows without interpolation;
  retained affected events in lifecycle and stage accounting.
- Passed the pre-registered one-second headline gate for all three endpoints,
  while preserving negative `C_session - B` re-hedge diagnostics and strong
  session concentration in the interpretation.
- Added endpoint/width accounting from lifecycle events through representable,
  common/floor, and joint-valid targets.
- Rebuilt all 12 local/report artifacts twice with zero byte changes.
- Kept the branch unmerged pending independent review and made no tradeable-edge
  claim. M5-004 remains out of scope.

## 2026-07-30 — M5-004 provenance amendment

- Preserved the original M5-004 human and machine preregistration files and
  added a separate effective companion amendment.
- Replaced Draft PR #8 provenance with merged M5-003 commit `bd4715d` and
  pinned the external-report hash.
- Permanently reassigned 2026-07-27..29 to seen external reuse diagnostics.
- Registered untouched primary 2026-08-03..07 and structural fallback
  2026-08-10..14 blocks before implementation or acquisition.
- Adapted only the daily coherence count from two of three to three of five;
  retained the one-sided headline bound, rejection rule, seed, cluster unit,
  descriptive LOSO, and non-gating 500-millisecond sensitivity.
- Locked blind structural intake, pre-weekend report context, replicated-gap
  handling, and outcome-independent fallback criteria.
- Stopped before M5-004 feature construction, fitting, or external loading.

## 2026-07-30 — M5-004 development package freeze

- Merged the independently approved provenance amendment as PR #11 before
  implementation.
- Built one event row per eligible unlock and recomputed the exact 12
  raw-directional predictors from causal tick windows.
- Reconciled the preregistered internal counts exactly at both 1,000 ms and
  500 ms.
- Fit `A_const_cause`, `A_age_cause`, `B_price_cause`, and
  `C_age_price_cause` on 2026-07-20 through 2026-07-23 only, with grouped
  fold-local preprocessing and independently selected penalties.
- Wrote the frozen manifest before loading 2026-07-27 through 2026-07-29.
  The 2026-07-24 and seen-external-reuse sessions remained diagnostics only.
- Preserved a null M5-004 verdict. The diagnostic C-minus-A increments were
  small and positive, while C-minus-B was negative on both reuse cohorts.
- Rebuilt all four local Parquet outputs and three committed report artifacts
  twice with 7/7 byte-identical hashes.
- Kept the August primary and fallback blocks unloaded. Because this is a
  single-developer implementation, independent Claude re-review is required
  before merge.

## 2026-07-30 — M5-004 pre-data external infrastructure

- Preserved the locked M5-004 preregistration, provenance amendment, frozen
  model manifest, and development report byte-for-byte.
- Added a five-session blind-intake contract with separate raw-file and
  canonical package hashes.
- Implemented information-firewalled structural intake for coverage,
  duplicate ticks, gaps, independent replica evidence, report context,
  financial reconciliation, inventory conservation, and aggregate lifecycle
  completeness.
- Kept lifecycle behavior and unlock-direction derivation out of blind intake;
  labels are first created only after the exclusive evaluation lock succeeds.
- Added a no-fit frozen evaluator, exact one-second verdict branches,
  non-gating 500-millisecond sensitivity, crash-safe identical-hash resume,
  consumed-evaluation refusal, and reviewed fallback authorization.
- Tested the complete two-stage workflow using anonymized synthetic fixtures
  only. No August file was acquired, opened, parsed, or inspected.
- Frozen runtime and protected-file hashes in the external infrastructure
  manifest. Independent review remains required before merge.

## 2026-07-30 — M5-004 infrastructure cold self-review

- Performed a fresh full-diff review after the independent reviewer became
  temporarily unavailable; the owner explicitly authorized self-review and
  merge if no blocker remained.
- Found and remediated one contract omission: external reports now publish
  five descriptive leave-one-session-out omissions for both registered widths
  without refitting and without affecting the headline verdict.
- Added primary structural-failure record hash verification before fallback
  authorization and rechecked the persisted started guard before consuming an
  evaluation.
- Kept every frozen model parameter, predictor, decision threshold, bootstrap
  setting, external date, and M2–M5-004 canonical artifact unchanged.
- This was a transparent self-review, not an independent-review claim.

## 2026-07-31 — M5-004 external infrastructure independent review

- A fresh independent CLI reviewer completed T-034 with `PASS` and no
  P0-P3 findings; it did not inspect raw exports or edit the worktree.
- Remediation binds each symbol-free MT5 tick export and replica to a
  content-hashed XAUUSD provenance sidecar, pins fallback to the original
  primary intake registration, and requires reviewed fallback authorization
  before any fallback snapshot or parse.
- Validation passed with 185 tests and a clean `git diff --check`.
- Residual operational assumptions remain explicit: provenance sidecars are
  operator attestations rather than broker-signed records, reviewed fallback
  authorization and the local primary registration must be retained, and
  evaluation guard files preserve the one-time constraint.

## 2026-08-01 -- RETRO-001 descriptive case review

- Recorded the owner-authorized, RETRO-only raw-data boundary, exact
  hash-verified source receipt, deterministic case window, ignored aggregate
  output, and M5 information firewall.
- The descriptive case reconstruction found no continuation re-hedge before
  the selected Buy-only interval ended, followed by a later rotation; manual
  intervention remains unresolved because no journal was in scope.
- The tick/report alignment passed inside the registered case window; the
  result retains aggregate-only conclusions and no raw rows or detailed
  timeline.
- A fresh independent review returned `PASS` with no P0-P3 findings. The full
  test suite passed: 185 tests with an isolated pytest base directory. M5
  contracts, inputs, models, and blind gates remained unchanged.

## 2026-08-01 -- RETRO-002 tick-source reconciliation

- Re-ran the owner-authorized, hash-verified three-source reconciliation after
  correcting the archive timestamp rule: only the UTC-declared archive uses
  the registered UTC+3 conversion; the original's undeclared source clock is
  diagnostic only.
- Aggregate digest is `bf58cb62fa3a27511fe14fa6ef2948f4371c5c37ab93817e4742cc37009a2344`; an identical rerun reproduced it.
- Added pinned quarantine-root, relative-path, and suffix validation before
  parsing. `py_compile` and the analyzer run passed without raw output.
- A fresh independent review returned `PASS` with no P0-P3 findings. The
  registered mapping shows source agreement on the coarse no-below-entry band;
  the original-source alternate clock remains compatible but unresolved.
- RETRO-002 remains descriptive and outside all M5 inputs, models, evaluations,
  thresholds, and gates; no M5 state or task entry changed.

## 2026-08-01 -- RETRO-003 through RETRO-SYNTH full retrospective lane

- Archived and hash-verified nine canonical monthly HTML reports plus the
  accepted 39-object UTC tick archive under a new RETRO-003 receipt; XLSX/PNG
  companions, journals, caches, M1, and terminal support sources remained out
  of scope.
- Applied the predeclared three-stratum selection rule over 2025-11-01 through
  2026-07-30. Twenty-one eligible dates yielded three selected starts:
  2025-11-12, 2026-03-03 (cross-midnight interval), and 2026-07-01.
- Completed RETRO-004..006 with exact report/tick receipts, bounded padded
  windows, UTC+2/UTC+3 diagnostics, aggregate-only quote-quality metrics, and
  no journal inspection. All three reconstructed the one-leg to opposite-side
  re-hedge transition with no continuation re-hedge inside the interval; all
  three clock mappings remained ambiguous.
- Completed RETRO-SYNTH over RETRO-001..006. The repeated wait-then-rehedge
  sequence is observed/compatible with state-dependent rotation, while trigger,
  manual action, broker clock, profitability, ownership, and edge remain
  unresolved.
- Validation: selected RETRO tests passed (`2 passed`); fresh independent
  review returned `PASS` with no P0-P3 findings; isolated full suite passed
  `187 passed` with one cache warning. Aggregate reruns were hash-identical.
- RETRO remains descriptive and outside all M5 inputs, models, evaluations,
  thresholds, and gates; M5 task entries and frozen artifacts were unchanged.

## 2026-08-01 -- RETRO-BOT-001 historical replay closeout

- Completed the separately contracted replay-only surrogate over the fixed
  2025-11 through 2026-07 population. The runner verified the locked
  9-report and 39-tick manifest sets before in-memory parsing and retained
  only a privacy-validated aggregate.
- The aggregate has 189 eligible intervals for every policy/clock row. Two
  independently named ignored runs were byte-identical and produced digest
  `09146b45382dcf4380c575e96151eaf1971f4947059c46e014c431b2c4e38fe5`.
- The tracked result reports all four fixed-delay policies beside all three
  clock scenarios without selecting a winner. It is compatible only with the
  registered surrogate policies and does not identify the original trigger,
  manual action, broker timezone, profitability, ownership, or a tradeable
  edge.
- Added a batch tick replay that streams each source at most once per full
  replay while preserving the fixed half-open timing window and fail-closed
  DST behavior. No raw rows, prices, tickets, traces, credentials, or source
  paths were retained in tracked artifacts.
- A fresh independent closeout review returned `PASS` with no P0-P3 findings.
  Focused RETRO-BOT validation passed 20 tests; the isolated full suite passed
  207 tests, both with one existing pytest cache warning. The M5 firewall
  passed and M5 frozen artifacts, blind August blocks, models, thresholds,
  and gates were unchanged.

## 2026-08-02 -- RETRO-BOT-001 DST remediation and closeout re-review

- Corrected the replay contract violation so any unresolved clock boundary or
  locked policy target excludes the whole interval for that clock scenario;
  a target at or after the observed re-hedge remains right-censored.
- Rebuilt two fresh aggregate runs from the exact locked source manifests;
  both were byte-identical with digest
  `09146b45382dcf4380c575e96151eaf1971f4947059c46e014c431b2c4e38fe5`.
- Focused validation passed 23 tests in the independent closeout review;
  full suite passed 208 tests, privacy check passed, and `git diff --check`
  was clean apart from existing line-ending/cache warnings.
- A fresh independent reviewer returned `PASS` with no P0-P3 findings. RETRO-BOT
  remains descriptive and outside all M5 inputs, models, evaluations,
  thresholds, and gates.

## 2026-08-02 -- RETRO-BOT-002/RB-006 paper-backtest closeout

- Added a bounded paper-only harness with fixed quantity 1.0, Buy-at-Ask /
  Sell-at-Bid execution, conservative mark at the observed re-hedge anchor,
  stream-only tick access, and aggregate-only loss/flat/gain bands.
- Ran the exact locked 9-report/39-tick historical population: 189 eligible
  intervals for every policy/clock row. Two aggregate runs were byte-identical
  with digest `4f40faae72bb4cd32df8ea5b24fcea9238912f77c3b0ca0bbd69deba088148f6`.
- Independent review found and remediated one P1 (single-pair policy/clock
  selection) and two P2 validation issues (mutable config and boolean schema
  version). The final independent review returned `PASS` with no P0-P3.
- Focused RB-006 tests passed 7; full suite passed 215; privacy, py_compile,
  and diff checks passed. The paper result is synthetic descriptive evidence,
  not profitability, live execution, model selection, or an M5 gate.

## 2026-08-02 -- RETRO-BOT-002 ordering remediation and final replay

- Independent review found a P1 in the vectorized scanner: an earlier valid
  tick in a later chunk/path could be ignored. The scanner now keeps the
  earliest action and mark quote across every chunk and source path, with a
  100,000-row boundary regression test.
- Rebuilt two fresh post-remediation aggregates; both remained byte-identical
  with digest `4f40faae72bb4cd32df8ea5b24fcea9238912f77c3b0ca0bbd69deba088148f6`.
- Focused tests passed 8 and full suite passed 216; the independent re-review
  returned `PASS` with no P0-P3 findings. RETRO-BOT remains outside M5.

## 2026-08-02 -- RETRO-BOT-003/RB-007 sequential replay closeout

- Added a chronological multi-cycle wrapper over RB-006 outcomes. It rejects
  non-increasing, overlapping, malformed, or identity-mismatched cycles and
  retains only aggregate total/eligible/action/marked/censored/overlap/invalid
  counts plus loss/flat/gain bands.
- Independent review found and remediated two P1 issues (RB-006 identity
  remapping and writer symlink containment) plus strict finite accounting
  validation. Final independent review returned `PASS` with no P0-P3.
- Ran the exact locked 9-report/39-tick population twice. Both aggregates were
  byte-identical with digest
  `0f803aad89838a45e31e4589897d7019f65c4fc7e888d7d5dfa8c02671cd9831`;
  189 cycles per policy/clock and zero overlap/invalid cycles were observed.
- Focused RB-007/RB-006 tests passed 17; full suite passed 225; privacy,
  py_compile, and diff checks passed. RETRO remains outside M5.

## 2026-08-03 -- RETRO-BOT-004/RB-008 evidence freeze closeout

- Locked the RETRO-only 9-report/39-tick source boundary, chronological
  report folds, fixed-seed and left-censored bootstrap rows, DST boundary
  scenarios, censor precedence, minimum-support gates, and privacy/M5 claims.
- Added deterministic fold/bootstrap/censor accounting, source manifest
  verification, clock boundary mapping, overlap rejection, redacted aggregate
  validation, CLI verification, and synthetic regression coverage.
- Focused contract/RB-008 tests passed 14; isolated full suite passed 235;
  privacy and py_compile passed; `git diff --check` was clean apart from
  existing line-ending/cache warnings.
- A fresh independent final re-review returned PASS with no P0-P3 findings.
  RB-008 remains descriptive and outside all M5 inputs, models, evaluations,
  thresholds, and gates. Next RETRO milestone is RB-009 lifecycle/state
  engine.

## 2026-08-03 -- RETRO-BOT-005/RB-009 lifecycle/state closeout

- Added the causal finite-state reducer with fixed-seed/left-censored
  bootstrap, separate `PolicyAction` and `OracleLabel` paths, strict
  transition/chronology/idempotency rules, RB-007 action mapping, and
  aggregate-only state accounting.
- Independent review found and remediated post-terminal handling,
  same-second collisions, anchor eligibility, quantity invariants,
  cross-fold semantics, action schema, aggregate validation, and timestamp
  normalization issues.
- Focused RB-009 tests passed 9; isolated full suite passed 244; privacy,
  py_compile, and diff checks passed. Fresh independent re-review returned
  PASS with no P0-P3 findings. RETRO remains outside M5; next milestone is
  RB-010 causal feature/trigger contract.

## 2026-08-03 -- RETRO-BOT-006/RB-010 causal feature/trigger closeout

- Added the frozen causal feature snapshot and trigger DSL: 60-second
  lookback anchor, price increment, side-specific adverse excursion, spread,
  tick rate, quote gap, session bucket, immutable domains, three-clause AND
  rules, legality mapping, deterministic rule-id ties, and aggregate-only
  provenance/firewall attestation.
- Remediated independent review findings for causal tick boundary/private
  field rejection, huge-number fail-closed handling, immutable numeric DSL
  parameters, duplicate rule ids, and inherited source digests.
- Focused RB-010 tests passed 9; isolated full suite passed 253; privacy and
  py_compile passed. A fresh independent review returned PASS with no P0-P3
  findings. RETRO remains outside M5; next milestone is RB-011.

## 2026-08-03 -- RETRO-BOT-009/RB-013 walk-forward evaluation closeout

- Locked the four-candidate Cartesian manifest, chronological development /
  validation / holdout folds, source-safe causal cutoff and report-alias
  enforcement, component and side support gates, explicit duplicate / invalid
  / feature-missing / censor accounting, and separate oracle diagnostics.
- Added frozen policy fingerprints, registered-population orchestration,
  structural-intake and sealed-aggregate CLI stages, bounded canonical
  autonomous/oracle schemas, and one-to-one earliest-unused oracle
  verification. No raw rows, paths, credentials, or M5 inputs were read or
  retained.
- Focused RB-013 tests passed 6; isolated full suite passed 268; privacy,
  compileall, and `git diff --check` passed. A fresh independent re-review
  returned PASS with no P0-P3 findings. RETRO remains descriptive and outside
  M5; next milestone is RB-014.

## 2026-08-03 -- RETRO-BOT-010/RB-014 end-to-end paper bot closeout

- Composed the locked RB-009 lifecycle, RB-011/RB-012 causal action engines,
  RB-013 fold/candidate matrix, and RB-006 paper accounting into a source-free
  typed replay API and CLI. Replay accepts causal cycles rather than
  precomputed result rows, verifies frozen policy manifests, state/epoch/action
  provenance, quote chronology, fixed-decimal scenarios, and M5 isolation.
- Added conservative Bid/Ask accounting for HEDGED and ONE_BUY/ONE_SELL starts,
  transaction fee/slippage/latency/margin assumptions, causal censor handling,
  aggregate unit/action/mark conservation, canonical cycle/scenario identity,
  and deterministic aggregate self-digests.
- Focused RB-014 tests passed 10; isolated full suite passed 278; privacy,
  compileall, and `git diff --check` passed. Direct CLI smoke and two typed
  fixture runs were deterministic. Fresh independent final review returned
  PASS with no P0-P3 findings. RETRO remains descriptive and outside all M5
  inputs, models, evaluations, thresholds, and gates; next milestone is
  RB-015.

## 2026-08-03 -- RETRO-BOT-011/RB-015 robustness closeout

- Locked the 40-case `RB015_PROJECTION_V1` matrix (digest
  `4b3f9a2bd98b3827641cafa7807c6b929a2e212243c7a340cb51c97da1c701c3`) across
  clock, timestamp, quote, cost, coverage, slice, and ablation dimensions.
- Added typed actionful synthetic fixtures, coupled clock/snapshot transforms,
  source-first quote fault precedence, action/mark coverage censoring, fixed
  cost fingerprints, structural feature ablations, direct projection/slice
  guards, redacted aggregate accounting, and stdin-only `validate-config`,
  `stress-replay`, and `verify-aggregate` CLI stages.
- Focused RB-015/RB-014 tests passed 33 in fresh review; isolated full suite
  passed 301; privacy, compileall, and `git diff --check` passed. Two CLI
  replays were byte-identical (output SHA-256
  `98f899d67f20acd5c219e1a107e5afa14b4a0c660879a4e35bc0acabe8816395`),
  aggregate verification passed, and a fresh independent re-review returned
  PASS with no P0-P3 findings. RETRO remains descriptive and outside all M5
  inputs, models, evaluations, thresholds, and gates; next milestone is
  RB-016.

## 2026-08-03 -- RETRO-BOT-012/RB-016 packaging closeout

- Locked `RB016_PACKAGE_V1` manifest, explicit RB-014 provenance digest
  `3621048bc7ca84d4be0717b0599cc1bfed5d8d565f5502f20543873aeabfde44`, all
  inherited RB-015 projection/cost fingerprints, duplicate-key canonical JSON,
  initial `all`-slice HEDGED state snapshot, and non-cyclic package/receipt/
  state/aggregate self-digests.
- Added source-free `package-replay`, `verify-receipt`, and `validate-config`
  CLI stages, typed canonical fixture digesting, recursive privacy/M5/live
  firewall, and known-limitations documentation. No raw source, credentials,
  paths, journals, tickets, `.ex5`, subprocess, network, MT5, or live-order
  surface is packaged.
- Focused RB-016/RB-015/RB-014 tests passed 40; isolated full suite passed
  308; privacy, compileall, and `git diff --check` passed. Two fresh
  subprocess package runs were byte-identical (output SHA-256
  `07ddf6c8b01aab14b9d1799b81271055914c88c59ff1e3db7fc5a4f277192045`),
  verify-receipt passed, and a fresh independent re-review returned PASS with
  no P0-P3 findings. RETRO remains descriptive and outside all M5 inputs,
  models, evaluations, thresholds, and gates; next milestone is RB-017.

## 2026-08-03 -- RETRO-BOT-013/RB-017 synthetic/shadow closeout

- Locked a synthetic/shadow holdout boundary over the frozen RB-016 package
  and typed RB-015 fixture: all four cycles use `fold=holdout`,
  `report-008.html`, and causal decision records with `future_read=false` and
  `oracle_used=false`. No new raw source or owner authorization was used.
- Added a redacted fixed-schema closeout report with recomputed package,
  aggregate, projection, source-manifest, attestation, fixture, and report
  digests. `verify-closeout` recomputes from package plus fixture and rejects
  duplicate keys, tampering, private/M5/live fields, and malformed provenance.
- Focused RB-017/RB-016/RB-015/RB-014 validation passed 47 tests; isolated full
  suite passed 315 tests; compileall, privacy, and `git diff --check` passed.
  Two independent CLI closeout runs were byte-identical with report digest
  `37ead2e0ddac61f88c5f68f8c782c9d526d3a879701fe7decf2e5916b25c7ca8`.
- Independent implementation review and a fresh re-review both returned
  `PASS` with no P0-P3 findings. The terminal status is permanently
  `behaviorally-compatible-accounting-inconclusive`; no candidate selection,
  profitability, live execution, or M5 gate claim is made. Next milestone is
  RB-018.

## 2026-08-03 -- RETRO-BOT-014/RB-018 offline-lane terminal seal

- Locked the owner-authorized synthetic/shadow registration, redacted RB-017
  prerequisite receipt, frozen RB-017 validator hash, two process receipts,
  canonical JSON/LF framing, exact gate attestation, and terminal receipt
  schema. No new source, replay, fitting, M5 input, external validation,
  `.ex5`, or live/demo surface was introduced.
- Added source-free `seal` and `verify-seal` stages with duplicate-key,
  non-finite, trailing-byte, strict int/bool/float schema, recursive privacy
  firewall, provenance/self-digest, nonce, and optional-receipt checks. The
  terminal status is `offline-lane-closed-synthetic-shadow-only` with the
  inherited permanent conclusion `behaviorally-compatible-accounting-inconclusive`.
- Focused RB-018/RB-017/RB-016/RB-015 validation passed 26 tests; isolated
  full suite passed 327 tests; compileall, privacy, and `git diff --check`
  passed. Two fresh CLI seal runs were byte-identical with SHA-256
  `69410d5608d8bac9948335f60ac21a69a23cf5fb8add4381baa8da06dd2f377c`.
- Independent RB-018 review found one P2 strict-integer issue; it was fixed
  and a fresh independent re-review returned `PASS` with no P0-P3 findings.
  The RETRO-BOT offline lane is now closed; future expansion requires a new
  owner authorization and contract.

## 2026-08-03 -- RETRO-BOT-015/RB-019 variable-lot offline paper bot

- Locked the typed/redacted RB-019 contract and plan after an independent
  plan-gate PASS. The contract fixes Decimal-only fixed8 parsing, quote and
  cost bounds, scenario fingerprints, unique cycle ids, per-leg quantity
  conservation, exact six-key verification framing, and the golden
  Bid/Ask accounting vector.
- Implemented `src/xau_trigger/retro_bot_015.py` and the stdin-only
  `scripts/run_retro_bot_019.py` replay/verify stages. OPEN events now apply
  their Bid/Ask cash flows, initial and event costs are charged, uneven lot
  changes are supported, and semantic-invalid cycles are counted without raw
  retention. No raw source, M5 input, live-order surface, or filesystem input
  is read.
- Focused RB-019/RB-018 validation passed 22 tests; isolated full suite passed
  337 tests with workspace `--basetemp`; compileall and `git diff --check`
  passed. A static privacy scan found no credentials or private paths in the
  milestone artifacts; only intentional firewall terms remain in the
  contract/constant definitions.
- Two independent CLI replay runs were byte-identical with output SHA-256
  `3db8ff3dc92c4ea73a70cd5ebb947a4f16476f90e057e783cd6dc8a8f05028ec`;
  separate `verify-aggregate` passed. Independent implementation review
  found one P1 aggregate-order issue; it was fixed, and a fresh independent
  final review returned `PASS` with no P0-P3 findings. RETRO remains
  descriptive and outside all M5 inputs, models, evaluations, thresholds,
  and gates.

## 2026-08-03 -- RETRO-007 historical concurrent-position screening

- Completed the owner-authorized aggregate-only scan over the exact RETRO-003
  report and tick manifests for server dates 2025-11-01 through 2026-07-30.
  The scan found maximum concurrent counts of 7 total, 4 Buy, and 5 Sell;
  5,422 definite 2-Buy + 2-Sell episodes; and 18 fixed post-gap windows with
  positive-duration multi-position overlap under both UTC+2 and UTC+3.
- Synthetic checks passed for close-only ambiguity, four-position overlap,
  Sunday-to-Monday bucketing, and clipped gap windows. The aggregate
  self-digest is
  `1bf1dba84b4a14f1f9b56bbfc711a104e94a8912a02cabc5a4a7bb94c42ac36a`.
- Independent review verdict: `PASS`, no P0-P3 findings. No raw rows,
  credentials, private paths, or M5 inputs were retained or printed. RETRO-
  007 does not establish gap causation, manual intervention, or a tradeable
  edge.

## 2026-08-03 -- RETRO-HIST-001 observed-lot distribution audit

- Locked a new RETRO-HIST contract, source receipt, and authorization record
  over the exact archived RETRO-003 report/tick manifests and the population
  `[2025-11-01, 2026-07-31)`. RH-001 reads only report positions and
  open_positions tables and retains no ordered schedule or raw rows.
- Implemented Decimal fixed8 quantity validation, side/symbol normalization,
  duplicate snapshot deduplication, closed-row precedence over missing close
  snapshots, conflict/censor/boundary handling, fixed aggregate schema, and a
  redacted CLI. The observed distribution is dominated by `0.10000000`, with
  nonzero `0.01000000`, `0.02000000`, `0.05000000`, `0.20000000`,
  `0.30000000`, and `1.00000000` bands on both sides.
- Focused validation passed 5 tests; isolated full suite passed 342 tests;
  compileall and `git diff --check` passed. Two real runs were byte-identical
  at aggregate level with self-digest
  `777ee6e852fd5f0576008ae8d36a49fec309fb8f14141443c07bf9915c40a383`.
- Independent contract re-review and fresh implementation re-review returned
  `VERDICT: PASS` with no P0-P3 findings. RH-001 remains descriptive and
  outside all M5 inputs, models, evaluations, thresholds, and live execution;
  RH-002 is the next bounded milestone.

## 2026-08-04 -- RETRO-HIST-002 historical lifecycle and stream adapter

- Locked RH-002 to the RH-001/RETRO-003 report and tick receipts over the
  half-open population `[2025-11-01, 2026-07-31)`. Conflicting snapshots are
  retained only as conservative censored interval markers; definite
  OPEN/CLOSE labels never drive the separate policy state.
- Added hash-verified manifest/path/object validation, global tick ordering
  before quote/envelope filtering, lexicographic same-time policy action keys,
  and fixed nested aggregate/digest/firewall checks. No raw rows, credentials,
  private paths, M5 inputs, or live execution surface were added.
- Focused RH-002 validation passed 18 tests; isolated full regression passed
  360 tests; compileall and `git diff --check` passed. Two real archived runs
  were byte-identical with aggregate digest
  `8392949ab28491953301d10fbcfe3efab8dab5b08354b68803e53a85c2e34db9`.
- Fresh independent implementation review returned `VERDICT: PASS` with no
  P0-P3 findings. RH-002 remains descriptive and outside all M5 inputs,
  models, evaluations, thresholds, and gates; next milestone is RH-003.

## 2026-08-05 -- RETRO-HIST-003 causal trigger and observed-sizing reconstruction

- Locked RH-003 to the inherited RH-002 report/tick receipt and its exact
  2025-11-01 through 2026-07-30 population. Implemented Decimal causal
  feature math, strict state/lot/action invariants, independent policy and
  oracle paths, bounded stream retention, and a RETRO-only report loader.
- Remediated FLAT fast-path parity for out-of-window envelope accounting and
  malformed-timestamp flushing. Added end-to-end future-lot isolation and
  non-FLAT fail-closed regressions. No raw rows, credentials, private paths,
  M5 inputs, live execution surface, or new source were added.
- Focused RH-003 validation passed 25 tests; full regression passed 385 tests;
  `compileall` and scoped `git diff --check` passed. Two full authorized
  archive runs were byte-identical with aggregate digest
  `95311f30fe6c2ce7e2c37503d51900787182285631feb1ab89c5530ceddd4369`, file
  SHA-256 `2c1683b83ebdb652f81d9343bda74b2ed8d453906bc6734192c4812ce81c2057`,
  and 27,603 bytes. Aggregate schema/self-digest validation passed.
- Fresh independent RH-003 re-review returned `VERDICT: PASS` with no P0-P3
  findings. Bootstrap was `FLAT` for both clock scenarios and no candidate
  emitted an action; the result is descriptive only. RH-004 is the next
  bounded milestone.

## 2026-08-05 -- RETRO-HIST-004 observed-lot paper accounting

- Locked RH-004 contract and source receipt to the exact RH-002 report/tick
  manifests and population `[2025-11-01, 2026-07-31)`. Added Decimal Bid/Ask
  accounting, fixed synthetic cost scenarios, latency-aware conservative
  marking, uneven/partial opens and closes, strict conservation, governance
  artifact hash pins, and recursive privacy/M5 validation.
- Focused validation passed 26 tests; full regression passed 411 tests;
  compileall and scoped `git diff --check` passed. Independent implementation
  re-reviews returned `VERDICT: PASS` with no P0-P3 findings.
- Two fresh authorized archive runs were byte-identical: aggregate digest
  `43ad1e09a59e78bbf2777e76d6b94f67cb7d98fe2824281e65e223c8f7b2d2b9`, file
  SHA-256 `2fd7c8f634dc320b31f7d8ab6ae2de36b58ae957a99da44f9f688e3f7fbec469`,
  and 5,706 bytes. Bootstrap was `FLAT`; all six inherited policy candidates
  emitted no actions under both clocks; every accounting scenario was
  `no_action` with zero quantities. RH-004 remains descriptive and outside
  all M5 inputs, models, evaluations, thresholds, and gates.

## 2026-08-06 -- RETRO-BOT-020 closeout

- Completed RB-020 under the accepted RH-002 source receipt and RETRO-only
  firewall. Autonomous replay remains causally isolated from oracle labels.
- Holdout receipt/seal and fold metric verifier blocks were remediated;
  independent final re-review returned `PASS` with no P0-P3 findings.
- Focused tests passed 13; privacy/RB checks passed 15; full regression passed
  424 with a repository-local basetemp; compileall, CLI smoke/tamper checks,
  and byte-identical deterministic reruns passed.
- Result is `no-supported-candidate` because the registered holdout fixture is
  fully censored. No tuning, profitability, M5, or live-execution claim is made.

## 2026-08-06 -- RETRO-LIVE-EVIDENCE-001 governance closeout

- Locked the independent evidence lane contract, source-receipt template,
  immutable gate registry, timezone/actionful definitions, holdout protocol,
  oracle isolation, and RETRO/M5/execution firewall using synthetic fixtures
  only.
- Independent plan critic recommended `complex`; revised plan was written
  before implementation. Fresh independent re-review returned `PASS` with no
  P0-P3 findings after recursive oracle isolation and strict registry/receipt
  validation fixes.
- Focused E-001/RB-020 tests passed 19; full regression passed 430 with a
  repository-local basetemp; compileall and scoped diff checks passed.
- E-002 requires a new owner authorization/source receipt; no raw source,
  realtime feed, demo, canary, or live execution was accessed.

## 2026-08-06 -- RETRO-LIVE-EVIDENCE-002 synthetic intake scaffold

- Added bounded redacted cycle intake, frozen gate aggregation, Decimal fixed8
  lot checks, denominator/actionful invariants, strict aggregate verification,
  stdin-only CLI, trusted external digest parameters, and tamper/firewall tests.
- Focused E-001/E-002/RB-020 tests passed 23; full regression passed 434 with
  repository-local basetemp; compileall and scoped diff checks passed.
- Fresh independent re-review returned `PASS` for the synthetic scaffold.
  Actual E-002 source capture remains unstarted pending new owner
  authorization, exact aliases/hashes/window, and allowed-field receipt.
- Post-review remediation added aggregate-level conservation and denominator
  invariants; fresh re-review returned `PASS` with no P0-P3 findings. Focused
  regression remained 23 passed.

## 2026-08-06 -- RETRO-LIVE-EVIDENCE-003/004 synthetic scaffolds

- Added redacted action-checkpoint fidelity metrics with exact frozen category
  vocabulary, finite metric validation, actionful population checks, and a
  strict aggregate verifier.
- Added one-shot synthetic holdout sealing with trusted source-receipt and
  fold-order/bounds digests. Fold bounds are required to be chronological,
  half-open, and non-overlapping; malformed robustness input does not consume
  the nonce.
- Added strict holdout-result verification and fail-closed status when any
  fold is actionful-insufficient, gate-failing, or robustness-failing.
- Focused tests passed 5; compileall and diff checks passed. Fresh independent
  re-review returned `PASS` with no P0-P3 findings. Real actionful capture,
  shadow observation, and demo/canary readiness remain unauthorized.

## 2026-08-06 -- RETRO-LIVE-EVIDENCE-005 synthetic shadow scaffold

- Added a redacted checkpoint-only observer with source/clone state and action
  parity, timestamp-bound latency, deterministic tie ordering, reconnect-event
  accounting, recovery failure detection, and fail-closed unsafe divergence.
- Added a stdin-only CLI and strict aggregate verifier with trusted input
  digest, explicit numerator/denominator formulas, finite-value checks, and
  determinism fixed false for the synthetic scaffold.
- Remediated the E-002 intake denominator boundary and added strict regression
  coverage for synthetic-only and fixed8 constraints.
- Focused E-002/E-003/E-005 tests passed 13; full `uv run --locked pytest`
  passed 443 tests with a repository-local basetemp; compileall and diff checks
  passed. Real shadow observation and E-006 demo/canary readiness remain
  unauthorized.

## 2026-08-06 -- RETRO-LIVE-EVIDENCE-006 synthetic safety/readiness scaffold

- Added the frozen E-006 contract, plan, safety gate registry, fail-closed
  readiness evaluator, and stdin-only deterministic CLI. Synthetic inputs
  always produce `hold-synthetic-only`.
- Added an offline `SafetyAdapterSimulator` with canonical fixed8 hard limits,
  idempotent intent receipts, position accounting, action/retry/latency bounds,
  monotonic stop latch, one simulated non-opening/non-reversing flatten, and
  operator-acknowledged sequence/snapshot reconnect recovery. Transport calls
  are structurally zero.
- Focused E-006 tests passed 8; full `uv run --locked pytest` passed 451 tests
  with a repository-local basetemp; compileall and diff checks passed. Fresh
  independent re-review returned `PASS` with no P0-P3 findings. Real E-002
  actionful capture, untouched holdout, shadow observation, and demo/canary
  readiness remain unauthorized.

## 2026-08-06 -- E-002 authorization checklist

- Added an unfilled owner-authorization/source-receipt checklist covering
  opaque aliases, hashes, byte counts, UTC half-open window, timezone code,
  exact allowlist, parser/canonicalization versions, retention, blindness, and
  M5/execution firewalls.
- No source was opened or hashed; the checklist does not authorize E-002.
