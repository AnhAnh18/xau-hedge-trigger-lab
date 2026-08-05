# RETRO-HIST-004 Contract

Status: owner-authorized on 2026-08-05 for a bounded observed-lot paper
accounting milestone. This contract inherits RH-002 sources and does not
authorize source expansion, M5 use, model selection, or live execution.

## Objective and boundary

Compose the RH-003 causal policy stream with a separate typed Bid/Ask paper
accounting reducer. Preserve observed quantities exactly, support uneven and
partial legs, and report only aggregate descriptive evidence. The inherited
archive bootstrap is `FLAT` and RH-003 emitted no policy actions; the historical
result must therefore report `FLAT`/`no_action` rather than inventing cycles.
Actionful and uneven cycles used in tests are synthetic and are never claimed
as historical observations.

Only the RH-002 accepted report positions/open_positions fields and tick
columns may be read. Deals, commissions, fees, swaps, profits, journals,
caches, credentials, terminal files, `.ex5`, August M5 data, and live/demo
surfaces are forbidden. Synthetic fees, slippage, latency, and margin reserve
parameters are descriptive scenarios, not broker-cost claims.

## Inherited source receipt

The exact RH-002 receipt, manifests, aliases, opaque run labels, quarantine
root, and population `[2025-11-01 00:00:00, 2026-07-31 00:00:00)` are pinned in
`RETRO-HIST-004-source-receipt.md`. Every object and path is verified before
source access. Any digest, alias, path, or authorization mismatch fails closed.

## Numeric and inventory rules

- All prices, quantities, costs, and latency values use `Decimal`; binary
  floats are forbidden. Quantities are positive fixed8 strings and preserve
  observed scale without normalization.
- Quote validation requires finite positive `Bid <= Ask`; invalid or crossed
  quotes cannot execute or mark inventory.
- Buy and Sell inventories are separate. Every leg satisfies
  `opened = closed + ending + censored` in exact fixed8 units.
- A close cannot exceed active inventory. Invalid ordering, negative inventory,
  ambiguous partial close, or conservation failure is counted/censored without
  partial ledger mutation; aggregate conservation failure rejects the run.
- Currency conversion and contract multiplier are not authorized. Results use
  normalized price-unit accounting and must not be described as broker cash P/L.
  Realized flow, unrealized marking, costs, and margin reserve remain separate.

## Execution and marking

For action decision time `t`, latency `L`, and slippage `S` points, select the
first valid quote with timestamp `>= t + L` within the fixed execution horizon.
The equality boundary is included; a missing quote is `unsupported`/censored and
never falls back to an earlier quote.

- Buy open: `-(Ask + S * point) * quantity`.
- Buy close: `+(Bid - S * point) * quantity`.
- Sell open: `+(Bid - S * point) * quantity`.
- Sell close: `-(Ask + S * point) * quantity`.

Fees use a predeclared non-negative per-unit parameter and subtract from cash
on each initial/event fill. Margin is a separately reported reserve; a scenario
may not silently treat reserve as P/L. Remaining Buy inventory is marked at Bid
and remaining Sell inventory at Ask using the last valid quote at or before the
mark time. Missing, stale, invalid, or out-of-envelope marks are censored with
zero fabricated proceeds. Accounting never feeds back into policy state,
features, action quantities, or oracle matching.

## Frozen scenarios

The scenario matrix is fixed before replay and serialized by fingerprints:

1. `zero_cost`: fee `0.00000000`, slippage `0.00000000`, latency `0` ns,
   margin reserve `0.00000000`.
2. `fixed_fee`: fee `0.10000000` per unit, zero slippage, zero latency, zero
   reserve.
3. `per_lot_fee`: fee `0.25000000` per unit, zero slippage, zero latency, zero
   reserve.
4. `spread_slippage`: fee `0.00000000`, slippage `2.00000000` points, zero
   latency, zero reserve.
5. `latency_slippage`: fee `0.00000000`, slippage `1.00000000` point, latency
   `6000000000` ns, zero reserve.

All scenarios run side-by-side. No scenario may select, rank, tune, or alter a
policy candidate. Fingerprints use compact canonical JSON with insertion order,
`ensure_ascii=true`, and no trailing newline.

## Policy/accounting isolation

The accounting reducer consumes immutable RH-003 policy decisions and typed
quotes only. Observed future labels/lots are never used to synthesize actions
or sizes. Mutation tests must prove that changing accounting scenarios,
oracle labels, or future quantities leaves policy state, action records, and
policy action digests byte-identical.

## Redacted aggregate

The canonical aggregate has exactly these top-level keys, in order:

`schema_version`, `case_id`, `source_validation`, `report_manifest_sha256`,
`tick_manifest_sha256`, `contract_sha256`, `source_receipt_sha256`,
`population`, `scenario_ids`, `bootstrap_state`,
`state_counts`, `action_counts`, `accounting_counts`, `quantity_bands`,
`latency_bands`, `cost_fingerprints`, `conservation`,
`policy_action_digests`, `accounting_digests`, `m5_firewall`, `claims`,
`aggregate_sha256`.

The contract and source-receipt digests are pinned before source access and
must match the accepted RH-004 governance artifacts byte-for-byte.

Claims are strict false booleans: `oracle_used_for_policy`, `raw_rows_printed`,
`pnl_or_model_selection`, and `live_execution`. The firewall attestation is
exactly `M5_FIREWALL_ATTESTATION_V1`. Reject unknown keys, duplicate keys,
non-finite values, raw identifiers, timestamps, prices, tickets, paths,
credentials, and detailed timelines. Output contains no raw rows and is never
added to an M5 input manifest.

## Gates

Synthetic tests cover Decimal/fixed8 parsing, four Bid/Ask signs, uneven and
partial legs, conservation and invalid transitions, latency boundaries and
no-quote censoring, duplicate/crossed/gapped quotes, conservative marking,
all scenario fingerprints, policy/accounting/oracle isolation, schema/digest/
privacy/firewall/path tampering, and the historical `FLAT`/`no_action` result.
Run focused and full tests, compileall, privacy/firewall checks, `git diff
--check`, and two fresh full archive runs. Their aggregate bytes, scenario
fingerprints, policy digests, and accounting digests must match exactly.
Independent review and fresh re-review must both return `VERDICT: PASS` before
commit/push with prefix `retro-hist-004:`.
