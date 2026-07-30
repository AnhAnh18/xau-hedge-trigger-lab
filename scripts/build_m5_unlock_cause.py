from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.hazard_bins import dataframe_sha256
from xau_trigger.risk_time import detect_coverage_gaps
from xau_trigger.unlock_cause import (
    CAUSE_FEATURES,
    FEATURE_GROUPS,
    build_unlock_cause_dataset,
    canonical_hash,
    fit_cause_bundle,
    predict_cause_bundle,
    select_cause_regularization,
    summarize_cause_predictions,
)


WIDTHS_MS = (1000, 500)
DEVELOPMENT_DATES = (
    "2026-07-20",
    "2026-07-21",
    "2026-07-22",
    "2026-07-23",
)
INTERNAL_REUSE_DATE = "2026-07-24"
SEEN_REUSE_DATES = ("2026-07-27", "2026-07-28", "2026-07-29")
BOOTSTRAP_DRAWS = 5000
BOOTSTRAP_SEED = 5004

EXPECTED_INTERNAL_COUNTS = {
    "1000": {
        "development": {"UNLOCK_TO_BUY": 714, "UNLOCK_TO_SELL": 730},
        "internal_reuse": {"UNLOCK_TO_BUY": 160, "UNLOCK_TO_SELL": 135},
    },
    "500": {
        "development": {"UNLOCK_TO_BUY": 715, "UNLOCK_TO_SELL": 730},
        "internal_reuse": {"UNLOCK_TO_BUY": 160, "UNLOCK_TO_SELL": 137},
    },
}


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return sha256(normalized.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _canonical_snapshot() -> dict[str, str]:
    paths = [
        ROOT / "data" / "interim" / "ticks.parquet",
        ROOT / "data" / "interim" / "state_intervals.parquet",
        ROOT / "data" / "interim" / "lifecycle_events.parquet",
        ROOT / "data" / "interim" / "m5_002" / "m5_002_risk_bin_audit.parquet",
        ROOT / "data" / "interim" / "m5_003" / "m5_003_feature_audit.parquet",
        ROOT
        / "data"
        / "interim"
        / "m5_003"
        / "m5_003_joint_valid_design_matrix.parquet",
        ROOT / "reports" / "phase_05" / "m5_003_price_increment_report.json",
        ROOT / "reports" / "phase_05" / "m5_003_frozen_model_manifest.json",
    ]
    return {
        str(path.relative_to(ROOT)).replace("\\", "/"): _file_sha256(path)
        for path in paths
    }


def _verify_preregistered_provenance() -> dict:
    prereg = json.loads(
        (ROOT / "data" / "m5_004_preregistration.json").read_text(
            encoding="utf-8"
        )
    )
    amendment = json.loads(
        (ROOT / "data" / "m5_004_provenance_amendment.json").read_text(
            encoding="utf-8"
        )
    )
    m5_report = json.loads(
        (
            ROOT / "reports" / "phase_05" / "m5_003_price_increment_report.json"
        ).read_text(encoding="utf-8")
    )
    m5_manifest = json.loads(
        (
            ROOT / "reports" / "phase_05" / "m5_003_frozen_model_manifest.json"
        ).read_text(encoding="utf-8")
    )
    external_report = json.loads(
        (
            ROOT
            / "reports"
            / "phase_05"
            / "m5_003_external_validation_report.json"
        ).read_text(encoding="utf-8")
    )
    checks = {
        "base_contract_status_registered": prereg["status"].startswith(
            "preregistered"
        ),
        "amendment_status_registered": amendment["status"].startswith(
            "preregistered"
        ),
        "m5_003_report_hash_matches_contract": (
            m5_report["deterministic_report_sha256"]
            == "9b6cc69feea7fd031c039a7af7f6cf8900c6fcc21cd952f6eb1a4ea5d6824eb1"
        ),
        "m5_003_manifest_hash_matches_contract": (
            m5_manifest["frozen_manifest_sha256"]
            == "da2f9e0c66bdf8e51a349bc77db67fc3bbd1f8dc100d359890ac7ee54b14e747"
        ),
        "m5_003_external_hash_matches_amendment": (
            external_report["deterministic_report_sha256"]
            == "f4e12813d091030a61a843251a172fe356b8261313bf56efc913a28e7af431bf"
        ),
        "predictor_allowlist_exact": tuple(
            prereg["feature_allowlist"]
        )
        == CAUSE_FEATURES,
    }
    if not all(checks.values()):
        failed = [key for key, value in checks.items() if not value]
        raise AssertionError(f"M5-004 provenance check failed: {failed}")
    return {
        "checks": checks,
        "base_preregistration_canonical_text_sha256": _canonical_text_sha256(
            ROOT / ".local_ai" / "M5_004_PREREGISTRATION.md"
        ),
        "provenance_amendment_canonical_text_sha256": _canonical_text_sha256(
            ROOT / ".local_ai" / "M5_004_PROVENANCE_AMENDMENT.md"
        ),
        "base_machine_contract_sha256": _file_sha256(
            ROOT / "data" / "m5_004_preregistration.json"
        ),
        "amendment_machine_contract_sha256": _file_sha256(
            ROOT / "data" / "m5_004_provenance_amendment.json"
        ),
    }


def _counts(audit: pd.DataFrame) -> dict:
    result: dict[str, dict] = {}
    for width_ms, width in audit.groupby("bin_width_ms", sort=True):
        width_result: dict[str, dict] = {}
        for role, role_frame in width.groupby("analysis_role", sort=True):
            included = role_frame[role_frame["is_joint_valid"]]
            causes = {
                cause: int(count)
                for cause, count in included["following_event_type"]
                .value_counts()
                .sort_index()
                .items()
            }
            excluded = {
                str(reason): int(count)
                for reason, count in role_frame.loc[
                    ~role_frame["is_joint_valid"], "first_exclusion_reason"
                ]
                .value_counts()
                .sort_index()
                .items()
            }
            width_result[str(role)] = {
                "target_events": int(len(role_frame)),
                "joint_valid_events": int(len(included)),
                "causes": causes,
                "excluded_by_first_reason": excluded,
            }
        result[str(int(width_ms))] = width_result
    return result


def _assert_internal_accounting(accounting: dict) -> None:
    for width, roles in EXPECTED_INTERNAL_COUNTS.items():
        for role, expected in roles.items():
            actual = accounting[width][role]["causes"]
            if actual != expected:
                raise AssertionError(
                    f"Known M5-004 accounting changed for {width}/{role}: "
                    f"{actual} != {expected}"
                )


def _fit_full_development(design: pd.DataFrame) -> dict:
    widths = {}
    for width_ms in WIDTHS_MS:
        development = design[
            design["bin_width_ms"].eq(width_ms)
            & design["analysis_role"].eq("development")
        ].reset_index(drop=True)
        selection = select_cause_regularization(development)
        bundle = fit_cause_bundle(development, selection)
        widths[str(width_ms)] = {
            "development_events": int(len(development)),
            "development_groups": int(development["group_id"].nunique()),
            "development_sessions": sorted(
                development["session_date"].astype(str).unique()
            ),
            "regularization_selection": selection,
            "fitted_bundle": bundle,
        }
    return widths


def _predict_all(design: pd.DataFrame, manifest: dict) -> pd.DataFrame:
    predictions = []
    for width_ms in WIDTHS_MS:
        frame = design[design["bin_width_ms"].eq(width_ms)].reset_index(
            drop=True
        )
        prediction = predict_cause_bundle(
            frame, manifest["widths"][str(width_ms)]["fitted_bundle"]
        )
        predictions.append(prediction)
    return pd.concat(predictions, ignore_index=True).sort_values(
        ["bin_width_ms", "analysis_role", "session_date", "bin_start", "sample_id"],
        kind="stable",
    ).reset_index(drop=True)


def _leave_one_session_out(design: pd.DataFrame) -> dict:
    results: dict[str, list] = {}
    for width_ms in WIDTHS_MS:
        development = design[
            design["bin_width_ms"].eq(width_ms)
            & design["analysis_role"].eq("development")
        ].reset_index(drop=True)
        rows = []
        for held_session in DEVELOPMENT_DATES:
            train = development[
                ~development["session_date"].astype(str).eq(held_session)
            ].reset_index(drop=True)
            validation = development[
                development["session_date"].astype(str).eq(held_session)
            ].reset_index(drop=True)
            selection = select_cause_regularization(train)
            bundle = fit_cause_bundle(train, selection)
            prediction = predict_cause_bundle(validation, bundle)
            summary = summarize_cause_predictions(
                prediction,
                bootstrap_draws=BOOTSTRAP_DRAWS,
                bootstrap_seed=BOOTSTRAP_SEED,
            )
            rows.append(
                {
                    "held_session": held_session,
                    "training_events": int(len(train)),
                    "validation_events": int(len(validation)),
                    "training_sessions": sorted(
                        train["session_date"].astype(str).unique()
                    ),
                    "selected_lambdas": {
                        model: values["selected_lambda"]
                        for model, values in selection["models"].items()
                    },
                    "summary": summary,
                }
            )
        results[str(width_ms)] = rows
    return results


def _summaries_by_role(predictions: pd.DataFrame) -> dict:
    output: dict[str, dict] = {}
    for width_ms, width in predictions.groupby("bin_width_ms", sort=True):
        output[str(int(width_ms))] = {}
        for role, frame in width.groupby("analysis_role", sort=True):
            output[str(int(width_ms))][str(role)] = summarize_cause_predictions(
                frame.reset_index(drop=True),
                bootstrap_draws=BOOTSTRAP_DRAWS,
                bootstrap_seed=BOOTSTRAP_SEED,
            )
    return output


def _render_markdown(report: dict) -> str:
    lines = [
        "# M5-004 Unlock-Cause Development Package",
        "",
        f"Status: `{report['status']}`",
        "",
        "## Scope",
        "",
        "This package estimates `P(UNLOCK_TO_BUY | an eligible unlock occurred)`.",
        "It is not an occurrence model, P/L model, execution rule, or tradeable-edge claim.",
        "The August primary external block has not been loaded.",
        "",
        "## Frozen development package",
        "",
        f"- Predictor allowlist: {len(report['predictor_allowlist'])} raw-directional features.",
        f"- Bootstrap: {BOOTSTRAP_DRAWS} deterministic interval-cluster draws, seed {BOOTSTRAP_SEED}.",
        "- Fit sessions: 2026-07-20 through 2026-07-23 only.",
        "- 2026-07-24 and 2026-07-27 through 2026-07-29 are descriptive reuse diagnostics only.",
        "",
        "## Event accounting",
        "",
        "| Width | Role | Buy | Sell | Joint valid | Excluded |",
        "| ---: | --- | ---: | ---: | ---: | ---: |",
    ]
    for width, roles in report["event_accounting"].items():
        for role, values in roles.items():
            causes = values["causes"]
            lines.append(
                f"| {width} ms | {role} | "
                f"{causes.get('UNLOCK_TO_BUY', 0)} | "
                f"{causes.get('UNLOCK_TO_SELL', 0)} | "
                f"{values['joint_valid_events']} | "
                f"{values['target_events'] - values['joint_valid_events']} |"
            )
    lines.extend(["", "## Diagnostic likelihood increments", ""])
    for width, roles in report["diagnostics"].items():
        lines.extend([f"### {width} ms", ""])
        for role, values in roles.items():
            headline = values["comparisons"][
                "C_age_price_cause_minus_A_age_cause"
            ]
            secondary = values["comparisons"][
                "C_age_price_cause_minus_B_price_cause"
            ]
            lines.append(
                f"- `{role}`: C-A mean `{headline['mean']:.6f}` "
                f"(95% `{headline['ci95_low']:.6f}`, `{headline['ci95_high']:.6f}`); "
                f"C-B mean `{secondary['mean']:.6f}`."
            )
        lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            "All results in this report are development, internal-reuse, or seen-external-reuse diagnostics.",
            "They cannot create an M5-004 verdict. Only a blind accepted 2026-08-03 through",
            "2026-08-07 block can satisfy the registered external gate.",
            "",
            "## Validation",
            "",
        ]
    )
    for key, value in report["validation_gates"].items():
        lines.append(f"- `{key}`: {'PASS' if value else 'FAIL'}")
    lines.extend(
        [
            "",
            f"Deterministic report hash: `{report['deterministic_report_sha256']}`",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    provenance = _verify_preregistered_provenance()
    canonical_before = _canonical_snapshot()
    interim = ROOT / "data" / "interim"
    output_dir = interim / "m5_004"
    report_dir = ROOT / "reports" / "phase_05"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Internal and retrospective inputs are the only data loaded before freeze.
    internal_feature_audit = pd.read_parquet(
        interim / "m5_003" / "m5_003_feature_audit.parquet"
    )
    ticks_by_cohort = {
        "internal_2026_07_23_24": pd.read_parquet(interim / "ticks.parquet"),
        "supplemental_2026_07_20_22": pd.read_parquet(
            interim / "m5_002" / "ticks_supplemental_2026_07_20_22.parquet"
        ),
    }
    gaps_by_cohort = {
        cohort_id: detect_coverage_gaps(
            ticks[["timestamp"]], threshold_seconds=60
        )
        for cohort_id, ticks in ticks_by_cohort.items()
    }
    audit, predictors, targets, design = build_unlock_cause_dataset(
        internal_feature_audit,
        ticks_by_cohort,
        gaps_by_cohort,
    )
    accounting = _counts(audit)
    _assert_internal_accounting(accounting)

    manifest = {
        "schema_version": 1,
        "milestone": "M5-004",
        "status": "frozen_before_seen_reuse_and_future_external_loading",
        "estimand": "P(UNLOCK_TO_BUY | eligible unlock occurred)",
        "development_sessions": list(DEVELOPMENT_DATES),
        "internal_reuse_session": INTERNAL_REUSE_DATE,
        "seen_external_reuse_sessions": list(SEEN_REUSE_DATES),
        "primary_untouched_external_sessions": [
            "2026-08-03",
            "2026-08-04",
            "2026-08-05",
            "2026-08-06",
            "2026-08-07",
        ],
        "predictor_allowlist": list(CAUSE_FEATURES),
        "feature_groups": {
            key: list(values) for key, values in FEATURE_GROUPS.items()
        },
        "group_and_bootstrap_key": "cohort_id:interval_id",
        "bootstrap_draws": BOOTSTRAP_DRAWS,
        "bootstrap_seed": BOOTSTRAP_SEED,
        "provenance": provenance,
        "canonical_inputs_before_fit": canonical_before,
        "internal_accounting": accounting,
        "widths": _fit_full_development(design),
        "internal_reuse_loaded_for_fit_or_selection": False,
        "seen_external_reuse_loaded_before_freeze": False,
        "future_external_loaded_before_freeze": False,
    }
    manifest["frozen_manifest_sha256"] = canonical_hash(manifest)
    manifest_path = report_dir / "m5_004_frozen_model_manifest.json"
    # This write is deliberately before any 2026-07-27..29 input is opened.
    _write_json(manifest_path, manifest)

    internal_predictions = _predict_all(design, manifest)
    loso = _leave_one_session_out(design)

    # Seen external reuse is loaded only after the model package is frozen.
    external_dir = interim / "m5_003_external"
    external_feature_audit = pd.read_parquet(
        external_dir / "m5_003_external_feature_audit.parquet"
    ).copy()
    external_feature_audit["analysis_role"] = (
        "seen_external_reuse_diagnostic"
    )
    external_ticks = pd.read_parquet(
        external_dir / "m5_003_external_ticks.parquet"
    )
    external_gaps = pd.read_parquet(
        external_dir / "m5_003_external_coverage_gaps.parquet"
    )
    ext_audit, ext_predictors, ext_targets, ext_design = (
        build_unlock_cause_dataset(
            external_feature_audit,
            {"external_2026_07_27_29": external_ticks},
            {"external_2026_07_27_29": external_gaps},
        )
    )
    ext_predictions = _predict_all(ext_design, manifest)

    all_audit = pd.concat([audit, ext_audit], ignore_index=True).sort_values(
        ["bin_width_ms", "analysis_role", "session_date", "bin_start", "sample_id"],
        kind="stable",
    ).reset_index(drop=True)
    all_predictors = pd.concat(
        [predictors, ext_predictors], ignore_index=True
    ).sort_values("sample_id", kind="stable").reset_index(drop=True)
    all_targets = pd.concat(
        [targets, ext_targets], ignore_index=True
    ).sort_values("sample_id", kind="stable").reset_index(drop=True)
    all_predictions = pd.concat(
        [internal_predictions, ext_predictions], ignore_index=True
    ).sort_values(
        ["bin_width_ms", "analysis_role", "session_date", "bin_start", "sample_id"],
        kind="stable",
    ).reset_index(drop=True)

    paths = {
        "audit": output_dir / "m5_004_unlock_cause_audit.parquet",
        "predictors": output_dir / "m5_004_unlock_cause_predictors.parquet",
        "targets": output_dir / "m5_004_unlock_cause_targets.parquet",
        "predictions": output_dir / "m5_004_unlock_cause_predictions.parquet",
    }
    all_audit.to_parquet(paths["audit"], index=False)
    all_predictors.to_parquet(paths["predictors"], index=False)
    all_targets.to_parquet(paths["targets"], index=False)
    all_predictions.to_parquet(paths["predictions"], index=False)

    event_accounting = _counts(all_audit)
    diagnostics = _summaries_by_role(all_predictions)
    canonical_after = _canonical_snapshot()
    validation = {
        "upstream_provenance_reconciles": all(provenance["checks"].values()),
        "canonical_m2_to_m5_003_outputs_unchanged": (
            canonical_before == canonical_after
        ),
        "known_internal_event_counts_reconcile": True,
        "one_row_per_unlock_event": not all_audit.duplicated(
            ["cohort_id", "interval_id", "bin_width_ms"]
        ).any(),
        "predictor_allowlist_exact": list(all_predictors.columns)
        == ["sample_id", *CAUSE_FEATURES],
        "labels_absent_from_predictors": "cause_label"
        not in all_predictors.columns,
        "metadata_absent_from_predictor_allowlist": set(CAUSE_FEATURES).isdisjoint(
            {
                "sample_id",
                "cohort_id",
                "interval_id",
                "timestamp",
                "bin_start",
                "bin_end",
                "cause_label",
                "following_event_type",
            }
        ),
        "development_only_fit_sessions": all(
            item["development_sessions"] == list(DEVELOPMENT_DATES)
            for item in manifest["widths"].values()
        ),
        "internal_reuse_not_loaded_for_fit": not manifest[
            "internal_reuse_loaded_for_fit_or_selection"
        ],
        "seen_reuse_loaded_only_after_manifest_write": manifest_path.exists()
        and not manifest["seen_external_reuse_loaded_before_freeze"],
        "future_external_not_loaded": not manifest[
            "future_external_loaded_before_freeze"
        ],
        "all_prediction_probabilities_finite_and_bounded": bool(
            all_predictions.filter(regex=r"^p_")
            .apply(lambda column: column.between(0.0, 1.0).all())
            .all()
        ),
        "group_key_collision_safe": all(
            all_predictions["group_id"].eq(
                all_predictions["cohort_id"].astype(str)
                + ":"
                + all_predictions["interval_id"].astype(str)
            )
        ),
        "no_tradeable_edge_claim": True,
    }
    if not all(validation.values()):
        failed = [key for key, value in validation.items() if not value]
        raise AssertionError(f"M5-004 validation failed: {failed}")

    output_hashes = {
        key: {
            "dataframe_sha256": dataframe_sha256(frame),
            "file_sha256": _file_sha256(paths[key]),
            "rows": int(len(frame)),
        }
        for key, frame in {
            "audit": all_audit,
            "predictors": all_predictors,
            "targets": all_targets,
            "predictions": all_predictions,
        }.items()
    }
    report = {
        "schema_version": 1,
        "milestone": "M5-004",
        "status": "development_package_frozen_future_external_pending",
        "estimand": "P(UNLOCK_TO_BUY | eligible unlock occurred)",
        "predictor_allowlist": list(CAUSE_FEATURES),
        "frozen_manifest_sha256": manifest["frozen_manifest_sha256"],
        "event_accounting": event_accounting,
        "diagnostics": diagnostics,
        "leave_one_session_out_development_diagnostic": loso,
        "decision": {
            "verdict": None,
            "reason": (
                "No M5-004 verdict is permitted before blind evaluation on "
                "the accepted 2026-08-03 through 2026-08-07 block."
            ),
            "seen_external_reuse_role": "descriptive_diagnostic_only",
        },
        "limitations": [
            "Cause classification is conditional on an eligible unlock already occurring.",
            "Report timestamps have one-second resolution; sub-second triggers are not identified.",
            "Internal and seen-reuse diagnostics cannot validate the frozen package.",
            "No profitability, execution feasibility, or tradeable edge is established.",
        ],
        "output_hashes": output_hashes,
        "canonical_input_file_sha256_before": canonical_before,
        "canonical_input_file_sha256_after": canonical_after,
        "validation_gates": validation,
    }
    report["deterministic_report_sha256"] = canonical_hash(report)
    report_path = report_dir / "m5_004_unlock_cause_report.json"
    markdown_path = report_dir / "m5_004_unlock_cause_report.md"
    _write_json(report_path, report)
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": report["status"],
                "manifest_sha256": manifest["frozen_manifest_sha256"],
                "report_sha256": report["deterministic_report_sha256"],
                "output_hashes": output_hashes,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
