"""Fail-closed synthetic E-006 readiness decision and safety matrix.

This is a governance/safety scaffold only. It never connects to a broker,
creates an execution adapter, or authorizes demo/canary/live operation.
"""
from __future__ import annotations

import math
import re
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .retro_bot import RetroBotInputError
from .retro_live_evidence_001 import FROZEN_GATE_DIGEST, assert_firewall_clean, digest

E006_ID = "RETRO-LIVE-EVIDENCE-006"
FLAG_FIELDS = frozenset({
    "e002_actionful", "e003_fidelity", "e004_holdout", "e005_shadow",
    "source_receipts_trusted", "m5_firewall", "submission_surface_absent",
})
SAFETY_FIELDS = frozenset({
    "dry_run_only", "submission_surface_absent", "idempotency",
    "reconnect_recovery", "operator_stop", "position_limits", "flatten_control",
})
REQUIRED_FIELDS = frozenset({
    "schema_version", "case_id", "synthetic_only", "gate_digest",
    "evidence_digests", "evidence_flags", "adapter_safety", "status",
    "evidence_digest", "aggregate_sha256",
})
LIMIT_FIELDS = frozenset({"max_gross_lots", "max_net_lots", "max_actions", "max_outstanding", "max_retries", "max_latency_ms"})
INTENT_FIELDS = frozenset({"intent_id", "action", "quantity", "payload_digest", "nonce", "retry_count", "latency_ms"})


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RetroBotInputError(f"E-006 {label} invalid")
    return value


def _bool_map(value: object, fields: frozenset[str], label: str) -> dict[str, bool]:
    if not isinstance(value, Mapping) or set(value) != fields or any(type(item) is not bool for item in value.values()):
        raise RetroBotInputError(f"E-006 {label} invalid")
    return {key: bool(value[key]) for key in sorted(fields)}


def _validate_document(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != REQUIRED_FIELDS:
        raise RetroBotInputError("E-006 readiness schema invalid")
    if type(value.get("schema_version")) is not int or value.get("schema_version") != 1 or value.get("case_id") != E006_ID or value.get("synthetic_only") is not True:
        raise RetroBotInputError("E-006 readiness identity invalid")
    if value.get("gate_digest") != FROZEN_GATE_DIGEST:
        raise RetroBotInputError("E-006 gate digest is not frozen")
    evidence_digests = value.get("evidence_digests")
    if not isinstance(evidence_digests, Mapping) or set(evidence_digests) != {"e002", "e003", "e004", "e005"}:
        raise RetroBotInputError("E-006 evidence digest map invalid")
    for item in evidence_digests.values():
        _digest(item, "evidence digest")
    flags = _bool_map(value.get("evidence_flags"), FLAG_FIELDS, "evidence flags")
    safety = _bool_map(value.get("adapter_safety"), SAFETY_FIELDS, "adapter safety")
    if value.get("status") != "hold-synthetic-only":
        raise RetroBotInputError("E-006 readiness status invalid")
    _digest(value.get("evidence_digest"), "evidence")
    return {
        "schema_version": 1, "case_id": E006_ID, "synthetic_only": True,
        "gate_digest": FROZEN_GATE_DIGEST,
        "evidence_digests": {key: evidence_digests[key] for key in sorted(evidence_digests)},
        "evidence_flags": flags, "adapter_safety": safety,
        "status": value["status"], "evidence_digest": value["evidence_digest"],
        "aggregate_sha256": value["aggregate_sha256"],
    }


def evaluate_readiness(*, evidence_digests: Mapping[str, str], evidence_flags: Mapping[str, bool], adapter_safety: Mapping[str, bool]) -> dict[str, Any]:
    """Produce a synthetic, fail-closed E-006 readiness result."""
    if not isinstance(evidence_digests, Mapping) or set(evidence_digests) != {"e002", "e003", "e004", "e005"}:
        raise RetroBotInputError("E-006 evidence digest map invalid")
    clean_digests = {key: _digest(evidence_digests[key], "evidence digest") for key in sorted(evidence_digests)}
    flags = _bool_map(evidence_flags, FLAG_FIELDS, "evidence flags")
    safety = _bool_map(adapter_safety, SAFETY_FIELDS, "adapter safety")
    # A synthetic scaffold can demonstrate the safety matrix but can never
    # become a demo/canary authorization decision.
    status = "hold-synthetic-only" if not all(flags.values()) or not all(safety.values()) else "hold-synthetic-only"
    evidence_payload = {"gate_digest": FROZEN_GATE_DIGEST, "evidence_digests": clean_digests, "evidence_flags": flags, "adapter_safety": safety}
    result = {
        "schema_version": 1, "case_id": E006_ID, "synthetic_only": True,
        "gate_digest": FROZEN_GATE_DIGEST, "evidence_digests": clean_digests,
        "evidence_flags": flags, "adapter_safety": safety, "status": status,
        "evidence_digest": digest(evidence_payload),
    }
    result["aggregate_sha256"] = digest(result)
    return result


def verify_readiness(value: Mapping[str, Any], *, expected_evidence_digest: str, expected_component_digests: Mapping[str, str]) -> bool:
    clean = _validate_document(value)
    _digest(expected_evidence_digest, "trusted evidence")
    if clean["evidence_digest"] != expected_evidence_digest:
        raise RetroBotInputError("E-006 trusted evidence digest mismatch")
    if not isinstance(expected_component_digests, Mapping) or set(expected_component_digests) != set(clean["evidence_digests"]):
        raise RetroBotInputError("E-006 trusted component digest map invalid")
    for key, item in expected_component_digests.items():
        _digest(item, "trusted component")
        if clean["evidence_digests"][key] != item:
            raise RetroBotInputError("E-006 trusted component digest mismatch")
    expected_evidence = digest({"gate_digest": clean["gate_digest"], "evidence_digests": clean["evidence_digests"], "evidence_flags": clean["evidence_flags"], "adapter_safety": clean["adapter_safety"]})
    if clean["evidence_digest"] != expected_evidence:
        raise RetroBotInputError("E-006 evidence formula mismatch")
    expected_aggregate = digest({key: value[key] for key in value if key != "aggregate_sha256"})
    if value.get("aggregate_sha256") != expected_aggregate:
        raise RetroBotInputError("E-006 aggregate digest mismatch")
    if clean["status"] != "hold-synthetic-only":
        raise RetroBotInputError("E-006 synthetic readiness must remain held")
    if clean["evidence_flags"]["submission_surface_absent"] is not True or clean["adapter_safety"]["dry_run_only"] is not True:
        raise RetroBotInputError("E-006 execution safety boundary invalid")
    assert_firewall_clean([
        value["status"], value["evidence_digest"], value["aggregate_sha256"],
        list(value["evidence_digests"].values()),
        list(value["evidence_flags"].values()),
        list(value["adapter_safety"].values()),
    ])
    return True


def _fixed8(value: object, label: str, *, positive: bool = False) -> Decimal:
    if not isinstance(value, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)\.[0-9]{8}", value):
        raise RetroBotInputError(f"E-006 {label} must be a string")
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise RetroBotInputError(f"E-006 {label} invalid") from exc
    if not parsed.is_finite() or parsed < 0 or (positive and parsed <= 0):
        raise RetroBotInputError(f"E-006 {label} invalid")
    try:
        rounded = parsed.quantize(Decimal("0.00000001"))
    except InvalidOperation as exc:
        raise RetroBotInputError(f"E-006 {label} magnitude invalid") from exc
    if rounded != parsed:
        raise RetroBotInputError(f"E-006 {label} precision invalid")
    return parsed


def validate_limits(limits: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a frozen safety-limit matrix; no transport is involved."""
    if not isinstance(limits, Mapping) or set(limits) != LIMIT_FIELDS:
        raise RetroBotInputError("E-006 safety limits schema invalid")
    clean = {key: limits[key] for key in sorted(limits)}
    clean["max_gross_lots"] = _fixed8(clean["max_gross_lots"], "max gross lots", positive=True)
    clean["max_net_lots"] = _fixed8(clean["max_net_lots"], "max net lots", positive=True)
    for key in ("max_actions", "max_outstanding", "max_retries"):
        if type(clean[key]) is not int or clean[key] < 1:
            raise RetroBotInputError("E-006 integer safety limit invalid")
    if type(clean["max_latency_ms"]) not in (int, float) or isinstance(clean["max_latency_ms"], bool) or clean["max_latency_ms"] <= 0:
        raise RetroBotInputError("E-006 latency limit invalid")
    try:
        finite_latency = float(clean["max_latency_ms"])
    except (OverflowError, ValueError) as exc:
        raise RetroBotInputError("E-006 latency limit invalid") from exc
    if not math.isfinite(finite_latency):
        raise RetroBotInputError("E-006 latency limit invalid")
    return clean


class SafetyAdapterSimulator:
    """Typed intent/ack simulator with zero transport calls.

    This class deliberately cannot connect, submit, or inspect broker state.
    It only exercises idempotency, stop-latch, flatten, and reconnect safety.
    """

    def __init__(self, limits: Mapping[str, Any]):
        self.limits = validate_limits(limits)
        self._intents: dict[str, dict[str, Any]] = {}
        self._sequence = 0
        self._stopped = False
        self._flatten_emitted = False
        self._connection = "connected"
        self._last_snapshot_sequence: int | None = None
        self._last_snapshot_digest: str | None = None
        self._gross_lots = Decimal("0")
        self._net_lots = Decimal("0")
        self._outstanding = 0

    @property
    def transport_calls(self) -> int:
        return 0

    def submit_intent(self, intent: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(intent, Mapping) or set(intent) != INTENT_FIELDS:
            raise RetroBotInputError("E-006 intent schema invalid")
        if self._stopped:
            raise RetroBotInputError("E-006 stop latch blocks new intent")
        if intent["action"] not in {"enter", "exit", "hold"}:
            raise RetroBotInputError("E-006 intent action invalid")
        if not isinstance(intent["intent_id"], str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", intent["intent_id"]):
            raise RetroBotInputError("E-006 intent id invalid")
        if not isinstance(intent["nonce"], str) or not re.fullmatch(r"[A-Za-z0-9_.-]{8,120}", intent["nonce"]):
            raise RetroBotInputError("E-006 intent nonce invalid")
        if type(intent["retry_count"]) is not int or not 0 <= intent["retry_count"] <= self.limits["max_retries"]:
            raise RetroBotInputError("E-006 retry limit exceeded")
        if type(intent["latency_ms"]) not in (int, float) or isinstance(intent["latency_ms"], bool) or intent["latency_ms"] < 0:
            raise RetroBotInputError("E-006 latency limit exceeded")
        try:
            intent_latency = float(intent["latency_ms"])
        except (OverflowError, ValueError) as exc:
            raise RetroBotInputError("E-006 latency limit exceeded") from exc
        if not math.isfinite(intent_latency) or intent_latency > float(self.limits["max_latency_ms"]):
            raise RetroBotInputError("E-006 latency limit exceeded")
        quantity = _fixed8(intent["quantity"], "intent quantity", positive=intent["action"] != "hold")
        _digest(intent["payload_digest"], "intent payload")
        clean = {key: intent[key] for key in sorted(intent)}
        prior = self._intents.get(intent["intent_id"])
        if prior is not None:
            if prior["request"] != clean:
                raise RetroBotInputError("E-006 intent idempotency mutation")
            return dict(prior["receipt"])
        if len(self._intents) >= self.limits["max_actions"]:
            raise RetroBotInputError("E-006 action limit exceeded")
        if self._outstanding >= self.limits["max_outstanding"]:
            raise RetroBotInputError("E-006 outstanding limit exceeded")
        if intent["action"] == "exit" and quantity > self._gross_lots:
            raise RetroBotInputError("E-006 exit exceeds tracked position")
        next_gross = self._gross_lots + quantity if intent["action"] == "enter" else self._gross_lots
        next_net = self._net_lots + quantity if intent["action"] == "enter" else self._net_lots - quantity if intent["action"] == "exit" else self._net_lots
        if next_gross > self.limits["max_gross_lots"] or abs(next_net) > self.limits["max_net_lots"]:
            raise RetroBotInputError("E-006 lot safety limit exceeded")
        if intent["action"] == "enter":
            self._gross_lots = next_gross
        elif intent["action"] == "exit":
            self._gross_lots = max(Decimal("0"), self._gross_lots - quantity)
        self._net_lots = next_net
        self._outstanding += 1
        self._sequence += 1
        receipt = {"sequence": self._sequence, "intent_id": intent["intent_id"], "action": intent["action"], "outstanding": 0, "transport_calls": 0, "receipt_sha256": digest({"sequence": self._sequence, "request": clean})}
        self._outstanding -= 1
        self._intents[intent["intent_id"]] = {"request": clean, "receipt": receipt}
        return dict(receipt)

    def stop(self) -> dict[str, Any]:
        self._stopped = True
        flatten = None
        if not self._flatten_emitted:
            self._flatten_emitted = True
            self._sequence += 1
            flatten = {"sequence": self._sequence, "action": "flatten", "opens": False, "reverses": False, "transport_calls": 0, "receipt_sha256": digest({"sequence": self._sequence, "action": "flatten"})}
        return {"stopped": True, "flatten": flatten}

    def reconnect(self, *, snapshot_digest: str, sequence: int, operator_ack: bool) -> dict[str, Any]:
        _digest(snapshot_digest, "snapshot")
        if self._connection == "connected":
            self._connection = "disconnected"
        if self._connection == "disconnected":
            self._connection = "reconnecting"
        if not operator_ack or type(sequence) is not int or sequence < 0 or snapshot_digest == self._last_snapshot_digest or (self._last_snapshot_sequence is not None and sequence != self._last_snapshot_sequence + 1):
            raise RetroBotInputError("E-006 reconnect recovery is uncertain")
        self._last_snapshot_sequence = sequence
        self._last_snapshot_digest = snapshot_digest
        self._connection = "recovered"
        return {"connection": self._connection, "sequence": sequence, "auto_resume": False, "transport_calls": 0}
