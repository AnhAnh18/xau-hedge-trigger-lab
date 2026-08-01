# RETRO-001: 2026-07-31 One-Leg Hedge Case

Status: owner-authorized; source receipt accepted; ready for descriptive
analysis.

## Purpose

Reconstruct the owner-authorized 2026-07-31 one-leg hedge interval to decide
whether the observed sequence is compatible with an automated state-dependent
rotation.  This is a case study, not a strategy change or a claim that the
bot was or was not manually operated.

## Lane boundary

This work belongs exclusively to the RETRO lane.  It must not modify an M5
contract, preregistration, manifest, model, threshold, feature, evaluation,
or verdict.  The registered 2026-08-03 through 2026-08-07 M5 block remains
outcome-blind until its structural intake passes.

## Authorization record

The owner authorized bounded RETRO parsing in the current task on 2026-08-01.
The governing policy amendment is recorded in `AGENTS.md`; this contract and
the accepted source receipt define the exact case scope.  No raw rows or
detailed timelines may be printed or committed, and this case remains outside
all M5 input manifests.

## Approved case scope

Use only these source objects, identified by generated aliases and hashes in
the RETRO-001 source receipt:

- one July 2026 MT5 report export, filtered to server date 2026-07-31; and
- one XAUUSD tick export spanning 2026-07-25 through 2026-08-01, streamed and
  filtered to the bounded case window below.

The first pass excludes terminal and MQL journals.  A journal can be added
only through a new authorization/receipt that names its exact alias, recorded
time window, retrieval reason, credential preflight, and retention.  Do not
open older reports or unrelated tick exports.  A later expansion is a separate
RETRO contract.

## Deterministic inspection window

All event/tick reconstruction is in recorded server time (UTC+3 for this
window):

- primary incident window: 2026-07-31 16:00:00.000 through 17:21:00.000;
- target interval: the unique `ONE_BUY` interval in that window that starts
  with `UNLOCK_TO_BUY`, ends with `REHEDGE_SELL`, and lasts at least 300
  seconds;
- same-report comparator: one-leg intervals whose close, re-hedge, and next
  rotation action all fall on server date 2026-07-31; and
- no journal window is authorized in this version.

## Questions

1. What is the exact observable sequence from the prior Sell close, through
   the Buy-only drawdown and recovery, to the next Sell and Buy actions?
2. Is the missing immediate hedge and lack of continuation Sell consistent
   with the same observable rotation behavior seen elsewhere in this report?
3. Does the available evidence distinguish an automated state-dependent rule
   from manual intervention?  Absence of a journal indicator is not evidence
   of either explanation.

## Method and safeguards

1. Verify the selected source objects against their archive manifests before
   parsing them.
2. Build the event/tick timeline in memory, confined to the case window.  If
   an intermediate artifact is needed, write only aggregate, anonymized
   counts under verified-ignored `reports/private/retro-001/`; never persist
   raw rows, prices, timestamps, tickets, or a detailed event/tick timeline.
3. Compare the case with only same-report one-leg intervals using descriptive
   counts and sequences, never fitted rules, optimized thresholds, or
   profitability metrics.
4. Publish a privacy-safe tracked result note containing only conclusion
   labels, aggregate counts, limitations, and source-receipt manifest hashes.
   Do not commit timestamps, prices, ticket IDs, event sequences, raw rows,
   credentials, private paths, or detailed trade exports.

## Acceptance criteria

- Every input is hash-verified and remains outside M5 input manifests.
- The result labels each conclusion as observed, compatible, or unresolved.
- The result makes no causal, profitability, tradeable-edge, or ownership
  claim.
- `git diff` shows no M5 code, data contract, preregistration, or frozen
  artifact change attributable to RETRO-001.

## Follow-up rule

Only after an independent review of this case workflow may a new RETRO
contract expand analysis to older monthly history.  M5 proceeds separately
when the registered August block and covering report are available.
