# Data

Raw MT5 account reports and broker tick data are not committed to Git.

## Local layout

- `data/raw/trades/`: MT5 HTML history reports
- `data/raw/ticks/`: broker XAUUSD tick CSV files
- `data/interim/`: parsed but not fully validated tables
- `data/processed/`: validated analysis datasets

## Privacy

Raw reports can contain account-holder identity, account number, balance, and transaction history. Never commit passwords, account-identifying HTML reports, raw tick exports, or balance/deposit/withdrawal records.

Dataset identity and integrity are recorded in `manifest.yaml`. Run `python scripts/audit_data.py` after copying private files locally.

## M5 external-session intake

The locked M5 acquisition plan is machine-readable at
`data/m5_acquisition_plan.json`. Validate the registration and exercise the
entire intake path without private data:

```bash
python scripts/validate_m5_acquisition.py --plan-only
python scripts/validate_m5_acquisition.py --dry-run
```

After copying the registered exports into `data/raw/ticks/` and
`data/raw/trades/`, run:

```bash
python scripts/validate_m5_acquisition.py \
  --output reports/private/m5_acquisition_validation.json
```

The output uses generated file aliases rather than raw filenames, emits no
financial values, records SHA-256 checksums, preserves duplicate millisecond
ticks, and audits coverage gaps against the pre-registered 60-second rule.
Raw files remain outside Git.

Historical data is technically valid for temporal validation when its ticks
are complete and it has not already been inspected for the M5 result. The
current 2026-07-27 through 2026-07-29 dates were selected as the first
contiguous untouched sessions, not because validation requires future data.
Changing those dates requires a dated manifest/plan amendment before any
replacement result is inspected; dates must never be selected because they
produce a favorable model result.
