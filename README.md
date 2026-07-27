# XAU Hedge Trigger Lab

Research and reconstruction of an alternating XAUUSD hedge-rotation trading strategy using MT5 trade reports and broker tick data.

## Scope

This repository prioritizes behavioral fidelity: reconstructing what the strategy did before evaluating profitability. It is intended for private research and must not contain raw account exports or personally identifying trading data.

Project memory and the current execution state live in [`.local_ai/`](.local_ai/).

## Current phase

**M5 — Trigger Inference**

M0–M4 are complete. M5-002 has implemented a bounded state-age-only hazard
pilot on locked causal support. Frozen age buckets improve internal holdout
cause-specific occurrence likelihood for all three endpoints, with the
approximate six-second unlock timer floor transporting most clearly. External
validation remains pending and no tradeable-edge claim is made.

The M5-003 causal price-increment pipeline is implemented and frozen under the
pre-registered contract in `.local_ai/M5_003_PREREGISTRATION.md` and
`data/m5_003_preregistration.json`. Development and 2026-07-24 internal-reuse
results are diagnostic only. They create no supported/rejected price verdict
and no tradeable-edge claim.

Independent review prompted a bounded session-baseline remediation before any
external data was loaded. The frozen headline is now
`C_session - A_session`; the old `C_dev - A_dev` result is retained only for
audit. Fixed server-time blocks, fully refit LOSO diagnostics, and the reduced
shape diagnostic are documented in the M5-003 report.

Claude independently reproduced and accepted the remediated implementation.
The bounded review follow-ups add an external two-of-three positive-session
gate and stricter interpretation limits without changing the fitted model. The
remaining data task is to acquire the pre-registered 2026-07-27 through
2026-07-29 XAUUSD tick sessions and the covering MT5 report. Raw files remain
in external, access-controlled storage; only manifests, aggregate reports, and
reproducible processing logic are committed.

Rebuild the local M5-002 pilot outputs and aggregate report with:

```bash
python scripts/build_m5_state_age_pilot.py
```

Rebuild the local M5-003 causal feature/model artifacts and committed aggregate
reports with:

```bash
python scripts/build_m5_price_increment.py
```

## Layout

```text
.local_ai/   Project memory, status, decisions, findings, and tasks
data/        Data handling and provenance guidance (raw data is ignored)
src/         Analysis and reconstruction code
notebooks/   Exploratory work
tests/       Automated checks
reports/     Generated research reports
```

## Privacy

Do not commit account numbers, account-holder names, trade history, balances, cash flows, broker tick exports, or raw MT5 reports. See `.gitignore` and `data/README.md`.
