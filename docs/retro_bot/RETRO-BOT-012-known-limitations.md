# RB-016 Known Limitations

- Input is a synthetic, typed RB-015 fixture; this package does not fetch,
  mount, parse, or retain raw historical exports.
- The aggregate is descriptive and `descriptive-only-no-selection`; it is not
  a profitability, broker-ownership, or live-trading claim.
- Quote gaps, action/mark censoring, second-level report timestamps, and the
  inferred UTC+3 server window remain structural limitations.
- State snapshots are bookkeeping of the initial synthetic `all` slice, not
  live broker state or an order-management checkpoint.
- The package never calls MT5, sends orders, reads credentials, accesses
  `.ex5` artifacts, or changes M5 inputs, models, thresholds, or gates.
