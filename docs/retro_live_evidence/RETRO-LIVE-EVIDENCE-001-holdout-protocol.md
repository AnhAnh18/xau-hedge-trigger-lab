# RETRO-LIVE-EVIDENCE-001 Holdout Protocol

- Register chronological development, validation, and one final holdout
  interval before any E-002 inspection.
- Use a half-open UTC RFC3339 window and reject overlap or ambiguous timezone
  conversion.
- Bind the one-shot nonce to the gate-config digest, source-receipt digest,
  and holdout-input digest.
- Reject reused nonces, changed payloads/configuration, parser changes,
  threshold changes, and second consumption.
- After consumption, no candidate, threshold, timezone, parser, or cost change
  is permitted. Any failed holdout gate yields `HOLD`.
