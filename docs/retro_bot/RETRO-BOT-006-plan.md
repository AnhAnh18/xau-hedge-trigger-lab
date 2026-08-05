# RETRO-BOT-006 Implementation Plan

Status: revised and approved after independent plan critique; implementation
and independent code review complete.

1. Add immutable feature snapshot and DSL rule dataclasses with the strict
   allowlist, exact numeric grid `{0,1,5,10,60,300,900,3600}`, categorical
   domains, parameterless `always`/`never`, inclusive `between`, three-clause
   AND limits, and deterministic rule-id ties.
2. Implement the pinned causal feature mathematics (latest valid tick at or
   before `t-60s` anchor and side-signed excursion) and validation: all feature
   timestamps must be at or before the decision tick; reject future, oracle,
   raw/private, duplicate/out-of-order, non-finite, and malformed fields.
3. Implement deterministic rule evaluation with explicit `hold`, mapped
   `candidate_action`, `feature_missing`, and `invalid_transition` outcomes;
   no implicit defaults or unrestricted composition.
4. Add configuration self-digest, immutability checks, privacy-safe aggregate
   validation, and M5 firewall assertions.
5. Add synthetic tests for every operator, boundary inclusivity, missing data,
   future-field rejection, oracle invariance, config tampering, and digest
   reproducibility.
6. Run focused/full tests, privacy, py_compile, diff checks, independent code
   review, remediation, fresh re-review, and commit only after PASS.
