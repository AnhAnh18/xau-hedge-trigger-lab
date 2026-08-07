# RETRO-LIVE-EVIDENCE-004 Tooling Status

Status: synthetic/redacted governance primitive only.

- `scripts/run_retro_live_evidence_004.py` reads one bounded JSON envelope
  from stdin and writes one canonical redacted ledger envelope to stdout.
- `verify` requires an externally pinned expected head, trusted source/fold
  context, and a `trusted_input_digests` set covering every ledger entry.
- `append` requires a complete redacted `evaluation_proof` and an explicit
  `evaluation_succeeded=true` marker; failed proof,
  reused nonce, reused holdout, altered context, missing candidate
  `trusted_input_digest`, or CAS/head mismatch fails without mutating the
  input ledger.
- The module opens no source files and exposes no realtime, broker, order,
  demo, canary, live, M5, or `.ex5` surface. The only `live` token permitted
  by the firewall is the exact governance `case_id`.
- This does not promote E-003/E-004 real fidelity, shadow, demo, canary, or
  live readiness. E-002 remains fail-closed at insufficient actionful
  coverage.
