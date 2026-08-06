# RETRO-LIVE-EVIDENCE-003/004 Tooling Status

Status: synthetic fidelity and holdout protocol scaffold only.

Each E-003 comparison record represents one comparable `action_checkpoint`;
the category vocabulary is frozen to the five registered population classes.
E-003 computes redacted state/direction/order/timing/lot/coverage/duplicate and
state-safety metrics with actionful population checks. E-004 binds a holdout
receipt to the frozen gate digest, independently trusted source-receipt digest,
input digest, canonical development-validation-holdout order digest, and nonce.
Its result has a strict schema/digest verifier and remains `hold` unless all
fold actionful/gate requirements and robustness requirements pass.

The `used_nonces` ledger is an explicit caller-owned append-only receipt store;
the current scaffold does not create a durable filesystem ledger and does not
claim that a fresh process can authenticate a real holdout. Actual E-004
consumption requires an independently retained receipt artifact under a new
owner authorization. No raw source or holdout was opened.
