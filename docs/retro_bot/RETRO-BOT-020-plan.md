# RETRO-BOT-020 Plan

Status: draft pending independent critique and owner authorization.

## Work packages

1. Lock the RB-020 contract, source receipt, authorization, claim limits, and
   M5 firewall before any historical parsing.
2. Build synthetic causal fixtures for bootstrap, lifecycle transitions,
   missing ticks, ambiguous timestamps, observed-label isolation, and
   Bid/Ask paper accounting.
3. Implement separate autonomous and oracle-diagnostic APIs. Add guards that
   make oracle fields unavailable to autonomous feature/state/action code.
4. Freeze a small candidate vocabulary covering state age, price increments,
   excursions, quote side/spread, tick gaps/rate, session context, and
   autonomous position-side context. Do not tune on holdout outcomes.
5. Add chronological walk-forward evaluation with hold/action/censor,
   direction/timing, duplicate-action, state-safety, coverage, and support
   metrics. Keep accounting as a downstream diagnostic only.
6. Run the authorized archive twice, validate redacted schema and deterministic
   digests, then produce the result and closeout receipt.

## Stop conditions

Stop for missing authorization, source/hash/path mismatch, M5 contamination,
lookahead, oracle leakage, insufficient bootstrap coverage, privacy exposure,
nondeterminism, unsupported claims, or any request for live/demo execution.

## Review workflow

An independent plan critic must assess this plan and begin with
`RECOMMENDED_IMPLEMENTATION_PROFILE: build` or `complex`. A plan reviser must
write the complete actionable plan before implementation. Implementation and
fixes receive separate independent review sessions and a fresh re-review.
