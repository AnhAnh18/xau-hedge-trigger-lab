"""RETRO-BOT-006 causal feature snapshot and frozen rule DSL."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Mapping
from types import MappingProxyType

import pandas as pd

from .retro_bot import RetroBotInputError


CASE_ID = "RETRO-BOT-006"
RB008_CONFIG_SHA256 = "26fec4baa2b8e2680cc17afaad299bbbb00afba32810865ac60bf28eb2e49ebf"
REPORT_MANIFEST_SHA256 = "88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30"
TICK_MANIFEST_SHA256 = "a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c"
M5_FIREWALL_ATTESTATION = "not_an_M5_input; descriptive RETRO only"
NUMERIC_FEATURES = frozenset({"state_age_seconds", "price_increment", "adverse_excursion", "spread_points", "tick_rate", "quote_gap_seconds"})
CATEGORICAL_FEATURES = frozenset({"session_bucket", "clock_id", "state", "side"})
ALLOWED_FEATURES = frozenset(NUMERIC_FEATURES | CATEGORICAL_FEATURES)
NUMERIC_GRID = frozenset({0, 1, 5, 10, 60, 300, 900, 3600})
CATEGORICAL_VALUES = MappingProxyType({
    "session_bucket": frozenset({"asia", "europe", "us"}),
    "clock_id": frozenset({"utc_plus_2", "utc_plus_3", "eu_dst_2025_2026"}),
    "state": frozenset({"HEDGED", "ONE_BUY", "ONE_SELL"}),
    "side": frozenset({"buy", "sell"}),
})
OPERATORS = frozenset({"always", "never", "ge", "gt", "le", "lt", "between"})


@dataclass(frozen=True)
class FeatureSnapshot:
    decision_time: pd.Timestamp
    values: Mapping[str, object]
    oracle_labels: tuple[object, ...] = ()
    feature_times: Mapping[str, pd.Timestamp] | None = None


@dataclass(frozen=True)
class RuleClause:
    feature: str
    operator: str
    lower: object | None = None
    upper: object | None = None


@dataclass(frozen=True)
class TriggerRule:
    rule_id: str
    clauses: tuple[RuleClause, ...]
    candidate_kind: str


def _time(value: object) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError, pd.errors.OutOfBoundsDatetime) as error:
        raise RetroBotInputError("RB-010 decision time is invalid") from error
    if pd.isna(timestamp):
        raise RetroBotInputError("RB-010 decision time is invalid")
    return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")


def validate_snapshot(snapshot: FeatureSnapshot) -> FeatureSnapshot:
    decision = _time(snapshot.decision_time)
    if snapshot.oracle_labels:
        raise RetroBotInputError("RB-010 oracle labels are diagnostic-only")
    if not isinstance(snapshot.values, Mapping) or set(snapshot.values) - ALLOWED_FEATURES:
        raise RetroBotInputError("RB-010 feature allowlist violation")
    feature_times = snapshot.feature_times
    if feature_times is None:
        feature_times = {}
    if not isinstance(feature_times, Mapping) or set(feature_times) - set(snapshot.values):
        raise RetroBotInputError("RB-010 feature provenance is invalid")
    for feature, raw_time in feature_times.items():
        feature_time = _time(raw_time)
        if feature_time > decision:
            raise RetroBotInputError("RB-010 future feature is not causal")
    for feature, value in snapshot.values.items():
        if feature in NUMERIC_FEATURES:
            if type(value) not in (int, float) or isinstance(value, bool):
                raise RetroBotInputError("RB-010 numeric feature is invalid")
        elif value not in CATEGORICAL_VALUES[feature]:
            raise RetroBotInputError("RB-010 categorical feature is invalid")
    return FeatureSnapshot(decision, MappingProxyType(dict(snapshot.values)), tuple(snapshot.oracle_labels), MappingProxyType(dict(feature_times)))


def validate_rule(rule: TriggerRule) -> None:
    if not isinstance(rule, TriggerRule) or not isinstance(rule.rule_id, str) or not rule.rule_id or not isinstance(rule.candidate_kind, str) or not isinstance(rule.clauses, tuple) or len(rule.clauses) > 3:
        raise RetroBotInputError("RB-010 rule schema is invalid")
    for clause in rule.clauses:
        if not isinstance(clause, RuleClause):
            raise RetroBotInputError("RB-010 rule clause schema is invalid")
        if clause.feature not in ALLOWED_FEATURES or clause.operator not in OPERATORS:
            raise RetroBotInputError("RB-010 rule feature/operator is invalid")
        if clause.operator in {"always", "never"}:
            if clause.lower is not None or clause.upper is not None:
                raise RetroBotInputError("RB-010 parameterless operator has parameters")
            continue
        if clause.feature in CATEGORICAL_FEATURES and clause.operator != "between":
            raise RetroBotInputError("RB-010 rule operator/domain combination is invalid")
        if clause.feature in NUMERIC_FEATURES and clause.operator not in {"ge", "gt", "le", "lt", "between"}:
            raise RetroBotInputError("RB-010 rule operator/domain combination is invalid")
        values = (clause.lower, clause.upper) if clause.operator == "between" else (clause.lower,)
        allowed = CATEGORICAL_VALUES[clause.feature] if clause.feature in CATEGORICAL_FEATURES else NUMERIC_GRID
        if any(type(value) is bool or value not in allowed for value in values):
            raise RetroBotInputError("RB-010 rule parameter is outside frozen grid")
        if clause.operator == "between" and clause.lower > clause.upper:
            raise RetroBotInputError("RB-010 between bounds are reversed")
        if clause.feature in CATEGORICAL_FEATURES and clause.lower != clause.upper:
            raise RetroBotInputError("RB-010 categorical between requires equal bounds")


def evaluate_rule(snapshot: FeatureSnapshot, rule: TriggerRule) -> str:
    snapshot = validate_snapshot(snapshot)
    validate_rule(rule)
    missing = [clause.feature for clause in rule.clauses if clause.feature not in snapshot.values]
    invalid = []
    for feature, value in snapshot.values.items():
        if feature not in NUMERIC_FEATURES:
            continue
        try:
            finite = math.isfinite(float(value))
        except (OverflowError, ValueError, TypeError):
            finite = False
        if not finite:
            invalid.append(feature)
    if missing or invalid:
        return "feature_missing"
    if not rule.clauses:
        return "hold"
    results: list[bool] = []
    for clause in rule.clauses:
        if clause.operator == "always":
            results.append(True)
        elif clause.operator == "never":
            results.append(False)
        else:
            value = snapshot.values[clause.feature]
            if clause.operator == "ge": results.append(value >= clause.lower)
            elif clause.operator == "gt": results.append(value > clause.lower)
            elif clause.operator == "le": results.append(value <= clause.lower)
            elif clause.operator == "lt": results.append(value < clause.lower)
            elif clause.feature in CATEGORICAL_FEATURES: results.append(value == clause.lower == clause.upper)
            else: results.append(clause.lower <= value <= clause.upper)
    if not all(results):
        return "hold"
    legal = {"HEDGED": {"CLOSE_BUY", "CLOSE_SELL"}, "ONE_BUY": {"OPEN_SELL"}, "ONE_SELL": {"OPEN_BUY"}}
    return "candidate_action" if rule.candidate_kind in legal.get(snapshot.values.get("state"), set()) else "invalid_transition"


def build_causal_snapshot(
    ticks: list[Mapping[str, object]], decision_time: object, *, state: str, side: str,
    clock_id: str,
) -> FeatureSnapshot:
    """Build the frozen feature set from an ordered causal tick prefix."""
    decision = _time(decision_time)
    parsed = []
    previous = None
    for raw in ticks:
        if not isinstance(raw, Mapping) or set(raw) != {"time", "bid", "ask"}:
            raise RetroBotInputError("RB-010 tick schema is invalid")
        timestamp = _time(raw["time"])
        if timestamp > decision or previous is not None and timestamp <= previous:
            raise RetroBotInputError("RB-010 tick order/lookahead violation")
        try:
            bid, ask = float(raw["bid"]), float(raw["ask"])
        except (TypeError, ValueError, OverflowError) as error:
            raise RetroBotInputError("RB-010 quote is invalid") from error
        if not math.isfinite(bid) or not math.isfinite(ask) or bid <= 0 or ask < bid:
            raise RetroBotInputError("RB-010 quote is invalid")
        parsed.append((timestamp, bid, ask))
        previous = timestamp
    if not parsed:
        return validate_snapshot(FeatureSnapshot(decision, {"state": state, "side": side, "clock_id": clock_id}, (), {}))
    current_time, bid, ask = parsed[-1]
    mids = [(b + a) / 2 for _, b, a in parsed]
    anchor_index = max((i for i, (timestamp, _, _) in enumerate(parsed) if timestamp <= decision - pd.Timedelta(seconds=60)), default=None)
    values: dict[str, object] = {"state": state, "side": side, "clock_id": clock_id, "spread_points": (ask - bid) / 0.01, "quote_gap_seconds": (current_time - parsed[-2][0]).total_seconds() if len(parsed) > 1 else 0.0, "tick_rate": sum(timestamp >= decision - pd.Timedelta(seconds=60) for timestamp, _, _ in parsed) / 60.0, "session_bucket": "asia" if decision.hour < 8 else "europe" if decision.hour < 16 else "us"}
    times = {key: current_time for key in values}
    if anchor_index is not None:
        anchor_mid = mids[anchor_index]
        values["price_increment"] = mids[-1] - anchor_mid
        window = mids[anchor_index:]
        values["price_increment"] = mids[-1] - anchor_mid
        times["price_increment"] = current_time
        if state == "ONE_BUY":
            values["adverse_excursion"] = max(0.0, anchor_mid - min(window))
            times["adverse_excursion"] = current_time
        elif state == "ONE_SELL":
            values["adverse_excursion"] = max(0.0, max(window) - anchor_mid)
            times["adverse_excursion"] = current_time
    return validate_snapshot(FeatureSnapshot(decision, values, (), times))


def evaluate_rules(snapshot: FeatureSnapshot, rules: tuple[TriggerRule, ...]) -> str:
    if not isinstance(rules, tuple) or any(not isinstance(rule, TriggerRule) for rule in rules):
        raise RetroBotInputError("RB-010 rule collection is invalid")
    rule_ids = [rule.rule_id for rule in rules]
    if len(set(rule_ids)) != len(rule_ids):
        raise RetroBotInputError("RB-010 duplicate rule id")
    for rule in sorted(rules, key=lambda item: item.rule_id):
        outcome = evaluate_rule(snapshot, rule)
        if outcome in {"candidate_action", "invalid_transition"}:
            return outcome
    return "hold"


def aggregate_rule_results(results: Mapping[str, int]) -> dict:
    allowed = {"hold", "candidate_action", "feature_missing", "invalid_transition"}
    if not isinstance(results, Mapping) or set(results) - allowed or any(type(v) is not int or v < 0 for v in results.values()):
        raise RetroBotInputError("RB-010 aggregate outcomes are invalid")
    payload = {
        "schema_version": 1,
        "case_id": CASE_ID,
        "rb008_config_sha256": RB008_CONFIG_SHA256,
        "source_manifest_digests": {
            "report_manifest_sha256": REPORT_MANIFEST_SHA256,
            "tick_manifest_sha256": TICK_MANIFEST_SHA256,
        },
        "m5_firewall": M5_FIREWALL_ATTESTATION,
        "outcome_counts": {key: int(results.get(key, 0)) for key in sorted(allowed)},
        "aggregate_sha256": "TO_BE_FILLED",
    }
    payload["aggregate_sha256"] = hashlib.sha256(json.dumps({k: v for k, v in payload.items() if k != "aggregate_sha256"}, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode()).hexdigest()
    return payload
