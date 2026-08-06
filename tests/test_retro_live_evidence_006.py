from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_live_evidence_001 import FROZEN_GATE_DIGEST, digest
from xau_trigger.retro_live_evidence_006 import SafetyAdapterSimulator, evaluate_readiness, validate_limits, verify_readiness


LIMITS = {"max_gross_lots": "1.00000000", "max_net_lots": "0.50000000", "max_actions": 3, "max_outstanding": 1, "max_retries": 2, "max_latency_ms": 100.0}


def _flags(value: bool = False) -> dict[str, bool]:
    return {"e002_actionful": value, "e003_fidelity": value, "e004_holdout": value, "e005_shadow": value, "source_receipts_trusted": value, "m5_firewall": True, "submission_surface_absent": True}


def _safety(value: bool = False) -> dict[str, bool]:
    return {"dry_run_only": True, "submission_surface_absent": True, "idempotency": value, "reconnect_recovery": value, "operator_stop": value, "position_limits": value, "flatten_control": value}


def _intent(identifier: str = "i-1", action: str = "enter", quantity: str = "0.10000000") -> dict[str, object]:
    return {"intent_id": identifier, "action": action, "quantity": quantity, "payload_digest": digest({"id": identifier, "action": action, "quantity": quantity}), "nonce": "nonce-1234", "retry_count": 0, "latency_ms": 1.0}


def test_readiness_is_fail_closed_and_synthetic_only():
    result = evaluate_readiness(evidence_digests={key: digest({"key": key}) for key in ("e002", "e003", "e004", "e005")}, evidence_flags=_flags(), adapter_safety=_safety())
    assert result["status"] == "hold-synthetic-only" and result["synthetic_only"] is True
    assert verify_readiness(result, expected_evidence_digest=result["evidence_digest"], expected_component_digests=result["evidence_digests"])


def test_readiness_rejects_identity_or_boundary_tampering():
    result = evaluate_readiness(evidence_digests={key: digest({"key": key}) for key in ("e002", "e003", "e004", "e005")}, evidence_flags=_flags(), adapter_safety=_safety())
    bad = dict(result); bad["synthetic_only"] = 1
    with pytest.raises(RetroBotInputError): verify_readiness(bad, expected_evidence_digest=result["evidence_digest"], expected_component_digests=result["evidence_digests"])
    bad = dict(result); bad["schema_version"] = True
    with pytest.raises(RetroBotInputError): verify_readiness(bad, expected_evidence_digest=result["evidence_digest"], expected_component_digests=result["evidence_digests"])
    bad = dict(result); bad["gate_digest"] = "0" * 64; bad["aggregate_sha256"] = digest({key: bad[key] for key in bad if key != "aggregate_sha256"})
    with pytest.raises(RetroBotInputError): verify_readiness(bad, expected_evidence_digest=result["evidence_digest"], expected_component_digests=result["evidence_digests"])
    with pytest.raises(RetroBotInputError): verify_readiness(result, expected_evidence_digest=result["evidence_digest"], expected_component_digests={**result["evidence_digests"], "e002": "0" * 64})


def test_simulator_enforces_idempotency_limits_stop_flatten_and_no_transport():
    simulator = SafetyAdapterSimulator(LIMITS)
    first = simulator.submit_intent(_intent())
    assert simulator.submit_intent(_intent()) == first and simulator.transport_calls == 0
    with pytest.raises(RetroBotInputError): simulator.submit_intent(_intent(quantity="0.20000000", identifier="i-1"))
    simulator.submit_intent(_intent(identifier="i-2", quantity="0.40000000"))
    with pytest.raises(RetroBotInputError): simulator.submit_intent(_intent(identifier="i-3", quantity="0.20000000"))
    stopped = simulator.stop()
    assert stopped["flatten"]["opens"] is False and stopped["flatten"]["reverses"] is False
    assert simulator.stop()["flatten"] is None
    with pytest.raises(RetroBotInputError): simulator.submit_intent(_intent(identifier="i-4"))


def test_simulator_reconnect_requires_monotonic_ack_and_snapshot():
    simulator = SafetyAdapterSimulator(LIMITS)
    snapshot = digest({"snapshot": 1})
    with pytest.raises(RetroBotInputError): simulator.reconnect(snapshot_digest=snapshot, sequence=0, operator_ack=False)
    assert simulator.reconnect(snapshot_digest=snapshot, sequence=0, operator_ack=True)["auto_resume"] is False
    with pytest.raises(RetroBotInputError): simulator.reconnect(snapshot_digest=snapshot, sequence=1, operator_ack=True)
    with pytest.raises(RetroBotInputError): simulator.reconnect(snapshot_digest=digest({"snapshot": 2}), sequence=2, operator_ack=False)


def test_simulator_rejects_exit_without_tracked_position():
    simulator = SafetyAdapterSimulator(LIMITS)
    with pytest.raises(RetroBotInputError): simulator.submit_intent(_intent(action="exit", quantity="0.10000000"))


def test_limits_reject_nonfinite_and_invalid_precision():
    with pytest.raises(RetroBotInputError): validate_limits({**LIMITS, "max_latency_ms": float("nan")})
    with pytest.raises(RetroBotInputError): validate_limits({**LIMITS, "max_gross_lots": "1.000000001"})
    with pytest.raises(RetroBotInputError): validate_limits({**LIMITS, "max_gross_lots": "1E-8"})
    with pytest.raises(RetroBotInputError): validate_limits({**LIMITS, "max_gross_lots": "01.00000000"})


def test_cli_is_stdin_only_and_byte_deterministic():
    payload = {"evidence_digests": {key: digest({"key": key}) for key in ("e002", "e003", "e004", "e005")}, "evidence_flags": _flags(), "adapter_safety": _safety()}
    script = Path(__file__).parents[1] / "scripts" / "run_retro_live_evidence_006.py"
    first = subprocess.run([sys.executable, str(script)], input=json.dumps(payload), text=True, capture_output=True, check=True)
    second = subprocess.run([sys.executable, str(script)], input=json.dumps(payload), text=True, capture_output=True, check=True)
    assert first.stdout == second.stdout and json.loads(first.stdout)["status"] == "hold-synthetic-only"


def test_simulator_has_no_transport_import_or_surface():
    source = (Path(__file__).parents[1] / "src" / "xau_trigger" / "retro_live_evidence_006.py").read_text(encoding="utf-8").lower()
    assert all(token not in source for token in ("import socket", "import requests", "mt5.initialize", "send_order"))
