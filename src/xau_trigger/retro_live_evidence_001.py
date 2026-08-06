"""Governance-only validators for RETRO-LIVE-EVIDENCE E-001.

No filesystem source access, realtime feed, MT5 API, or order surface is
exposed here. Validators operate on synthetic or already-redacted mappings.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

from .retro_bot import RetroBotInputError

CASE_ID = "RETRO-LIVE-EVIDENCE-001"
ROOT = Path(__file__).resolve().parents[2]
GATES_PATH = ROOT / "docs" / "retro_live_evidence" / "RETRO-LIVE-EVIDENCE-001-gates.json"
FROZEN_GATE_DIGEST = "4b10421035cdd6920c0d044f521c6ebf78384c588b02d15798299eedc960920d"
FORBIDDEN_TERMS = ("credential", "password", "secret", "private", "raw", "journal", "deal", "fee", "profit", "ticket", "ex5", "m5", "mt5", "order", "realtime", "live", "demo", "canary")


def canonical_json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RetroBotInputError("E-001 canonical JSON is invalid") from exc


def parse_unique_json(text: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise RetroBotInputError("E-001 duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("non-finite")))
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise RetroBotInputError("E-001 JSON is invalid") from exc


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def load_gate_registry() -> dict[str, Any]:
    try:
        value = json.loads(GATES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RetroBotInputError("E-001 gate registry unavailable") from exc
    validate_gate_registry(value)
    return value


def validate_gate_registry(value: Mapping[str, Any]) -> bool:
    if not isinstance(value, Mapping) or value.get("schema_version") != 1 or value.get("case_id") != CASE_ID:
        raise RetroBotInputError("E-001 gate registry identity invalid")
    if value.get("status") != "frozen-before-E002" or value.get("m5_firewall") != "RETRO_ONLY_NO_M5_CONTAMINATION":
        raise RetroBotInputError("E-001 gate registry is not frozen/firewalled")
    if digest(value) != FROZEN_GATE_DIGEST:
        raise RetroBotInputError("E-001 gate registry digest mismatch")
    timezone = value.get("timezone")
    if timezone != {"canonical": "UTC RFC3339 microseconds", "hypotheses": ["UTC+2 winter", "UTC+3 summer"], "ambiguous_action": "censor"}:
        raise RetroBotInputError("E-001 timezone policy invalid")
    population = value.get("actionful_population")
    if not isinstance(population, Mapping) or population.get("minimum_total") != 30 or population.get("minimum_buy_actions") != 10 or population.get("minimum_sell_actions") != 10 or population.get("minimum_categories") != {"normal_hedge": 8, "one_leg_recovery": 6, "monday_gap": 4, "variable_lot": 6, "wide_spread": 4} or population.get("gap_threshold_xau") != 0.5:
        raise RetroBotInputError("E-001 actionful target invalid")
    gates = value.get("gates")
    if not isinstance(gates, Mapping) or set(gates) != {"state_parity", "direction_parity", "ordering_parity", "timing_within_band", "lot_parity", "duplicate_action_rate", "coverage", "censor_rate", "state_safety", "robustness_pass_fraction", "determinism"}:
        raise RetroBotInputError("E-001 gate set invalid")
    expected_formulas = {"state_parity": "matching_state_checkpoints/eligible_state_checkpoints", "direction_parity": "matching_direction_actions/comparable_direction_actions", "ordering_parity": "cycles_with_matching_action_order/comparable_cycles", "timing_within_band": "actions_abs_delta_le_5s/comparable_actions", "lot_parity": "quantities_abs_delta_le_max_1e-8_or_1pct/comparable_quantities", "duplicate_action_rate": "duplicate_actions/observed_actions", "coverage": "comparable_checkpoints/eligible_checkpoints", "censor_rate": "censored_checkpoints/eligible_checkpoints", "state_safety": "zero_illegal_transitions_negative_lots_same_tick_double_actions_conservation_failures_future_reads", "robustness_pass_fraction": "passing_registered_perturbations/registered_perturbations", "determinism": "two_independent_runs_byte_identical"}
    for name, gate in gates.items():
        if not isinstance(gate, Mapping) or not isinstance(gate.get("formula"), str) or gate.get("direction") not in {"ge", "le", "eq"} or "threshold" not in gate:
            raise RetroBotInputError(f"E-001 gate {name} invalid")
        if gate.get("formula") != expected_formulas[name]:
            raise RetroBotInputError(f"E-001 gate {name} formula is not frozen")
    expected = {"state_parity": 0.9, "direction_parity": 0.85, "ordering_parity": 0.9, "timing_within_band": 0.8, "lot_parity": 0.95, "duplicate_action_rate": 0.01, "coverage": 0.8, "censor_rate": 0.2, "state_safety": 0, "robustness_pass_fraction": 0.75, "determinism": True}
    if {name: gates[name]["threshold"] for name in expected} != expected:
        raise RetroBotInputError("E-001 gate thresholds are not frozen")
    if value.get("result_taxonomy") != ["package-ready", "behaviorally-compatible-accounting-inconclusive", "insufficient-actionful-coverage", "no-supported-candidate"] or value.get("retention") != "redacted-aggregates-and-digests-only":
        raise RetroBotInputError("E-001 result taxonomy/retention invalid")
    return True


def validate_synthetic_receipt(value: Mapping[str, Any]) -> bool:
    required = {"authorization_id", "source_aliases", "object_types", "sha256_by_alias", "population_utc_half_open", "allowed_fields", "canonicalization_version", "parser_version", "retention", "receipt_sha256"}
    if not isinstance(value, Mapping) or set(value) != required or value.get("authorization_id") != "E001-SYNTHETIC-ONLY":
        raise RetroBotInputError("E-001 synthetic receipt schema invalid")
    if value.get("source_aliases") != [] or value.get("object_types") != [] or value.get("sha256_by_alias") != {} or value.get("retention") != "redacted-aggregates-and-digests-only":
        raise RetroBotInputError("E-001 synthetic receipt boundary invalid")
    timestamps = value.get("population_utc_half_open")
    if not isinstance(timestamps, list) or len(timestamps) != 2 or any(not isinstance(item, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z", item) for item in timestamps) or timestamps[0] >= timestamps[1]:
        raise RetroBotInputError("E-001 synthetic receipt population invalid")
    if not isinstance(value.get("object_types"), list) or not isinstance(value.get("allowed_fields"), Mapping) or not isinstance(value.get("canonicalization_version"), str) or not isinstance(value.get("parser_version"), str):
        raise RetroBotInputError("E-001 synthetic receipt types invalid")
    payload = dict(value); receipt = payload.pop("receipt_sha256")
    if not isinstance(receipt, str) or receipt != digest(payload):
        raise RetroBotInputError("E-001 synthetic receipt digest invalid")
    return True


def assert_firewall_clean(value: object) -> bool:
    def check_text(text: str) -> None:
        lowered = text.lower()
        if any(term in lowered for term in FORBIDDEN_TERMS) or re.search(r"(?:^[A-Za-z]:[\\/]|^[\\/]{2}|^[\\/]|%[A-Za-z_]+%|\\\\)", text):
            raise RetroBotInputError("E-001 forbidden firewall content")
    def walk(node: object) -> None:
        if isinstance(node, Mapping):
            for key, child in node.items():
                check_text(str(key))
                walk(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                walk(child)
        elif isinstance(node, str):
            check_text(node)
    walk(value)
    return True


def seal_holdout_receipt(*, gate_digest: str, source_digest: str, holdout_digest: str, nonce: str) -> dict[str, str]:
    if not isinstance(nonce, str) or len(nonce) < 8 or any(char in nonce for char in "\\/\r\n"):
        raise RetroBotInputError("E-001 holdout nonce invalid")
    if gate_digest != FROZEN_GATE_DIGEST or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in (source_digest, holdout_digest)):
        raise RetroBotInputError("E-001 holdout digest binding invalid")
    payload = {"gate_digest": gate_digest, "source_digest": source_digest, "holdout_digest": holdout_digest, "nonce": nonce}
    return {**payload, "receipt_sha256": digest(payload)}


def verify_holdout_receipt(receipt: Mapping[str, str], *, used_nonces: set[str] | None = None) -> bool:
    required = {"gate_digest", "source_digest", "holdout_digest", "nonce", "receipt_sha256"}
    if not isinstance(receipt, Mapping) or set(receipt) != required:
        raise RetroBotInputError("E-001 holdout receipt schema invalid")
    if used_nonces is None:
        raise RetroBotInputError("E-001 holdout nonce ledger is required")
    if receipt["nonce"] in used_nonces:
        raise RetroBotInputError("E-001 holdout receipt reused")
    expected = seal_holdout_receipt(gate_digest=receipt["gate_digest"], source_digest=receipt["source_digest"], holdout_digest=receipt["holdout_digest"], nonce=receipt["nonce"])
    if dict(receipt) != expected:
        raise RetroBotInputError("E-001 holdout receipt tampered")
    return True


def assert_oracle_isolated(autonomous: Mapping[str, Any], oracle: Mapping[str, Any]) -> bool:
    if not isinstance(autonomous, Mapping) or not isinstance(oracle, Mapping):
        raise RetroBotInputError("E-001 lane inputs invalid")
    forbidden = {"observed_events", "oracle_labels", "outcomes", "profit", "fees"}
    def walk(node: object) -> None:
        if isinstance(node, Mapping):
            if any(str(key).lower() in forbidden for key in node):
                raise RetroBotInputError("E-001 oracle field entered autonomous lane")
            for child in node.values():
                walk(child)
        elif isinstance(node, (list, tuple)):
            for child in node:
                walk(child)
    walk(autonomous)
    return True
