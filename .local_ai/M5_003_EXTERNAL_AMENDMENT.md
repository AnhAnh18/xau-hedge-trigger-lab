# M5-003 External Intake Amendment

Recorded: 2026-07-30, after raw acquisition inspection but before external
feature construction or prediction.

This amendment does not change any M5-003 predictor, preprocessing transform,
coefficient, regularization choice, comparison, multiplicity rule, or verdict
gate. M2 through the frozen M5-003 model outputs remain immutable.

## Qualitative exposure disclosure

Selected operational screenshots from 2026-07-27 and 2026-07-28 were discussed
before the full external batch was acquired. They exposed a small, selected set
of lifecycle actions and P/L outcomes. Raw file coverage metadata and aggregate
report event counts were also inspected during acquisition validation.

No external price feature, model prediction, paired likelihood increment, or
endpoint verdict was computed before this amendment. The 2026-07-27 through
2026-07-29 batch is therefore described as a prospective frozen-model
evaluation with disclosed qualitative exposure, not as analyst-blinded
validation.

## Immutable external inputs

| Input alias | Coverage | Rows | SHA-256 |
| --- | --- | ---: | --- |
| `external-tick-2026-07-27` | 2026-07-27 01:00:00.757–23:57:58.013 | 642,462 | `ded63bcbb771fd5e18970674672961573416f556188623726aac04b119efa101` |
| `external-tick-2026-07-28` | 2026-07-28 01:00:00.488–23:57:58.759 | 683,869 | `955874623e6d84be62a8382dda4a8ffd55e49dc0f888d9dc63a98e9b5c48cf7f` |
| `external-tick-2026-07-29` | 2026-07-29 01:00:00.648–23:57:59.992 | 716,152 | `f4fd7b51f55db58a7e1d669095fbd54c2992f631310593a76ff0a7016ffaca63` |
| `external-report-2026-07-24-through-2026-07-30` | clipped to registered 27–29 sessions | n/a | `57e58a6286777d4ee1ec74886b8ea2eb8bfd0eaacaad4250390e4d81861db45d` |

The separately exported 2026-07-24 tick file is context only. The external
model cohort remains exactly 2026-07-27 through 2026-07-29.

## Replicated source quote gap

Two independent 2026-07-27 exports contain the same consecutive ticks around:

```text
2026-07-27 18:08:35.303  4074.07 / 4074.30
2026-07-27 18:10:21.660  4072.69 / 4072.91
```

The 106.357-second interval is classified as
`replicated_source_quote_gap`. The trade report contains lifecycle events
inside it.

The fixed policy is:

- never interpolate or fabricate ticks;
- exclude the gap from tradeable risk time;
- invalidate every price window crossing the gap;
- retain report events inside the gap for lifecycle and accounting;
- do not force those events into tick-aligned inference.

## External decision contract

The one-second headline remains `C_session−A_session`. Support still requires
a positive pooled mean, a positive Bonferroni family-wise one-sided lower
bound, and positive point estimates in at least two of the three registered
sessions. Null, weak, mixed, or rejected findings are valid outputs. No result
may be described as a standalone tradeable edge.
