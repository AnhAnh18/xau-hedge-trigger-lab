"""Redacted fidelity and holdout evaluators for the evidence lane.

Inputs are aggregate comparison records only. No raw timelines or source
paths are accepted; real capture remains separately authorized.
"""
from __future__ import annotations

from decimal import Decimal, Inexact, InvalidOperation, Rounded, localcontext
import math
import re
from typing import Any, Mapping, Sequence

from .retro_bot import RetroBotInputError
from .retro_live_evidence_001 import FROZEN_GATE_DIGEST, canonical_json, digest, load_gate_registry, assert_firewall_clean

E003_ID = "RETRO-LIVE-EVIDENCE-003"
MAX_COMPARISONS = 100_000
FIELDS = frozenset({"comparison_id", "categories", "buy_actions", "sell_actions", "observed_actions", "state_match", "direction_match", "ordering_match", "timing_delta_seconds", "lot_observed_quantity", "lot_predicted_quantity", "duplicate_actions", "eligible", "censored", "future_read", "illegal_transition", "negative_lots", "same_tick_double_actions", "conservation_failures"})
CATEGORIES = frozenset({"normal_hedge", "one_leg_recovery", "monday_gap", "variable_lot", "wide_spread"})


def _lot(value: object) -> Decimal:
    if not isinstance(value, str):
        raise RetroBotInputError("E-003 lot must be a string")
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise RetroBotInputError("E-003 lot invalid") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise RetroBotInputError("E-003 lot invalid")
    try:
        with localcontext() as context:
            context.prec = max(28, len(parsed.as_tuple().digits) + 8)
            context.traps[Inexact] = False; context.traps[Rounded] = False
            rounded = parsed.quantize(Decimal("0.00000001"))
    except InvalidOperation as exc:
        raise RetroBotInputError("E-003 lot magnitude invalid") from exc
    if parsed != rounded:
        raise RetroBotInputError("E-003 lot precision invalid")
    return parsed


def _comparison(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != FIELDS or not isinstance(value["comparison_id"], str) or not value["comparison_id"]:
        raise RetroBotInputError("E-003 comparison schema invalid")
    if not isinstance(value["categories"], list) or any(item not in CATEGORIES for item in value["categories"]):
        raise RetroBotInputError("E-003 comparison categories invalid")
    if any(type(value[key]) is not bool for key in ("state_match", "direction_match", "ordering_match", "eligible", "censored", "future_read", "illegal_transition")):
        raise RetroBotInputError("E-003 comparison boolean invalid")
    if value["censored"] and not value["eligible"]:
        raise RetroBotInputError("E-003 censored comparison is not eligible")
    if any(type(value[key]) is not int or value[key] < 0 for key in ("buy_actions", "sell_actions", "observed_actions", "timing_delta_seconds", "duplicate_actions", "negative_lots", "same_tick_double_actions", "conservation_failures")):
        raise RetroBotInputError("E-003 comparison counts invalid")
    if value["observed_actions"] < 1 or value["buy_actions"] + value["sell_actions"] > value["observed_actions"] or value["duplicate_actions"] > value["observed_actions"]:
        raise RetroBotInputError("E-003 action counts invalid")
    observed, predicted = _lot(value["lot_observed_quantity"]), _lot(value["lot_predicted_quantity"])
    return {**value, "lot_observed_quantity": observed, "lot_predicted_quantity": predicted}


def evaluate_fidelity(rows: Sequence[Mapping[str, Any]], *, synthetic_only: bool = True) -> dict[str, Any]:
    if synthetic_only is not True:
        raise RetroBotInputError("E-003 source evaluation requires separate authorization")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or not rows or len(rows) > MAX_COMPARISONS:
        raise RetroBotInputError("E-003 comparison bound invalid")
    clean = [_comparison(row) for row in rows]
    if len({row["comparison_id"] for row in clean}) != len(clean):
        raise RetroBotInputError("E-003 duplicate comparison id")
    eligible = [row for row in clean if row["eligible"]]
    comparable = [row for row in eligible if not row["censored"]]
    threshold = load_gate_registry()["gates"]
    category_counts = {category: sum(category in row["categories"] for row in eligible) for category in ("normal_hedge", "one_leg_recovery", "monday_gap", "variable_lot", "wide_spread")}
    population = load_gate_registry()["actionful_population"]
    sufficient = len(eligible) >= population["minimum_total"] and all(category_counts[key] >= value for key, value in population["minimum_categories"].items()) and sum(row["buy_actions"] for row in eligible) >= population["minimum_buy_actions"] and sum(row["sell_actions"] for row in eligible) >= population["minimum_sell_actions"]
    quantities = [row for row in comparable]
    lot_matches = sum(abs(row["lot_observed_quantity"] - row["lot_predicted_quantity"]) <= max(Decimal("0.00000001"), Decimal("0.01") * row["lot_observed_quantity"]) for row in quantities)
    metrics = {"state_parity": sum(row["state_match"] for row in comparable) / len(comparable) if comparable else None, "direction_parity": sum(row["direction_match"] for row in comparable) / len(comparable) if comparable else None, "ordering_parity": sum(row["ordering_match"] for row in comparable) / len(comparable) if comparable else None, "timing_within_band": sum(row["timing_delta_seconds"] <= 5 for row in comparable) / len(comparable) if comparable else None, "lot_parity": lot_matches / len(quantities) if quantities else None, "duplicate_action_rate": sum(row["duplicate_actions"] for row in clean) / sum(row["observed_actions"] for row in clean) if clean else None, "coverage": len(comparable) / len(eligible) if eligible else None, "censor_rate": sum(row["censored"] for row in eligible) / len(eligible) if eligible else None, "state_safety": sum(row["future_read"] or row["illegal_transition"] or row["negative_lots"] or row["same_tick_double_actions"] or row["conservation_failures"] for row in clean), "robustness_pass_fraction": None, "determinism": False}
    gate_pass = {}
    for name, gate in threshold.items():
        metric = metrics[name]
        gate_pass[name] = False if metric is None else metric >= gate["threshold"] if gate["direction"] == "ge" else metric <= gate["threshold"] if gate["direction"] == "le" else metric == gate["threshold"]
    result = {"schema_version": 1, "case_id": E003_ID, "synthetic_only": True, "unit": "action_checkpoint", "comparison_count": len(clean), "eligible_count": len(eligible), "comparable_count": len(comparable), "category_counts": category_counts, "buy_actions": sum(row["buy_actions"] for row in eligible), "sell_actions": sum(row["sell_actions"] for row in eligible), "actionful_sufficient": sufficient, "metrics": metrics, "gate_pass": gate_pass, "status": "insufficient-actionful-coverage" if not sufficient else "no-supported-candidate" if not all(gate_pass.values()) else "package-ready", "input_digest": digest([{**row, "lot_observed_quantity": format(row["lot_observed_quantity"], "f"), "lot_predicted_quantity": format(row["lot_predicted_quantity"], "f")} for row in clean])}
    result["aggregate_sha256"] = digest(result)
    return result


def verify_fidelity_aggregate(value: Mapping[str, Any]) -> bool:
    required = {"schema_version", "case_id", "synthetic_only", "unit", "comparison_count", "eligible_count", "comparable_count", "category_counts", "buy_actions", "sell_actions", "actionful_sufficient", "metrics", "gate_pass", "status", "input_digest", "aggregate_sha256"}
    if not isinstance(value, Mapping) or set(value) != required or value.get("schema_version") != 1 or value.get("case_id") != E003_ID or value.get("synthetic_only") is not True or value.get("unit") != "action_checkpoint":
        raise RetroBotInputError("E-003 aggregate schema invalid")
    if value.get("aggregate_sha256") != digest({key: value[key] for key in value if key != "aggregate_sha256"}):
        raise RetroBotInputError("E-003 aggregate digest mismatch")
    if any(type(value.get(key)) is not int or value[key] < 0 for key in ("comparison_count", "eligible_count", "comparable_count", "buy_actions", "sell_actions")) or value["comparable_count"] > value["eligible_count"] or value["eligible_count"] > value["comparison_count"]:
        raise RetroBotInputError("E-003 aggregate counts invalid")
    if not isinstance(value.get("category_counts"), Mapping) or set(value["category_counts"]) != {"normal_hedge", "one_leg_recovery", "monday_gap", "variable_lot", "wide_spread"} or any(type(item) is not int or item < 0 or item > value["eligible_count"] for item in value["category_counts"].values()):
        raise RetroBotInputError("E-003 category counts invalid")
    if not isinstance(value.get("metrics"), Mapping) or set(value["metrics"]) != {"state_parity", "direction_parity", "ordering_parity", "timing_within_band", "lot_parity", "duplicate_action_rate", "coverage", "censor_rate", "state_safety", "robustness_pass_fraction", "determinism"} or any((key not in {"determinism", "state_safety"} and metric is not None and (type(metric) not in (int, float) or isinstance(metric, bool) or not math.isfinite(metric) or metric < 0 or metric > 1)) or (key == "state_safety" and (type(metric) is not int or metric < 0)) or (key == "determinism" and type(metric) is not bool) for key, metric in value["metrics"].items()) or not isinstance(value.get("gate_pass"), Mapping) or set(value["gate_pass"]) != set(load_gate_registry()["gates"]) or any(type(item) is not bool for item in value["gate_pass"].values()):
        raise RetroBotInputError("E-003 aggregate metrics invalid")
    if not isinstance(value.get("input_digest"), str) or not re.fullmatch(r"[0-9a-f]{64}", value["input_digest"]):
        raise RetroBotInputError("E-003 input digest invalid")
    gates = load_gate_registry()["gates"]
    expected_pass = {name: (value["metrics"][name] is not None and ((value["metrics"][name] >= gate["threshold"]) if gate["direction"] == "ge" else (value["metrics"][name] <= gate["threshold"]) if gate["direction"] == "le" else value["metrics"][name] == gate["threshold"])) for name, gate in gates.items()}
    if dict(value["gate_pass"]) != expected_pass:
        raise RetroBotInputError("E-003 gate results inconsistent")
    population = load_gate_registry()["actionful_population"]
    sufficient = value["eligible_count"] >= population["minimum_total"] and all(value["category_counts"][key] >= threshold for key, threshold in population["minimum_categories"].items()) and value["buy_actions"] >= population["minimum_buy_actions"] and value["sell_actions"] >= population["minimum_sell_actions"]
    if value["actionful_sufficient"] is not sufficient or value["status"] != ("insufficient-actionful-coverage" if not sufficient else "no-supported-candidate" if not all(expected_pass.values()) else "package-ready"):
        raise RetroBotInputError("E-003 status inconsistent")
    assert_firewall_clean([list(value["category_counts"].values()), list(value["metrics"].values()), list(value["gate_pass"].values())])
    return True


def _validate_fold_bounds(bounds: Sequence[Sequence[int]]) -> str:
    if not isinstance(bounds, Sequence) or len(bounds) != 3 or any(not isinstance(item, Sequence) or len(item) != 2 or any(type(v) is not int for v in item) or item[0] >= item[1] for item in bounds):
        raise RetroBotInputError("E-004 fold bounds invalid")
    if any(bounds[index][1] > bounds[index + 1][0] for index in range(2)):
        raise RetroBotInputError("E-004 fold bounds overlap/out of order")
    return digest([[int(v) for v in item] for item in bounds])


def seal_holdout_block(*, gate_digest: str, source_digest: str, input_digest: str, nonce: str, fold_order_digest: str | None = None, fold_bounds_digest: str | None = None) -> dict[str, str]:
    fold_order_digest = fold_order_digest or digest(["development", "validation", "holdout"])
    fold_bounds_digest = fold_bounds_digest or _validate_fold_bounds([[0, 1], [1, 2], [2, 3]])
    if gate_digest != FROZEN_GATE_DIGEST or any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value) for value in (source_digest, input_digest, fold_order_digest, fold_bounds_digest)) or not isinstance(nonce, str) or len(nonce) < 8 or any(char in nonce for char in "\\/\r\n"):
        raise RetroBotInputError("E-004 holdout binding invalid")
    payload = {"gate_digest": gate_digest, "source_digest": source_digest, "input_digest": input_digest, "fold_order_digest": fold_order_digest, "fold_bounds_digest": fold_bounds_digest, "nonce": nonce}
    return {**payload, "receipt_sha256": digest(payload)}


def verify_holdout_block(receipt: Mapping[str, str], *, used_nonces: set[str]) -> bool:
    if not isinstance(receipt, Mapping) or set(receipt) != {"gate_digest", "source_digest", "input_digest", "fold_order_digest", "fold_bounds_digest", "nonce", "receipt_sha256"} or not isinstance(receipt.get("nonce"), str) or receipt["nonce"] in used_nonces:
        raise RetroBotInputError("E-004 holdout receipt invalid/reused")
    expected = seal_holdout_block(gate_digest=receipt["gate_digest"], source_digest=receipt["source_digest"], input_digest=receipt["input_digest"], fold_order_digest=receipt["fold_order_digest"], fold_bounds_digest=receipt["fold_bounds_digest"], nonce=receipt["nonce"])
    if dict(receipt) != expected:
        raise RetroBotInputError("E-004 holdout receipt tampered")
    used_nonces.add(receipt["nonce"])
    return True


def evaluate_holdout(*, development: Mapping[str, Any], validation: Mapping[str, Any], holdout: Mapping[str, Any], receipt: Mapping[str, str], used_nonces: set[str], robustness_results: Sequence[bool], trusted_source_receipt_digest: str, fold_bounds: Sequence[Sequence[int]], trusted_fold_order_digest: str | None = None, trusted_fold_bounds_digest: str | None = None) -> dict[str, Any]:
    """Evaluate a sealed synthetic holdout without selecting or retuning a rule."""
    for aggregate in (development, validation, holdout):
        verify_fidelity_aggregate(aggregate)
    if len({development["input_digest"], validation["input_digest"], holdout["input_digest"]}) != 3:
        raise RetroBotInputError("E-004 fold inputs overlap")
    expected_order_digest = trusted_fold_order_digest or digest(["development", "validation", "holdout"])
    actual_bounds_digest = _validate_fold_bounds(fold_bounds)
    expected_bounds_digest = trusted_fold_bounds_digest or actual_bounds_digest
    if receipt.get("fold_order_digest") != expected_order_digest:
        raise RetroBotInputError("E-004 fold order is not trusted")
    if receipt.get("fold_bounds_digest") != expected_bounds_digest or actual_bounds_digest != expected_bounds_digest:
        raise RetroBotInputError("E-004 fold chronology is not trusted")
    if receipt.get("source_digest") != trusted_source_receipt_digest or not re.fullmatch(r"[0-9a-f]{64}", trusted_source_receipt_digest):
        raise RetroBotInputError("E-004 source receipt is not trusted")
    if receipt.get("input_digest") != holdout["input_digest"]:
        raise RetroBotInputError("E-004 receipt is not bound to holdout")
    if not isinstance(robustness_results, Sequence) or isinstance(robustness_results, (str, bytes)) or not robustness_results or any(type(item) is not bool for item in robustness_results):
        raise RetroBotInputError("E-004 robustness results invalid")
    verify_holdout_block(receipt, used_nonces=used_nonces)
    robustness_fraction = sum(robustness_results) / len(robustness_results)
    all_actionful = all(item["actionful_sufficient"] for item in (development, validation, holdout))
    all_gates = all(all(item["gate_pass"].values()) for item in (development, validation, holdout))
    status = "hold" if not all_actionful or not all_gates or robustness_fraction < load_gate_registry()["gates"]["robustness_pass_fraction"]["threshold"] else "descriptive-only"
    result = {"schema_version": 1, "case_id": "RETRO-LIVE-EVIDENCE-004", "synthetic_only": True, "holdout_consumed": True, "development_digest": development["input_digest"], "validation_digest": validation["input_digest"], "holdout_digest": holdout["input_digest"], "robustness_pass_fraction": robustness_fraction, "robustness_count": len(robustness_results), "fold_order_digest": receipt["fold_order_digest"], "fold_bounds_digest": receipt["fold_bounds_digest"], "source_receipt_digest": receipt["source_digest"], "status": status, "receipt_sha256": receipt["receipt_sha256"]}
    result["aggregate_sha256"] = digest(result)
    return result


def verify_holdout_result(value: Mapping[str, Any]) -> bool:
    required = {"schema_version", "case_id", "synthetic_only", "holdout_consumed", "development_digest", "validation_digest", "holdout_digest", "robustness_pass_fraction", "robustness_count", "fold_order_digest", "fold_bounds_digest", "source_receipt_digest", "status", "receipt_sha256", "aggregate_sha256"}
    if not isinstance(value, Mapping) or set(value) != required or value.get("schema_version") != 1 or value.get("case_id") != "RETRO-LIVE-EVIDENCE-004" or value.get("synthetic_only") is not True or value.get("holdout_consumed") is not True:
        raise RetroBotInputError("E-004 result schema invalid")
    if value["aggregate_sha256"] != digest({key: value[key] for key in value if key != "aggregate_sha256"}):
        raise RetroBotInputError("E-004 result digest mismatch")
    for key in ("development_digest", "validation_digest", "holdout_digest", "fold_order_digest", "fold_bounds_digest", "source_receipt_digest", "receipt_sha256"):
        if not isinstance(value[key], str) or not re.fullmatch(r"[0-9a-f]{64}", value[key]):
            raise RetroBotInputError("E-004 result digest invalid")
    if len({value["development_digest"], value["validation_digest"], value["holdout_digest"]}) != 3 or type(value["robustness_count"]) is not int or value["robustness_count"] < 1 or type(value["robustness_pass_fraction"]) not in (int, float) or not math.isfinite(value["robustness_pass_fraction"]) or not 0 <= value["robustness_pass_fraction"] <= 1 or value["status"] not in {"hold", "descriptive-only"}:
        raise RetroBotInputError("E-004 result values invalid")
    # The case identifier is governance metadata and intentionally contains
    # the word "live"; validate data-bearing fields only.
    assert_firewall_clean([value[key] for key in value if key not in {"case_id"}])
    return True
