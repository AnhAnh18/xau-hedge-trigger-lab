# XAU Hedge Trigger Lab

Research and reconstruction of an alternating XAUUSD hedge-rotation trading strategy using MT5 trade reports and broker tick data.

## Scope

This repository prioritizes behavioral fidelity: reconstructing what the strategy did before evaluating profitability. It is intended for private research and must not contain raw account exports or personally identifying trading data.

Project memory and the current execution state live in [`.local_ai/`](.local_ai/).

## Current phase

**M0 — Repository bootstrap**

The next executable task is to parse MT5 reports and the XAUUSD tick CSV into normalized, reproducible tables. Raw files belong in external, access-controlled storage; only dataset names, checksums, and processing logic should be recorded here.

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
