# RETRO-BOT-011 Implementation Plan

Canonical milestone: `RB-015`. Implement only this revised plan; do not
expand the RETRO source boundary or alter M5 artifacts.

1. Reconcile durable state to the roadmap's RB-015 Robustness/Stress/Ablation
   identity. Define `RB015_PROJECTION_V1`, its exact 40-row projection,
   synthetic fixture id, projection digest, immutable dimensions/costs,
   canonical case ids, typed observations, and strict privacy/value validators.
2. Implement coupled UTC-label/causal-snapshot clock transforms, exact quote
   and coverage perturbation semantics, deterministic fault precedence, and
   feature-ablation adapters that call the locked RB-014 paper cycle API
   without source access or action injection.
3. Implement the redacted RB-015 observation and complete-matrix aggregate
   schema. Verify conservative status/band counts, fixed no-selection terminal
   status, inherited RB-014 digests/attestation/firewall, projection and
   fixture identity, canonical row order, recursive privacy allowlists, and
   self-digest; never retain RB-014 returns or raw cycles.
4. Add offline `validate-config`, `stress-replay`, and `verify-aggregate` CLI
   stages over typed JSON only; reject raw paths, precomputed rows, unknown
   dimensions, and private keys.
5. Add synthetic tests for every projection family and stress dimension,
   coupled clock labels, quote/censor precedence, timestamp collisions,
   one-leg starts and slices, ablations, exact cost/latency/margin behavior,
   matrix/case/projection/fixture/digest tampering, duplicate/missing cases,
   recursive private-key rejection, deterministic reruns, privacy, and M5
   isolation.
6. Run focused RB-015/RB-014 tests, full suite, privacy, compileall, diff
   checks, and two byte-identical stress runs. Obtain a fresh independent code
   review, remediate every in-scope P0-P3, and perform a new re-review.
7. Only after PASS update state, stage only RB-015 artifacts, commit with the
   `RB-015:` prefix, and push the `codex/rb-015-stress` branch.

Acceptance: a locked, descriptive stress/ablation matrix exercises RB-014
without tuning or candidate selection, fails closed on malformed conditions,
and remains entirely outside M5.
