# RETRO-BOT-010: End-to-End Historical Paper Bot Contract

Canonical milestone: `RB-014`. This is an owner-authorized RETRO follow-on
to RB-013 on 2026-08-03. It is descriptive only and remains outside every M5
input, model, evaluation, threshold, and gate.

## Purpose and boundary

RB-014 composes the locked RB-009 lifecycle, RB-011 close engine, RB-012
one-leg re-hedge engine, RB-013 candidate/fold identity, RB-006 conservative
paper accounting, and RB-007 sequential chronology into one offline paper-bot
API/CLI. It tests whether a frozen causal action stream can be accounted for
under explicit assumptions. It does not identify the original bot, prove
profitability, authorize live execution, or call MT5.

Only validated in-memory records are accepted by the new layer. No raw paths,
CSV/XLSX/HTML exports, credentials, tickets, journals, `.ex5` files, private
source aliases, or M5 data may be opened or retained. Inputs are hash-verified
against the RB-008/RB-013 source receipt and an immutable attestation object
(`schema_version`, config digest, report/tick digests, firewall literal, and
fixture id); caller-supplied digests without this attestation fail closed.
Retained output is aggregate-only.

## Locked accounting

- quantity is exactly `1.0` per leg;
- initial hedge is Buy at Ask and Sell at Bid;
- closing a Buy uses Bid and closing a Sell uses Ask;
- opening a Sell uses Bid and opening a Buy uses Ask;
- remaining positions are conservatively marked Buy at Bid and Sell at Ask;
- default fee, slippage, latency, and margin assumptions are zero and are
  represented explicitly by an immutable scenario object;
- fee is charged once per unit transaction, slippage is in points and shifts
  execution by `0.01 * points`, latency selects the first quote at or after
  `decision_time + latency`, and margin is a terminal notional deduction;
- all scenario values are finite, non-negative, bounded, serialized in fixed
  decimal form, and never selected from outcomes or paper return.

Initial cash is `bid_0 - ask_0` for the one-buy/one-sell hedge, reduced by the
two initial transaction fees and the two initial slippage shifts. One-leg
starts apply the corresponding single entry fee and slippage shift. Close/open
cash flows use the side rules above, then remaining legs are marked at the final
valid quote after the last action. A missing latency quote is
`action_censored`; a missing terminal mark is `mark_censored`. Precedence is
`source_censored` (receipt/quote schema) > `invalid_transition` >
`action_censored` > `mark_censored` > `marked`.

The cycle identity is a redacted `(fold, clock, bootstrap, candidate, unit)`
tuple where `unit` is `^[A-Za-z0-9_-]{1,64}`; `cycle_id` is the SHA-256 of the
canonical joined identity and must be unique. The scenario carries a
SHA-256 fingerprint over all cost fields. Exactly one row is required for every RB-013
fold x clock x bootstrap x candidate cell; multiple report units are allowed
only with distinct unit ids. Duplicate units, cross-candidate ids, and mixed
scenarios fail closed. Each cycle consumes a strictly chronological quote
sequence and a recomputed policy action sequence. An action must have a quote
at or after its latency-adjusted decision time; a missing, duplicate,
out-of-order, or same-second quote censors the cycle.
The state reducer remains the authority for legal transitions and epoch
checks. No observed label can mutate state or accounting.

## Results and gates

Each cycle ends in exactly one status: `marked`, `mark_censored`,
`action_censored`, `invalid_transition`, or `source_censored`. It reports only
bounded counts, action/mark counts, loss/flat/gain bands, conservation flags,
scenario id, and inherited digests. P/L is a descriptive accounting field,
never a candidate ranking or selection statistic; mutating return values cannot
change terminal status or gate fields.

The aggregate contains the complete RB-013 fold x clock x bootstrap x
candidate matrix, with rows sorted by the locked fold/clock/bootstrap/
candidate order and joined only by locked identity. It verifies
that action count, mark count, terminal status, and return-band counts
conserve; all candidate rows are retained side by side. Any duplicate unit,
missing matrix cell, illegal transition, non-finite number, lookahead, privacy
key, or digest mismatch fails closed.
Aggregate cost fields use canonical eight-decimal fixed strings (for example
`0.00000000`) so equivalent numeric spellings cannot produce distinct valid
aggregates.

## CLI and reproducibility

The offline CLI exposes `validate-config`, `paper-replay`, and
`verify-aggregate`. `paper-replay` accepts a typed synthetic fixture JSON
object with exactly `attestation`, `scenario`,
`frozen_candidate_policies`, and `cycles`. Each cycle contains only a redacted
identity, typed state, policy actions, quotes, and a causal window holding
feature snapshots, decision records, report alias, and cutoff. It rejects
unknown/private keys and never accepts a source path or precomputed result row.
The frozen policy manifest is checked against RB-013's canonical policy
registry. RB-011/RB-012 actions are recomputed from causal snapshots; injected
action streams and mismatched action digests are rejected. Two clean runs over the same fixture and scenario must emit
byte-identical canonical UTF-8 JSON and the same self-digest. The CLI never
prints raw rows, exact timestamps, prices, paths, account identifiers,
credentials, or private source details.

RB-014 is complete only after focused and full tests, privacy, compile,
determinism, independent review, remediation, and fresh re-review all pass.
