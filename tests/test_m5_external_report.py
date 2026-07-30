from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = (
    ROOT / "reports" / "phase_05" / "m5_003_external_validation_report.json"
)
ACQUISITION_PATH = (
    ROOT / "reports" / "phase_05" / "m5_001_external_acquisition_report.json"
)
MANIFEST_PATH = (
    ROOT / "reports" / "phase_05" / "m5_003_frozen_model_manifest.json"
)
ENDPOINTS = (
    "rehedge_buy_occurrence",
    "rehedge_sell_occurrence",
    "unlock_occurrence",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _payload_hash(payload: dict, hash_field: str) -> str:
    source = dict(payload)
    source.pop(hash_field)
    encoded = json.dumps(source, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def test_external_report_is_hash_consistent_and_uses_frozen_model() -> None:
    report = _load(REPORT_PATH)
    manifest = _load(MANIFEST_PATH)

    assert report["deterministic_report_sha256"] == _payload_hash(
        report, "deterministic_report_sha256"
    )
    assert report["frozen_manifest_sha256"] == manifest[
        "frozen_manifest_sha256"
    ]
    assert manifest["external_loaded_for_fit_or_evaluation"] is False
    assert report["canonical_input_file_sha256_before"] == report[
        "canonical_input_file_sha256_after"
    ]
    assert all(report["validation_gates"].values())


def test_external_acquisition_discloses_the_replicated_gap_and_qualitative_exposure() -> None:
    acquisition = _load(ACQUISITION_PATH)
    report = _load(REPORT_PATH)

    assert acquisition["status"] == "PASS_WITH_REPLICATED_SOURCE_QUOTE_GAP"
    assert acquisition["source_raw_validation_sha256"]
    assert acquisition["source_amended_validation_sha256"]
    assert acquisition["deterministic_report_sha256"] == _payload_hash(
        acquisition, "deterministic_report_sha256"
    )
    july_27 = next(
        row for row in acquisition["ticks"]["sessions"]
        if row["date"] == "2026-07-27"
    )
    assert july_27["status"] == "PASS_WITH_REPLICATED_SOURCE_QUOTE_GAP"
    assert july_27["coverage_gaps"][0]["classification"] == (
        "replicated_source_quote_gap"
    )
    assert "not analyst-blinded" in report["qualitative_exposure_limitation"]


def test_external_event_stages_reconcile_monotonically() -> None:
    report = _load(REPORT_PATH)
    expected_source = {
        "rehedge_buy_occurrence": 868,
        "rehedge_sell_occurrence": 837,
        "unlock_occurrence": 1705,
    }
    expected_joint_valid_1s = {
        "rehedge_buy_occurrence": 620,
        "rehedge_sell_occurrence": 574,
        "unlock_occurrence": 1282,
    }

    for width in ["1000", "500"]:
        for endpoint in ENDPOINTS:
            stage = report["event_stage_accounting"][width][endpoint]
            assert stage["source_lifecycle_events"] == expected_source[endpoint]
            assert (
                stage["source_lifecycle_events"]
                >= stage["representable_target_bins"]
                >= stage["common_floor_candidate_targets"]
                >= stage["joint_valid_targets"]
            )
    assert {
        endpoint: report["event_stage_accounting"]["1000"][endpoint][
            "joint_valid_targets"
        ]
        for endpoint in ENDPOINTS
    } == expected_joint_valid_1s


def test_external_headline_passes_registered_gate_without_tradeable_claim() -> None:
    report = _load(REPORT_PATH)
    expected_means = {
        "rehedge_buy_occurrence": 0.2312687179,
        "rehedge_sell_occurrence": 0.1666650507,
        "unlock_occurrence": 0.2216389007,
    }

    assert report["registered_sessions"] == [
        "2026-07-27",
        "2026-07-28",
        "2026-07-29",
    ]
    for endpoint, expected_mean in expected_means.items():
        result = report["external_results"]["1000"][endpoint]
        metric = result["paired_interval_comparisons"][
            "C_session_minus_A_session"
        ]
        assert metric["draws"] == 5000
        assert metric["cluster_count"] == result["intervals"]
        assert metric["mean"] == pytest.approx(expected_mean, abs=1e-10)
        assert metric["familywise_one_sided_low"] > 0
        assert result["headline_decision"]["verdict"] == "supported"
        assert (
            result["headline_decision"]["positive_external_sessions"] >= 2
        )

    assert report["decision"]["supported_endpoint_count"] == 3
    assert report["decision"]["tradeable_edge_claimed"] is False
    assert report["decision"]["independent_review_required_before_merge"] is True
    assert report["decision"]["ready_to_merge"] is False


def test_external_interpretation_preserves_architecture_and_session_limits() -> None:
    report = _load(REPORT_PATH)
    results = report["external_results"]["1000"]

    assert results["rehedge_buy_occurrence"]["paired_interval_comparisons"][
        "C_session_minus_B"
    ]["mean"] < 0
    assert results["rehedge_sell_occurrence"]["paired_interval_comparisons"][
        "C_session_minus_B"
    ]["mean"] < 0
    for endpoint in ENDPOINTS:
        means = {
            row["session_date"]: row["C_session_minus_A_session_mean"]
            for row in results[endpoint]["per_session"]
        }
        assert means["2026-07-29"] == max(means.values())

    assert "underperforms price-only B" in report["architecture_limitation"]
    assert "2026-07-29" in report["session_concentration_limitation"]
