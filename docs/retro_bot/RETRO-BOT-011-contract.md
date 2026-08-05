# RETRO-BOT-011: Robustness, Stress, and Ablation Contract

Canonical milestone: `RB-015`. This is a RETRO-only follow-on to RB-014.
It is descriptive, synthetic/typed by default, and remains outside every M5
input, model, evaluation, threshold, and gate.

## Scope and locked matrix

RB-015 exercises the already-locked RB-014 paper bot under a bounded,
predeclared stress matrix. The matrix covers all of the following dimensions:

- clock mappings: `utc_plus_2`, `utc_plus_3`, `eu_dst_2025_2026`;
- timestamp modes: normal seconds, second collisions, and DST-boundary labels;
- quote modes: clean, gap, duplicate, out-of-order, crossed, and non-finite;
- cost scenarios: zero cost, spread/slippage, and latency/margin;
- coverage: complete, action-truncated, and mark-truncated;
- descriptive slices: all, hedged, one-buy, and one-sell;
- feature ablations: baseline, drop-price-increment, and drop-adverse-excursion.

The exact case list is the 40-row `RB015_PROJECTION_V1` projection over the
synthetic fixture `synthetic_rb015_base_cycle_v1`: 18 clock/quote rows, 6
timestamp rows, 6 coverage rows, 4 slice rows, 3 ablation rows, and 3 cost
rows. The projection family, dimension values, fixture id, and row order are
frozen and carry a projection digest. There is no post-test case selection.
The registered typed fixture must contain at least one causal action in each
active slice so action- and mark-coverage perturbations exercise their stated
boundaries; an actionless fixture is rejected as an incomplete stress fixture.
The locked projection digest is
`4b3f9a2bd98b3827641cafa7807c6b929a2e212243c7a340cb51c97da1c701c3`.
Every case has a canonical SHA-256 id over projection version, fixture id,
family, and every dimension, and appears exactly once in the aggregate. Cases are typed in-memory and
may not contain paths, raw rows, credentials, journals, tickets, `.ex5`
artifacts, or M5 fields.

## Stress behavior

Each stress case runs `paper_backtest_cycle` with the typed fixture. Clock
labels mutate the cycle `clock_id` and every causal snapshot's `clock_id`
categorical value without converting UTC timestamps. `second_collision` makes
two quotes share a second; `dst_boundary` changes only the locked clock label.
`gap` removes the quote needed by an action, `duplicate` repeats a quote,
`out_of_order` reverses two quotes, `crossed` sets ask below bid, and
`nonfinite` injects a non-finite quote. Coverage truncation removes quotes
after the first action or before the terminal mark. No sorting or repair is
performed. Source/quote censoring precedes causal invalidity, which precedes
action/mark censoring, matching RB-014.

Cost ids are fixed: `zero` is all zero; `spread_slippage` uses fee `0`,
slippage `10.0` points, latency `0`, margin `0`; `latency_margin` uses fee
`0.25`, slippage `5.0` points, latency `1` second, margin `2.0`. Values are
fixed-decimal and scenario fingerprints are inherited from RB-014. Feature
ablations remove the named key and its provenance from every close/re-hedge
snapshot; no neutral values, refitting, recalibration, or action injection is
allowed. Ablation is therefore a structural causal-input check; if a frozen
RB-014 rule does not reference the removed feature, no action-count change is
expected and no performance inference may be drawn. Parameter perturbation
beyond these locked cost scenarios is out of scope for RB-015.

The retained observation contains only case identity, terminal status, bounded
action/mark counts, accounting flag, and loss/flat/gain band. It never retains
RB-014 `net_return`, raw cycles, quote values, or causal rows. P/L is never used
for ranking. The aggregate reports conservative status/band counts and a fixed
`descriptive-only-no-selection` terminal literal.

## Gates and reproducibility

The stress matrix rejects missing/duplicate cases, unknown dimensions,
non-finite counts, impossible action/mark accounting, mixed case ids, unknown
or private keys/values, and projection or fixture digest mismatches. It pins
the RB-014 schema/config/source-manifest digests, attestation fields, fixture
id, and M5 firewall literal without changing them. It verifies canonical row
order and a self-digest. CLI input is stdin-only typed JSON with exact
`attestation`, `projection`, `cases`, and `cycles` top-level keys; errors are
non-sensitive. Two clean runs over the same typed fixture must emit
byte-identical UTF-8 JSON.

RB-015 is complete only after focused/full tests, privacy, compile, diff,
determinism, an independent review, remediation, and a fresh re-review pass.
No stress result is a profitability claim, a live-execution authorization, or
an M5 decision.
