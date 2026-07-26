from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
M5_000_PATH = ROOT / "reports" / "phase_05" / "m5_000_risk_time_audit.json"
M5_002_PATH = ROOT / "reports" / "phase_05" / "m5_002_state_age_pilot.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_m5_002_report_reconciles_m5_000_internal_seconds() -> None:
    m5_000 = _load(M5_000_PATH)
    m5_002 = _load(M5_002_PATH)
    expected = sum(
        row["primary_risk_seconds"]
        for row in m5_000["canonical_full_coverage_by_day"]
    )
    internal = next(
        row
        for row in m5_002["support_accounting"]
        if row["cohort_id"] == "internal_2026_07_23_24"
        and row["bin_width_ms"] == 1000
    )

    assert round(expected, 6) == 125503.257
    assert internal["eligible_fragment_seconds"] == round(expected, 6)
    assert internal["representable_bin_seconds"] == 125501.0
    assert internal["dropped_partial_seconds"] == 2.257
    assert internal["reconciliation_delta_seconds"] == 0.0


def test_m5_002_report_passes_all_bounded_pilot_gates() -> None:
    report = _load(M5_002_PATH)

    assert report["status"] == "pilot_complete_external_pending"
    assert all(report["validation_gates"].values())
    assert report["data_isolation"]["canonical_ticks_unchanged"]
    assert report["data_isolation"]["supplemental_fit_isolation_pass"]
    assert report["external_gate_satisfied"] is False
    assert report["m5_closed"] is False
    assert report["tradeable_edge_claimed"] is False
    assert report["boundary_accounting"]["internal_2026_07_23_24"][
        "cross_split_interval_ids"
    ] == ["13321"]


def test_m5_002_report_hash_and_predictor_allowlist_are_stable() -> None:
    report = _load(M5_002_PATH)
    expected_hash = report.pop("deterministic_report_sha256")
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":"))

    assert sha256(encoded.encode("utf-8")).hexdigest() == expected_hash
    assert expected_hash == (
        "03f41d7e3838960a23aca5eb001add0f74a1eb285396f97b8228fdbf446781fb"
    )
    forbidden = set(report["predictor_allowlist_excludes"])
    assert forbidden.isdisjoint(report["predictor_allowlist"])


def test_m5_002_timer_floor_keeps_exception_and_correct_terminal_bucket() -> None:
    report = _load(M5_002_PATH)
    finding = report["timer_floor_verification"]["month_wide"]
    unlock = finding["unlock_occurrence"]
    unlock_buckets = report["primary_parameters"]["endpoints"][
        "unlock_occurrence"
    ]["age_buckets"]

    assert unlock["events"] == 6276
    assert unlock["under_six_seconds"] == 1
    assert unlock_buckets["age_3_5"]["target_events"] == 0
    # Predictor at age five represents the target event at bin end age six.
    assert unlock_buckets["age_5_6"]["target_events"] == 143


def test_m5_002_timing_and_occurrence_estimands_are_not_conflated() -> None:
    report = _load(M5_002_PATH)
    one_second = report["holdout_inference"]["1000"]

    assert one_second["rehedge_buy_occurrence"][
        "primary_conditional_timing"
    ]["ci95_high"] < 0
    assert one_second["rehedge_sell_occurrence"][
        "primary_conditional_timing"
    ]["ci95_high"] < 0
    assert one_second["unlock_occurrence"]["primary_conditional_timing"][
        "ci95_low"
    ] < 0
    assert one_second["unlock_occurrence"]["primary_conditional_timing"][
        "ci95_high"
    ] > 0
    for endpoint in one_second.values():
        assert endpoint["secondary_occurrence_likelihood"]["ci95_low"] > 0
