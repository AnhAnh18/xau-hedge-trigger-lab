from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "reports" / "phase_05" / "m5_003_price_increment_report.json"
MANIFEST_PATH = (
    ROOT / "reports" / "phase_05" / "m5_003_frozen_model_manifest.json"
)
PREREG_PATH = ROOT / "data" / "m5_003_preregistration.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _payload_hash(payload: dict, hash_field: str) -> str:
    source = dict(payload)
    source.pop(hash_field)
    encoded = json.dumps(source, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def _canonical_text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return sha256(normalized.encode("utf-8")).hexdigest()


def test_m5_003_report_is_frozen_external_pending_without_internal_verdict() -> None:
    report = _load(REPORT_PATH)

    assert report["status"] == (
        "pipeline_frozen_external_pending_zero_validated_price_results"
    )
    assert report["decision"] == {
        "development_verdict_allowed": False,
        "internal_reuse_verdict_allowed": False,
        "external_verdict_available": False,
        "external_support_requires_positive_sessions": 2,
        "registered_external_session_count": 3,
        "missing_external_session_substitution_allowed": False,
        "price_information_verdict": "not_available_external_pending",
        "tradeable_edge_claimed": False,
    }
    assert report["external_gate"]["data_available"] is False
    assert report["external_gate"]["satisfied"] is False
    assert report["external_gate"]["m5_closed"] is False
    assert report["merge_readiness"]["ready_to_merge"] is True
    assert report["merge_readiness"]["independent_re_review"] == (
        "independent_re_review_accepted_followups_applied"
    )


def test_m5_003_report_and_manifest_hashes_are_self_consistent() -> None:
    report = _load(REPORT_PATH)
    manifest = _load(MANIFEST_PATH)

    assert report["deterministic_report_sha256"] == _payload_hash(
        report, "deterministic_report_sha256"
    )
    assert manifest["frozen_manifest_sha256"] == _payload_hash(
        manifest, "frozen_manifest_sha256"
    )
    assert report["frozen_manifest_sha256"] == manifest[
        "frozen_manifest_sha256"
    ]
    assert manifest["preregistration_sha256"] == _canonical_text_sha256(
        PREREG_PATH
    )
    assert report["preregistration_sha256"] == manifest[
        "preregistration_sha256"
    ]


def test_m5_003_feature_and_immutable_input_gates_pass() -> None:
    report = _load(REPORT_PATH)
    accounting = report["feature_accounting"]

    assert all(report["validation_gates"].values())
    assert accounting["registered_internal_full_allowlist_audit"] == {
        "expected_dropped_bins": 937,
        "observed_dropped_bins": 937,
        "expected_dropped_targets": 3,
        "observed_dropped_targets": 3,
        "status": "PASS",
    }
    assert accounting["july23_unlock_floor_audit"] == {
        "dropped_bins": 3115,
        "dropped_targets": 0,
        "status": "PASS",
    }
    assert report["canonical_input_file_sha256_before"] == report[
        "canonical_input_file_sha256_after"
    ]
    assert report["m5_002_rebuild_attestation"][
        "local_parquet_values_equal_after_null_normalization"
    ] is True


def test_m5_003_manifest_locks_development_only_models_and_eleven_buckets() -> None:
    manifest = _load(MANIFEST_PATH)
    prereg = _load(PREREG_PATH)

    assert manifest["development_sessions"] == [
        "2026-07-20",
        "2026-07-21",
        "2026-07-22",
        "2026-07-23",
    ]
    assert manifest["internal_reuse_session"] == "2026-07-24"
    assert manifest["internal_reuse_loaded_for_fit"] is False
    assert manifest["external_loaded_for_fit_or_evaluation"] is False
    assert manifest["external_sessions"] == [
        "2026-07-27",
        "2026-07-28",
        "2026-07-29",
    ]
    allowed_lambdas = set(prereg["regularization"]["lambda_grid"])
    for width in manifest["widths"].values():
        assert width["development_sessions"] == manifest["development_sessions"]
        for endpoint in width["endpoints"].values():
            bundle = endpoint["fitted_bundle"]
            assert len(bundle["A_dev"]["bucket_labels"]) == 11
            assert bundle["A_dev"]["bucket_labels"][4:7] == [
                "age_5_6",
                "age_6_8",
                "age_8_10",
            ]
            assert bundle["C_dev"]["fit_intercept"] is False
            assert bundle["C_session"]["fit_intercept"] is False
            assert bundle["C_shape"]["fit_intercept"] is False
            assert bundle["A_session"]["parameterization"] == (
                "three_one_hot_block_effects_no_intercept"
            )
            assert bundle["A_session"]["server_hour_bounds"] == [
                [12, 16],
                [16, 20],
                [20, 24],
            ]
            assert len(bundle["A_session"]["parameters"]["coefficients"]) == 3
            assert endpoint["regularization_selection"]["models"]["B"][
                "selected_lambda"
            ] in allowed_lambdas
            assert endpoint["regularization_selection"]["models"]["C_dev"][
                "selected_lambda"
            ] in allowed_lambdas
            assert endpoint["regularization_selection"]["models"]["C_session"][
                "selected_lambda"
            ] in allowed_lambdas
            assert bundle["C_shape"]["regularization"] == bundle["C_session"][
                "regularization"
            ]
            assert all(
                fold["group_overlap"] == 0
                for fold in endpoint["regularization_selection"]["folds"]
            )


def test_m5_003_loso_and_internal_results_are_diagnostic_only() -> None:
    report = _load(REPORT_PATH)

    assert len(report["leave_one_session_out"]) == 12
    assert {row["held_out_session"] for row in report["leave_one_session_out"]} == {
        "2026-07-20",
        "2026-07-21",
        "2026-07-22",
        "2026-07-23",
    }
    assert all(
        row["role"]
        == "session_stability_diagnostic_only_no_selection_no_verdict"
        for row in report["leave_one_session_out"]
    )
    for width in ["1000", "500"]:
        for role in ["development", "internal_reuse"]:
            for endpoint in report["model_diagnostics"][width][role].values():
                assert endpoint["role"] == "diagnostic_only_no_verdict"
                assert endpoint["paired_interval_comparisons"][
                    "C_session_minus_A_session"
                ]["draws"] == 5000


def test_m5_003_session_remediation_is_explicit_and_internal_results_are_non_gating() -> None:
    report = _load(REPORT_PATH)
    prereg = _load(PREREG_PATH)
    internal = report["model_diagnostics"]["1000"]["internal_reuse"]

    assert prereg["review_driven_session_amendment"]["server_time_blocks"] == [
        [12, 16],
        [16, 20],
        [20, 24],
    ]
    assert prereg["secondary_shape_diagnostic"]["external_multiplicity"] == (
        "descriptive_only_no_supported_or_rejected_label"
    )
    expected = {
        "rehedge_buy_occurrence": (0.065349, 0.081396, 0.009696),
        "rehedge_sell_occurrence": (0.132032, 0.039308, 0.030655),
        "unlock_occurrence": (0.148346, 0.080685, 0.036852),
    }
    for endpoint, values in expected.items():
        metrics = internal[endpoint]["paired_interval_comparisons"]
        observed = (
            metrics["A_session_minus_A_dev"]["mean"],
            metrics["C_session_minus_A_session"]["mean"],
            metrics["C_shape_minus_A_session"]["mean"],
        )
        assert observed == pytest.approx(values, abs=1e-5)
        assert internal[endpoint]["role"] == "diagnostic_only_no_verdict"


def test_m5_003_markdown_publishes_registered_comparison_families() -> None:
    markdown = REPORT_PATH.with_suffix(".md").read_text(encoding="utf-8")

    for required in [
        "C_session−A_session",
        "C_session−B",
        "Registered one-second ablations",
        "500 ms causal-anchor sensitivity",
        "Multiplicity registry",
        "independent_re_review_accepted_followups_applied",
        "at least two of the three registered external-session means are positive",
    ]:
        assert required in markdown


def test_m5_003_committed_outputs_do_not_contain_row_identifiers() -> None:
    report_text = REPORT_PATH.read_text(encoding="utf-8")
    manifest_text = MANIFEST_PATH.read_text(encoding="utf-8")

    for forbidden in [
        '"risk_bin_id":',
        '"interval_id":',
        '"account_id":',
        '"position_id":',
        "D:\\Claude",
        "C:\\Users",
    ]:
        assert forbidden not in report_text
        assert forbidden not in manifest_text
