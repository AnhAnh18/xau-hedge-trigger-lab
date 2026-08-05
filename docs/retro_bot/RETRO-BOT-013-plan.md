# RETRO-BOT-013 Implementation Plan

Canonical milestone: `RB-017`. Implement only this revised synthetic/shadow
closeout plan over frozen RB-016/RB-015 artifacts; preserve all M5 and privacy
boundaries.

1. Lock the exact two-key input schema, holdout fold/alias/decision-record
   constraints, report nested schemas/constants, fixed shown/unresolved lists,
   permanent inconclusive terminal, and canonical digest rules.
2. Implement strict holdout fixture validation and canonical replay through
   RB-015; retain only holdout aggregate and fixture digests.
3. Implement closeout report construction over a verified RB-016 package and
   holdout aggregate, cross-checking package/aggregate/projection/source/
   attestation digests and rejecting raw/private/M5/live fields.
4. Implement `closeout` and `verify-closeout` stdin-only CLI stages. Verify must
   recompute from package+fixture and optionally compare a supplied report;
   duplicate keys and malformed inputs use fixed exit code 2/errors.
5. Add tests for fold/alias/decision-record tampering, package/projection/source
   and aggregate digest mismatches, exact nested report fields/literals,
   duplicate keys, private/M5/live values, optional report comparison,
   canonical-equivalent JSON, deterministic subprocess runs, privacy, compile,
   and M5 isolation.
6. Run focused/full/privacy/compile/diff checks and two report hashes. Obtain
   independent review, remediate every P0-P3, obtain a fresh re-review, update
   durable state, stage only RB-017 artifacts, commit with `RB-017:` prefix,
   and push its branch.

Acceptance: a separate process can recompute and verify a redacted,
deterministic shadow closeout report that states exactly what was shown and
unresolved, without making a historical profitability or M5/live claim.
