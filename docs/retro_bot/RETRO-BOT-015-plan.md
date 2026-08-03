# RETRO-BOT-015 Implementation Plan

Canonical milestone: RB-019. Implement only the typed/redacted variable-lot
paper bot defined by `RETRO-BOT-015-contract.md`.

1. Freeze the revised contract before implementation: owner authorization,
   exact ordered schemas, the scenario cost fingerprint, the consolidated
   fixed8 parser and bounds, quote ordering, unique `cycle_id` rule,
   transition table, per-leg conservation semantics, initial/event cost
   formulas, golden accounting vector, aggregate population rules, firewall,
   and CLI error/digest framing.
2. Obtain an independent plan critique in a new session. The critic must
   identify missing requirements, risks, alternatives, acceptance criteria,
   and tests, and begin with `RECOMMENDED_IMPLEMENTATION_PROFILE: build` or
   `RECOMMENDED_IMPLEMENTATION_PROFILE: complex`. A plan reviser must write
   the complete actionable revision to the requested run-artifact path. No
   source or test implementation begins until the revised plan is accepted.
3. Implement an in-memory Decimal-based replay engine. Validate the scenario
   fingerprint, exact fixed8 bounds, required initial quote, chronology,
   unique cycle ids, state transitions, per-leg quantity matching, quantity
   conservation, Bid/Ask execution, terminal marking, initial/event costs,
   invalid-cycle accounting, quantity min/max/traded totals, and redacted
   loss/flat/gain bands. Keep semantic-invalid details out of memory after
   counting them.
4. Add stdin-only `scripts/run_retro_bot_019.py` `replay` and
   `verify-aggregate` stages; preserve `scripts/run_retro_bot_015.py`
   unchanged. Enforce duplicate-key rejection, finite/trailing-byte checks,
   six-key verify framing, scenario-fingerprint validation, no input echo,
   and deterministic canonical JSON.
5. Add tests for uneven HEDGED and one-leg quantities, quantity changes on
   OPEN events, the explicit golden accounting vector (including exact cash,
   mark, P/L, and traded quantity), scenario-cost/fingerprint tampering,
   duplicate `cycle_id` rejection, partial/invalid quantities, transition
   tampering, lookahead, cost scaling, exact Decimal/fixed8 output,
   malformed-vs-invalid behavior, privacy/M5 firewall, deterministic
   subprocess runs, exact six-key verification shape, duplicate/nonfinite/
   trailing input, actual-history/source-path rejection with no side effects,
   and exact CLI errors.
6. Run an independent code review in a new session after implementation. The
   reviewer never edits files and reports concrete P0-P3 findings. Remediate
   every confirmed finding in scope, add or adjust tests as needed, and obtain
   a fresh independent re-review using the same review profile.
7. Run focused RB-019 tests, the isolated full suite, privacy scan,
   `compileall`, `git diff --check`, and two deterministic subprocess
   aggregate runs from one fixed synthetic fixture. Record both output
   digests and verify the aggregate in a separate process.
8. Execute durable state recorder task T-049 only after the fresh re-review
   verdict is PASS and all validation succeeds. Update only
   `.local_ai/STATUS.md`, `.local_ai/TASKS.md`, and `.local_ai/SESSION_LOG.md`
   from the completed plan, implementation, review, and validation artifacts;
   do not alter preregistrations, frozen artifacts, raw data, or source code.
9. Stage only the RB-019 implementation, tests, contract/plan, and T-049
   state-record artifacts. Commit with the `RB-019:` prefix on branch
   `codex/rb-019-variable-lot`, then push it.

Acceptance: a separate process can replay typed uneven lots with exact
quantity-aware accounting, prove the selected cost scenario by fingerprint,
verify its redacted aggregate using the exact six-key envelope, and remain
strictly outside raw data, M5, and live execution.
