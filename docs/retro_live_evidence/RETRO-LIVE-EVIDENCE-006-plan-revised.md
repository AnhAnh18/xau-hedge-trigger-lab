# RETRO-LIVE-EVIDENCE-006 Revised Plan

1. Freeze the E-001 gate digest and a redacted E-002/E-003/E-004/E-005 digest
   envelope; reject missing or malformed prerequisites.
2. Implement only an in-memory safety simulator: fixed8 lot limits, action
   bounds, idempotent intent receipts, stop latch, one simulated flatten, and
   operator-acknowledged monotonic reconnect recovery.
3. Provide a stdin-only readiness evaluator that derives
   `hold-synthetic-only` and never emits `demo-ready`, `canary-ready`, or live
   suitability.
4. Add schema/tamper/privacy/M5/firewall tests, deterministic CLI checks,
   compileall, full regression, independent review, remediation, and re-review.
5. Record the real blocker: actionful source capture and real shadow evidence
   need a new owner authorization and source receipts.
