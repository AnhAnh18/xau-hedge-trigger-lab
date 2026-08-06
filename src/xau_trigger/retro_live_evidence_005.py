"""Synthetic read-only shadow-observer evidence for RETRO-LIVE-EVIDENCE-005.

This module models the safety and accounting boundary of a future observer
without opening a realtime feed or exposing an execution surface. Inputs are
redacted observation checkpoints only.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping, Sequence

from .retro_bot import RetroBotInputError
from .retro_live_evidence_001 import assert_firewall_clean, digest

E005_ID = "RETRO-LIVE-EVIDENCE-005"
MAX_OBSERVATIONS = 100_000
OBSERVATION_FIELDS = frozenset({
    "observation_id", "source_timestamp_ns", "clone_timestamp_ns",
    "source_state_digest", "clone_state_digest", "source_action",
    "clone_action", "connection_state", "reconnect_count",
    "state_recovered", "unsafe_divergence", "future_read",
    "execution_surface_used", "latency_ms",
})
ACTIONS = frozenset({"buy", "sell", "hold", "none", "censored"})
CONNECTION_STATES = frozenset({"connected", "reconnecting", "recovered", "disconnected"})


def _hex(value: object, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RetroBotInputError(f"E-005 {label} invalid")
    return value


def _observation(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != OBSERVATION_FIELDS:
        raise RetroBotInputError("E-005 observation schema invalid")
    if not isinstance(value["observation_id"], str) or not value["observation_id"]:
        raise RetroBotInputError("E-005 observation id invalid")
    for key in ("source_timestamp_ns", "clone_timestamp_ns", "reconnect_count"):
        if type(value[key]) is not int or value[key] < 0 or (key != "reconnect_count" and value[key] > 10**24):
            raise RetroBotInputError("E-005 observation integer invalid")
    for key in ("source_state_digest", "clone_state_digest"):
        _hex(value[key], key)
    for key in ("source_action", "clone_action"):
        if value[key] not in ACTIONS:
            raise RetroBotInputError("E-005 action invalid")
    if value["connection_state"] not in CONNECTION_STATES:
        raise RetroBotInputError("E-005 connection state invalid")
    if type(value["state_recovered"]) is not bool or type(value["unsafe_divergence"]) is not bool or type(value["future_read"]) is not bool or type(value["execution_surface_used"]) is not bool:
        raise RetroBotInputError("E-005 safety flag invalid")
    if type(value["latency_ms"]) not in (int, float) or isinstance(value["latency_ms"], bool) or value["latency_ms"] < 0:
        raise RetroBotInputError("E-005 latency invalid")
    try:
        latency_value = float(value["latency_ms"])
    except (OverflowError, ValueError) as exc:
        raise RetroBotInputError("E-005 latency invalid") from exc
    if not math.isfinite(latency_value) or value["clone_timestamp_ns"] < value["source_timestamp_ns"] or abs(latency_value - (value["clone_timestamp_ns"] - value["source_timestamp_ns"]) / 1_000_000.0) > 0.001:
        raise RetroBotInputError("E-005 timestamp/latency mismatch")
    return dict(value)


def evaluate_shadow(observations: Sequence[Mapping[str, Any]], *, synthetic_only: bool = True) -> dict[str, Any]:
    if synthetic_only is not True:
        raise RetroBotInputError("E-005 source observation requires separate authorization")
    if not isinstance(observations, Sequence) or isinstance(observations, (str, bytes)) or not observations or len(observations) > MAX_OBSERVATIONS:
        raise RetroBotInputError("E-005 observation bound invalid")
    clean = [_observation(item) for item in observations]
    if len({item["observation_id"] for item in clean}) != len(clean):
        raise RetroBotInputError("E-005 duplicate observation id")
    if any(clean[index]["source_timestamp_ns"] > clean[index + 1]["source_timestamp_ns"] for index in range(len(clean) - 1)):
        raise RetroBotInputError("E-005 source chronology invalid")
    clean = sorted(clean, key=lambda item: (item["source_timestamp_ns"], item["observation_id"]))
    assert_firewall_clean(clean)
    state_matches = sum(item["source_state_digest"] == item["clone_state_digest"] for item in clean)
    action_comparable = [item for item in clean if item["source_action"] != "censored" and item["clone_action"] != "censored"]
    action_matches = sum(item["source_action"] == item["clone_action"] for item in action_comparable)
    unsafe = sum(item["unsafe_divergence"] or item["future_read"] or item["execution_surface_used"] for item in clean)
    recovery_failures = sum(item["connection_state"] == "recovered" and not item["state_recovered"] for item in clean)
    metrics = {
        "state_matches": state_matches,
        "state_parity": state_matches / len(clean),
        "action_matches": action_matches,
        "action_comparable": len(action_comparable),
        "action_parity": action_matches / len(action_comparable) if action_comparable else None,
        "coverage": len(action_comparable) / len(clean),
        "mean_latency_ms": sum(float(item["latency_ms"]) for item in clean) / len(clean),
        "max_latency_ms": max(float(item["latency_ms"]) for item in clean),
        "reconnect_count": sum(item["reconnect_count"] for item in clean),
        "recovery_failures": recovery_failures,
        "unsafe_event_count": unsafe,
        "determinism": False,
    }
    status = "hold" if unsafe or recovery_failures or metrics["action_parity"] is None else "descriptive-only"
    result = {
        "schema_version": 1, "case_id": E005_ID, "synthetic_only": True,
        "observation_count": len(clean), "comparable_count": len(action_comparable),
        "metrics": metrics, "status": status,
        "input_digest": digest(clean),
    }
    result["aggregate_sha256"] = digest(result)
    return result


def verify_shadow_aggregate(value: Mapping[str, Any], *, expected_input_digest: str | None = None) -> bool:
    required = {"schema_version", "case_id", "synthetic_only", "observation_count", "comparable_count", "metrics", "status", "input_digest", "aggregate_sha256"}
    if not isinstance(value, Mapping) or set(value) != required or value.get("schema_version") != 1 or value.get("case_id") != E005_ID or value.get("synthetic_only") is not True:
        raise RetroBotInputError("E-005 aggregate schema invalid")
    if value["aggregate_sha256"] != digest({key: value[key] for key in value if key != "aggregate_sha256"}):
        raise RetroBotInputError("E-005 aggregate digest mismatch")
    if type(value["observation_count"]) is not int or value["observation_count"] < 1 or type(value["comparable_count"]) is not int or not 0 <= value["comparable_count"] <= value["observation_count"]:
        raise RetroBotInputError("E-005 aggregate counts invalid")
    expected_metrics = {"state_matches", "state_parity", "action_matches", "action_comparable", "action_parity", "coverage", "mean_latency_ms", "max_latency_ms", "reconnect_count", "recovery_failures", "unsafe_event_count", "determinism"}
    if not isinstance(value["metrics"], Mapping) or set(value["metrics"]) != expected_metrics:
        raise RetroBotInputError("E-005 metrics schema invalid")
    for key in ("state_parity", "coverage"):
        metric = value["metrics"][key]
        if type(metric) not in (int, float) or isinstance(metric, bool) or not math.isfinite(metric) or not 0 <= metric <= 1:
            raise RetroBotInputError("E-005 ratio invalid")
    if value["metrics"]["action_parity"] is not None and (type(value["metrics"]["action_parity"]) not in (int, float) or not math.isfinite(value["metrics"]["action_parity"]) or not 0 <= value["metrics"]["action_parity"] <= 1):
        raise RetroBotInputError("E-005 action parity invalid")
    for key in ("mean_latency_ms", "max_latency_ms"):
        if type(value["metrics"][key]) not in (int, float) or not math.isfinite(value["metrics"][key]) or value["metrics"][key] < 0:
            raise RetroBotInputError("E-005 latency metric invalid")
    for key in ("reconnect_count", "recovery_failures", "unsafe_event_count"):
        if type(value["metrics"][key]) is not int or value["metrics"][key] < 0:
            raise RetroBotInputError("E-005 count metric invalid")
    for key in ("state_matches", "action_matches", "action_comparable"):
        if type(value["metrics"][key]) is not int or value["metrics"][key] < 0:
            raise RetroBotInputError("E-005 audit count invalid")
    if value["metrics"]["state_matches"] > value["observation_count"] or value["metrics"]["action_comparable"] != value["comparable_count"] or value["metrics"]["action_matches"] > value["metrics"]["action_comparable"]:
        raise RetroBotInputError("E-005 audit conservation invalid")
    expected_state_parity = value["metrics"]["state_matches"] / value["observation_count"]
    expected_coverage = value["metrics"]["action_comparable"] / value["observation_count"]
    if not math.isclose(value["metrics"]["state_parity"], expected_state_parity, rel_tol=0.0, abs_tol=1e-12) or not math.isclose(value["metrics"]["coverage"], expected_coverage, rel_tol=0.0, abs_tol=1e-12):
        raise RetroBotInputError("E-005 ratio formula mismatch")
    if value["metrics"]["action_comparable"] == 0:
        if value["metrics"]["action_parity"] is not None:
            raise RetroBotInputError("E-005 action parity denominator mismatch")
    elif not math.isclose(value["metrics"]["action_parity"], value["metrics"]["action_matches"] / value["metrics"]["action_comparable"], rel_tol=0.0, abs_tol=1e-12):
        raise RetroBotInputError("E-005 action parity formula mismatch")
    expected_status = "hold" if value["metrics"]["unsafe_event_count"] or value["metrics"]["recovery_failures"] or value["metrics"]["action_parity"] is None else "descriptive-only"
    if value["metrics"]["determinism"] is not False or value["status"] != expected_status or not re.fullmatch(r"[0-9a-f]{64}", value["input_digest"]) or not isinstance(expected_input_digest, str) or value["input_digest"] != expected_input_digest:
        raise RetroBotInputError("E-005 aggregate values invalid")
    if value["metrics"]["recovery_failures"] > value["observation_count"] or value["metrics"]["unsafe_event_count"] > value["observation_count"] or value["metrics"]["max_latency_ms"] < value["metrics"]["mean_latency_ms"]:
        raise RetroBotInputError("E-005 aggregate conservation invalid")
    assert_firewall_clean([value[key] for key in value if key != "case_id"])
    return True
