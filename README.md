# XAU Hedge Trigger Lab

Research and reconstruction of an alternating XAUUSD hedge-rotation trading strategy using MT5 trade reports and broker tick data.

## Scope

This repository prioritizes behavioral fidelity: reconstructing what the strategy did before evaluating profitability. It is intended for private research and must not contain raw account exports or personally identifying trading data.

Project memory and the current execution state live in [`.local_ai/`](.local_ai/).

## Current phase

**M5 — Trigger Inference**

M0–M4 are complete. M5-000 has locked canonical tradeable-time accounting,
common-hour cohort support, timezone status, and the external validation
protocol without fitting a model.

The next executable task is to acquire the pre-registered 2026-07-27 through
2026-07-29 XAUUSD tick sessions and the covering MT5 report. Raw files remain
in external, access-controlled storage; only manifests, aggregate reports, and
reproducible processing logic are committed.

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
