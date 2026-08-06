from __future__ import annotations

import json
import subprocess
import sys
from decimal import Inexact, getcontext
from pathlib import Path
import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_live_evidence_002 import component_digest, ingest_redacted_cycles, verify_evidence_aggregate


def _cycle(index: int, category: str = "normal_hedge") -> dict:
    return {"cycle_id": f"c-{index}", "categories": [category], "action_count": 2, "buy_actions": 1, "sell_actions": 1, "state_matches": 1, "state_checkpoints": 1, "direction_matches": 1, "direction_comparable": 1, "order_matches": 1, "order_comparable": 1, "timing_matches": 1, "timing_comparable": 1, "lot_matches": 1, "lot_comparable": 1, "lot_observed_quantity":"0.30000000", "lot_predicted_quantity":"0.30000000", "duplicate_actions": 0, "observed_actions": 2, "censored_checkpoints": 0, "eligible_checkpoints": 1, "comparable_checkpoints": 1, "robustness_passes": 1, "robustness_cases": 1, "illegal_transitions": 0, "negative_lots": 0, "same_tick_double_actions": 0, "conservation_failures": 0, "future_reads": 0}


def test_synthetic_intake_is_redacted_and_deterministic() -> None:
    rows = [_cycle(i, "normal_hedge") for i in range(3)]
    first = ingest_redacted_cycles(rows)
    second = ingest_redacted_cycles(rows)
    assert first == second and first["synthetic_only"] is True
    assert verify_evidence_aggregate(first, expected_input_digest=first["input_digest"], expected_component_digest=component_digest(first))


def test_intake_rejects_duplicates_raw_surface_and_bad_counts() -> None:
    row = _cycle(1)
    with pytest.raises(RetroBotInputError): ingest_redacted_cycles([row, row])
    bad = dict(row); bad["raw_rows"] = []
    with pytest.raises(RetroBotInputError): ingest_redacted_cycles([bad])
    bad = dict(row); bad["state_matches"] = 2
    with pytest.raises(RetroBotInputError): ingest_redacted_cycles([bad])
    bad = dict(row); bad["action_count"] = 0; bad["observed_actions"] = 0
    with pytest.raises(RetroBotInputError): ingest_redacted_cycles([bad])
    bad = dict(row); bad["censored_checkpoints"] = 1; bad["comparable_checkpoints"] = 1; bad["eligible_checkpoints"] = 1
    with pytest.raises(RetroBotInputError): ingest_redacted_cycles([bad])
    bad = dict(row); bad["lot_observed_quantity"] = "0.300000001"
    with pytest.raises(RetroBotInputError): ingest_redacted_cycles([bad])
    previous_precision = getcontext().prec
    previous_trap = getcontext().traps[Inexact]
    getcontext().prec = 2
    getcontext().traps[Inexact] = True
    try:
        assert ingest_redacted_cycles([row])["cycle_count"] == 1
    finally:
        getcontext().prec = previous_precision
        getcontext().traps[Inexact] = previous_trap


def test_aggregate_tamper_is_rejected_even_with_rehashed_digest() -> None:
    result = ingest_redacted_cycles([_cycle(1)])
    result["buy_actions"] = "oops"
    from xau_trigger.retro_live_evidence_001 import digest
    result["aggregate_sha256"] = digest({key: result[key] for key in result if key != "aggregate_sha256"})
    with pytest.raises(RetroBotInputError): verify_evidence_aggregate(result, expected_input_digest=result["input_digest"], expected_component_digest=component_digest(ingest_redacted_cycles([_cycle(1)])))
    result = ingest_redacted_cycles([_cycle(1)])
    result["gate_pass"]["coverage"] = 1
    result["aggregate_sha256"] = digest({key: result[key] for key in result if key != "aggregate_sha256"})
    with pytest.raises(RetroBotInputError): verify_evidence_aggregate(result, expected_input_digest=result["input_digest"], expected_component_digest=component_digest(ingest_redacted_cycles([_cycle(1)])))
    result = ingest_redacted_cycles([_cycle(1)])
    result["category_counts"]["normal_hedge"] = 2
    result["aggregate_sha256"] = digest({key: result[key] for key in result if key != "aggregate_sha256"})
    with pytest.raises(RetroBotInputError): verify_evidence_aggregate(result, expected_input_digest=result["input_digest"], expected_component_digest=component_digest(ingest_redacted_cycles([_cycle(1)])))
    result = ingest_redacted_cycles([_cycle(1)])
    result["metrics"]["state_parity"] = 2.0
    result["aggregate_sha256"] = digest({key: result[key] for key in result if key != "aggregate_sha256"})
    with pytest.raises(RetroBotInputError): verify_evidence_aggregate(result, expected_input_digest=result["input_digest"], expected_component_digest=component_digest(ingest_redacted_cycles([_cycle(1)])))
    result = ingest_redacted_cycles([_cycle(1)])
    result["metrics"]["determinism"] = True
    result["gate_pass"]["determinism"] = True
    result["status"] = "package-ready"
    result["aggregate_sha256"] = digest({key: result[key] for key in result if key != "aggregate_sha256"})
    with pytest.raises(RetroBotInputError): verify_evidence_aggregate(result, expected_input_digest=result["input_digest"], expected_component_digest=component_digest(ingest_redacted_cycles([_cycle(1)])))


def test_cli_is_stdin_only_and_rejects_extra_fields() -> None:
    root = Path(__file__).parents[1]
    payload = json.dumps({"cycles": [_cycle(1)]})
    run = subprocess.run([sys.executable, str(root / "scripts" / "run_retro_live_evidence_002.py")], input=payload, text=True, capture_output=True)
    assert run.returncode == 0
    output = json.loads(run.stdout)
    assert verify_evidence_aggregate(output, expected_input_digest=output["input_digest"], expected_component_digest=component_digest(output))
    bad = subprocess.run([sys.executable, str(root / "scripts" / "run_retro_live_evidence_002.py")], input=json.dumps({"cycles": [_cycle(1)], "path": "C:\\secret"}), text=True, capture_output=True)
    assert bad.returncode == 2
