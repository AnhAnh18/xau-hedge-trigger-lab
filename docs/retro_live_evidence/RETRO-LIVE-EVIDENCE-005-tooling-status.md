# RETRO-LIVE-EVIDENCE-005 Tooling Status

Status: synthetic read-only shadow-observer scaffold only.

The observer accepts redacted checkpoints, compares source and clone state and
actions, and records latency, reconnect, recovery, and safety flags. It has no
realtime connector and no execution/order API. Unsafe divergence, future reads,
execution-surface use, or failed recovery force `hold`. A real observer remains
blocked on E-002 through E-004 actionful evidence and a new owner authorization.

`reconnect_count` is an event delta for the checkpoint (not a cumulative
counter); aggregate metrics retain explicit parity numerators/denominators.
Determinism is intentionally fixed false in this synthetic scaffold. The
verifier requires a trusted input digest but is not a source-authenticity
boundary; a real observer must add source-receipt and clone-package digests.
