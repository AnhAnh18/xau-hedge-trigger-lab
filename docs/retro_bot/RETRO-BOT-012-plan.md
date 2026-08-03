# RETRO-BOT-012 Implementation Plan

Canonical milestone: `RB-016`. Implement only this revised synthetic
packaging/freeze plan. Preserve the RB-015 projection, RB-014 paper accounting,
RB-013 fold/candidate freeze, RB-009 policy/oracle separation, and M5 firewall.

1. Lock the literal provenance constants, `RB016_PACKAGE_V1` manifest schema,
   insertion order, fixed-decimal cost list/fingerprints, canonicalizer,
   duplicate-key rejection, and self-digest preimages from the contract.
2. Implement `RB016_STATE_V1` serialization/parsing for the initial `all`
   slice state; require HEDGED/epoch-0/quantity-1.0/empty seen keys and embed
   the canonical snapshot so its digest is independently verifiable.
3. Implement package replay over the validated RB-015 typed fixture. Compute a
   canonical fixture digest in memory, validate the complete inherited RB-015
   aggregate/provenance, build the redacted receipt, and package artifact with
   non-cyclic nested self-digests. Reject raw/private/M5/live fields recursively.
4. Implement stdin-only `validate-config`, `package-replay`, and
   `verify-receipt` with exact exit codes, duplicate-key JSON loading, fixed
   non-sensitive errors, and no subprocess/network/MT5 surface.
5. Add `docs/retro_bot/RETRO-BOT-012-known-limitations.md` with the required
   synthetic-only, descriptive/no-selection, censoring/timezone/second-
   resolution, profitability, and no-live-execution sections.
6. Add tests for every manifest/aggregate/receipt/state field and digest,
   inherited RB-015 provenance/cost mismatch, fixture digest mismatch,
   duplicate keys, canonical-equivalent JSON, malformed/non-UTC/duplicate
   states, recursive privacy/M5/live firewall, CLI schemas/exit codes,
   cross-process deterministic output, and clean RB-015 isolation. Run focused,
   full, privacy, compileall, diff, and two CLI hash checks.
7. Obtain an independent code review; remediate every confirmed P0-P3 finding;
   obtain a fresh independent re-review; then update durable state, stage only
   RB-016 artifacts, commit with `RB-016:` prefix, and push the milestone branch.

Acceptance: identical valid typed RB-015 input yields one versioned, redacted,
self-hashed package artifact that a separate process verifies byte-for-byte,
while no raw data, live execution, or M5 coupling is introduced.
