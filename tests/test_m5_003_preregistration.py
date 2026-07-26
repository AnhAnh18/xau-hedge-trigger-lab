from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "data" / "m5_003_preregistration.json"
M5_002_REPORT_PATH = (
    ROOT / "reports" / "phase_05" / "m5_002_state_age_pilot.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_m5_003_is_preregistered_without_implementation_authority() -> None:
    plan = _load(PLAN_PATH)

    assert plan["status"] == "preregistered_not_implemented"
    assert plan["scope"]["current_task_authorizes_implementation"] is False
    assert plan["scope"]["current_task_authorizes_price_model_fit"] is False
    assert plan["scope"]["canonical_outputs_mutable"] is False
    assert plan["scope"]["tradeable_edge_claim_allowed"] is False
    assert sha256(PLAN_PATH.read_bytes()).hexdigest() == (
        "1c0b59a897b4a4b7e4a4e2019e11d05b2aee400a75f2576efa74311c64f83478"
    )
    markdown = ROOT / ".local_ai" / "M5_003_PREREGISTRATION.md"
    assert sha256(markdown.read_bytes()).hexdigest() == (
        "01b7193394b6bb2e24bca3c9deb95a19d78398f1a11f8636151eb46f8fcd5a74"
    )


def test_m5_003_locks_exact_m5_002_inputs_and_frozen_a() -> None:
    plan = _load(PLAN_PATH)
    report = _load(M5_002_REPORT_PATH)
    immutable = plan["immutable_inputs"]

    assert immutable["m5_002_report_sha256"] == report[
        "deterministic_report_sha256"
    ]
    assert immutable["m5_002_risk_bin_dataframe_sha256"] == report[
        "output_hashes"
    ]["risk_bin_audit"]
    assert immutable["m5_002_interval_audit_dataframe_sha256"] == report[
        "output_hashes"
    ]["interval_audit"]
    assert immutable["a_common_1000ms_parameter_sha256"] == report[
        "parameters_by_width"
    ]["1000"]["fitted_parameter_sha256"]
    assert immutable["a_common_500ms_parameter_sha256"] == report[
        "parameters_by_width"
    ]["500"]["fitted_parameter_sha256"]
    assert plan["models"]["A_common"]["refit_allowed"] is False


def test_m5_003_endpoint_allowlists_are_bounded_and_causal() -> None:
    plan = _load(PLAN_PATH)
    allowlists = plan["feature_allowlists"]

    assert len(allowlists["rehedge"]) == 12
    assert len(allowlists["unlock"]) == 12
    assert len(set(allowlists["rehedge"])) == 12
    assert len(set(allowlists["unlock"])) == 12
    assert not any(
        "500ms" in feature
        for values in allowlists.values()
        for feature in values
    )
    assert not any("direction" in feature for feature in allowlists["unlock"])
    assert plan["anchors"]["subsecond_price_windows_in_primary_allowlist"] is False
    assert plan["common_cohort_rule"][
        "require_every_endpoint_allowlisted_price_feature_valid"
    ]
    assert plan["common_cohort_rule"][
        "models_a_b_c_use_identical_bins_within_endpoint_and_split"
    ]
    for endpoint in ["rehedge", "unlock"]:
        grouped = {
            feature
            for group in plan["feature_groups"][endpoint].values()
            for feature in group
        }
        assert grouped == set(allowlists[endpoint])


def test_m5_003_unlock_floor_and_cohort_roles_are_fixed() -> None:
    plan = _load(PLAN_PATH)
    report = _load(M5_002_REPORT_PATH)

    assert plan["common_cohort_rule"][
        "unlock_minimum_state_age_at_bin_start_seconds"
    ] == 5.0
    assert plan["validity"]["unlock_floor_audit"] == {
        "scope": "internal_2026_07_23_development_1000ms",
        "state_age_below_5s_dropped_bins": 3115,
        "state_age_below_5s_dropped_targets": 0,
    }
    buckets = report["primary_parameters"]["endpoints"]["unlock_occurrence"][
        "age_buckets"
    ]
    before_floor = ["age_0_1", "age_1_2", "age_2_3", "age_3_5"]
    assert sum(buckets[name]["exposure_bins"] for name in before_floor) == 3115
    assert sum(buckets[name]["target_events"] for name in before_floor) == 0
    assert plan["cohorts"]["development"]["sessions"] == [
        "2026-07-20",
        "2026-07-21",
        "2026-07-22",
        "2026-07-23",
    ]
    assert plan["cohorts"]["development"][
        "retrospective_sessions_can_validate_or_gate"
    ] is False
    assert plan["cohorts"]["internal_holdout"]["role"] == (
        "locked_internal_reuse_diagnostic_non_gating"
    )
    assert plan["cohorts"]["external"]["role"] == "only_external_validation_gate"


def test_m5_003_selection_and_inference_use_interval_clusters() -> None:
    plan = _load(PLAN_PATH)
    regularization = plan["regularization"]
    inference = plan["inference"]

    assert regularization["cross_validation"] == "GroupKFold"
    assert regularization["group"] == "interval_id"
    assert inference["bootstrap_cluster"] == "interval_id"
    assert inference["bootstrap_draws"] == 5000
    assert inference["headline_by_endpoint"] == (
        "C_minus_A_common_on_primary_1000ms_anchor"
    )
    assert inference["headline_family"]["comparisons"] == 3
    assert inference["ablation_family"]["comparisons"] == 12
    assert plan["decision_rule"]["null_result_blocks_merge"] is False
    assert plan["decision_rule"]["tradeable_edge_claim_allowed"] is False
    assert plan["base_rate_attenuation"][
        "holdout_label_recalibration_allowed"
    ] is False


def test_m5_003_forbids_holdout_leakage_and_black_box_inputs() -> None:
    plan = _load(PLAN_PATH)
    forbidden = set(plan["forbidden"])

    assert {
        "P/L",
        "entry_lineage",
        "black_box_boosting",
        "holdout_preprocessing",
        "holdout_feature_selection",
        "holdout_hyperparameter_selection",
        "holdout_calibration",
        "post_action_ticks",
        "directional_unlock_features",
    } <= forbidden
    assert plan["preprocessing"]["holdout_or_external_labels_allowed"] is False
