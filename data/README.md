# Data handling

Raw and derived datasets are intentionally excluded from Git. Store them in access-controlled external storage, using stable dataset names and recording checksums outside the raw files.

Expected private inputs:

- Four MT5 weekly trade reports
- One XAUUSD tick file covering 2026-07-23 to 2026-07-24
- Approximately one month of trade history

For each dataset, record its source, timezone, coverage, schema version, processing code version, and SHA-256 checksum in the relevant research notes. Never commit account numbers, names, balances, cash flows, trade reports, or broker tick data.
