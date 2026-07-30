# M5-004 Provenance Amendment

Status: Registered on 2026-07-30 before M5-004 implementation, feature
construction, model fitting, or inspection of the replacement external block.

Machine-readable companion:
`data/m5_004_provenance_amendment.json`.

This document amends only the upstream provenance, cohort roles, future
external dates, and the session-count coherence clause of the locked
`.local_ai/M5_004_PREREGISTRATION.md`. All other event, feature, model,
preprocessing, selection, inference, output, privacy, and claim restrictions
remain binding.

## Reason for the amendment

The 2026-07-27 through 2026-07-29 sessions were evaluated by M5-003. Selected
operational screenshots from 2026-07-27 and 2026-07-28 were also discussed.
Those dates are therefore no longer untouched for the later M5-004
unlock-direction question.

They receive the permanent M5-004 role:

```text
seen_external_reuse_diagnostic
```

They may be evaluated descriptively only after the full M5-004 package is
frozen. They may never enter fitting, preprocessing, feature or penalty
selection, calibration, threshold selection, verdicts, merge gates, or a
future external result.

## Explicit delta from the 2026-07-27 contract

| Contract item | Locked contract | Effective amended contract | Reason |
| --- | --- | --- | --- |
| Upstream reference | Draft PR #8 head | Merged M5-003 commit `bd4715d0f06791e60ab01a44146a87d1297a6e56` | Replace mutable draft provenance |
| 2026-07-27..29 role | Untouched external verdict gate | Seen external reuse diagnostic only | Dates were evaluated and partly observed |
| Primary external block | 3 sessions on 2026-07-27..29 | 5 sessions on 2026-08-03..07 | Fresh untouched block |
| Fallback external block | None | 2026-08-10..14 | Pre-registered structural fallback |
| Session coherence | At least 2 of 3 means strictly positive | At least 3 of 5 means strictly positive | Mechanical adaptation to five sessions |

No other inference rule changes:

- the headline remains one-second
  `C_age_price_cause - A_age_cause`;
- support still requires a positive pooled mean and a positive one-sided 95%
  interval-cluster bootstrap lower bound;
- rejection still requires the ordinary two-sided 95% upper bound to be at or
  below zero;
- LOSO is required and descriptive only;
- 500 milliseconds is timing sensitivity only and cannot create or overturn a
  verdict;
- bootstrap draws remain 5,000, seed remains 5004, and the cluster key remains
  `cohort_id:interval_id`.

## Upstream provenance

The M5-003 external evaluation did not mutate the already locked M5-002 or
M5-003 canonical artifacts. Existing hashes remain binding:

| Artifact | SHA-256 |
| --- | --- |
| M5-003 preregistration | `4da95ca8b787e201a77f03fcfe1bf40145752bb967d4d847325349c528f50616` |
| M5-003 internal report | `9b6cc69feea7fd031c039a7af7f6cf8900c6fcc21cd952f6eb1a4ea5d6824eb1` |
| M5-003 frozen manifest | `da2f9e0c66bdf8e51a349bc77db67fc3bbd1f8dc100d359890ac7ee54b14e747` |
| M5-003 feature audit dataframe | `44183dbf388a9dc86344d3beaea480f0db3242488c66afa937ddef0475ce78b4` |
| M5-003 joint-valid dataframe | `69deadc6a6d2ed45ff12c15ef7659a73cf09ace74d27b496938dd057569800f2` |
| M5-002 risk-bin dataframe | `62f0f0fa4f961b699461c2c3ba935c460d853b4553142130187c503fb4698520` |

New provenance:

| Artifact | Value |
| --- | --- |
| M5-003 merge commit on `main` | `bd4715d0f06791e60ab01a44146a87d1297a6e56` |
| M5-003 external report hash | `f4e12813d091030a61a843251a172fe356b8261313bf56efc913a28e7af431bf` |

## Effective event and model contract

The exact event-construction, one-row-per-unlock, eligibility, causal-window,
12-feature allowlist, forbidden-predictor, joint-validity, A/B/C model,
development-only preprocessing, GroupKFold, regularization, ablation, output,
and privacy clauses are inherited by reference from the locked
M5-004 preregistration.

In particular:

- the estimand remains
  `P(UNLOCK_TO_BUY | an eligible unlock event occurred)`;
- non-event, censored, competing, unresolved, and excluded rows never become
  cause negatives;
- state age at bin start is at least five seconds;
- common-hour and non-cross-split restrictions remain;
- duplicate `(cohort_id, interval_id, bin_width_ms)` event rows are fatal;
- all A/B/C comparisons use identical jointly valid event rows;
- the exact GroupKFold and bootstrap unit is `cohort_id:interval_id`;
- M5-003 predictions or residuals are forbidden predictors.

## Replacement external blocks

Primary untouched block, in server dates:

```text
2026-08-03
2026-08-04
2026-08-05
2026-08-06
2026-08-07
```

Fallback block, usable only after a locked structural failure of the complete
primary block:

```text
2026-08-10
2026-08-11
2026-08-12
2026-08-13
2026-08-14
```

No subset of either block may create a verdict. If the primary block fails,
all usable primary sessions become descriptive only. The fallback switch may
not depend on unlock counts, direction balance, feature associations,
predictions, likelihoods, or daily model results.

The primary trade report must include context beginning 2026-07-31 and cover
through 2026-08-08. The fallback report must include context beginning
2026-08-07 and cover through 2026-08-15. This preserves pre-weekend carry-over
accounting. Context dates are not model sessions.

## Blind intake contract

Before either block is acquired, the model package, target dates, intake
rules, allowlist, preprocessing, penalty selection, inference, and hashes must
be frozen.

The intake report may expose only:

- generated file aliases and SHA-256 hashes;
- parser/schema status;
- XAUUSD and server-date coverage;
- timestamp ordering and duplicate-millisecond preservation;
- first tick no later than 01:05 server time;
- last tick no earlier than 23:50 server time;
- quote-gap boundaries and structural classifications;
- report/tick overlap;
- financial and inventory reconciliation statuses;
- aggregate lifecycle completeness without unlock direction counts.

It must not expose unlock-direction balance, directional daily event counts,
feature/label associations, predictions, coefficients, calibration, or model
performance.

A session is structurally accepted when parsing, symbol/date coverage,
financial reconciliation, inventory reconciliation, and boundary coverage all
pass, and every gap longer than 60 seconds is either:

- classified as scheduled by the frozen recurring-clock rule; or
- reproduced with identical boundary ticks in an independent export and
  classified as `replicated_source_quote_gap`.

Accepted gaps are never interpolated. Their time and every causal lookback
crossing them are excluded. An unknown or non-replicated material gap makes
the complete block structurally unusable. Low sample size, no eligible unlock
on a day, class imbalance, and adverse model results are not structural
failures and cannot activate the fallback.

## Effective external decision rule

The one-second external headline is `supported` only when:

1. the pooled paired mean is strictly positive;
2. the deterministic one-sided 95% interval-cluster bootstrap lower bound is
   strictly positive;
3. at least three of five daily point estimates are strictly positive;
4. every intake, leakage, freeze, determinism, CI, and privacy check passes.

It is `weak/inconclusive` when the pooled mean is positive but an inferential
or session-coherence condition fails. It is `mixed/inconclusive` when the
one-sided lower bound is positive but fewer than three daily means are
positive. It is `rejected for this design` only when the ordinary two-sided
95% upper bound is at or below zero. All other outcomes are inconclusive.

A session with zero eligible jointly valid unlock events has an undefined
daily mean, counts as not positive for the three-of-five coherence clause, and
does not activate the fallback.

Daily, pooled, LOSO, secondary `C_age_price_cause - B_price_cause`, ablation,
and 500-millisecond timing-sensitivity results must be published. LOSO and
500-millisecond results receive no independent verdict and do not alter the
one-second headline verdict.

Any result concerns incremental directional information only. It cannot prove
unlock timing, causality, profitability, execution feasibility, broker
ownership, strategy equivalence, or a tradeable edge.

## Authorization and review gate

This amendment does not authorize M5-004 implementation or fitting. After it
is independently reviewed and merged, the owner may separately authorize
implementation on development 2026-07-20 through 2026-07-23 with
2026-07-24 as internal-reuse diagnostics.

No raw file from the primary or fallback block may be loaded before the
development package is frozen. The future block is evaluated exactly once
after blind intake passes.
