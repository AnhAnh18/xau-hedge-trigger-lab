# RETRO-BOT-010 Implementation Plan

Canonical milestone: `RB-014`. Implement only the revised plan below; do not
expand the source boundary or alter M5 artifacts.

1. Add immutable source attestation, `PaperScenario`, quote/action/cycle
   records, and strict validators for quantity, fee/slippage/latency/margin
   units/bounds, fixed decimal serialization, source receipt, unit/cycle
   identity, chronology, and privacy allowlists.
2. Implement one-cycle accounting that recomputes RB-011/RB-012 actions from
   causal snapshots (or verifies an action digest), composes the RB-013 causal
   window and RB-009 transition authority, applies locked Bid/Ask sides and
   explicit cost formulas, and marks remaining positions conservatively.
   Missing/duplicate/out-of-order quotes censor the cycle instead of repairing
   or sorting it; implement the declared status precedence.
3. Implement chronological multi-cycle aggregation over the complete RB-013
   fold/clock/bootstrap/candidate matrix. Enforce canonical row sorting,
   unique unit/cycle ids, immutable scenario fingerprints, receipt attestation,
   reject incomplete cells, mixed scenarios, illegal transitions, and
   non-finite values, and keep P/L out of all gate/selection fields.
4. Add canonical redacted aggregate writer/verifier with fixed key order,
   inherited source digests, `M5_FIREWALL_ATTESTATION_V1`, self-digest,
   bounded counts/bands, and explicit accounting conservation.
5. Add offline CLI stages `validate-config`, `paper-replay`, and
   `verify-aggregate` over a pinned typed synthetic fixture transport. The
   replay input must contain typed cycles (state, actions, quotes, causal
   snapshots, decision records, and cutoff) plus the frozen candidate manifest;
   source paths, raw exports, precomputed result rows, unknown/private keys,
   and raw error values are rejected.
6. Add synthetic tests for full multi-action lifecycle and all quote-side
   conventions, conservative marks, cost formulas/bounds/rounding/latency,
   censor precedence, duplicate/lookahead/action-injection rejection,
   receipt/unit/matrix/scenario tampering, P/L mutation without gate/status
   changes, deterministic reruns, privacy, and M5 isolation.
7. Run focused RB-014/RB-013/RB-006/RB-007 tests, full suite, privacy,
   compileall, diff check, and two byte-identical synthetic runs. Obtain a
   fresh independent code review, remediate every P0-P3, and re-review.
8. Only after PASS update the RETRO state record, create/push the
   `codex/rb-014-paper-bot` milestone commit. Do not stage unrelated user or
   M5 state changes.

Acceptance: a deterministic offline paper-bot aggregate composes the locked
causal engines and accounting assumptions without source, privacy, or M5
contamination; no candidate is selected by paper return.
