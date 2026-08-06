# RETRO-LIVE-EVIDENCE-002 Tooling Status

Status: synthetic intake scaffold only; E-002 historical capture is not
complete and no source receipt is claimed.

The intake accepts bounded, redacted cycle aggregates and computes the frozen
gate families, including comparable coverage, Decimal lot tolerance, state
safety, robustness counts, and tamper-resistant component totals. It rejects
raw/source paths, credentials, private fields, and execution surfaces.

The verifier's `expected_input_digest` and `expected_component_digest` must be
supplied from an independently retained intake receipt; the aggregate's own
self-digest is not an authenticity mechanism. The accounting-inconclusive
taxonomy is reserved for a later accounting stage and is not emitted by this
synthetic intake.

`determinism` is intentionally `false` until a later caller supplies two
independent canonical subprocess outputs and a receipt bound to the source,
gate configuration, and holdout digests. Therefore this scaffold cannot report
`package-ready` by itself.

E-002 capture remains locked until a new owner authorization names exact source
aliases, SHA-256 hashes, UTC window, timezone declaration, allowed fields,
retention, and parser version. No raw data was opened by this milestone.
