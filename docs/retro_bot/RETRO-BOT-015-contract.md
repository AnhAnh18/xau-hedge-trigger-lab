# RETRO-BOT-015: Variable-Lot Offline Paper Bot

Canonical milestone: RB-019. This is a RETRO-only, typed/redacted
variable-lot accounting extension requested by the owner. It provides a
runnable offline bot over caller-supplied typed cycles; it does not read raw
exports, infer lot sizes from private history, fit a strategy, modify M5, or
place live/demo orders.

## Authorization and boundary

Owner authorization token: RB019_TYPED_VARIABLE_LOT_AUTHORIZED.

The input is exactly one JSON object with ordered keys:

```text
schema_version:int=1,
case_id:str="RB-019",
attestation:{schema_version:int=1,authorization:"RB019_TYPED_VARIABLE_LOT_AUTHORIZED",
             source_kind:"typed-redacted",m5_firewall:"M5_FIREWALL_ATTESTATION_V1",
             live_execution:bool=False},
scenario:{scenario_id:"zero"|"spread_slippage",fee_per_unit:fixed8,
          slippage_points:fixed8,fingerprint:64-lowercase-hex},
cycles:[cycle,...]
```

The scenario fingerprint is the SHA-256 of the canonical UTF-8 JSON for the
three fields `scenario_id`, `fee_per_unit`, and `slippage_points`, in that
order, with compact separators, ASCII escaping, and without the fingerprint
field itself. The fingerprint is required on input and is emitted in the
aggregate, so a cost change cannot be hidden behind an unchanged scenario id.

Each cycle has ordered keys:

```text
cycle_id:str, start_state:"HEDGED"|"ONE_BUY"|"ONE_SELL",
initial:{buy_quantity:fixed8,sell_quantity:fixed8},
initial_quote:{bid:fixed8,ask:fixed8},
events:[{kind:"CLOSE_BUY"|"CLOSE_SELL"|"OPEN_BUY"|"OPEN_SELL",
         time_ns:int,bid:fixed8,ask:fixed8,quantity:fixed8},...],
terminal_quote:{bid:fixed8,ask:fixed8}
```

### Fixed8 numeric contract

Every quantity, price, fee, and slippage value is a finite decimal string
matching exactly `^(0|[1-9][0-9]*)\\.[0-9]{8}$`, parsed with `Decimal` without
binary floating point. Leading zeros, signs, exponents, NaN, Infinity, and
alternate decimal spellings are rejected. The bounds are:

| Value | Bound | Additional rule |
| --- | --- | --- |
| quantity | `0.00000000` through `1000.00000000` | zero is allowed only for an absent initial leg; event quantities are positive |
| bid/ask price | `0.00000001` through `10000000.00000000` | `Ask >= Bid` |
| `fee_per_unit` | `0.00000000` through `1000.00000000` | non-negative |
| `slippage_points` | `0.00000000` through `1000.00000000` | non-negative |

There is no separate user-supplied total-cost bound. For every traded
quantity `q`, the derived cost is exactly
`cost(q) = fee_per_unit*q + 0.01*slippage_points*q`; with the bounds above
its maximum per unit is `1010.00000000`. All arithmetic remains Decimal and is
quantized to fixed8 only when producing the redacted output.

`time_ns` is an exact non-negative integer; booleans and floats are rejected.
Events are already chronological; the bot never sorts or uses future events.
Each cycle has at most 16 events. `cycle_id` matches
`^[A-Za-z0-9_-]{1,64}$` and must be unique across the ordered `cycles` list.
A duplicate id is malformed input and rejects the whole document; it is not
counted as a semantic invalid cycle.

## State and transitions

Every event quantity must exactly match the active leg being closed or the new
leg being opened. HEDGED starts require both quantities positive; one-leg
starts require exactly one positive quantity. The final quote must be valid
and finite.

Allowed transitions are:

```text
HEDGED + CLOSE_BUY  -> ONE_SELL
HEDGED + CLOSE_SELL -> ONE_BUY
ONE_BUY + OPEN_SELL  -> HEDGED
ONE_SELL + OPEN_BUY  -> HEDGED
```

Duplicate `(time_ns, kind)`, same-side, non-increasing, illegal, or
post-terminal events make that otherwise well-formed cycle invalid and
increment `invalid_count` without retaining its details. OPEN lot changes are
intentional: closing removes exactly the active leg quantity, while opening
creates a new opposite leg with its declared quantity. The invariant is
per-leg quantity conservation across each transition, not a constant total
hedge volume.

## Variable-lot accounting

For Buy quantity `q` and Sell quantity `r`, initial cash uses
`initial_quote`:

```text
(-initial_ask*q + initial_bid*r) - cost(q) - cost(r)
```

Absent legs are omitted. For each event, `CLOSE_BUY` adds `Bid*q`,
`CLOSE_SELL` subtracts `Ask*q`, `OPEN_BUY` subtracts `Ask*q`, and `OPEN_SELL`
adds `Bid*q`; every event also subtracts `cost(q)`. The terminal mark adds
`Bid*active_buy - Ask*active_sell`. P/L is cash plus terminal mark. Loss,
flat, and gain compare the unrounded Decimal P/L to zero, so exact zero is
flat. `traded_quantity_total` includes all positive initial quantities plus
all accepted event quantities.

Normative golden accounting vector (scenario `zero`, all costs zero):

```text
initial: HEDGED, buy=0.30000000, sell=0.10000000,
         initial bid/ask=2000.00000000/2000.20000000
CLOSE_BUY: quantity=0.30000000, bid/ask=2000.50000000/2000.70000000
OPEN_BUY:  quantity=0.50000000, bid/ask=2000.40000000/2000.60000000
terminal bid/ask=2000.00000000/2000.20000000
expected initial cash=-400.06000000
expected post-events cash=-800.21000000
expected terminal mark=799.98000000
expected P/L=-0.23000000
expected traded quantity=1.20000000
```

## Output and CLI

`replay` emits exactly this fixed aggregate, in this order:

```text
schema_version, case_id, scenario_id, scenario_fingerprint,
cycle_count, marked_count, invalid_count, loss_count, flat_count, gain_count,
quantity_min_fixed8, quantity_max_fixed8, traded_quantity_total_fixed8,
aggregate_sha256
```

`quantity_min` and `quantity_max` are the minimum and maximum positive
quantities over all valid cycles' initial legs and accepted events. A
zero-cycle valid population is rejected; invalid cycles do not contribute to
quantity bands or traded quantity. `cycle_count` includes valid and invalid
cycles, while P/L bands count only valid cycles. The exact return is never
emitted.

`verify-aggregate` accepts exactly six root keys, in this order:
`schema_version`, `case_id`, `attestation`, `scenario`, `cycles`, and a final
`aggregate` key. It recomputes the aggregate from the first five keys,
rechecks the scenario fingerprint, and compares canonical aggregate bytes.
`replay` rejects an `aggregate` key. Both stages parse duplicate-free, finite
JSON with no trailing bytes, emit compact canonical UTF-8 JSON plus one LF,
and hash the canonical aggregate without the final digest field. Success
emits exactly `{"stage":"verify-aggregate","verified":true}`. Malformed or
tampered input exits 2 with empty stdout and exact stderr
`RB-019 input rejected`.

Schema keys are ordered exactly as shown at every nesting level; unknown,
missing, reordered, duplicate, or extra keys fail closed. Recursive scanning
runs before semantic validation and allows only the exact firewall token
`M5_FIREWALL_ATTESTATION_V1`; it rejects raw/private paths, credentials,
journals, tickets, `.ex5`, MT5/network/order/live aliases, non-finite numbers,
and path-like strings. The implementation writes no input or source file and
never echoes input values.

## Limitations and stop conditions

This milestone proves that the bot can account for uneven typed quantities. It
does not claim that these quantities are the original historical lot schedule.
A future actual-history lot audit requires a new case-specific source receipt,
deterministic window, retention period, and independent review. It cannot
retroactively alter RB-001 through RB-018 or any M5 artifact.

Stop on any raw/private source request, M5 coupling, live-execution surface,
non-finite quantity, quantity conservation failure, lookahead, or privacy
failure. RB-019 is complete only after focused/full tests, privacy, compile,
determinism, independent review, remediation, fresh re-review, T-049 durable
state recording, and a milestone commit/push.
