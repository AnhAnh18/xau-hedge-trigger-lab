# RETRO-007: Historical Concurrent-Position Screening

Status: owner-authorized aggregate-only descriptive case, opened 2026-08-03.

## Question

Determine whether the retained XAUUSD history ever contains more than one
active Buy and one active Sell at the same time, with special reporting for
Monday server dates and fixed temporal quote gaps. This case tests an
observational possibility only; it does not infer a trigger, profitability,
manual intervention, or broker ownership.

## Authorization and source boundary

The owner authorized this case in the current task on 2026-08-03. Retention is
until project close or earlier owner revocation. The exact source set is the
accepted RETRO-003 source receipt:

- nine report aliases `report-001.html` through `report-009.html`;
- the exact 39 tick aliases listed in the accepted RETRO-003 receipt;
- report manifest digest
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`;
- tick manifest digest
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`.

The deterministic server-date population is inclusive `2025-11-01` through
`2026-07-30`; `2026-07-31` remains covered only by RETRO-001/002 and the
2026-08-03 observation is outside this case. Only the quarantine paths pinned
by the parent receipt may be opened. No journal, terminal log, support cache,
screenshot, M1 object, XLSX/PNG companion, credential, or opaque history cache
is in scope.

## Definitions

- A position interval is `[open_time, close_time)` for a closed position. An
  open-ended snapshot is right-censored at the population end and is reported
  separately; it is never silently treated as a complete interval.
- Position rows are deduplicated by `position_id` across monthly reports. Any
  conflicting duplicate is counted as a source conflict and excluded from
  concurrency claims.
- `max_total_active`, `max_buy_active`, and `max_sell_active` count distinct
  position rows with positive-duration overlap. A count above two is definite
  only when the overlap has positive duration; same-second open/close ordering
  is reported as possible/ambiguous, never definite.
- Monday means the report/server date has `weekday() == 0`.
- A temporal quote gap is a consecutive valid UTC tick gap strictly greater
  than 60 seconds. A weekend-opening candidate is a temporal gap whose UTC
  start is Friday and UTC end is Saturday/Sunday, with the mapped local gap
  end falling on Monday under UTC+2/UTC+3. No price jump is called a gap in
  this case.
- `multi_position_gap_windows` counts only positive-duration `>2` overlap
  after clipping position intervals to the gap plus a fixed 120-second
  post-gap window, reported per clock mapping. It is separate from boundary
  proximity and does not claim that the gap caused the overlap.

## Allowed output

Only aggregate counts and fixed bands may be retained: source digests,
coverage/status, report/tick counts, dedup/conflict/censor counts,
`max_total_active`, `max_buy_active`, `max_sell_active`, definite and possible
multi-position episode counts, Monday/non-Monday buckets, gap classification
buckets, `raw_rows_printed=false`, an explicit M5 firewall token, and a
self-digest. Raw rows, timestamps, prices, volumes, comments, ticket/order
identifiers, private paths, credentials, and detailed timelines must not be
printed or committed. The result remains outside every M5 input manifest.

## Stop conditions

Stop on a missing or hash-mismatched source, source expansion, journal/cache
access, ambiguous schema that cannot be fail-closed, raw-output leak, or any
request to use the result for fitting, tuning, model selection, profitability,
M5 evaluation, or live/demo execution. A new source, time window, or price-gap
definition requires a new authorization and receipt.
