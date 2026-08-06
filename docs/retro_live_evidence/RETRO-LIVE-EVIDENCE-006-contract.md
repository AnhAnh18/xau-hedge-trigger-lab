# RETRO-LIVE-EVIDENCE-006 Contract

Status: synthetic safety/governance scaffold only. E-001 does not authorize a
broker connector, transport, execution adapter, demo, canary, or live order.

The milestone verifies a fail-closed readiness envelope and an offline
`SafetyAdapterSimulator`. The simulator exercises frozen limits, intent
idempotency, monotonic operator stop, simulated flatten, and reconnect
recovery. It has zero transport calls and cannot emit a broker request.

The synthetic lane always returns `hold-synthetic-only`, even when every
caller-provided flag is true. A real demo/canary decision requires a separate
owner authorization, independently retained E-002 through E-005 receipts,
trusted component digests, and a new implementation/review; this scaffold
cannot produce that decision.
