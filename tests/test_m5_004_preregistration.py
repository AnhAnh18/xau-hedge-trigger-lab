from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "data" / "m5_004_preregistration.json"


def _load() -> dict:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _canonical_text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return sha256(normalized.encode("utf-8")).hexdigest()


def test_m5_004_is_preregistered_without_fit_authority() -> None:
    plan = _load()

    assert plan["schema_version"] == 1
    assert plan["plan_id"] == "m5_004_unlock_cause_v1"
    assert plan["registered_on"] == "2026-07-27"
    assert plan["status"] == (
        "preregistered_stacked_on_reviewed_m5_003_no_fit"
    )
    assert plan["scope"] == {
        "task": "M5-004",
        "implementation_authorized": False,
        "model_fit_authorized": False,
        "canonical_outputs_mutable": False,
        "tradeable_edge_claim_allowed": False,
    }
    assert plan["implementation_gate"]["separate_authorization_required"] is True
    assert plan["implementation_gate"]["review_PR8_and_this_contract_first"] is True
    assert _canonical_text_sha256(PLAN_PATH) == (
        "f28a8eb35b236b8196788008e43ff613ad674c8815bf711a861067c453be8fea"
    )
    markdown = ROOT / ".local_ai" / "M5_004_PREREGISTRATION.md"
    assert _canonical_text_sha256(markdown) == (
        "d60c4e12dc84e72ab13da79402111acb00d66a814c02d4718d6cfa5a88059056"
    )


def test_m5_004_locks_current_m5_003_upstream_and_requires_amendment() -> None:
    upstream = _load()["upstream_dependency"]

    assert upstream["draft_pr"] == 8
    assert upstream["head_commit"] == (
        "7434505e9e6fcff7d8c427a51943ea6b571c3328"
    )
    assert upstream["review_status"] == (
        "independent_re_review_accepted_followups_applied"
    )
    assert upstream["amend_before_fit_if_hash_changes"] is True
    assert upstream["amended_on"] == "2026-07-27"
    assert upstream["m5_004_design_changed"] is False
    assert upstream["text_hash_policy"] == "canonical_utf8_lf"
    assert upstream["locked_hashes"] == {
        "m5_003_preregistration_sha256": (
            "4da95ca8b787e201a77f03fcfe1bf40145752bb967d4d847325349c528f50616"
        ),
        "m5_003_report_sha256": (
            "9b6cc69feea7fd031c039a7af7f6cf8900c6fcc21cd952f6eb1a4ea5d6824eb1"
        ),
        "m5_003_frozen_manifest_sha256": (
            "da2f9e0c66bdf8e51a349bc77db67fc3bbd1f8dc100d359890ac7ee54b14e747"
        ),
        "m5_003_feature_audit_dataframe_sha256": (
            "44183dbf388a9dc86344d3beaea480f0db3242488c66afa937ddef0475ce78b4"
        ),
        "m5_003_joint_valid_dataframe_sha256": (
            "69deadc6a6d2ed45ff12c15ef7659a73cf09ace74d27b496938dd057569800f2"
        ),
        "m5_002_risk_bin_dataframe_sha256": (
            "62f0f0fa4f961b699461c2c3ba935c460d853b4553142130187c503fb4698520"
        ),
    }


def test_m5_004_estimand_is_cause_conditional_on_observed_unlock() -> None:
    plan = _load()
    estimand = plan["estimand"]
    selection = plan["event_selection"]

    assert estimand["unit"] == "one_eligible_unlock_event"
    assert estimand["target"] == {"UNLOCK_TO_BUY": 1, "UNLOCK_TO_SELL": 0}
    assert estimand["non_event_risk_bins_as_negatives"] is False
    assert estimand["censored_or_competing_intervals_as_negatives"] is False
    assert estimand["occurrence_timing_claim_allowed"] is False
    assert selection["endpoint"] == "unlock_occurrence"
    assert selection["target_label"] == 1
    assert set(selection["allowed_following_event_types"]) == {
        "UNLOCK_TO_BUY",
        "UNLOCK_TO_SELL",
    }
    assert selection["minimum_tradeable_state_age_at_bin_start_seconds"] == 5
    assert selection["unexpected_target_cause_policy"] == "fatal"
    assert selection["missing_feature_policy"] == "joint_exclusion_no_imputation"


def test_m5_004_known_event_accounting_is_explicit() -> None:
    accounting = {
        (row["bin_width_ms"], row["role"]): row
        for row in _load()["known_internal_accounting"]
    }

    assert accounting[(1000, "development")] == {
        "bin_width_ms": 1000,
        "role": "development",
        "UNLOCK_TO_BUY": 714,
        "UNLOCK_TO_SELL": 730,
        "total": 1444,
    }
    assert accounting[(1000, "internal_reuse")]["total"] == 295
    assert accounting[(500, "development")]["total"] == 1445
    assert accounting[(500, "internal_reuse")]["total"] == 297
    for row in accounting.values():
        assert row["UNLOCK_TO_BUY"] + row["UNLOCK_TO_SELL"] == row["total"]


def test_m5_004_allowlist_is_exact_directional_and_partitioned() -> None:
    plan = _load()
    allowlist = plan["feature_allowlist"]
    groups = plan["feature_groups"]

    assert allowlist == [
        "mid_change_2s",
        "mid_change_5s",
        "tick_imbalance_2s",
        "tick_imbalance_5s",
        "range_position_2s",
        "range_position_5s",
        "range_position_10s",
        "prior_upper_boundary_touch_2s",
        "prior_lower_boundary_touch_2s",
        "prior_upper_boundary_touch_5s",
        "prior_lower_boundary_touch_5s",
        "state_start_displacement",
    ]
    assert len(allowlist) == len(set(allowlist)) == 12
    flattened = [feature for values in groups.values() for feature in values]
    assert len(flattened) == len(set(flattened))
    assert set(flattened) == set(allowlist)
    assert set(groups) == {
        "momentum",
        "range_location",
        "boundary_side",
        "state_path",
    }
    assert not set(allowlist) & set(plan["forbidden_predictors"])
    assert "spread_at_anchor" not in allowlist
    assert "matched_timestamp" not in allowlist


def test_m5_004_anchors_and_windows_are_causal() -> None:
    plan = _load()
    anchors = plan["anchors"]
    windows = plan["window_contract"]

    assert anchors["primary"]["bin_width_ms"] == 1000
    assert anchors["primary"]["role"] == "headline"
    assert anchors["sensitivity"]["bin_width_ms"] == 500
    assert anchors["sensitivity"]["role"] == (
        "timing_sensitivity_not_independent_replication"
    )
    assert anchors["matched_timestamp_as_model_anchor_allowed"] is False
    assert anchors["post_action_ticks_allowed"] is False
    assert windows["rolling_windows_seconds"] == [2, 5, 10]
    assert windows["prior_boundary_windows_seconds"] == [2, 5]
    assert windows["prior_boundary_interval"] == "[t-2w,t-w)"
    assert windows["touch_interval"] == "[t-w,t)"
    assert windows["touch_strictly_before_anchor"] is True
    assert windows["gap_crossing_window_valid"] is False
    assert windows["price_basis"] == "mid"


def test_m5_004_cohort_roles_prevent_internal_or_external_leakage() -> None:
    cohorts = _load()["cohorts"]

    assert cohorts["development"]["sessions"] == [
        "2026-07-20",
        "2026-07-21",
        "2026-07-22",
        "2026-07-23",
    ]
    assert cohorts["development"]["role"] == "fit_and_selection_only_no_verdict"
    assert cohorts["internal_reuse"]["sessions"] == ["2026-07-24"]
    assert cohorts["internal_reuse"][
        "labels_allowed_for_preprocessing_selection_or_calibration"
    ] is False
    assert cohorts["external"]["sessions"] == [
        "2026-07-27",
        "2026-07-28",
        "2026-07-29",
    ]
    assert cohorts["external"]["role"] == "only_verdict_gate"
    assert cohorts["external"]["load_before_model_freeze_allowed"] is False


def test_m5_004_models_preserve_age_baseline_and_no_free_c_intercept() -> None:
    models = _load()["models"]

    assert models["A_const_cause"]["alpha"] == 0.5
    assert models["A_age_cause"]["age_buckets_seconds"] == [
        [5, 6],
        [6, 8],
        [8, 10],
        [10, 20],
        [20, 30],
        [30, 60],
        [60, "inf"],
    ]
    assert models["A_age_cause"]["zero_training_event_bucket_policy"] == (
        "fatal_no_adaptive_merge_or_fallback"
    )
    assert models["B_price_cause"]["state_age_allowed"] is False
    assert models["C_age_price_cause"]["free_intercept"] is False
    assert models["C_age_price_cause"]["offset_coefficient"] == 1
    assert "fixed_logit_A_age_cause" in models["C_age_price_cause"]["definition"]


def test_m5_004_selection_inference_and_decision_are_fixed() -> None:
    plan = _load()
    selection = plan["selection"]
    inference = plan["inference"]
    decision = plan["decision_rule"]

    assert selection["regularization_grid"] == [0.0001, 0.001, 0.01, 0.1, 1, 10]
    assert selection["folds"] == 5
    assert selection["group"] == "cohort_id_colon_interval_id"
    assert selection["rule"] == "one_standard_error_strongest_eligible_penalty"
    assert selection["class_weighting_allowed"] is False
    assert selection["threshold_tuning_allowed"] is False
    assert selection["black_box_boosting_allowed"] is False
    assert inference["headline"] == (
        "external_1000ms_C_age_price_cause_minus_A_age_cause"
    )
    assert inference["bootstrap_draws"] == 5000
    assert inference["bootstrap_seed"] == 5004
    assert inference["per_external_session_results_required"] is True
    assert decision["development_internal_reuse_or_M4_verdict_allowed"] is False
    assert decision["occurrence_profitability_or_tradeable_edge_claim_allowed"] is False
    assert "at_least_2_of_3" in decision["supported"]


def test_m5_004_outputs_separate_audit_predictors_and_targets() -> None:
    output = _load()["output_contract"]

    assert output["local_audit"].endswith("_audit.parquet")
    assert output["local_predictors"].endswith("_predictors.parquet")
    assert output["local_targets"].endswith("_targets.parquet")
    assert output["local_predictions"].endswith("_predictions.parquet")
    assert output["sample_key_in_predictor_allowlist"] is False
    assert output["raw_data_committed"] is False
