"""Bounded, redacted E-002 evidence intake primitives.

This module accepts only aggregate cycle records. It never accepts source paths,
raw rows, credentials, or order/execution surfaces.
"""
from __future__ import annotations

from decimal import Decimal, Inexact, InvalidOperation, Rounded, localcontext
import math
from typing import Any, Mapping, Sequence

from .retro_bot import RetroBotInputError
from .retro_live_evidence_001 import CASE_ID as E001_ID, canonical_json, digest, load_gate_registry, assert_firewall_clean

E002_ID = "RETRO-LIVE-EVIDENCE-002"
MAX_CYCLES = 10_000
CATEGORIES = frozenset({"normal_hedge", "one_leg_recovery", "monday_gap", "variable_lot", "wide_spread"})
FIELDS = frozenset({"cycle_id", "categories", "action_count", "buy_actions", "sell_actions", "state_matches", "state_checkpoints", "direction_matches", "direction_comparable", "order_matches", "order_comparable", "timing_matches", "timing_comparable", "lot_matches", "lot_comparable", "lot_observed_quantity", "lot_predicted_quantity", "duplicate_actions", "observed_actions", "censored_checkpoints", "eligible_checkpoints", "comparable_checkpoints", "robustness_passes", "robustness_cases", "illegal_transitions", "negative_lots", "same_tick_double_actions", "conservation_failures", "future_reads"})
TOTAL_FIELDS = ("action_count", "buy_actions", "sell_actions", "state_matches", "state_checkpoints", "direction_matches", "direction_comparable", "order_matches", "order_comparable", "timing_matches", "timing_comparable", "lot_matches", "lot_comparable", "duplicate_actions", "observed_actions", "censored_checkpoints", "eligible_checkpoints", "comparable_checkpoints", "robustness_passes", "robustness_cases", "illegal_transitions", "negative_lots", "same_tick_double_actions", "conservation_failures", "future_reads")


def _nonnegative_int(value: object) -> int:
    if type(value) is not int or value < 0:
        raise RetroBotInputError("E-002 count invalid")
    return value


def _quantity(value: object) -> Decimal:
    if not isinstance(value, str):
        raise RetroBotInputError("E-002 quantity must be a string")
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise RetroBotInputError("E-002 quantity invalid") from exc
    if not parsed.is_finite() or parsed < 0:
        raise RetroBotInputError("E-002 quantity invalid")
    try:
        with localcontext() as context:
            context.prec = max(28, len(parsed.as_tuple().digits) + 8)
            context.traps[Inexact] = False
            context.traps[Rounded] = False
            rounded = parsed.quantize(Decimal("0.00000001"))
    except InvalidOperation as exc:
        raise RetroBotInputError("E-002 quantity magnitude invalid") from exc
    if parsed != rounded:
        raise RetroBotInputError("E-002 quantity exceeds fixed8 precision")
    return parsed


def _validate_cycle(value: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != FIELDS or not isinstance(value["cycle_id"], str) or not value["cycle_id"]:
        raise RetroBotInputError("E-002 cycle schema invalid")
    categories = value["categories"]
    if not isinstance(categories, list) or not categories or any(not isinstance(item, str) or item not in CATEGORIES for item in categories) or len(set(categories)) != len(categories):
        raise RetroBotInputError("E-002 cycle categories invalid")
    cleaned = {"cycle_id": value["cycle_id"], "categories": sorted(categories)}
    for field in FIELDS - {"cycle_id", "categories"}:
        cleaned[field] = _quantity(value[field]) if field in {"lot_observed_quantity", "lot_predicted_quantity"} else _nonnegative_int(value[field])
    if cleaned["buy_actions"] + cleaned["sell_actions"] > cleaned["action_count"] or cleaned["action_count"] > cleaned["observed_actions"]:
        raise RetroBotInputError("E-002 cycle action conservation invalid")
    tolerance = max(Decimal("0.00000001"), Decimal("0.01") * cleaned["lot_observed_quantity"])
    if cleaned["lot_observed_quantity"] <= 0 or cleaned["lot_predicted_quantity"] <= 0:
        raise RetroBotInputError("E-002 lot quantities must be positive")
    expected_lot_match = int(abs(cleaned["lot_observed_quantity"] - cleaned["lot_predicted_quantity"]) <= tolerance)
    if cleaned["action_count"] < 1 or cleaned["observed_actions"] < 1 or cleaned["duplicate_actions"] > cleaned["observed_actions"] or cleaned["lot_comparable"] != 1 or cleaned["lot_matches"] != expected_lot_match or cleaned["state_matches"] > cleaned["state_checkpoints"] or cleaned["state_checkpoints"] > cleaned["observed_actions"] or cleaned["direction_matches"] > cleaned["direction_comparable"] or cleaned["direction_comparable"] > cleaned["action_count"] or cleaned["order_matches"] > cleaned["order_comparable"] or cleaned["order_comparable"] > cleaned["action_count"] or cleaned["timing_matches"] > cleaned["timing_comparable"] or cleaned["timing_comparable"] > cleaned["observed_actions"] or cleaned["censored_checkpoints"] > cleaned["eligible_checkpoints"] or cleaned["comparable_checkpoints"] > cleaned["eligible_checkpoints"] or cleaned["censored_checkpoints"] + cleaned["comparable_checkpoints"] != cleaned["eligible_checkpoints"] or cleaned["robustness_passes"] > cleaned["robustness_cases"]:
        raise RetroBotInputError("E-002 cycle numerator exceeds denominator")
    return cleaned


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


def ingest_redacted_cycles(rows: Sequence[Mapping[str, Any]], *, synthetic_only: bool = True) -> dict[str, Any]:
    if synthetic_only is not True:
        raise RetroBotInputError("E-002 raw source intake requires separate authorization")
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)) or len(rows) == 0 or len(rows) > MAX_CYCLES:
        raise RetroBotInputError("E-002 cycle bound invalid")
    cleaned = [_validate_cycle(row) for row in rows]
    if len({row["cycle_id"] for row in cleaned}) != len(cleaned):
        raise RetroBotInputError("E-002 duplicate cycle id")
    totals = {field: sum((row[field] for row in cleaned), Decimal("0")) if field in {"lot_observed_quantity", "lot_predicted_quantity"} else sum(row[field] for row in cleaned) for field in FIELDS - {"cycle_id", "categories", "lot_observed_quantity", "lot_predicted_quantity"}}
    category_counts = {category: sum(category in row["categories"] for row in cleaned) for category in sorted(CATEGORIES)}
    gates = load_gate_registry()["gates"]
    metrics = {
        "state_parity": _ratio(totals["state_matches"], totals["state_checkpoints"]),
        "direction_parity": _ratio(totals["direction_matches"], totals["direction_comparable"]),
        "ordering_parity": _ratio(totals["order_matches"], totals["order_comparable"]),
        "timing_within_band": _ratio(totals["timing_matches"], totals["timing_comparable"]),
        "lot_parity": _ratio(totals["lot_matches"], totals["lot_comparable"]),
        "duplicate_action_rate": _ratio(totals["duplicate_actions"], totals["observed_actions"]),
        "coverage": _ratio(totals["comparable_checkpoints"], totals["eligible_checkpoints"]),
        "censor_rate": _ratio(totals["censored_checkpoints"], totals["eligible_checkpoints"]),
        "state_safety": totals["illegal_transitions"] + totals["negative_lots"] + totals["same_tick_double_actions"] + totals["conservation_failures"] + totals["future_reads"],
        "robustness_pass_fraction": _ratio(totals["robustness_passes"], totals["robustness_cases"]),
        "determinism": False,
    }
    thresholds = {name: gates[name]["threshold"] for name in gates}
    gate_pass = {}
    for name, threshold in thresholds.items():
        value = metrics.get(name)
        if value is None:
            gate_pass[name] = False
        elif gates[name]["direction"] == "ge":
            gate_pass[name] = value >= threshold
        elif gates[name]["direction"] == "le":
            gate_pass[name] = value <= threshold
        else:
            gate_pass[name] = value == threshold
    population = load_gate_registry()["actionful_population"]
    sufficient = len(cleaned) >= population["minimum_total"] and all(category_counts[k] >= v for k, v in population["minimum_categories"].items()) and totals["buy_actions"] >= population["minimum_buy_actions"] and totals["sell_actions"] >= population["minimum_sell_actions"]
    digest_rows = [{**row, "lot_observed_quantity": format(row["lot_observed_quantity"], "f"), "lot_predicted_quantity": format(row["lot_predicted_quantity"], "f")} for row in cleaned]
    result = {"schema_version": 1, "case_id": E002_ID, "parent_case_id": E001_ID, "synthetic_only": True, "source_receipt_present": False, "cycle_count": len(cleaned), "category_counts": category_counts, "totals": {field: totals[field] for field in TOTAL_FIELDS}, "buy_actions": totals["buy_actions"], "sell_actions": totals["sell_actions"], "metrics": metrics, "gate_pass": gate_pass, "actionful_sufficient": sufficient, "status": "package-ready" if sufficient and all(gate_pass.values()) else "insufficient-actionful-coverage" if not sufficient else "no-supported-candidate", "input_digest": digest(digest_rows)}
    result["aggregate_sha256"] = digest(result)
    return result


def component_digest(value: Mapping[str, Any]) -> str:
    return digest({"cycle_count": value.get("cycle_count"), "category_counts": value.get("category_counts"), "totals": value.get("totals")})


def verify_evidence_aggregate(value: Mapping[str, Any], *, expected_input_digest: str | None = None, expected_component_digest: str | None = None) -> bool:
    required = {"schema_version", "case_id", "parent_case_id", "synthetic_only", "source_receipt_present", "cycle_count", "category_counts", "totals", "buy_actions", "sell_actions", "metrics", "gate_pass", "actionful_sufficient", "status", "input_digest", "aggregate_sha256"}
    if not isinstance(value, Mapping) or set(value) != required or value.get("schema_version") != 1 or value.get("case_id") != E002_ID or value.get("parent_case_id") != E001_ID or value.get("synthetic_only") is not True or value.get("source_receipt_present") is not False:
        raise RetroBotInputError("E-002 aggregate identity/firewall invalid")
    if value.get("aggregate_sha256") != digest({key: value[key] for key in value if key != "aggregate_sha256"}):
        raise RetroBotInputError("E-002 aggregate digest mismatch")
    if expected_input_digest is None or expected_component_digest is None or value.get("input_digest") != expected_input_digest or component_digest(value) != expected_component_digest:
        raise RetroBotInputError("E-002 trusted intake digests are required")
    assert_firewall_clean([list(value.get("category_counts", {}).values()), list(value.get("metrics", {}).values()), list(value.get("gate_pass", {}).values())])
    if type(value.get("cycle_count")) is not int or value["cycle_count"] <= 0:
        raise RetroBotInputError("E-002 aggregate values invalid")
    if not isinstance(value.get("category_counts"), Mapping) or set(value["category_counts"]) != set(CATEGORIES) or any(type(item) is not int or item < 0 for item in value["category_counts"].values()):
        raise RetroBotInputError("E-002 category counts invalid")
    if any(value["category_counts"][category] > value["cycle_count"] for category in CATEGORIES):
        raise RetroBotInputError("E-002 category count exceeds cycles")
    if not isinstance(value.get("totals"), Mapping) or set(value["totals"]) != set(TOTAL_FIELDS) or any(type(item) is not int or item < 0 for item in value["totals"].values()):
        raise RetroBotInputError("E-002 aggregate totals invalid")
    if not isinstance(value.get("metrics"), Mapping) or set(value["metrics"]) != {"state_parity", "direction_parity", "ordering_parity", "timing_within_band", "lot_parity", "duplicate_action_rate", "coverage", "censor_rate", "state_safety", "robustness_pass_fraction", "determinism"} or not isinstance(value.get("gate_pass"), Mapping) or set(value["gate_pass"]) != set(load_gate_registry()["gates"]) or any(type(item) is not bool for item in value["gate_pass"].values()):
        raise RetroBotInputError("E-002 aggregate metrics invalid")
    if any(type(value.get(field)) is not int or value[field] < 0 for field in ("buy_actions", "sell_actions")) or value["cycle_count"] > MAX_CYCLES or not isinstance(value.get("input_digest"), str) or len(value["input_digest"]) != 64 or any(char not in "0123456789abcdef" for char in value["input_digest"]):
        raise RetroBotInputError("E-002 aggregate scalar values invalid")
    if value["buy_actions"] != value["totals"]["buy_actions"] or value["sell_actions"] != value["totals"]["sell_actions"]:
        raise RetroBotInputError("E-002 action totals inconsistent")
    if value["status"] not in {"package-ready", "insufficient-actionful-coverage", "no-supported-candidate"} or any((name != "determinism" and (metric is not None and (type(metric) not in (int, float) or isinstance(metric, bool) or not math.isfinite(metric) or metric < 0))) or (name == "determinism" and type(metric) is not bool) for name, metric in value["metrics"].items()):
        raise RetroBotInputError("E-002 aggregate values invalid")
    bounded_metrics = {"state_parity", "direction_parity", "ordering_parity", "timing_within_band", "lot_parity", "duplicate_action_rate", "coverage", "censor_rate", "robustness_pass_fraction"}
    if any(value["metrics"][name] is not None and value["metrics"][name] > 1 for name in bounded_metrics) or type(value["metrics"]["state_safety"]) is not int or value["metrics"]["determinism"] is not False:
        raise RetroBotInputError("E-002 metric bounds invalid")
    gates = load_gate_registry()["gates"]
    totals = value["totals"]
    expected_metrics = {"state_parity": _ratio(totals["state_matches"], totals["state_checkpoints"]), "direction_parity": _ratio(totals["direction_matches"], totals["direction_comparable"]), "ordering_parity": _ratio(totals["order_matches"], totals["order_comparable"]), "timing_within_band": _ratio(totals["timing_matches"], totals["timing_comparable"]), "lot_parity": _ratio(totals["lot_matches"], totals["lot_comparable"]), "duplicate_action_rate": _ratio(totals["duplicate_actions"], totals["observed_actions"]), "coverage": _ratio(totals["comparable_checkpoints"], totals["eligible_checkpoints"]), "censor_rate": _ratio(totals["censored_checkpoints"], totals["eligible_checkpoints"]), "state_safety": totals["illegal_transitions"] + totals["negative_lots"] + totals["same_tick_double_actions"] + totals["conservation_failures"] + totals["future_reads"], "robustness_pass_fraction": _ratio(totals["robustness_passes"], totals["robustness_cases"]), "determinism": value["metrics"]["determinism"]}
    if value["metrics"] != expected_metrics:
        raise RetroBotInputError("E-002 metrics are inconsistent with totals")
    expected_pass = {name: (value["metrics"][name] is not None and ((value["metrics"][name] >= gate["threshold"]) if gate["direction"] == "ge" else (value["metrics"][name] <= gate["threshold"]) if gate["direction"] == "le" else value["metrics"][name] == gate["threshold"])) for name, gate in gates.items()}
    if dict(value["gate_pass"]) != expected_pass:
        raise RetroBotInputError("E-002 gate results inconsistent")
    population = load_gate_registry()["actionful_population"]
    sufficient = value["cycle_count"] >= population["minimum_total"] and all(value["category_counts"].get(key, 0) >= threshold for key, threshold in population["minimum_categories"].items()) and value["buy_actions"] >= population["minimum_buy_actions"] and value["sell_actions"] >= population["minimum_sell_actions"]
    if value["actionful_sufficient"] is not sufficient:
        raise RetroBotInputError("E-002 actionful sufficiency inconsistent")
    expected_status = "package-ready" if sufficient and all(expected_pass.values()) else "insufficient-actionful-coverage" if not sufficient else "no-supported-candidate"
    if value["status"] != expected_status:
        raise RetroBotInputError("E-002 status inconsistent")
    return True
