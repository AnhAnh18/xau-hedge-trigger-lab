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
