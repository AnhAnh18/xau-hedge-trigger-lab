# RETRO-003: 2025-11 to 2026-07 Historical Screening

Status: owner-authorized; source receipt accepted; aggregate screening
complete; independent review PASS.

## Purpose

Screen the retained monthly HTML reports against the accepted UTC tick archive to
select three independent descriptive cases without choosing dates by price,
drawdown, profit, or apparent bot outcome. This case only builds an aggregate
candidate inventory and selects the next RETRO cases; it does not fit a model
or make an M5 decision.

## Lane and authorization

This is a separately named RETRO case authorized by the owner in the current
task on 2026-08-01. Retention is until project close or earlier owner
revocation. Only the nine generated HTML report aliases copied into the
accepted RETRO-003 run and the 39 exact tick aliases listed in the accepted
receipt are in scope. Matching XLSX/PNG files are archival companions only and
are not parsed. No journal, terminal log, support cache, screenshot, M1
object, or opaque history cache is in scope.

RETRO-003 remains outside every M5 input manifest. Raw rows, detailed
timelines, credentials, and private paths must not be printed or committed.
Only aggregate, anonymized inventory and selection output may be retained.

## Fixed population and clock rule

The candidate population is server dates 2025-11-01 through 2026-07-30,
inclusive. 2026-07-31 is excluded because it is already covered by RETRO-001
and RETRO-002. Tick coverage is screened structurally from the accepted weekly
object ranges; historical server-clock conversion is not assumed at this
stage. Each selected case must resolve the registered clock candidates
`UTC+2` and `UTC+3` against its own report/tick window, or mark tick metrics
unresolved if neither is uniquely supported.

## Predeclared selection rule

For every date in the fixed population, reconstruct report state and test the
same structural predicate:

- an XAUUSD one-leg interval has a preceding `UNLOCK_TO_BUY` or
  `UNLOCK_TO_SELL` event;
- its following event is the opposite-side `REHEDGE` event;
- duration is at least 300 seconds;
- both boundaries are deterministic; and
- no lifecycle or state reconstruction exception is relevant to the interval.

No price, drawdown, P/L, profit, comment text, manual-intervention indicator,
or continuation outcome may enter eligibility or ranking.

Partition dates into three fixed strata: 2025-11 through 2026-01,
2026-02 through 2026-04, and 2026-05 through 2026-07. Select the earliest
eligible date in each stratum. Within a selected date choose the longest
qualifying interval, breaking ties by earliest server start. If a stratum has
no eligible date, select the earliest remaining eligible date from the next
stratum in chronological order and record the fallback explicitly.

## Output and follow-up

The screening output may retain only counts, coverage status, selected dates,
selected sides, duration bands, source manifest digests, and selection status.
Each selected date must receive a separate RETRO-004/005/006 contract,
source receipt, bounded time window, analyzer, and independent review before
its tick prices or case-specific aggregates are inspected. Journals or source
expansion require a new case-specific authorization and receipt.

RETRO-003 must not modify RETRO-001, RETRO-002, M5 contracts,
preregistrations, models, thresholds, evaluations, or gates.

## Acceptance criteria

- The nine HTML report objects are byte-preserving copied and hash-verified in a
  new ignored run with no `.partial` accepted.
- The accepted receipt lists every report alias/hash and every tick
  alias/hash used by the screening.
- Candidate eligibility and the three-stratum rule are applied identically to
  every date before any selected-case analysis.
- Only aggregate output is retained; no raw rows or detailed timeline is
  printed, committed, or added to M5.
- A fresh independent review reports no P0-P3 finding before RETRO-003 is
  marked complete.
