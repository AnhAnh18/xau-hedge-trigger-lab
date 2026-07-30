from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AMENDMENT_PATH = ROOT / "data" / "m5_004_provenance_amendment.json"
BASE_PATH = ROOT / "data" / "m5_004_preregistration.json"
MARKDOWN_PATH = (
    ROOT / ".local_ai" / "M5_004_PROVENANCE_AMENDMENT.md"
)
EXTERNAL_REPORT_PATH = (
    ROOT / "reports" / "phase_05" / "m5_003_external_validation_report.json"
)
FROZEN_MANIFEST_PATH = (
    ROOT / "reports" / "phase_05" / "m5_003_frozen_model_manifest.json"
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return sha256(normalized.encode("utf-8")).hexdigest()


def test_amendment_is_docs_only_and_locks_both_artifacts() -> None:
    amendment = _load(AMENDMENT_PATH)

    assert amendment["status"] == (
        "preregistered_amendment_only_no_implementation_no_fit"
    )
    assert amendment["scope"] == {
        "amendment_only": True,
        "implementation_authorized": False,
        "model_fit_authorized": False,
        "feature_construction_started": False,
        "model_fit_started": False,
        "canonical_m2_through_m5_003_outputs_mutable": False,
        "tradeable_edge_claim_allowed": False,
    }
    assert _canonical_text_sha256(MARKDOWN_PATH) == (
        "4c8537abcc2604ae11be4fdc937cb4fb1ac6b24a5bca6f25f34b2a0a4c6565ad"
    )
    assert _canonical_text_sha256(AMENDMENT_PATH) == (
        "50bef8e873f801fd7c23ae63678e195f2c500e3a6d48cf6f0411c9b27358a442"
    )


def test_base_contract_is_inherited_without_rewriting() -> None:
    amendment = _load(AMENDMENT_PATH)
    base = amendment["base_contract"]

    assert _canonical_text_sha256(BASE_PATH) == base[
        "machine_readable_sha256"
    ]
    assert _canonical_text_sha256(
        ROOT / base["human_readable_path"]
    ) == base["human_readable_sha256"]
    assert base["unchanged_except_explicit_amendment_fields"] is True
    inherited = amendment["inherited_by_reference"]
    assert all(
        inherited[key]
        for key in [
            "estimand_and_event_construction",
            "causal_anchors_and_windows",
            "exact_12_feature_allowlist",
            "forbidden_predictors",
            "joint_validity_and_outputs",
            "models_and_preprocessing",
            "selection_and_diagnostics",
            "ablations_and_multiplicity",
            "implementation_merge_gate",
        ]
    )
    assert inherited["group_and_bootstrap_key"] == (
        "cohort_id_colon_interval_id"
    )
    assert inherited[
        "m5_003_predictions_or_residuals_as_predictors_allowed"
    ] is False


def test_upstream_provenance_matches_merged_external_artifacts() -> None:
    amendment = _load(AMENDMENT_PATH)
    provenance = amendment["upstream_provenance"]
    external_report = _load(EXTERNAL_REPORT_PATH)
    manifest = _load(FROZEN_MANIFEST_PATH)

    assert provenance["m5_003_merge_commit"] == (
        "bd4715d0f06791e60ab01a44146a87d1297a6e56"
    )
    assert provenance["m5_003_external_report_sha256"] == external_report[
        "deterministic_report_sha256"
    ]
    locked = provenance["existing_locked_hashes_unchanged"]
    assert locked["m5_003_frozen_manifest_sha256"] == manifest[
        "frozen_manifest_sha256"
    ]
    assert locked["m5_003_preregistration_sha256"] == manifest[
        "preregistration_sha256"
    ]


def test_seen_external_sessions_are_permanently_non_gating() -> None:
    amendment = _load(AMENDMENT_PATH)
    cohort = amendment["cohorts"]["seen_external_reuse"]

    assert cohort["sessions"] == [
        "2026-07-27",
        "2026-07-28",
        "2026-07-29",
    ]
    assert cohort["role"] == "seen_external_reuse_diagnostic"
    assert cohort["evaluate_before_model_freeze_allowed"] is False
    assert cohort["fit_preprocess_select_calibrate_or_gate_allowed"] is False
    assert cohort["pool_with_future_external_allowed"] is False
    assert amendment["effective_decision_rule"][
        "development_internal_seen_external_reuse_or_M4_verdict_allowed"
    ] is False


def test_primary_and_fallback_blocks_are_complete_and_pre_registered() -> None:
    cohorts = _load(AMENDMENT_PATH)["cohorts"]

    assert cohorts["primary_external"] == {
        "sessions": [
            "2026-08-03",
            "2026-08-04",
            "2026-08-05",
            "2026-08-06",
            "2026-08-07",
        ],
        "role": "only_external_verdict_gate",
        "report_context_start": "2026-07-31",
        "report_coverage_end": "2026-08-08",
        "load_before_model_freeze_allowed": False,
    }
    assert cohorts["fallback_external"]["sessions"] == [
        "2026-08-10",
        "2026-08-11",
        "2026-08-12",
        "2026-08-13",
        "2026-08-14",
    ]
    assert cohorts["fallback_external"]["report_context_start"] == "2026-08-07"
    assert cohorts["fallback_external"]["report_coverage_end"] == "2026-08-15"


def test_gate_changes_only_session_count_and_uses_strict_positive_means() -> None:
    amendment = _load(AMENDMENT_PATH)
    inference = amendment["unchanged_inference_contract"]
    decision = amendment["effective_decision_rule"]

    assert inference["headline"] == (
        "external_1000ms_C_age_price_cause_minus_A_age_cause"
    )
    assert inference["bootstrap_draws"] == 5000
    assert inference["bootstrap_seed"] == 5004
    assert inference["bootstrap_cluster"] == "cohort_id_colon_interval_id"
    assert inference["loso_role"] == "required_descriptive_only_no_verdict"
    assert inference["sensitivity_500ms_role"] == (
        "timing_sensitivity_only_no_verdict_no_gate"
    )
    assert "at_least_3_of_5_daily_means_strictly_positive" in decision[
        "supported"
    ]
    assert decision["loso_can_create_or_override_verdict"] is False
    assert decision["sensitivity_500ms_can_create_or_override_verdict"] is False
    assert decision["zero_eligible_event_day"] == (
        "daily_mean_undefined_counts_as_not_positive_no_fallback"
    )
    assert amendment["explicit_deltas"]["session_coherence"] == {
        "old": "at_least_2_of_3_strictly_positive",
        "new": "at_least_3_of_5_strictly_positive",
        "reason": "mechanical_adaptation_to_five_sessions",
    }


def test_blind_intake_cannot_switch_blocks_on_model_outcomes() -> None:
    intake = _load(AMENDMENT_PATH)["blind_intake"]

    assert intake["complete_five_session_block_required"] is True
    assert intake["subset_verdict_allowed"] is False
    assert intake["interpolation_allowed"] is False
    assert intake["coverage_gap_threshold_seconds"] == 60
    assert intake[
        "replicated_gap_requires_independent_export_and_identical_boundary_ticks"
    ] is True
    assert "unlock_direction_balance" in intake["forbidden_outputs"]
    assert "model_performance" in intake["forbidden_outputs"]
    assert "low_sample_size" in intake["forbidden_fallback_reasons"]
    assert "no_eligible_unlock_on_a_day" in intake[
        "forbidden_fallback_reasons"
    ]
    assert "unknown_or_nonreplicated_material_quote_gap" in intake[
        "structural_fallback_reasons"
    ]


def test_future_external_files_remain_blocked_until_model_freeze() -> None:
    authorization = _load(AMENDMENT_PATH)["authorization"]

    assert authorization["independent_review_required_before_merge"] is True
    assert authorization["separate_implementation_authorization_required"] is True
    assert authorization[
        "future_external_acquisition_before_model_freeze_allowed"
    ] is False
    assert authorization[
        "evaluate_future_external_exactly_once_after_blind_intake"
    ] is True
