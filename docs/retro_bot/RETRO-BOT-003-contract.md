# RETRO-BOT-003: Sequential Multi-Cycle Paper Wrapper

Status: owner-authorized RETRO follow-on; descriptive only and outside M5.

This lane wraps the locked RETRO-BOT-002 paper outcomes over a chronological
sequence of eligible one-sided intervals. It reuses the RB-001 configuration,
source receipts, clock scenarios, and fixed policies without adding sources,
`.ex5` access, August M5 data, journals, live APIs, fitting, or policy
selection.

Cycles are consumed in caller-provided chronological order. A non-increasing
unlock order, a non-positive interval, or a cycle whose unlock overlaps the
preceding observed re-hedge is fail-closed: it is counted as invalid or overlap
and cannot contribute an action, mark, or return band. No sorting or lookahead
repairs malformed order.

The tracked result is an aggregate only. Each clock/policy row reports total,
eligible, action, marked, censored, overlap, and invalid-order counts plus
loss/flat/gain bands. Raw identifiers, timestamps, prices, tickets, paths,
traces, and account fields are never retained or printed. All registered
clock/policy rows are shown side by side; no winner or profitability claim is
permitted.

Acceptance requires synthetic tests for chronological preservation, overlap
and invalid-order exclusion, RB-006 status accounting, digest/schema/config/
source/privacy rejection, deterministic aggregation, CLI containment, and the
M5 firewall. Historical raw replay is a separate owner-authorized action.
