# RETRO-BOT-004: Evidence and Temporal Population Freeze

Status: owner-authorized follow-on for the RETRO-BOT V2 lane on 2026-08-03;
not an M5 task.

## Purpose

Freeze the historical population, temporal folds, bootstrap policy, and
censoring taxonomy required before an autonomous historical bot is built.
This milestone defines data boundaries only. It does not fit candidates,
select a policy, tune thresholds, or produce a profitability result.

## Source boundary

Only the exact sources already locked by RETRO-BOT-001 may be used:

- `docs/observational_cases/RETRO-003-2025-11_to_2026-07-history-screening-receipt.md`;
- report manifest SHA-256
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`;
- tick manifest SHA-256
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`;
- base configuration
  `docs/retro_bot/RETRO-BOT-001-config.json`, SHA-256
  `b420d9d014c2cac67461eda9603a200b2a48d0ad1fa0299baaf1c8cdeded5c52`.

The population is the half-open server-time interval
`[2025-11-01 00:00:00, 2026-07-31 00:00:00)`. August M5 blocks, July 31
RETRO-001/002 sources, XLSX/PNG companions, M1 bars, journals, terminal logs,
support caches, credentials, account details, and `.ex5` remain excluded.

Before any source is opened, the runner must verify manifest digests, exact
aliases, suffixes, path containment below the registered quarantine run, and
non-partial status. Any mismatch fails closed. Raw rows, source paths,
timestamps, prices, tickets, identifiers, and detailed traces must not appear
in stdout, stderr, tracked files, receipts, or result artifacts.

## Temporal folds

Folds are assigned before parsing and are grouped at report/session/case
boundaries. A cross-midnight or overlapping interval belongs to one fold only;
tick chunks supporting that interval follow the same fold. No random interval
split is allowed.

The initial deterministic fold proposal is:

| Fold | Report aliases | Role |
| --- | --- | --- |
| `development` | `report-001.html` through `report-005.html` | candidate development only |
| `validation` | `report-006.html` through `report-007.html` | protocol selection only |
| `holdout` | `report-008.html` through `report-009.html` | untouched final evaluation |

The report date ranges are pinned and must be verified before parsing:

| Alias | Half-open server range |
| --- | --- |
| `report-001.html` | `[2025-11-01, 2025-12-01)` |
| `report-002.html` | `[2025-12-01, 2026-01-01)` |
| `report-003.html` | `[2026-01-01, 2026-02-01)` |
| `report-004.html` | `[2026-02-01, 2026-03-01)` |
| `report-005.html` | `[2026-03-01, 2026-04-01)` |
| `report-006.html` | `[2026-04-01, 2026-05-01)` |
| `report-007.html` | `[2026-05-01, 2026-06-01)` |
| `report-008.html` | `[2026-06-01, 2026-07-01)` |
| `report-009.html` | `[2026-07-01, 2026-07-31)` |

Duplicate aliases, date-range mismatches, and ambiguous report ownership fail
closed. A weekly tick object may serve more than one fold, but every in-memory
row is masked to the target half-open fold/window before use; the object hash
and source receipt remain unchanged. An interval or continuation crossing a
fold boundary is assigned `cross_fold_continuation` and contributes to no
fold's valid denominator.

The executable sufficiency thresholds are at least 2 independent report/case
units per fold and at least 2 eligible intervals per side (`ONE_BUY` and
`ONE_SELL`) in each non-empty evaluation fold. They are evaluated separately
for each bootstrap row. The `left_censored` evidence row is expected to report
`insufficient_population`; the V2 implementation may proceed only if the
fixed-seed row clears the same thresholds. If that feasibility row also misses
a threshold, the deterministic terminal result is `insufficient_population`
and the workflow stops rather than expanding sources or reusing an oracle
population silently.

## Bootstrap and causal state boundary

Each replay window uses one immutable bootstrap mode selected before parsing:

1. `receipt_pinned_snapshot`, if a pre-window position snapshot is present in
   a future owner-authorized receipt;
2. `fixed_warmup_seed`, only with a declared seed state and warm-up duration;
   warm-up actions and labels are excluded from evaluation; or
3. `left_censored`, when neither of the above is available.

The current source receipt provides no autonomous pre-window position
snapshot, so RB-008 registers two separate, non-selectable rows:

- `left_censored`: the evidence row; every current window remains
  `left_censored_unknown_bootstrap` and no later event can make it
  autonomous-eligible.
- `fixed_warmup_seed`: a feasibility scenario with fixed seed state `HEDGED`,
  warm-up duration `0` seconds, and an explicit
  `assumption_dependent_not_observed` flag. It is allowed to feed later
  autonomous pipeline tests, but it is never treated as an observed account
  snapshot or a broker-time conclusion.

Both rows must be reported side by side. No historical outcome may select the
seed mode, alter its parameters, or hide the left-censored row. The first
observed unlock, close, or re-hedge event may be an oracle label but can never
initialize autonomous state. A future receipt may add a verified snapshot as
a separate scenario.

## Clock, boundaries, and censoring

The three existing clock scenarios remain separate rows: `utc_plus_2`,
`utc_plus_3`, and `eu_dst_2025_2026`. All report and tick windows are half-open.
The exact DST transition instants are `2025-03-30T01:00:00Z` (UTC+2 to
UTC+3), `2025-10-26T01:00:00Z` (UTC+3 to UTC+2),
`2026-03-29T01:00:00Z` (UTC+2 to UTC+3), and
`2026-10-25T01:00:00Z` (UTC+3 to UTC+2). Cross-midnight conversion, DST
spring gaps, fall-back folds, second-level timestamp collisions, and
missing-tick gaps are explicit fixtures.

The only censor/exclusion classes are:

- `left_censored_unknown_bootstrap`;
- `cross_fold_continuation`;
- `right_censored_no_terminal`;
- `coverage_censored_no_valid_tick`;
- `invalid_transition`;
- `clock_unresolved`.

Apply this precedence exactly once per window: `clock_unresolved`,
`invalid_transition`, `cross_fold_continuation`,
`left_censored_unknown_bootstrap`, `coverage_censored_no_valid_tick`, then
`right_censored_no_terminal`. Every aggregate must satisfy conservation: total
windows equal valid windows plus exactly one disjoint censor/exclusion class.
Censored windows contribute no actions, marks, or paper P/L.

## Retained outputs and claims

Retain only a privacy-validated aggregate containing schema/version, source
manifest digests, fold counts, clock ids, bootstrap/censor counts, and a
self-digest. Canonical tracked references to the contract, receipt, and config
are allowed; private quarantine paths and raw source paths are prohibited.
Internal identifiers may be used in memory for grouping but may not survive
into output. No fitting, threshold tuning, policy selection, profitability
claim, broker/manual attribution, live execution, or M5 gate decision is
permitted.

## Acceptance and stop conditions

- Manifest, alias, path, suffix, partial-file, and config tamper tests fail
  before source opening.
- Fold assignment is deterministic, chronological, disjoint, and grouped by
  report/session/case with cross-boundary continuations rejected.
- Bootstrap tests prove that missing snapshots produce left censoring and that
  the first observed event never seeds autonomous state.
- DST, second-resolution collision, cross-midnight, and tick-gap fixtures
  produce the declared fail-closed classes.
- Censor classes conserve denominators and cannot contribute actions or marks.
- Privacy scans cover stdout/stderr, receipts, results, and source paths; the
  RETRO/M5 firewall passes.
- Two clean synthetic runs produce byte-identical aggregates.

Stop if any source verification, firewall, privacy, population sufficiency,
or causal bootstrap gate fails. Source expansion requires a new owner decision,
source receipt, and contract.

Reproducible validation commands are `uv run --offline pytest
tests/test_retro_bot_contract.py tests/test_retro_bot_004.py`, `uv run
--offline python scripts/check_privacy.py`, and `uv run --offline pytest
tests/test_retro_bot_contract.py -q` for the pinned firewall/contract scan.
