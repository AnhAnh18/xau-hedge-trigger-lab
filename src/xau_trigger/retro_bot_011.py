"""RB-015 locked robustness, stress, and ablation matrix."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from types import MappingProxyType
from typing import Iterable, Mapping

import pandas as pd

from .retro_bot import RetroBotInputError
from .retro_bot_005 import StateSnapshot
from .retro_bot_006 import FeatureSnapshot, NUMERIC_FEATURES, validate_snapshot
from .retro_bot_009 import (
    CLOCKS,
    M5_FIREWALL,
    RB008_CONFIG_SHA256,
    REPORT_MANIFEST_SHA256,
    TICK_MANIFEST_SHA256,
    FOLDS,
    BOOTSTRAPS,
    CANDIDATES,
    DecisionRecord,
    frozen_candidate_policies,
)
from .retro_bot_010 import (
    ATTESTATION_FIELDS,
    PaperAttestation,
    PaperCycleResult,
    PaperQuote,
    PaperScenario,
    STATUSES,
    RETURN_BANDS,
    _action_digest,
    canonical_cycle_id,
    _fixture_action,
    _fixture_decision_record,
    _fixture_mapping,
    _fixture_quote,
    _fixture_snapshot,
    _fixture_state,
    _time,
    paper_backtest_cycle,
    scenario_fingerprint,
)

RB015_ID = "RB-015"
SCHEMA_VERSION = 1
PROJECTION_VERSION = "RB015_PROJECTION_V1"
FIXTURE_ID = "synthetic_rb015_base_cycle_v1"
STRESS_CLOCKS = CLOCKS
FAMILIES = ("clock_quote", "timestamp", "coverage", "slice", "ablation", "cost")
TIMESTAMP_MODES = ("normal", "second_collision", "dst_boundary")
QUOTE_MODES = ("clean", "gap", "duplicate", "out_of_order", "crossed", "nonfinite")
COST_SCENARIOS = ("zero", "spread_slippage", "latency_margin")
COVERAGE_MODES = ("complete", "action_truncated", "mark_truncated")
SLICE_IDS = ("all", "hedged", "one_buy", "one_sell")
ABLATIONS = ("baseline", "drop_price_increment", "drop_adverse_excursion")
PAPER_STATUSES = STATUSES

_COSTS = MappingProxyType({
    "zero": PaperScenario(scenario_id="zero"),
    "spread_slippage": PaperScenario(scenario_id="spread_slippage", slippage_points=10.0),
    "latency_margin": PaperScenario(scenario_id="latency_margin", fee_per_unit=0.25, slippage_points=5.0, latency_seconds=1, margin_per_unit=2.0),
})


def _sha(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode("utf-8")).hexdigest()


def canonical_stress_case_id(*, family: str, clock_id: str, timestamp_mode: str, quote_mode: str, cost_scenario_id: str, coverage_mode: str, slice_id: str, ablation_id: str, projection_version: str = PROJECTION_VERSION, fixture_id: str = FIXTURE_ID) -> str:
    return _sha([projection_version, fixture_id, family, clock_id, timestamp_mode, quote_mode, cost_scenario_id, coverage_mode, slice_id, ablation_id])


@dataclass(frozen=True)
class StressCase:
    case_id: str
    family: str
    clock_id: str
    timestamp_mode: str
    quote_mode: str
    cost_scenario_id: str
    coverage_mode: str
    slice_id: str
    ablation_id: str
    projection_version: str = PROJECTION_VERSION
    fixture_id: str = FIXTURE_ID

    def validate(self) -> None:
        if self.projection_version != PROJECTION_VERSION or self.fixture_id != FIXTURE_ID or not isinstance(self.family, str) or self.family not in FAMILIES or self.clock_id not in STRESS_CLOCKS or self.timestamp_mode not in TIMESTAMP_MODES or self.quote_mode not in QUOTE_MODES or self.cost_scenario_id not in COST_SCENARIOS or self.coverage_mode not in COVERAGE_MODES or self.slice_id not in SLICE_IDS or self.ablation_id not in ABLATIONS or not isinstance(self.case_id, str) or not re.fullmatch(r"[0-9a-f]{64}", self.case_id):
            raise RetroBotInputError("RB-015 stress case schema is invalid")
        expected_shape = {
            "clock_quote": self.timestamp_mode == "normal" and self.cost_scenario_id == "zero" and self.coverage_mode == "complete" and self.slice_id == "all" and self.ablation_id == "baseline",
            "timestamp": self.timestamp_mode in {"second_collision", "dst_boundary"} and self.quote_mode == "clean" and self.cost_scenario_id == "spread_slippage" and self.coverage_mode == "complete" and self.slice_id == "hedged" and self.ablation_id == "drop_price_increment",
            "coverage": self.timestamp_mode == "normal" and self.quote_mode == "clean" and self.cost_scenario_id == "spread_slippage" and self.coverage_mode in {"action_truncated", "mark_truncated"} and self.slice_id == "one_buy" and self.ablation_id == "drop_adverse_excursion",
            "slice": self.clock_id == "utc_plus_3" and self.timestamp_mode == "dst_boundary" and self.quote_mode == "clean" and self.cost_scenario_id == "zero" and self.coverage_mode == "complete" and self.ablation_id == "baseline",
            "ablation": self.clock_id == "utc_plus_3" and self.timestamp_mode == "normal" and self.quote_mode == "clean" and self.cost_scenario_id == "spread_slippage" and self.coverage_mode == "complete" and self.slice_id == "one_sell",
            "cost": self.clock_id == "utc_plus_3" and self.timestamp_mode == "normal" and self.quote_mode == "clean" and self.coverage_mode == "complete" and self.slice_id == "all" and self.ablation_id == "baseline",
        }
        if not expected_shape[self.family]:
            raise RetroBotInputError("RB-015 stress case is outside locked projection")
        expected = canonical_stress_case_id(family=self.family, clock_id=self.clock_id, timestamp_mode=self.timestamp_mode, quote_mode=self.quote_mode, cost_scenario_id=self.cost_scenario_id, coverage_mode=self.coverage_mode, slice_id=self.slice_id, ablation_id=self.ablation_id, projection_version=self.projection_version, fixture_id=self.fixture_id)
        if self.case_id != expected:
            raise RetroBotInputError("RB-015 stress case identity mismatch")


def _case(family: str, clock_id: str, timestamp_mode: str, quote_mode: str, cost: str, coverage: str, slice_id: str, ablation: str) -> StressCase:
    return StressCase(canonical_stress_case_id(family=family, clock_id=clock_id, timestamp_mode=timestamp_mode, quote_mode=quote_mode, cost_scenario_id=cost, coverage_mode=coverage, slice_id=slice_id, ablation_id=ablation), family, clock_id, timestamp_mode, quote_mode, cost, coverage, slice_id, ablation)


def locked_stress_cases() -> tuple[StressCase, ...]:
    rows: list[StressCase] = []
    for clock_id in STRESS_CLOCKS:
        for quote_mode in QUOTE_MODES:
            rows.append(_case("clock_quote", clock_id, "normal", quote_mode, "zero", "complete", "all", "baseline"))
    for clock_id in STRESS_CLOCKS:
        for timestamp_mode in ("second_collision", "dst_boundary"):
            rows.append(_case("timestamp", clock_id, timestamp_mode, "clean", "spread_slippage", "complete", "hedged", "drop_price_increment"))
    for clock_id in STRESS_CLOCKS:
        for coverage_mode in ("action_truncated", "mark_truncated"):
            rows.append(_case("coverage", clock_id, "normal", "clean", "spread_slippage", coverage_mode, "one_buy", "drop_adverse_excursion"))
    for slice_id in SLICE_IDS:
        rows.append(_case("slice", "utc_plus_3", "dst_boundary", "clean", "zero", "complete", slice_id, "baseline"))
    for ablation_id in ABLATIONS:
        rows.append(_case("ablation", "utc_plus_3", "normal", "clean", "spread_slippage", "complete", "one_sell", ablation_id))
    for cost_id in COST_SCENARIOS:
        rows.append(_case("cost", "utc_plus_3", "normal", "clean", cost_id, "complete", "all", "baseline"))
    result = tuple(rows)
    if len(result) != 40 or len({item.case_id for item in result}) != len(result):
        raise RetroBotInputError("RB-015 locked projection is invalid")
    for item in result:
        item.validate()
    return result


def projection_digest(cases: Iterable[StressCase] | None = None) -> str:
    materialized = tuple(locked_stress_cases() if cases is None else cases)
    for case in materialized:
        case.validate()
    return _sha([[case.case_id, case.family, case.clock_id, case.timestamp_mode, case.quote_mode, case.cost_scenario_id, case.coverage_mode, case.slice_id, case.ablation_id] for case in materialized])


# Keep the projection fingerprint literal so an accidental matrix edit cannot
# silently change the registered experiment.
PROJECTION_DIGEST = "4b3f9a2bd98b3827641cafa7807c6b929a2e212243c7a340cb51c97da1c701c3"
if projection_digest() != PROJECTION_DIGEST:
    raise RuntimeError("RB-015 projection fingerprint drift")


@dataclass(frozen=True)
class StressObservation:
    case_id: str
    status: str
    action_count: int
    mark_count: int
    accounting_pass: bool
    return_band: str | None

    def validate(self) -> None:
        if not isinstance(self.case_id, str) or not re.fullmatch(r"[0-9a-f]{64}", self.case_id) or self.status not in PAPER_STATUSES or type(self.action_count) is not int or self.action_count < 0 or self.action_count > 2 or type(self.mark_count) is not int or self.mark_count not in {0, 1} or type(self.accounting_pass) is not bool:
            raise RetroBotInputError("RB-015 observation schema is invalid")
        if self.status == "marked":
            if self.mark_count != 1 or not self.accounting_pass or self.return_band not in RETURN_BANDS:
                raise RetroBotInputError("RB-015 marked observation is invalid")
        elif self.mark_count != 0 or self.accounting_pass or self.return_band is not None:
            raise RetroBotInputError("RB-015 censored observation carries accounting")


def observe_paper_result(case: StressCase, result: PaperCycleResult) -> StressObservation:
    case.validate()
    if not isinstance(result, PaperCycleResult):
        raise RetroBotInputError("RB-015 paper result is invalid")
    result.validate()
    observation = StressObservation(case.case_id, result.status, result.action_count, result.mark_count, result.accounting_pass, result.return_band)
    observation.validate()
    return observation


def _replace_snapshot(snapshot: FeatureSnapshot, *, clock_id: str, ablation_id: str) -> FeatureSnapshot:
    validated = validate_snapshot(snapshot)
    values = dict(validated.values)
    feature_times = dict(validated.feature_times or {})
    values["clock_id"] = clock_id
    if ablation_id == "drop_price_increment":
        values.pop("price_increment", None)
        feature_times.pop("price_increment", None)
    elif ablation_id == "drop_adverse_excursion":
        values.pop("adverse_excursion", None)
        feature_times.pop("adverse_excursion", None)
    return FeatureSnapshot(validated.decision_time, values, (), feature_times)


def _transform_quotes(quotes: tuple[PaperQuote, ...], case: StressCase) -> tuple[PaperQuote, ...]:
    if not quotes:
        return quotes
    transformed = quotes
    # Apply quote faults first so source corruption wins over coverage censoring.
    if case.quote_mode == "gap":
        transformed = transformed[:1]
    if case.quote_mode == "duplicate":
        transformed = transformed + (transformed[-1],)
    elif case.quote_mode == "out_of_order" and len(transformed) >= 2:
        transformed = (transformed[1], transformed[0], *transformed[2:])
    elif case.quote_mode == "crossed":
        first = transformed[0]
        transformed = (PaperQuote(first.decision_time, first.bid, first.bid - 0.01), *transformed[1:])
    elif case.quote_mode == "nonfinite":
        first = transformed[0]
        transformed = (PaperQuote(first.decision_time, float("inf"), first.ask), *transformed[1:])
    if case.timestamp_mode == "second_collision" and len(transformed) >= 2:
        first, second = transformed[0], transformed[1]
        transformed = (first, PaperQuote(first.decision_time, second.bid, second.ask), *transformed[2:])
    if case.coverage_mode == "action_truncated":
        transformed = transformed[:1]
    elif case.coverage_mode == "mark_truncated":
        transformed = transformed[: max(1, len(transformed) - 1)]
    return transformed


def _transform_cycle(cycle_kwargs: Mapping[str, object], case: StressCase) -> dict[str, object]:
    required = ("cycle_id", "unit_id", "fold", "clock_id", "bootstrap_id", "candidate_id", "state", "actions", "quotes", "causal_window")
    if not isinstance(cycle_kwargs, Mapping) or tuple(cycle_kwargs.keys()) != required:
        raise RetroBotInputError("RB-015 typed cycle schema is invalid")
    if not isinstance(cycle_kwargs["quotes"], tuple) or not all(isinstance(item, PaperQuote) for item in cycle_kwargs["quotes"]):
        raise RetroBotInputError("RB-015 typed quotes are invalid")
    identity_fields = ("cycle_id", "unit_id", "fold", "clock_id", "bootstrap_id", "candidate_id")
    if any(not isinstance(cycle_kwargs[field], str) for field in identity_fields):
        raise RetroBotInputError("RB-015 cycle identity is invalid")
    try:
        expected_cycle_id = canonical_cycle_id(cycle_kwargs["fold"], cycle_kwargs["clock_id"], cycle_kwargs["bootstrap_id"], cycle_kwargs["candidate_id"], cycle_kwargs["unit_id"])
    except (TypeError, ValueError):
        raise RetroBotInputError("RB-015 cycle identity is invalid")
    if cycle_kwargs["cycle_id"] != expected_cycle_id:
        raise RetroBotInputError("RB-015 cycle identity mismatch")
    window = cycle_kwargs["causal_window"]
    causal_keys = ("state", "close_policy", "rehedge_policy", "close_snapshots", "rehedge_snapshots", "decision_records", "causal_cutoff_ns", "report_alias")
    if not isinstance(window, Mapping) or tuple(window.keys()) != causal_keys:
        raise RetroBotInputError("RB-015 causal window is invalid")
    if not isinstance(window["close_snapshots"], tuple) or not isinstance(window["rehedge_snapshots"], tuple):
        raise RetroBotInputError("RB-015 causal snapshots are invalid")
    close_snapshots = tuple(_replace_snapshot(item, clock_id=case.clock_id, ablation_id=case.ablation_id) for item in window["close_snapshots"])
    rehedge_snapshots = tuple(_replace_snapshot(item, clock_id=case.clock_id, ablation_id=case.ablation_id) for item in window["rehedge_snapshots"])
    transformed_window = dict(window)
    transformed_window["close_snapshots"] = close_snapshots
    transformed_window["rehedge_snapshots"] = rehedge_snapshots
    return {"cycle_id": canonical_cycle_id(cycle_kwargs["fold"], case.clock_id, cycle_kwargs["bootstrap_id"], cycle_kwargs["candidate_id"], cycle_kwargs["unit_id"]), "unit_id": cycle_kwargs["unit_id"], "fold": cycle_kwargs["fold"], "clock_id": case.clock_id, "bootstrap_id": cycle_kwargs["bootstrap_id"], "candidate_id": cycle_kwargs["candidate_id"], "state": cycle_kwargs["state"], "actions": cycle_kwargs["actions"], "quotes": _transform_quotes(cycle_kwargs["quotes"], case), "causal_window": transformed_window}


def run_stress_case(case: StressCase, cycle_kwargs: Mapping[str, object]) -> StressObservation:
    case.validate()
    transformed = _transform_cycle(cycle_kwargs, case)
    expected_states = {"all": "HEDGED", "hedged": "HEDGED", "one_buy": "ONE_BUY", "one_sell": "ONE_SELL"}
    if not isinstance(transformed["state"], StateSnapshot) or transformed["state"].state != expected_states[case.slice_id]:
        raise RetroBotInputError("RB-015 cycle state does not match slice")
    result = paper_backtest_cycle(**transformed, scenario=_COSTS[case.cost_scenario_id])
    return observe_paper_result(case, result)


def _row_for(case: StressCase, observation: StressObservation) -> dict[str, object]:
    return {"case_id": case.case_id, "family": case.family, "clock_id": case.clock_id, "timestamp_mode": case.timestamp_mode, "quote_mode": case.quote_mode, "cost_scenario_id": case.cost_scenario_id, "coverage_mode": case.coverage_mode, "slice_id": case.slice_id, "ablation_id": case.ablation_id, "status": observation.status, "action_count": observation.action_count, "mark_count": observation.mark_count, "accounting_pass": observation.accounting_pass, "return_band": observation.return_band}


def aggregate_stress_observations(observations: Iterable[StressObservation], *, attestation: PaperAttestation | None = None) -> dict[str, object]:
    if not isinstance(attestation, PaperAttestation):
        raise RetroBotInputError("RB-015 source attestation is required")
    attestation.validate()
    if attestation.fixture_id != FIXTURE_ID:
        raise RetroBotInputError("RB-015 fixture attestation mismatch")
    cases = locked_stress_cases()
    expected = {case.case_id: case for case in cases}
    materialized = tuple(observations)
    if len(materialized) != len(cases):
        raise RetroBotInputError("RB-015 complete stress matrix is required")
    seen: set[str] = set()
    rows: list[dict[str, object]] = []
    for observation in materialized:
        if not isinstance(observation, StressObservation):
            raise RetroBotInputError("RB-015 observation schema is invalid")
        observation.validate()
        if observation.case_id not in expected or observation.case_id in seen:
            raise RetroBotInputError("RB-015 stress case is duplicated or unknown")
        seen.add(observation.case_id)
    if seen != set(expected):
        raise RetroBotInputError("RB-015 stress matrix is incomplete")
    by_id = {item.case_id: item for item in materialized}
    for case in cases:
        rows.append(_row_for(case, by_id[case.case_id]))
    status_counts = {status: sum(row["status"] == status for row in rows) for status in PAPER_STATUSES}
    return_bands = {band: sum(row["return_band"] == band for row in rows) for band in RETURN_BANDS}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "case_id": RB015_ID,
        "projection_version": PROJECTION_VERSION,
        "fixture_id": FIXTURE_ID,
        "projection_digest": PROJECTION_DIGEST,
        "rb014_schema_version": 1,
        "rb008_config_sha256": RB008_CONFIG_SHA256,
        "source_manifest_digests": {"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256},
        "attestation": {"schema_version": attestation.schema_version, "rb008_config_sha256": attestation.rb008_config_sha256, "report_manifest_sha256": attestation.report_manifest_sha256, "tick_manifest_sha256": attestation.tick_manifest_sha256, "fixture_id": attestation.fixture_id, "m5_firewall": attestation.m5_firewall},
        "row_count": len(rows),
        "rows": rows,
        "status_counts": status_counts,
        "return_bands": return_bands,
        "marked_count": status_counts["marked"],
        "accounting_pass_count": sum(row["accounting_pass"] for row in rows),
        "terminal_status": "descriptive-only-no-selection",
        "m5_firewall": M5_FIREWALL,
        "aggregate_sha256": "TO_BE_FILLED",
    }
    payload["aggregate_sha256"] = _sha({key: value for key, value in payload.items() if key != "aggregate_sha256"})
    validate_stress_aggregate(payload)
    return payload


def _reject_output_privacy(value: object) -> None:
    forbidden = ("password", "credential", "journal", "ticket", ".ex5", "raw_path", "private_path", "account_id", "account_number", "login", "secret")
    if isinstance(value, Mapping):
        for key, item in value.items():
            if isinstance(key, str) and any(token in key.casefold() for token in forbidden):
                raise RetroBotInputError("RB-015 aggregate privacy violation")
            _reject_output_privacy(item)
    elif isinstance(value, list):
        for item in value:
            _reject_output_privacy(item)
    elif isinstance(value, str) and any(token in value.casefold() for token in forbidden):
        raise RetroBotInputError("RB-015 aggregate privacy violation")


def validate_stress_aggregate(payload: Mapping[str, object]) -> None:
    keys = ("schema_version", "case_id", "projection_version", "fixture_id", "projection_digest", "rb014_schema_version", "rb008_config_sha256", "source_manifest_digests", "attestation", "row_count", "rows", "status_counts", "return_bands", "marked_count", "accounting_pass_count", "terminal_status", "m5_firewall", "aggregate_sha256")
    if not isinstance(payload, Mapping) or tuple(payload.keys()) != keys or type(payload.get("schema_version")) is not int or payload.get("schema_version") != SCHEMA_VERSION or payload.get("case_id") != RB015_ID or payload.get("projection_version") != PROJECTION_VERSION or payload.get("fixture_id") != FIXTURE_ID or payload.get("projection_digest") != PROJECTION_DIGEST or type(payload.get("rb014_schema_version")) is not int or payload.get("rb014_schema_version") != 1 or payload.get("rb008_config_sha256") != RB008_CONFIG_SHA256 or payload.get("terminal_status") != "descriptive-only-no-selection" or payload.get("m5_firewall") != M5_FIREWALL:
        raise RetroBotInputError("RB-015 aggregate schema/provenance mismatch")
    source = payload.get("source_manifest_digests")
    if source != {"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256}:
        raise RetroBotInputError("RB-015 source digest mismatch")
    attestation = payload.get("attestation")
    if not isinstance(attestation, Mapping) or tuple(attestation.keys()) != ATTESTATION_FIELDS:
        raise RetroBotInputError("RB-015 attestation schema mismatch")
    if attestation.get("fixture_id") != FIXTURE_ID or attestation.get("rb008_config_sha256") != RB008_CONFIG_SHA256 or attestation.get("report_manifest_sha256") != REPORT_MANIFEST_SHA256 or attestation.get("tick_manifest_sha256") != TICK_MANIFEST_SHA256 or attestation.get("m5_firewall") != M5_FIREWALL:
        raise RetroBotInputError("RB-015 attestation provenance mismatch")
    PaperAttestation(**attestation).validate()
    cases = locked_stress_cases()
    if type(payload.get("row_count")) is not int or payload["row_count"] != len(cases) or not isinstance(payload.get("rows"), list) or len(payload["rows"]) != len(cases):
        raise RetroBotInputError("RB-015 row count mismatch")
    row_keys = ("case_id", "family", "clock_id", "timestamp_mode", "quote_mode", "cost_scenario_id", "coverage_mode", "slice_id", "ablation_id", "status", "action_count", "mark_count", "accounting_pass", "return_band")
    expected = {case.case_id: case for case in cases}
    seen: set[str] = set()
    for index, row in enumerate(payload["rows"]):
        if not isinstance(row, Mapping) or tuple(row.keys()) != row_keys or not isinstance(row.get("case_id"), str):
            raise RetroBotInputError("RB-015 row schema mismatch")
        case = expected.get(row["case_id"])
        if case is None or row["case_id"] in seen or row["case_id"] != cases[index].case_id:
            raise RetroBotInputError("RB-015 row identity/order mismatch")
        actual_dimensions = tuple(row[field] for field in ("family", "clock_id", "timestamp_mode", "quote_mode", "cost_scenario_id", "coverage_mode", "slice_id", "ablation_id"))
        expected_dimensions = (case.family, case.clock_id, case.timestamp_mode, case.quote_mode, case.cost_scenario_id, case.coverage_mode, case.slice_id, case.ablation_id)
        if actual_dimensions != expected_dimensions:
            raise RetroBotInputError("RB-015 row dimensions mismatch")
        observation = StressObservation(row["case_id"], row["status"], row["action_count"], row["mark_count"], row["accounting_pass"], row["return_band"])
        observation.validate()
        seen.add(row["case_id"])
    if seen != set(expected):
        raise RetroBotInputError("RB-015 matrix is incomplete")
    status_counts = payload["status_counts"]
    bands = payload["return_bands"]
    if not isinstance(status_counts, Mapping) or tuple(status_counts.keys()) != PAPER_STATUSES or any(type(value) is not int or value < 0 for value in status_counts.values()) or sum(status_counts.values()) != len(cases):
        raise RetroBotInputError("RB-015 status accounting mismatch")
    if not isinstance(bands, Mapping) or tuple(bands.keys()) != RETURN_BANDS or any(type(value) is not int or value < 0 for value in bands.values()) or sum(bands.values()) != status_counts["marked"]:
        raise RetroBotInputError("RB-015 band accounting mismatch")
    expected_status_counts = {status: sum(row["status"] == status for row in payload["rows"]) for status in PAPER_STATUSES}
    expected_bands = {band: sum(row["return_band"] == band for row in payload["rows"]) for band in RETURN_BANDS}
    if dict(status_counts) != expected_status_counts or dict(bands) != expected_bands:
        raise RetroBotInputError("RB-015 aggregate counts do not match rows")
    if type(payload.get("marked_count")) is not int or type(payload.get("accounting_pass_count")) is not int or payload["marked_count"] != status_counts["marked"] or payload["accounting_pass_count"] != status_counts["marked"] or payload["marked_count"] < 0 or payload["accounting_pass_count"] < 0 or payload["marked_count"] > len(cases) or payload["accounting_pass_count"] > len(cases):
        raise RetroBotInputError("RB-015 accounting summary mismatch")
    _reject_output_privacy(payload)
    if payload.get("aggregate_sha256") != _sha({key: value for key, value in payload.items() if key != "aggregate_sha256"}):
        raise RetroBotInputError("RB-015 aggregate digest mismatch")


def _parse_stress_cycle(value: object) -> tuple[str, dict[str, object]]:
    wrapper = _fixture_mapping(value, ("slice_id", "cycle"), "RB-015 cycle wrapper schema is invalid")
    if not isinstance(wrapper["slice_id"], str) or wrapper["slice_id"] not in SLICE_IDS:
        raise RetroBotInputError("RB-015 cycle slice is invalid")
    cycle = _fixture_mapping(wrapper["cycle"], ("cycle_id", "unit_id", "fold", "clock_id", "bootstrap_id", "candidate_id", "state", "actions", "quotes", "causal_window"), "RB-015 cycle schema is invalid")
    state = _fixture_state(cycle["state"])
    if not isinstance(cycle["actions"], list) or not isinstance(cycle["quotes"], list):
        raise RetroBotInputError("RB-015 cycle sequences are invalid")
    identity_fields = ("cycle_id", "unit_id", "fold", "clock_id", "bootstrap_id", "candidate_id")
    if any(not isinstance(cycle[field], str) for field in identity_fields):
        raise RetroBotInputError("RB-015 cycle identity is invalid")
    try:
        expected_cycle_id = canonical_cycle_id(cycle["fold"], cycle["clock_id"], cycle["bootstrap_id"], cycle["candidate_id"], cycle["unit_id"])
    except (TypeError, ValueError):
        raise RetroBotInputError("RB-015 cycle identity is invalid")
    if cycle["cycle_id"] != expected_cycle_id:
        raise RetroBotInputError("RB-015 cycle identity mismatch")
    actions = tuple(_fixture_action(item) for item in cycle["actions"])
    quotes = tuple(_fixture_quote(item) for item in cycle["quotes"])
    causal = _fixture_mapping(cycle["causal_window"], ("state", "close_snapshots", "rehedge_snapshots", "decision_records", "causal_cutoff_ns", "report_alias"), "RB-015 causal window schema is invalid")
    causal_state = _fixture_state(causal["state"])
    if causal_state != state or not isinstance(causal["close_snapshots"], list) or not isinstance(causal["rehedge_snapshots"], list) or not isinstance(causal["decision_records"], list):
        raise RetroBotInputError("RB-015 causal state/sequences are invalid")
    close_policy, rehedge_policy = frozen_candidate_policies(cycle["candidate_id"])
    window = {"state": causal_state, "close_policy": close_policy, "rehedge_policy": rehedge_policy, "close_snapshots": tuple(_fixture_snapshot(item) for item in causal["close_snapshots"]), "rehedge_snapshots": tuple(_fixture_snapshot(item) for item in causal["rehedge_snapshots"]), "decision_records": tuple(_fixture_decision_record(item) for item in causal["decision_records"]), "causal_cutoff_ns": causal["causal_cutoff_ns"], "report_alias": causal["report_alias"]}
    return wrapper["slice_id"], {"cycle_id": cycle["cycle_id"], "unit_id": cycle["unit_id"], "fold": cycle["fold"], "clock_id": cycle["clock_id"], "bootstrap_id": cycle["bootstrap_id"], "candidate_id": cycle["candidate_id"], "state": state, "actions": actions, "quotes": quotes, "causal_window": window}


def stress_replay_fixture(document: Mapping[str, object]) -> dict[str, object]:
    top_keys = ("attestation", "projection", "cases", "cycles")
    if not isinstance(document, Mapping) or tuple(document.keys()) != top_keys:
        raise RetroBotInputError("RB-015 fixture schema is invalid")
    attestation_item = _fixture_mapping(document["attestation"], ATTESTATION_FIELDS, "RB-015 fixture attestation schema is invalid")
    projection = _fixture_mapping(document["projection"], ("projection_version", "fixture_id", "projection_digest"), "RB-015 projection schema is invalid")
    cases = locked_stress_cases()
    if projection != {"projection_version": PROJECTION_VERSION, "fixture_id": FIXTURE_ID, "projection_digest": PROJECTION_DIGEST}:
        raise RetroBotInputError("RB-015 projection mismatch")
    if not isinstance(document["cases"], list) or len(document["cases"]) != len(cases):
        raise RetroBotInputError("RB-015 fixture case list is invalid")
    case_keys = ("case_id", "family", "clock_id", "timestamp_mode", "quote_mode", "cost_scenario_id", "coverage_mode", "slice_id", "ablation_id")
    for raw, expected in zip(document["cases"], cases):
        item = _fixture_mapping(raw, case_keys, "RB-015 fixture case schema is invalid")
        if dict(item) != {key: getattr(expected, key) for key in case_keys}:
            raise RetroBotInputError("RB-015 fixture case mismatch")
    if not isinstance(document["cycles"], list):
        raise RetroBotInputError("RB-015 fixture cycles are invalid")
    parsed_items = tuple(_parse_stress_cycle(item) for item in document["cycles"])
    parsed_cycles = dict(parsed_items)
    if len(parsed_items) != len(SLICE_IDS) or len(parsed_cycles) != len(parsed_items) or set(parsed_cycles) != set(SLICE_IDS):
        raise RetroBotInputError("RB-015 fixture slice coverage is incomplete")
    expected_states = {"all": "HEDGED", "hedged": "HEDGED", "one_buy": "ONE_BUY", "one_sell": "ONE_SELL"}
    if any(parsed_cycles[slice_id]["state"].state != expected_states[slice_id] for slice_id in SLICE_IDS):
        raise RetroBotInputError("RB-015 fixture slice state mismatch")
    expected_action_counts = {"all": 2, "hedged": 2, "one_buy": 1, "one_sell": 1}
    if any(len(parsed_cycles[slice_id]["actions"]) != expected_action_counts[slice_id] for slice_id in SLICE_IDS):
        raise RetroBotInputError("RB-015 fixture action coverage is incomplete")
    observations = tuple(run_stress_case(case, parsed_cycles[case.slice_id]) for case in cases)
    return aggregate_stress_observations(observations, attestation=PaperAttestation(**attestation_item))
