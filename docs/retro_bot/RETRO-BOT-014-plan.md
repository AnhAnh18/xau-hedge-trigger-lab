# RETRO-BOT-014 Implementation Plan

Canonical milestone: `RB-018`. Implement only the bounded synthetic/shadow
terminal seal in `RETRO-BOT-014-contract.md`. This plan consumes redacted
RB-017 closeout reports; it introduces no raw source, historical replay,
candidate fitting, M5 use, or live/external execution surface.

1. Treat `RETRO-BOT-014-registration.md` as the locked registration artifact;
   verify its fixed registration preimage and the pinned digest in the
   contract. Verify `RETRO-BOT-013-prerequisite-receipt.json` against its
   pinned canonical digest, and confirm RB-017 has a PASS verdict, focused
   re-review, durable state recording, and the pinned validator module hash.
   If any prerequisite is absent, stop without implementation or state
   changes.
2. Freeze the RB-018 constants, exact ordered schemas, canonical JSON rules,
   fixed shown/unresolved lists, terminal literals, and self-digest preimages
   from the contract. Treat the RB-017 report validator as an inherited,
   immutable dependency.
3. Add `src/xau_trigger/retro_bot_014.py` with strict duplicate-key loading,
   finite/trailing-byte rejection, a schema-aware recursive privacy/M5/live
   scan, RB-017 report and validator-hash validation, two-run canonical
   equality/process-receipt checks, run/attestation self-digest verification,
   and deterministic terminal-receipt construction. Use the frozen canonical
   JSON serializer locally rather than relying on a mutable upstream helper.
   Keep all values in memory; never open a source path or write input.
4. Add `scripts/run_retro_bot_018.py` with stdin-only `seal` and
   `verify-seal` stages. Emit exactly `{"stage":"verify-seal","verified":true}`
   on verification success. Normalize `OverflowError`, `UnicodeError`,
   `AttributeError`, `IndexError`, `RecursionError`, malformed JSON, and
   non-finite values to fixed exit code `2`, empty stdout, and exact stderr
   `RB-018 input rejected` plus one LF; never echo rejected input.
5. Add `tests/test_retro_bot_014.py` covering the exact schemas and literals,
   report/run/attestation digest tampering, mismatched run reports, duplicate
   keys and unknown fields, canonical-equivalent input, optional receipt
   comparison, recursive privacy/M5/live firewall, fixed stop conditions,
   deterministic subprocess output, clean RB-017 isolation, registration and
   prerequisite digest vectors, validator hash, stdout-with-LF framing,
   process nonce requirements, golden canonical preimages, uppercase-hex and
   boolean-as-int rejection, deep/trailing/non-finite malformed inputs,
   exact stderr/empty-stdout failures, and no filesystem side effects.
6. Run focused tests, then the isolated full suite, privacy scan, `py_compile`,
   and `git diff --check`. Run `seal` twice in fresh processes and compare
   stdout bytes and SHA-256 values; run `verify-seal` on both recomputed and
   supplied receipts.
7. Obtain an independent review in a separate session. Fix every confirmed
   in-scope P0-P3 finding, run a focused re-review, and repeat all validation
   checks. Any privacy, M5, source-expansion, live-execution, or
   non-determinism finding blocks closeout.
8. Only after a PASS re-review, let the state recorder update `STATUS.md`,
   `TASKS.md`, and `SESSION_LOG.md`; stage only the RB-018 contract,
   implementation, CLI, and tests, and commit with an `RB-018:` prefix. Do
   not alter frozen RB-016/RB-017 artifacts, M5 files, raw data, or receipts.

Acceptance: a separate process can validate two byte-identical RB-017 redacted
reports with distinct process receipts and emit a self-hashed terminal receipt
that closes the offline RETRO-BOT lane as synthetic/shadow-only and
accounting-inconclusive, while every source, privacy, M5, and live-execution
boundary remains fail-closed.
