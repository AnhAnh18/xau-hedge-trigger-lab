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


def _canonical_text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return sha256(normalized.encode("utf-8")).hexdigest()


def test_m5_003_is_preregistered_with_separate_implementation_authority() -> None:
    plan = _load(PLAN_PATH)

    assert plan["schema_version"] == 2
    assert plan["plan_id"] == "m5_003_causal_price_increment_v2"
    assert plan["status"] == "preregistered_implementation_authorized"
    assert plan["implementation_authorized_on"] == "2026-07-26"
    assert plan["amendment"]["price_models_fitted_before_amendment"] is False
    assert plan["amendment"]["external_labels_inspected"] is False
    assert plan["amendment"]["confirmatory_internal_verdict_allowed"] is False
    assert plan["scope"]["current_task_authorizes_implementation"] is True
    assert plan["scope"]["current_task_authorizes_price_model_fit"] is True
    assert plan["scope"]["canonical_outputs_mutable"] is False
    assert plan["scope"]["tradeable_edge_claim_allowed"] is False
    assert _canonical_text_sha256(PLAN_PATH) == (
        "a5d51e73b012379f58b38bcb0d6e27154d07c77955735e4b08cce9014c334130"
    )
    markdown = ROOT / ".local_ai" / "M5_003_PREREGISTRATION.md"
    assert _canonical_text_sha256(markdown) == (
        "a7187f5c294cd3e9e49201c8b73f71b9d84caf71c09924e1dd6e538829ebdc7e"
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
        "all_models_use_identical_bins_within_endpoint_and_split"
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
    assert plan["cohorts"]["internal_holdout"][
        "supported_rejected_or_absent_price_verdict_allowed"
    ] is False
    assert plan["cohorts"]["external"]["role"] == "only_external_validation_gate"


def test_m5_003_development_age_baseline_is_fixed_without_price_credit() -> None:
    plan = _load(PLAN_PATH)
    models = plan["models"]

    assert models["A_common"]["refit_allowed"] is False
    assert models["A_common"]["role"] == (
        "immutable_provenance_and_transport_reference"
    )
    assert models["A_level"]["role"] == (
        "noninferential_level_transport_diagnostic"
    )
    assert models["A_dev"]["age_buckets_seconds"] == [
        [0, 1],
        [1, 2],
        [2, 3],
        [3, 5],
        [5, 6],
        [6, 8],
        [8, 10],
        [10, 20],
        [20, 30],
        [30, 60],
        [60, None],
    ]
    assert models["A_dev"]["jeffreys_alpha"] == 0.5
    assert models["A_dev"]["bucket_or_smoothing_selection_allowed"] is False
    assert models["A_dev"]["zero_training_exposure_bucket_contract"] == (
        "fail_before_price_fit_no_adaptive_merge_A_common_fallback_or_"
        "holdout_informed_repair"
    )
    assert len(models["A_dev"]["age_buckets_seconds"]) == 11
    assert models["A_dev"]["unlock_floor_eligible_bucket_count"] == 7
    assert models["C_dev"]["free_intercept"] is False
    assert "logit(A_dev)" in models["C_dev"]["definition"]
    assert plan["preprocessing"][
        "a_dev_validation_probabilities_use_training_fold_bucket_parameters_only"
    ]


def test_m5_003_selection_inference_and_session_diagnostics_are_locked() -> None:
    plan = _load(PLAN_PATH)
    regularization = plan["regularization"]
    inference = plan["inference"]

    assert regularization["cross_validation"] == "GroupKFold"
    assert regularization["group"] == "interval_id"
    assert inference["bootstrap_cluster"] == "interval_id"
    assert inference["bootstrap_draws"] == 5000
    assert inference["headline_by_endpoint"] == (
        "C_dev_minus_A_dev_on_primary_1000ms_anchor"
    )
    assert inference["required_secondary"] == (
        "C_dev_minus_B_on_primary_1000ms_anchor"
    )
    assert inference["noninferential_transport_diagnostics"] == [
        "A_level_minus_A_common",
        "A_dev_minus_A_level",
    ]
    assert inference["effect_magnitudes_comparable_across_endpoints"] is False
    assert inference["headline_family"]["comparisons"] == 3
    assert inference["ablation_family"]["comparisons"] == 12
    stability = plan["session_stability"]
    assert stability["method"] == "leave_one_development_session_out"
    assert stability["folds"] == 4
    assert stability["can_select_or_tune_model"] is False
    assert stability["can_create_verdict"] is False
    assert stability["lambda_selection"] == (
        "nested_GroupKFold_on_remaining_training_session_intervals_only"
    )
    assert set(stability["refit_each_fold"]) == {
        "A_dev",
        "preprocessing",
        "lambda_selection",
        "B",
        "C_dev",
    }
    assert plan["freeze_manifest"][
        "must_be_created_before_loading_2026_07_24_for_evaluation"
    ]
    assert plan["freeze_manifest"][
        "parameter_hash_identical_with_or_without_2026_07_24"
    ]
    assert {
        "A_dev_bucket_parameters",
        "all_existing_model_intercepts",
        "preprocessing_parameters",
        "selected_lambdas",
        "price_coefficients",
    } <= set(plan["freeze_manifest"]["hashed_components"])
    assert plan["decision_rule"][
        "development_and_internal_reuse_verdict_allowed"
    ] is False
    assert plan["decision_rule"]["pre_external_status"] == (
        "pipeline_frozen_external_pending_zero_validated_price_results"
    )
    assert plan["decision_rule"]["null_result_blocks_merge"] is False
    assert plan["decision_rule"]["tradeable_edge_claim_allowed"] is False
    assert plan["base_rate_attenuation"][
        "holdout_label_recalibration_allowed"
    ] is False


def test_m5_003_support_audits_distinguish_precheck_and_full_allowlist() -> None:
    plan = _load(PLAN_PATH)
    validity = plan["validity"]

    assert validity["known_generic_window_support_audit"][
        "windows_2s_5s_10s_dropped_bins"
    ] == 501
    assert validity["known_generic_window_support_audit"][
        "windows_2s_5s_10s_dropped_targets"
    ] == 0
    full = validity["known_full_allowlist_support_audit"]
    assert full["expected_dropped_bins"] == 937
    assert full["expected_dropped_targets"] == 3
    assert full["must_be_recomputed_before_fit"] is True
    assert full["endpoint_specific_accounting_required"] is True


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


def test_m5_003_requires_independent_re_review_before_merge() -> None:
    plan = _load(PLAN_PATH)
    review = plan["independent_re_review"]

    assert review["reviewer"] == "Claude"
    assert review["required_before_merge"] is True
    assert review["status"] == "independent_re_review_pending"
    assert {
        "M5-002 bucket-grid correction",
        "joint-valid cohort and exclusion accounting",
        "development internal-reuse and external leakage isolation",
        "frozen-model manifest and parameter hashes",
        "A_dev B and C_dev comparisons",
        "report verdict language",
    } == set(review["required_topics"])
