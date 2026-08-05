# RETRO-BOT-007 Implementation Plan

## Objective

Implement the locked RB-011 unlock/close candidate engine as a pure offline
layer over RB-009 and RB-010. Preserve autonomous/oracle separation and emit
aggregate-only, reproducible diagnostics.

## Planned artifacts

- `src/xau_trigger/retro_bot_007.py`: immutable candidate policy/config,
  eligibility gate, rule evaluation adapter, one-action-per-tick reducer,
  oracle benchmark comparator, timing-band/minimum-support gates, aggregate
  schema/digest validation, and M5-firewall attestation.
- `tests/test_retro_bot_007.py`: synthetic causal, lifecycle, benchmark,
  privacy, and determinism coverage listed in the contract.
- `scripts/run_retro_bot_007.py`: offline CLI accepting only verified
  synthetic/registered manifests, writing a redacted aggregate to an ignored
  run root; never opening MT5, credentials, journals, `.ex5`, or raw paths.

## Implementation sequence

1. Re-read RB-008 through RB-010 contracts and import only their public,
   validated APIs. Define immutable enums/dataclasses for mode, candidate
   outcome, policy id, and anonymized oracle label.
2. Implement eligibility and chronology checks with required `state_epoch`.
   Report stale epochs as `invalid_transition`; classify terminal, one-leg, and
   censored states as distinct noneligible outcomes. Reject future, duplicate,
   same-second, and non-increasing inputs without mutating state. Delegate
   legal action mapping to RB-009.
3. Implement deterministic policy evaluation over a frozen tuple of RB-010
   rules. Enforce ascending rule-id tie resolution, exactly one legal HEDGED
   close action, finite feature handling, and at most one emitted action per
   tick. Any malformed policy or rule fails the whole policy closed as
   `invalid_transition`; it is never partially evaluated.
4. Implement oracle-diagnostic comparison as a separate pure function. Match
   each action to the earliest unused label in the same anonymized cycle using
   the first applicable inclusive timing band; never reuse labels and count
   unmatched actions/labels and direction mismatches. Prove changing labels
   leaves autonomous output/digest unchanged.
5. Implement the locked `always_hold` and `first_legal_match` policy manifest;
   require one accepted action per direction for support. Report exploratory,
   non-blocking coverage/timing gates. Enforce the exact aggregate allowlist,
   anonymized case-id pattern, inherited RB-008 digests, and literal
   `M5_FIREWALL_ATTESTATION_V1`; reject paths, raw-field names, credentials,
   and non-allowlisted output values.
6. Add the offline CLI and deterministic JSON writer. Run it twice on
   synthetic fixtures and assert byte-identical output; keep all run output
   under ignored RETRO directories.

## Verification commands and gates

Run, in order:

```text
uv run --offline pytest tests/test_retro_bot_007.py --basetemp .pytest-rb011-focused -q
uv run --offline pytest --basetemp .pytest-rb011-full -q
uv run --offline python scripts/check_privacy.py
uv run --offline python -m compileall -q src/xau_trigger
git diff --check
```

Before implementation, obtain an independent plan critique and have the
reviser write this actionable plan. After implementation, obtain an
independent code review in a separate session; fix every confirmed P0-P3
finding, then run a fresh independent re-review. Mark T-041 complete and
record state only after a PASS verdict and all gates succeed. Commit only the
RB-011 artifacts with message `retro-bot: add unlock close candidate engine`.

## Non-goals and stop conditions

Do not fit on holdout, inspect future M5 data, optimize paper P/L, add a live
EA/MT5 surface, read credentials or raw rows, or modify M5 code/manifests.
Stop and report a blocker if source receipts are unavailable, a required
owner decision expands scope, or any privacy/firewall/lookahead/state-safety
gate fails.
