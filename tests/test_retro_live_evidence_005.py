from __future__ import annotations

import pytest
from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_live_evidence_001 import digest
from xau_trigger.retro_live_evidence_005 import evaluate_shadow, verify_shadow_aggregate


def _obs(index: int, **changes):
    value = {"observation_id": f"obs-{index}", "source_timestamp_ns": index, "clone_timestamp_ns": index + 1, "source_state_digest": digest({"state": index}), "clone_state_digest": digest({"state": index}), "source_action": "hold", "clone_action": "hold", "connection_state": "connected", "reconnect_count": 0, "state_recovered": True, "unsafe_divergence": False, "future_read": False, "execution_surface_used": False, "latency_ms": 0.000001}
    value.update(changes)
    return value


def test_shadow_is_read_only_and_redacted():
    result = evaluate_shadow([_obs(1), _obs(2)])
    assert result["synthetic_only"] is True and result["status"] == "descriptive-only"
    assert verify_shadow_aggregate(result, expected_input_digest=result["input_digest"])


def test_shadow_fails_closed_on_unsafe_surface_or_bad_recovery():
    result = evaluate_shadow([_obs(1, execution_surface_used=True)])
    assert result["status"] == "hold"
    recovery = evaluate_shadow([_obs(1, connection_state="recovered", state_recovered=False)])
    assert recovery["status"] == "hold" and recovery["metrics"]["recovery_failures"] == 1


def test_shadow_rejects_out_of_order_source_checkpoints():
    with pytest.raises(RetroBotInputError):
        evaluate_shadow([_obs(2), _obs(1)])


def test_shadow_binds_latency_to_timestamps_and_trusted_digest():
    with pytest.raises(RetroBotInputError):
        evaluate_shadow([_obs(1, clone_timestamp_ns=1, latency_ms=2.0)])
    result = evaluate_shadow([_obs(1)])
    with pytest.raises(RetroBotInputError):
        verify_shadow_aggregate(result)
    forged = dict(result)
    forged["metrics"] = dict(result["metrics"])
    forged["metrics"]["determinism"] = True
    forged["aggregate_sha256"] = digest({key: forged[key] for key in forged if key != "aggregate_sha256"})
    with pytest.raises(RetroBotInputError):
        verify_shadow_aggregate(forged, expected_input_digest=forged["input_digest"])
    forged = dict(result)
    forged["metrics"] = dict(result["metrics"])
    forged["metrics"]["state_parity"] = 0.0
    forged["aggregate_sha256"] = digest({key: forged[key] for key in forged if key != "aggregate_sha256"})
    with pytest.raises(RetroBotInputError):
        verify_shadow_aggregate(forged, expected_input_digest=forged["input_digest"])
