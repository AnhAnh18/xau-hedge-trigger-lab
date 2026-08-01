# RETRO-BOT-001: Historical Behavioral Replay Prototype

Status: owner-authorized; planning and implementation permitted; not an M5
task.

## Purpose

Build a transparent Python replay prototype that tests a small, predeclared
set of re-hedge timing baselines against historical XAUUSD hedge-state
transitions. The prototype is a behavioral research tool, not a claim that
the original strategy's trigger, ownership, profitability, or tradeable edge
has been identified.

The owner authorized this separate RETRO-BOT lane in the current task on
2026-08-01. Retain its ignored derived artifacts until project close or an
earlier owner revocation.

## Scope and source receipt

The only raw inputs are the exact generated aliases accepted by
`RETRO-003-2025-11_to_2026-07-history-screening-receipt.md`:

- `report-001.html` through `report-009.html`, report-manifest digest
  `88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30`;
- the 39 `XAUUSD_ticks_<start>_to_<end>.csv` aliases listed in that receipt,
  tick-manifest digest
  `a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c`.

`RETRO-BOT-001-config.json` is the machine-readable lock for this contract.
Its canonical payload digest is
`32c65422bb774e0a9096884097dbd866a48d36be7d2bff346bd21ff98da8ca86`.
The implementation must verify that self-digest before accepting a run.

The fixed population is server time in the half-open interval
`[2025-11-01 00:00:00, 2026-07-31 00:00:00)`. July 31 is excluded because it
belongs to RETRO-001/002. A report or the final weekly tick object may contain
later rows, but the adapter must discard them before any replay or aggregate
calculation; no interval may cross the upper bound. The registered August M5
primary block `2026-08-03..2026-08-07` and fallback block
`2026-08-10..2026-08-14` are excluded and must remain outcome-blind.
XLSX/PNG companions, M1 bars, journals, terminal logs, support caches,
screenshots, account details, and the pre-existing `.ex5` binary are out of
scope. In particular, this contract does not authorize inspecting,
decompiling, executing, or copying that binary.

Source files may be parsed in memory only after their accepted manifest,
alias, suffix, path containment, and SHA-256 have been verified. No raw rows,
prices, tickets, account identifiers, comments, credentials, private paths,
or detailed event traces may be printed or committed.

## Information firewall

RETRO-BOT is permanently outside M5. Its data, source receipts, derived
features, candidate policies, metrics, reports, and decisions must not appear
in M5 input manifests, feature builders, models, thresholds, external intake,
fallback authorization, evaluator, gate, preregistration, or verdict. It must
not inspect the August M5 blocks before their own blind intake succeeds.

The only permitted shared code is generic, outcome-free infrastructure such as
the canonical report parser and state reconstruction. RETRO-BOT additions must
live under `retro_bot` names and must have an executable regression check that
M5 frozen artifacts do not reference the lane.

The protected-artifact inventory is
`RETRO-BOT-001-firewall-inventory.json`. Its canonical list digest pins the
exact files scanned; the registered digest is
`34628d77374130ab8aa47aa00d5c1b4dfda8aac53bd9bb19e3b98ad5c9a4ec03`.
For every listed UTF-8 file, the regression check rejects case-insensitive
occurrences of `retro-bot`, `retro_bot`, or `retrobot`.
The check guards the firewall; it does not rewrite, rehash, or otherwise take
ownership of M5's separately managed files.

## Predeclared v1 experiment

V1 addresses only the one-sided re-hedge transition after an *observed*,
deterministically reconstructed unlock. It does not attempt to predict the
unlock/close event, manage a live position, size orders, or optimize P/L.

For each eligible `ONE_BUY` or `ONE_SELL` interval, the candidate action is
the opposite side at the first available tick at or after the fixed delay from
the observed unlock. The complete, fixed policy set is:

| Policy id | Delay |
| --- | ---: |
| `first_available_tick` | 0 seconds |
| `wait_300_seconds` | 300 seconds |
| `wait_900_seconds` | 900 seconds |
| `wait_3600_seconds` | 3,600 seconds |

No price, spread, P/L, drawdown, comment, or future event chooses a policy or
changes a delay. All policies are reported side by side; v1 does not name a
winner or promote one to M5.

The fixed clock scenarios are `utc_plus_2`, `utc_plus_3`, and
`eu_dst_2025_2026`. The first two apply their named offset at every UTC
instant. The EET/EEST-style hypothesis has this exact mapping:

| UTC interval | Server offset |
| --- | ---: |
| before 2025-03-30 01:00:00 | UTC+2 |
| 2025-03-30 01:00:00 through before 2025-10-26 01:00:00 | UTC+3 |
| 2025-10-26 01:00:00 through before 2026-03-29 01:00:00 | UTC+2 |
| 2026-03-29 01:00:00 through before 2026-10-25 01:00:00 | UTC+3 |
| 2026-10-25 01:00:00 and later | UTC+2 |

It is not an accepted broker-time conclusion. For fixed clocks, a report
server timestamp maps uniquely to UTC by subtracting the fixed offset. For
the piecewise scenario, the inverse mapper enumerates UTC candidates from the
segments. If a report boundary or policy target maps to zero UTC instants
(spring gap) or multiple instants (fall-back fold), the entire interval is
`excluded_clock_unresolved` for that scenario; it emits no action and no
arbitrary fold is chosen. Each scenario is reported independently; no scenario
is selected from historical outcomes.

## Eligibility, censoring, and metrics

An interval enters every policy/clock denominator only if, after filtering to
`symbol == XAUUSD`, it meets all of the following fixed conditions:

- its complete server-time extent is inside the population interval;
- it is `ONE_BUY` or `ONE_SELL`, lasts at least 300 seconds, and may cross
  midnight;
- its preceding event is respectively `UNLOCK_TO_BUY` or `UNLOCK_TO_SELL` and
  its following event is respectively `REHEDGE_SELL` or `REHEDGE_BUY`;
- both boundary events have deterministic ordering;
- the filtered report has no lifecycle exception; and
- no state-reconstruction exception has a timestamp in the closed interval
  from the unlock through the following re-hedge.

For a policy delay `d`, its target time is `unlock_time + d`. The streaming
accessor considers valid ticks only in `[target_time, observed_rehedge_time)`;
a valid tick has a parseable UTC timestamp, positive Bid/Ask, and `ask >= bid`.
The first such tick is the only emitted conceptual action. If the target is at
or after the observed re-hedge, retain no action and count
`right_censored_delay_not_reached`. If the target precedes the observed
re-hedge but no valid tick occurs before it, retain no action and count
`right_censored_no_valid_tick`. A tick at the report-second re-hedge boundary
or later is always censored, never an action. The observed following re-hedge
is used only to classify the policy result, not to change the policy delay.

For emitted actions, `lead_seconds = observed_rehedge_time - action_time` and
the only timing bands are `0_to_under_60_seconds`,
`60_to_under_300_seconds`, `300_to_under_900_seconds`,
`900_to_under_3600_seconds`, and `at_least_3600_seconds`. Direction matching
is an invariant, not a fitted metric: `ONE_BUY` emits a conceptual sell and
`ONE_SELL` emits a conceptual buy. Aggregate outputs report the eligible,
emitted, and each censored count plus these lead-time bands for every policy
and clock scenario.

## Retained outputs and claims

Only deterministic aggregate outputs are retained: source-manifest digests,
clock/policy ids, counts, coverage categories, direction-match counts,
timing-error bands, and a digest of the canonical aggregate payload. A result
may label a fact as **observed**, **compatible**, or **unresolved**. An
independent reviewer may read a named ignored aggregate payload only after the
privacy-schema validator accepts it; that exception never permits access to
quarantine sources, raw rows, detailed traces, or any other ignored file.

The following remain prohibited claims: the actual bot trigger, manual action,
broker timezone, profitability, ownership, a tradeable edge, or safe live
execution. V1 produces neither an MQL5 EA nor any order sent to MT5.

## Acceptance and stop conditions

- Every raw source fails closed on manifest/hash/schema/path/suffix mismatch,
  `.partial` status, or quarantine escape.
- Synthetic tests cover cross-midnight intervals, all three clock scenarios,
  spring gaps, fall-back folds, tick gaps, no-lookahead action timing, policy
  immutability, and aggregate reproducibility.
- Privacy tests reject raw-like fields in retained outputs and M5 firewall
  tests reject every RETRO-BOT reference in frozen M5 artifacts.
- Two identical synthetic runs yield byte-identical aggregate payloads.
- A fresh independent review reports no P0/P1 finding before closeout.

Stop immediately if a required source cannot be verified, an M5 firewall
check fails, derived output would expose private/raw content, or the requested
work would require binary execution, live trading, a journal, or a new data
source. Each such expansion needs a new owner decision and contract.
