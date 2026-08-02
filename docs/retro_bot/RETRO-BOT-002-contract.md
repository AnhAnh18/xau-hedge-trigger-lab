# RETRO-BOT-002: Bounded Paper-Backtest Harness

Status: owner-authorized RETRO follow-on; descriptive only and outside M5.

This lane reuses only the locked RETRO-BOT-001 configuration, receipt, four
fixed delays, three clock scenarios, and observed eligible one-sided intervals.
It excludes August M5 blocks, `.ex5`, journals, account data, live APIs,
fitting, model selection, and threshold changes.

At each target, the first valid tick before the observed re-hedge is a
conceptual opposite-side action. Quantity is fixed at `1.0`; buys execute at
ask and sells at bid. The synthetic position is marked at the first valid tick
at or after the observed re-hedge anchor: buys at bid and sells at ask.
Missing action or mark ticks are censored. No future event may choose a policy
or alter accounting assumptions.

Only a self-hashed aggregate is retained under ignored
`retro-bot-002/paper_runs`. It contains policy/clock counts, action and mark
coverage, and coarse loss/flat/gain bands. Raw rows, prices, timestamps,
interval identifiers, traces, tickets, account fields, and source paths are
never retained or printed. All rows are reported side by side; no winner,
profitability, ownership, or live-execution claim is permitted.

Acceptance requires synthetic tests for bid/ask semantics, no-lookahead,
censoring, accounting/count reconciliation, digest/schema tamper rejection,
deterministic reruns, and the M5 firewall. Any new source, `.ex5` access,
August access, or live API requirement stops the run and requires a new owner
decision.
