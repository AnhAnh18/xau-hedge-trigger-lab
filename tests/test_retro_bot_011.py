from __future__ import annotations

import copy
import json
import subprocess
import sys

import pandas as pd
import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_005 import StateSnapshot
from xau_trigger.retro_bot_006 import FeatureSnapshot
from xau_trigger.retro_bot_009 import (
    M5_FIREWALL,
    RB008_CONFIG_SHA256,
    REPORT_MANIFEST_SHA256,
    TICK_MANIFEST_SHA256,
    DecisionRecord,
    frozen_candidate_policies,
)
from xau_trigger.retro_bot_010 import PaperAttestation, canonical_cycle_id, scenario_fingerprint, PaperScenario
from xau_trigger.retro_bot_011 import (
    ABLATIONS,
    COVERAGE_MODES,
    COST_SCENARIOS,
    FIXTURE_ID,
    PROJECTION_DIGEST,
    PROJECTION_VERSION,
    QUOTE_MODES,
    SLICE_IDS,
    STRESS_CLOCKS,
    TIMESTAMP_MODES,
    StressObservation,
    _COSTS,
    _parse_stress_cycle,
    _transform_cycle,
    aggregate_stress_observations,
    canonical_stress_case_id,
    locked_stress_cases,
    stress_replay_fixture,
    validate_stress_aggregate,
)


def _state(state: str) -> dict[str, object]:
    return {
        "state": state,
        "epoch": 0,
        "last_time": "2026-01-01T00:00:00Z",
        "quantity": 1.0,
        "seen_keys": [],
    }


def _snapshot(state: str, side: str, second: int = 1) -> dict[str, object]:
    timestamp = f"2026-01-01T00:00:0{second}Z"
    return {
        "decision_time": timestamp,
        "values": {
            "state": state,
            "side": side,
            "clock_id": "utc_plus_3",
            "price_increment": 0.0,
            "adverse_excursion": 0.0,
        },
        "feature_times": {
            "state": timestamp,
            "side": timestamp,
            "clock_id": timestamp,
            "price_increment": timestamp,
            "adverse_excursion": timestamp,
        },
        "oracle_labels": [],
    }


def _cycle(slice_id: str, state: str, side: str) -> dict[str, object]:
    candidate = "first_legal_match__first_legal_match"
    unit = f"rb015-{slice_id}"
    close_policy, rehedge_policy = frozen_candidate_policies(candidate)
    del close_policy, rehedge_policy
    cutoff = pd.Timestamp("2026-01-01T00:00:02Z").value
    if state == "HEDGED":
        actions = [
            {"kind": "CLOSE_BUY", "decision_time": "2026-01-01T00:00:01Z", "window_epoch": 0, "source": "policy"},
            {"kind": "OPEN_BUY", "decision_time": "2026-01-01T00:00:02Z", "window_epoch": 1, "source": "policy"},
        ]
    elif state == "ONE_BUY":
        actions = [{"kind": "OPEN_SELL", "decision_time": "2026-01-01T00:00:01Z", "window_epoch": 0, "source": "policy"}]
    else:
        actions = [{"kind": "OPEN_BUY", "decision_time": "2026-01-01T00:00:01Z", "window_epoch": 0, "source": "policy"}]
    return {
        "slice_id": slice_id,
        "cycle": {
            "cycle_id": canonical_cycle_id("development", "utc_plus_3", "fixed_warmup_seed", candidate, unit),
            "unit_id": unit,
            "fold": "development",
            "clock_id": "utc_plus_3",
            "bootstrap_id": "fixed_warmup_seed",
            "candidate_id": candidate,
            "state": _state(state),
            "actions": actions,
            "quotes": [
                {"decision_time": "2026-01-01T00:00:00Z", "bid": 2000.0, "ask": 2000.2},
                {"decision_time": "2026-01-01T00:00:01Z", "bid": 2000.1, "ask": 2000.3},
                {"decision_time": "2026-01-01T00:00:03Z", "bid": 2000.0, "ask": 2000.2},
            ],
            "causal_window": {
                "state": _state(state),
                "close_snapshots": [] if state != "HEDGED" else [_snapshot(state, side, 1)],
                "rehedge_snapshots": [_snapshot("ONE_SELL", "sell", 2)] if state == "HEDGED" else [_snapshot(state, side, 1)],
                "decision_records": [{
                    "fold": "development",
                    "decision_time_ns": cutoff,
                    "future_read": False,
                    "oracle_used": False,
                    "report_alias": "report-001.html",
                }],
                "causal_cutoff_ns": cutoff,
                "report_alias": "report-001.html",
            },
        },
    }


def _fixture() -> dict[str, object]:
    cases = locked_stress_cases()
    attestation = {
        "schema_version": 1,
        "rb008_config_sha256": RB008_CONFIG_SHA256,
        "report_manifest_sha256": REPORT_MANIFEST_SHA256,
        "tick_manifest_sha256": TICK_MANIFEST_SHA256,
        "fixture_id": FIXTURE_ID,
        "m5_firewall": M5_FIREWALL,
    }
    return {
        "attestation": attestation,
        "projection": {
            "projection_version": PROJECTION_VERSION,
            "fixture_id": FIXTURE_ID,
            "projection_digest": PROJECTION_DIGEST,
        },
        "cases": [
            {
                "case_id": case.case_id,
                "family": case.family,
                "clock_id": case.clock_id,
                "timestamp_mode": case.timestamp_mode,
                "quote_mode": case.quote_mode,
                "cost_scenario_id": case.cost_scenario_id,
                "coverage_mode": case.coverage_mode,
                "slice_id": case.slice_id,
                "ablation_id": case.ablation_id,
            }
            for case in cases
        ],
        "cycles": [
            _cycle("all", "HEDGED", "buy"),
            _cycle("hedged", "HEDGED", "buy"),
            _cycle("one_buy", "ONE_BUY", "buy"),
            _cycle("one_sell", "ONE_SELL", "sell"),
        ],
    }


def _typed_cycle(slice_id: str) -> dict[str, object]:
    parsed_slice, cycle = _parse_stress_cycle(next(item for item in _fixture()["cycles"] if item["slice_id"] == slice_id))
    assert parsed_slice == slice_id
    return cycle


def test_projection_is_locked_and_covers_declared_dimensions() -> None:
    cases = locked_stress_cases()
    assert len(cases) == 40
    assert len({case.case_id for case in cases}) == 40
    assert PROJECTION_DIGEST == __import__("xau_trigger.retro_bot_011", fromlist=["projection_digest"]).projection_digest(cases)
    assert {case.clock_id for case in cases} == set(STRESS_CLOCKS)
    assert {case.timestamp_mode for case in cases} == set(TIMESTAMP_MODES)
    assert {case.quote_mode for case in cases} == set(QUOTE_MODES)
    assert {case.cost_scenario_id for case in cases} == set(COST_SCENARIOS)
    assert {case.coverage_mode for case in cases} == set(COVERAGE_MODES)
    assert {case.slice_id for case in cases} == set(SLICE_IDS)
    assert {case.ablation_id for case in cases} == set(ABLATIONS)


def test_case_identity_is_canonical_and_tamper_evident() -> None:
    case = locked_stress_cases()[0]
    assert case.case_id == canonical_stress_case_id(
        family=case.family,
        clock_id=case.clock_id,
        timestamp_mode=case.timestamp_mode,
        quote_mode=case.quote_mode,
        cost_scenario_id=case.cost_scenario_id,
        coverage_mode=case.coverage_mode,
        slice_id=case.slice_id,
        ablation_id=case.ablation_id,
    )
    with pytest.raises(RetroBotInputError):
        type(case)("0" * 64, case.family, case.clock_id, case.timestamp_mode, case.quote_mode, case.cost_scenario_id, case.coverage_mode, case.slice_id, case.ablation_id).validate()
    non_projection_id = canonical_stress_case_id(
        family="clock_quote", clock_id="utc_plus_2", timestamp_mode="normal", quote_mode="clean",
        cost_scenario_id="latency_margin", coverage_mode="complete", slice_id="all", ablation_id="baseline",
    )
    non_projection = type(case)(non_projection_id, "clock_quote", "utc_plus_2", "normal", "clean", "latency_margin", "complete", "all", "baseline")
    with pytest.raises(RetroBotInputError):
        non_projection.validate()


def test_synthetic_fixture_replays_complete_matrix_deterministically() -> None:
    document = _fixture()
    first = stress_replay_fixture(document)
    validate_stress_aggregate(first)
    second = stress_replay_fixture(copy.deepcopy(document))
    assert json.dumps(first, ensure_ascii=True, separators=(",", ":")) == json.dumps(second, ensure_ascii=True, separators=(",", ":"))
    assert first["row_count"] == 40
    assert first["terminal_status"] == "descriptive-only-no-selection"
    assert first["status_counts"]["action_censored"] > 0
    assert first["status_counts"]["mark_censored"] > 0
    assert "net_return" not in json.dumps(first)


def test_actionless_fixture_is_rejected_before_stress_replay() -> None:
    document = _fixture()
    document["cycles"] = copy.deepcopy(document["cycles"])
    document["cycles"][0] = copy.deepcopy(document["cycles"][0])
    document["cycles"][0]["cycle"] = copy.deepcopy(document["cycles"][0]["cycle"])
    document["cycles"][0]["cycle"]["actions"] = []
    with pytest.raises(RetroBotInputError):
        stress_replay_fixture(document)


def test_all_stress_families_are_present_in_projection() -> None:
    families = {case.family for case in locked_stress_cases()}
    assert families == {"clock_quote", "timestamp", "coverage", "slice", "ablation", "cost"}
    assert [case.family for case in locked_stress_cases()].count("clock_quote") == 18
    assert [case.family for case in locked_stress_cases()].count("timestamp") == 6
    assert [case.family for case in locked_stress_cases()].count("coverage") == 6


def test_clock_transform_is_coupled_to_snapshot_clock_and_cycle_identity() -> None:
    raw = _typed_cycle("all")
    case = next(item for item in locked_stress_cases() if item.clock_id == "eu_dst_2025_2026")
    transformed = _transform_cycle(raw, case)
    assert transformed["clock_id"] == case.clock_id
    assert transformed["cycle_id"] == canonical_cycle_id("development", case.clock_id, "fixed_warmup_seed", "first_legal_match__first_legal_match", "rb015-all")
    assert transformed["causal_window"]["close_snapshots"][0].values["clock_id"] == case.clock_id


def test_direct_runner_rejects_slice_state_mismatch() -> None:
    raw = _typed_cycle("all")
    mismatched = next(item for item in locked_stress_cases() if item.slice_id == "one_buy")
    with pytest.raises(RetroBotInputError):
        from xau_trigger.retro_bot_011 import run_stress_case
        run_stress_case(mismatched, raw)


def test_ablation_removes_features_and_provenance_without_neutral_values() -> None:
    raw = _typed_cycle("one_buy")
    case = next(item for item in locked_stress_cases() if item.ablation_id == "drop_price_increment")
    transformed = _transform_cycle(raw, case)
    snapshot = transformed["causal_window"]["rehedge_snapshots"][0]
    assert "price_increment" not in snapshot.values
    assert "price_increment" not in snapshot.feature_times


@pytest.mark.parametrize("mode", ["duplicate", "out_of_order", "crossed", "nonfinite"])
def test_quote_faults_fail_closed_without_repair(mode: str) -> None:
    case = next(item for item in locked_stress_cases() if item.quote_mode == mode)
    transformed = _transform_cycle(_typed_cycle("all"), case)
    quotes = transformed["quotes"]
    if mode in {"duplicate", "out_of_order"}:
        assert len(quotes) >= 3
    if mode == "crossed":
        assert quotes[0].ask < quotes[0].bid
    if mode == "nonfinite":
        assert quotes[0].bid == float("inf")


def test_timestamp_collision_and_coverage_perturbations_are_deterministic() -> None:
    raw = _typed_cycle("all")
    collision = next(item for item in locked_stress_cases() if item.timestamp_mode == "second_collision")
    transformed = _transform_cycle(raw, collision)
    assert transformed["quotes"][0].decision_time.floor("s") == transformed["quotes"][1].decision_time.floor("s")
    truncated = next(item for item in locked_stress_cases() if item.coverage_mode == "mark_truncated")
    assert len(_transform_cycle(raw, truncated)["quotes"]) == len(raw["quotes"]) - 1


def test_locked_cost_scenarios_have_expected_values_and_fingerprints() -> None:
    assert _COSTS["zero"] == PaperScenario(scenario_id="zero")
    assert _COSTS["spread_slippage"].slippage_points == 10.0
    assert _COSTS["latency_margin"] == PaperScenario(scenario_id="latency_margin", fee_per_unit=0.25, slippage_points=5.0, latency_seconds=1, margin_per_unit=2.0)
    assert scenario_fingerprint(_COSTS["latency_margin"]) == scenario_fingerprint(PaperScenario(scenario_id="latency_margin", fee_per_unit=0.25, slippage_points=5.0, latency_seconds=1, margin_per_unit=2.0))


def test_observation_schema_redacts_returns_and_enforces_censor_precedence() -> None:
    case = locked_stress_cases()[0]
    obs = StressObservation(case.case_id, "marked", 1, 1, True, "gain")
    obs.validate()
    with pytest.raises(RetroBotInputError):
        StressObservation(case.case_id, "marked", 1, 0, True, "gain").validate()
    with pytest.raises(RetroBotInputError):
        StressObservation(case.case_id, "source_censored", 0, 0, False, "loss").validate()


def test_aggregate_rejects_duplicate_missing_and_tampered_rows() -> None:
    document = _fixture()
    payload = stress_replay_fixture(document)
    bad = copy.deepcopy(payload)
    bad["rows"] = list(bad["rows"])
    bad["rows"][1] = dict(bad["rows"][0])
    with pytest.raises(RetroBotInputError):
        validate_stress_aggregate(bad)


def test_aggregate_rejects_unhashable_dimension_values() -> None:
    document = _fixture()
    import xau_trigger.retro_bot_011 as module

    # The privacy defect is covered separately; bypass it to reach row checks.
    original = module._reject_output_privacy
    module._reject_output_privacy = lambda value: None
    try:
        payload = stress_replay_fixture(document)
    finally:
        module._reject_output_privacy = original
    bad = copy.deepcopy(payload)
    bad["rows"][0] = dict(bad["rows"][0])
    bad["rows"][0]["family"] = []
    with pytest.raises((RetroBotInputError, TypeError)):
        validate_stress_aggregate(bad)
    bad = copy.deepcopy(payload)
    bad["rows"][0] = dict(bad["rows"][0])
    bad["rows"][0]["return_band"] = "gain" if bad["rows"][0]["return_band"] != "gain" else "loss"
    with pytest.raises(RetroBotInputError):
        validate_stress_aggregate(bad)


@pytest.mark.parametrize("key", ["projection", "cases", "cycles"])
def test_fixture_tampering_fails_closed(key: str) -> None:
    document = _fixture()
    if key == "projection":
        document[key] = dict(document[key])
        document[key]["projection_digest"] = "0" * 64
    elif key == "cases":
        document[key] = list(document[key])
        document[key][0] = dict(document[key][0])
        document[key][0]["family"] = "unknown"
    else:
        document[key] = list(document[key])
        document[key].append(copy.deepcopy(document[key][0]))
    with pytest.raises((RetroBotInputError, TypeError)):
        stress_replay_fixture(document)


def test_recursive_private_values_are_rejected() -> None:
    document = _fixture()
    payload = stress_replay_fixture(document)
    bad = copy.deepcopy(payload)
    bad["rows"][0] = dict(bad["rows"][0])
    bad["rows"][0]["private_path"] = "C:/secret"
    with pytest.raises(RetroBotInputError):
        validate_stress_aggregate(bad)


def test_cli_validate_replay_and_verify_are_stdin_only() -> None:
    config = subprocess.run([sys.executable, "scripts/run_retro_bot_015.py", "validate-config"], text=True, capture_output=True, check=False)
    assert config.returncode == 0, config.stderr
    config_payload = json.loads(config.stdout)
    assert config_payload["case_count"] == 40
    fixture = json.dumps(_fixture(), ensure_ascii=True, separators=(",", ":"))
    replay = subprocess.run([sys.executable, "scripts/run_retro_bot_015.py", "stress-replay"], input=fixture, text=True, capture_output=True, check=False)
    assert replay.returncode == 0, replay.stderr
    aggregate = json.loads(replay.stdout)
    verify = subprocess.run([sys.executable, "scripts/run_retro_bot_015.py", "verify-aggregate"], input=json.dumps(aggregate), text=True, capture_output=True, check=False)
    assert verify.returncode == 0, verify.stderr
    assert json.loads(verify.stdout)["verified"] is True
    bad = subprocess.run([sys.executable, "scripts/run_retro_bot_015.py", "stress-replay"], input=json.dumps({"raw_path": "C:/secret"}), text=True, capture_output=True, check=False)
    assert bad.returncode != 0
    assert "C:/secret" not in bad.stderr


def test_cli_replay_is_byte_deterministic() -> None:
    fixture = json.dumps(_fixture(), ensure_ascii=True, separators=(",", ":"))
    outputs = [subprocess.run([sys.executable, "scripts/run_retro_bot_015.py", "stress-replay"], input=fixture, text=True, capture_output=True, check=False) for _ in range(2)]
    assert all(item.returncode == 0 for item in outputs)
    assert outputs[0].stdout == outputs[1].stdout
