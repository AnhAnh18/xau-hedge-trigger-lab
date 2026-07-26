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
    bridge = m5_002["m5_000_support_bridge"]
    assert bridge["m5_000_tradeable_risk_seconds"] == 125697.211
    assert bridge["left_truncated_excluded_seconds"] == 193.954
    assert bridge["m5_000_primary_known_age_seconds"] == 125503.257
    assert bridge["reconciliation_delta_seconds"] == 0.0


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
        "80a1a8c680e7ddd7eb0a9e8ed8813f5f69c025d3b62b292eba30b05a92401365"
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


def test_m5_002_occurrence_is_primary_and_conditional_is_noninferential() -> None:
    report = _load(M5_002_PATH)
    one_second = report["holdout_inference"]["1000"]

    for endpoint in one_second.values():
        assert endpoint["primary_occurrence_likelihood"]["ci95_low"] > 0
        assert "noninferential_age_only_conditional_diagnostic" in endpoint
    assert report["diagnostic_roles"]["conditional_timing"] == (
        "noninferential_for_age_only_outcome_truncated_risk_set"
    )
    assert all(
        item["verdict"] == "internal_occurrence_supported_external_pending"
        for item in report["pilot_verdict"].values()
    )
    oracle = report["conditional_degeneracy_audit"]["1000"][
        "oracle_conditional_mean"
    ]
    assert round(oracle["rehedge_buy_occurrence"], 6) == -0.320249
    assert round(oracle["rehedge_sell_occurrence"], 6) == -0.430092
    assert round(oracle["unlock_occurrence"], 6) == -0.060804
