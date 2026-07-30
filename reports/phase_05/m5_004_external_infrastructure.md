# M5-004 External Infrastructure

Status: `external_infrastructure_ready_data_unseen`

The frozen M5-004 package is ready for a two-stage external workflow:

```text
blind structural intake -> accepted record -> one-time frozen evaluation
```

No August input was used to build or test this infrastructure. Synthetic
fixtures cannot be accepted as real external data without an explicit fixture
flag and cannot create a project verdict.

## Registered blocks

- Primary ticks: 2026-08-03 through 2026-08-07, MT5 server dates.
- Primary report context: 2026-07-31 through 2026-08-08.
- Fallback ticks: 2026-08-10 through 2026-08-14.
- Fallback report context: 2026-08-07 through 2026-08-15.

The primary report should be exported only after the complete 2026-08-08
context is available. Fallback requires a reviewed primary structural-failure
authorization and cannot be activated by event counts, class balance, or
model performance.

## Local input manifest

Create an untracked `input_aliases.local.json` containing privacy-safe aliases
and local paths:

```json
{
  "schema_version": 1,
  "block_id": "primary",
  "data_origin": "real_external",
  "symbol": "XAUUSD",
  "tick_exports": [
    {
      "alias": "primary_ticks_d1",
      "path": "<local tick export>",
      "export_run_id": "run-a",
      "server_dates": ["2026-08-03"]
    }
  ],
  "replica_exports": [],
  "report": {
    "alias": "primary_report",
    "path": "<local report>",
    "declared_context_start": "2026-07-31",
    "declared_context_end": "2026-08-08"
  }
}
```

Add all five registered tick sessions. A replica export is needed only for an
unknown material quote gap and must use a distinct export run ID with identical
boundary ticks.

## Commands

Run blind intake first:

```bash
python scripts/intake_m5_004_external.py \
  --inputs data/interim/m5_004_external/primary/input_aliases.local.json
```

Only after intake creates an accepted structural record:

```bash
python scripts/evaluate_m5_004_external.py \
  --inputs data/interim/m5_004_external/primary/input_aliases.local.json \
  --intake reports/phase_05/m5_004_primary_blind_intake.json \
  --acceptance reports/phase_05/m5_004_primary_structural_acceptance.json
```

The evaluator locks the deterministic evaluation ID before deriving unlock
direction labels. An interrupted run can resume only with
`--resume-identical` and unchanged input, acceptance, model, and runtime
hashes. A consumed evaluation cannot run again.

The result publishes pooled, daily, ablation, and descriptive five-session
leave-one-session-out summaries. LOSO reuses the frozen predictions without
refitting and cannot affect the one-second headline verdict. The persisted
started guard is reverified immediately before consumption, and fallback
authorization rejects a structurally tampered primary-failure record.

Blind intake publishes structural statuses only. It never publishes unlock
direction, eligible-event counts, features, predictions, coefficients,
likelihoods, financial amounts, or model performance.
