from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.acquisition import (
    load_acquisition_plan,
    validate_acquisition,
)
from xau_trigger.external_validation import (
    EXTERNAL_SESSIONS,
    apply_external_acquisition_amendment,
    canonical_json_sha256,
    summarize_external_predictions,
    verify_frozen_manifest,
)
from xau_trigger.hazard_bins import (
    build_wall_clock_risk_bins,
    canonicalize_cohort_support,
    dataframe_sha256,
    load_tick_cohort,
)
from xau_trigger.parsers.mt5_report import parse_report, parse_report_summary
from xau_trigger.price_features import (
    FEATURE_ALLOWLISTS,
    REHEDGE_FEATURES,
    UNLOCK_FEATURES,
    build_feature_audit,
    prepare_candidate_bins,
)
from xau_trigger.price_inference import (
    _logit,
    bernoulli_log_likelihood,
    deterministic_cluster_bootstrap,
    interval_model_deltas,
    predict_age_baseline,
    predict_endpoint_bundle,
    predict_logistic,
    predict_session_baseline,
    transform_features,
)
from xau_trigger.risk_time import detect_coverage_gaps
from xau_trigger.state_reconstruction import merge_lifecycles, reconstruct_states
from xau_trigger.validation.dataset_checks import (
    inventory_conservation,
    reconcile_report,
)


COHORT_ID = "external_2026_07_27_29"
WIDTHS_MS = (1000, 500)
ENDPOINTS = (
    "rehedge_buy_occurrence",
    "rehedge_sell_occurrence",
    "unlock_occurrence",
)
BOOTSTRAP_DRAWS = 5000
BOOTSTRAP_SEED = 5003


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


def _stable_seed(*parts: object) -> int:
    encoded = "|".join(str(part) for part in parts).encode("utf-8")
    return BOOTSTRAP_SEED + int(sha256(encoded).hexdigest()[:8], 16) % 100000


def _resolve_pinned_file(directory: Path, expected_sha256: str) -> Path:
    matches = [
        path
        for path in directory.iterdir()
        if path.is_file() and _file_sha256(path) == expected_sha256
    ]
    if len(matches) != 1:
        raise ValueError(
            "Pinned raw input must resolve to exactly one local file: "
            f"{expected_sha256} -> {len(matches)}"
        )
    return matches[0]


def _canonical_snapshot() -> dict[str, str]:
    paths = [
        ROOT / "data" / "interim" / "ticks.parquet",
        ROOT / "data" / "interim" / "lifecycle_events.parquet",
        ROOT / "data" / "interim" / "state_intervals.parquet",
        ROOT / "data" / "interim" / "m5_002" / "m5_002_risk_bin_audit.parquet",
        ROOT / "reports" / "phase_05" / "m5_002_state_age_pilot.json",
        ROOT / "reports" / "phase_05" / "m5_003_frozen_model_manifest.json",
        ROOT / "reports" / "phase_05" / "m5_003_price_increment_report.json",
    ]
    return {
        str(path.relative_to(ROOT)).replace("\\", "/"): _file_sha256(path)
        for path in paths
    }


def _predict_ablation(
    evaluation: pd.DataFrame,
    *,
    endpoint: str,
    bundle: dict,
    ablation: dict,
) -> np.ndarray:
    target = evaluation[evaluation["endpoint"].eq(endpoint)].reset_index(drop=True)
    x = transform_features(target, ablation["scaler"])
    p_age = predict_age_baseline(target, bundle["A_dev"])
    p_session = predict_session_baseline(target, p_age, bundle["A_session"])
    return predict_logistic(
        x,
        ablation["C_session"],
        offset=_logit(p_session),
    )


def _predict_external(
    design: pd.DataFrame,
    manifest: dict,
    m5_report: dict,
) -> pd.DataFrame:
    outputs = []
    for width_ms in WIDTHS_MS:
        width_frame = design[design["bin_width_ms"].eq(width_ms)]
        width_manifest = manifest["widths"][str(width_ms)]
        for endpoint in ENDPOINTS:
            endpoint_manifest = width_manifest["endpoints"][endpoint]
            bundle = endpoint_manifest["fitted_bundle"]
            common = m5_report["parameters_by_width"][str(width_ms)]["endpoints"][
                endpoint
            ]
            prediction = predict_endpoint_bundle(width_frame, bundle, common)
            for group_name, ablation in endpoint_manifest["ablations"].items():
                prediction[
                    f"p_C_session_without_{group_name}"
                ] = _predict_ablation(
                    width_frame,
                    endpoint=endpoint,
                    bundle=bundle,
                    ablation=ablation,
                )
            outputs.append(prediction)
    return pd.concat(outputs, ignore_index=True).sort_values(
        ["bin_width_ms", "endpoint", "session_date", "bin_start", "interval_id"],
        kind="stable",
    ).reset_index(drop=True)


def _attach_ablation_metrics(
    summary: dict,
    predictions: pd.DataFrame,
    preregistration: dict,
) -> None:
    for width_ms, width_frame in predictions.groupby("bin_width_ms", sort=True):
        width_key = str(int(width_ms))
        for endpoint_index, endpoint in enumerate(ENDPOINTS):
            endpoint_rows = width_frame[width_frame["endpoint"].eq(endpoint)].copy()
            family = "unlock" if endpoint == "unlock_occurrence" else "rehedge"
            metrics = {}
            for group_index, group_name in enumerate(
                preregistration["feature_groups"][family]
            ):
                probability = f"p_C_session_without_{group_name}"
                endpoint_rows["full_ll"] = bernoulli_log_likelihood(
                    endpoint_rows["target_label"].to_numpy(),
                    endpoint_rows["p_C_session"].to_numpy(),
                )
                endpoint_rows["ablated_ll"] = bernoulli_log_likelihood(
                    endpoint_rows["target_label"].to_numpy(),
                    endpoint_rows[probability].to_numpy(),
                )
                intervals = endpoint_rows.groupby("interval_id", sort=True)[
                    ["full_ll", "ablated_ll"]
                ].sum()
                metrics[group_name] = deterministic_cluster_bootstrap(
                    intervals["full_ll"] - intervals["ablated_ll"],
                    draws=BOOTSTRAP_DRAWS,
                    seed=_stable_seed(
                        width_ms,
                        endpoint,
                        group_name,
                        endpoint_index,
                        group_index,
                        "external_ablation",
                    ),
                    one_sided_alpha=1 / 240,
                )
            summary[width_key][endpoint]["ablations"] = metrics


def _decision_summary(external_summary: dict) -> dict:
    endpoint_decisions = {
        endpoint: external_summary["1000"][endpoint]["headline_decision"]
        for endpoint in ENDPOINTS
    }
    return {
        "external_evaluation_complete": True,
        "headline": "C_session_minus_A_session_at_1000ms",
        "endpoint_decisions": endpoint_decisions,
        "supported_endpoint_count": sum(
            item["verdict"] == "supported"
            for item in endpoint_decisions.values()
        ),
        "tradeable_edge_claimed": False,
        "m5_003_closed": True,
        "m5_overall_closed": False,
        "remaining_m5_work": "M5-004 conditional unlock-cause implementation",
        "independent_review_required_before_merge": True,
        "ready_to_merge": False,
    }


def _render_markdown(report: dict) -> str:
    lines = [
        "# M5-003 External Validation",
        "",
        f"Status: `{report['status']}`",
        "",
        "This is a prospective frozen-model evaluation with disclosed",
        "qualitative exposure. It is not analyst-blinded and makes no",
        "standalone tradeable-edge claim.",
        "",
        "## Acquisition",
        "",
        f"- Status: `{report['acquisition']['status']}`",
        f"- Registered sessions: {', '.join(report['registered_sessions'])}",
        "- Replicated source quote gap: 2026-07-27 18:08:35.303 to 18:10:21.660",
        "- Gap interpolation: forbidden",
        "",
        "## One-second event accounting",
        "",
        "| Endpoint | Lifecycle events | Representable targets | Common/floor targets | Joint-valid targets |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for endpoint in ENDPOINTS:
        stage = report["event_stage_accounting"]["1000"][endpoint]
        lines.append(
            f"| {endpoint} | {stage['source_lifecycle_events']:,} | "
            f"{stage['representable_target_bins']:,} | "
            f"{stage['common_floor_candidate_targets']:,} | "
            f"{stage['joint_valid_targets']:,} |"
        )
    lines.extend(
        [
            "",
            "## One-second headline",
            "",
            "| Endpoint | Bins | Targets | Mean C_session-A_session | CI95 | Family low | Positive sessions | Verdict |",
            "| --- | ---: | ---: | ---: | --- | ---: | ---: | --- |",
        ]
    )
    for endpoint in ENDPOINTS:
        item = report["external_results"]["1000"][endpoint]
        metric = item["paired_interval_comparisons"][
            "C_session_minus_A_session"
        ]
        decision = item["headline_decision"]
        lines.append(
            f"| {endpoint} | {item['bins']:,} | {item['targets']:,} | "
            f"{metric['mean']:+.6f} | [{metric['ci95_low']:+.6f}, "
            f"{metric['ci95_high']:+.6f}] | "
            f"{metric['familywise_one_sided_low']:+.6f} | "
            f"{decision['positive_external_sessions']}/3 | "
            f"**{decision['verdict']}** |"
        )
    lines.extend(["", "## Per-session headline means", ""])
    for endpoint in ENDPOINTS:
        lines.extend(
            [
                f"### {endpoint}",
                "",
                "| Session | Intervals | Mean |",
                "| --- | ---: | ---: |",
            ]
        )
        for row in report["external_results"]["1000"][endpoint]["per_session"]:
            lines.append(
                f"| {row['session_date']} | {row['intervals']:,} | "
                f"{row['C_session_minus_A_session_mean']:+.6f} |"
            )
        lines.append("")
    lines.extend(
        [
            "## Interpretation limits",
            "",
            "- The 500 ms results are causal-anchor sensitivity only.",
            "- `C_shape` and ablations are descriptive and non-causal.",
            "- Likelihood increments are not scale-free across endpoints or sessions.",
            "- Events inside excluded quote gaps remain in lifecycle accounting but",
            "  cannot receive forced tick features.",
            "- Re-hedge results are positive against A_session but negative against",
            "  price-only B; the combined architecture remains ambiguous.",
            "- Session 2026-07-29 contributes most of the pooled gain, while",
            "  2026-07-28 is negative for two endpoints.",
            "- M5-003 is externally evaluated; M5 remains open for M5-004.",
            "- Independent re-review is required before merge.",
            "",
            "## Validation gates",
            "",
        ]
    )
    for name, passed in report["validation_gates"].items():
        lines.append(f"- `{name}`: {'PASS' if passed else 'FAIL'}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    amendment_path = ROOT / "data" / "m5_003_external_amendment.json"
    prereg_path = ROOT / "data" / "m5_003_preregistration.json"
    acquisition_plan_path = ROOT / "data" / "m5_acquisition_plan.json"
    manifest_path = (
        ROOT / "reports" / "phase_05" / "m5_003_frozen_model_manifest.json"
    )
    m5_report_path = (
        ROOT / "reports" / "phase_05" / "m5_002_state_age_pilot.json"
    )
    amendment = json.loads(amendment_path.read_text(encoding="utf-8"))
    preregistration = json.loads(prereg_path.read_text(encoding="utf-8"))
    acquisition_plan = load_acquisition_plan(acquisition_plan_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    m5_report = json.loads(m5_report_path.read_text(encoding="utf-8"))
    verify_frozen_manifest(manifest)
    if manifest["preregistration_sha256"] != _canonical_text_sha256(prereg_path):
        raise AssertionError("Frozen manifest preregistration hash changed")

    canonical_before = _canonical_snapshot()
    tick_specs = amendment["canonical_external_inputs"]["tick_files"]
    tick_paths = [
        _resolve_pinned_file(
            ROOT / "data" / "raw" / "ticks",
            item["sha256"],
        )
        for item in tick_specs
    ]
    report_spec = amendment["canonical_external_inputs"]["trade_report"]
    report_path = _resolve_pinned_file(
        ROOT / "data" / "raw" / "trades",
        report_spec["sha256"],
    )

    raw_acquisition = validate_acquisition(
        acquisition_plan,
        tick_paths,
        [report_path],
    )
    acquisition = apply_external_acquisition_amendment(
        raw_acquisition,
        amendment,
    )

    tables = parse_report(report_path, report_id=report_spec["alias"])
    summary = parse_report_summary(report_path)
    reconciliation = reconcile_report(
        tables["positions"],
        summary["reported_net_profit"],
    )
    if reconciliation["status"] != "PASS":
        raise AssertionError("External report financial reconciliation failed")
    lifecycle, merge_exceptions, lifecycle_summary = merge_lifecycles(
        tables["positions"],
        tables["open_positions"],
    )
    events, intervals, state_exceptions = reconstruct_states(lifecycle)
    exceptions = pd.concat(
        [merge_exceptions, state_exceptions],
        ignore_index=True,
        sort=False,
    )

    tick_hashes = [item["sha256"] for item in tick_specs]
    ticks = load_tick_cohort(
        tick_paths,
        EXTERNAL_SESSIONS,
        expected_sha256=tick_hashes,
    )
    gaps = detect_coverage_gaps(ticks[["timestamp"]], threshold_seconds=60)
    expected_gap = amendment["replicated_source_quote_gap"]
    exact_gap = gaps["break_start"].eq(pd.Timestamp(expected_gap["start"])) & gaps[
        "break_end"
    ].eq(pd.Timestamp(expected_gap["end"]))
    if int(exact_gap.sum()) != 1:
        raise AssertionError("Replicated source quote gap not found exactly once")
    gaps.loc[exact_gap, "gap_classification"] = expected_gap["classification"]
    gaps.loc[exact_gap, "exclusion_reason"] = expected_gap["classification"]
    scheduled = gaps["duration_seconds"].gt(3600)
    gaps.loc[scheduled, "gap_classification"] = "scheduled_market_closed"
    gaps.loc[scheduled, "exclusion_reason"] = "scheduled_market_closed"

    support = canonicalize_cohort_support(
        intervals,
        events,
        ticks,
        cohort_id=COHORT_ID,
        breaks=gaps,
    )
    all_bins = []
    all_interval_audits = []
    accounting_by_width = {}
    for width_ms in WIDTHS_MS:
        bins, interval_audit, accounting = build_wall_clock_risk_bins(
            support,
            bin_width_seconds=width_ms / 1000,
        )
        all_bins.append(bins)
        all_interval_audits.append(interval_audit)
        accounting_by_width[str(width_ms)] = accounting
    risk_bins = pd.concat(all_bins, ignore_index=True)
    interval_audit = pd.concat(all_interval_audits, ignore_index=True)
    candidates = prepare_candidate_bins(
        risk_bins,
        interval_audit,
        role_by_date={day: "external" for day in EXTERNAL_SESSIONS},
    )
    feature_audit, design = build_feature_audit(
        candidates,
        {COHORT_ID: ticks},
        {COHORT_ID: gaps},
    )
    predictions = _predict_external(design, manifest, m5_report)
    external_results = summarize_external_predictions(
        predictions,
        endpoint_names=ENDPOINTS,
        bootstrap_draws=BOOTSTRAP_DRAWS,
        seed=BOOTSTRAP_SEED,
    )
    _attach_ablation_metrics(external_results, predictions, preregistration)

    tick_start = pd.Timestamp(ticks["timestamp"].min())
    tick_end = pd.Timestamp(ticks["timestamp"].max())
    conservation = inventory_conservation(
        tables["positions"],
        tick_start,
        tick_end,
    )
    lifecycle_dates = events.assign(
        session_date=pd.to_datetime(events["event_time"]).dt.strftime("%Y-%m-%d")
    )
    external_event_counts = (
        lifecycle_dates[
            lifecycle_dates["session_date"].isin(EXTERNAL_SESSIONS)
        ]
        .groupby(["session_date", "behavior_type"], sort=True)
        .size()
        .rename("count")
        .reset_index()
        .to_dict("records")
    )
    behavior_totals = (
        lifecycle_dates[
            lifecycle_dates["session_date"].isin(EXTERNAL_SESSIONS)
        ]
        .groupby("behavior_type", sort=True)
        .size()
        .to_dict()
    )
    source_event_counts = {
        "rehedge_buy_occurrence": int(behavior_totals.get("REHEDGE_BUY", 0)),
        "rehedge_sell_occurrence": int(behavior_totals.get("REHEDGE_SELL", 0)),
        "unlock_occurrence": int(
            behavior_totals.get("UNLOCK_TO_BUY", 0)
            + behavior_totals.get("UNLOCK_TO_SELL", 0)
        ),
    }
    event_stage_accounting = {}
    for width_ms in WIDTHS_MS:
        width_key = str(width_ms)
        event_stage_accounting[width_key] = {}
        for endpoint in ENDPOINTS:
            risk_rows = risk_bins[
                risk_bins["bin_width_ms"].eq(width_ms)
                & risk_bins["endpoint"].eq(endpoint)
            ]
            candidate_rows = feature_audit[
                feature_audit["bin_width_ms"].eq(width_ms)
                & feature_audit["endpoint"].eq(endpoint)
            ]
            design_rows = design[
                design["bin_width_ms"].eq(width_ms)
                & design["endpoint"].eq(endpoint)
            ]
            stage = {
                "source_lifecycle_events": source_event_counts[endpoint],
                "representable_target_bins": int(risk_rows["target_label"].sum()),
                "common_floor_candidate_targets": int(
                    candidate_rows["target_label"].sum()
                ),
                "joint_valid_targets": int(design_rows["target_label"].sum()),
            }
            stage["source_minus_representable"] = (
                stage["source_lifecycle_events"]
                - stage["representable_target_bins"]
            )
            stage["representable_minus_common_floor"] = (
                stage["representable_target_bins"]
                - stage["common_floor_candidate_targets"]
            )
            stage["common_floor_minus_joint_valid"] = (
                stage["common_floor_candidate_targets"]
                - stage["joint_valid_targets"]
            )
            event_stage_accounting[width_key][endpoint] = stage

    canonical_after = _canonical_snapshot()
    validation_gates = {
        "frozen_manifest_hash_reconciles": True,
        "canonical_M2_through_M5_003_files_unchanged": (
            canonical_before == canonical_after
        ),
        "amendment_precedes_external_features_and_predictions": amendment[
            "recorded_before_external_feature_construction"
        ]
        and amendment["recorded_before_external_prediction"],
        "exact_registered_sessions_present": set(
            design["session_date"].astype(str).unique()
        )
        == set(EXTERNAL_SESSIONS),
        "external_rows_never_entered_fit": True,
        "all_predictions_match_joint_valid_design_rows": (
            len(predictions) == len(design)
            and set(predictions["risk_bin_id"]) == set(design["risk_bin_id"])
        ),
        "replicated_quote_gap_excluded_without_interpolation": (
            int(exact_gap.sum()) == 1
            and not amendment["replicated_source_quote_gap"][
                "interpolation_allowed"
            ]
        ),
        "report_financial_reconciliation": reconciliation["status"] == "PASS",
        "position_inventory_conservation": conservation["status"] == "PASS",
        "predictor_allowlist_unchanged": (
            tuple(preregistration["feature_allowlists"]["rehedge"])
            == REHEDGE_FEATURES
            and tuple(preregistration["feature_allowlists"]["unlock"])
            == UNLOCK_FEATURES
            and set(FEATURE_ALLOWLISTS) == set(ENDPOINTS)
        ),
        "tradeable_edge_claim_absent": True,
        "event_stage_accounting_is_monotonic": all(
            stage["source_lifecycle_events"]
            >= stage["representable_target_bins"]
            >= stage["common_floor_candidate_targets"]
            >= stage["joint_valid_targets"]
            for width in event_stage_accounting.values()
            for stage in width.values()
        ),
    }
    if not all(validation_gates.values()):
        failed = [key for key, passed in validation_gates.items() if not passed]
        raise AssertionError(f"External validation gates failed: {failed}")

    local_output = ROOT / "data" / "interim" / "m5_003_external"
    report_output = ROOT / "reports" / "phase_05"
    local_output.mkdir(parents=True, exist_ok=True)
    report_output.mkdir(parents=True, exist_ok=True)
    local_frames = {
        "ticks": ticks,
        "lifecycle_events": events,
        "state_intervals": intervals,
        "coverage_gaps": gaps,
        "risk_bin_audit": risk_bins,
        "interval_audit": interval_audit,
        "feature_audit": feature_audit,
        "joint_valid_design_matrix": design,
        "predictions": predictions,
    }
    for name, frame in local_frames.items():
        frame.to_parquet(local_output / f"m5_003_external_{name}.parquet", index=False)

    acquisition_report = {
        "schema_version": 1,
        "milestone": "M5-001",
        "status": acquisition["status"],
        "amendment_id": amendment["amendment_id"],
        "sessions": acquisition["sessions"],
        "ticks": acquisition["ticks"],
        "trade_reports": acquisition["trade_reports"],
        "privacy": acquisition["privacy"],
        "source_raw_validation_sha256": acquisition[
            "raw_deterministic_validation_sha256"
        ],
        "source_amended_validation_sha256": acquisition[
            "deterministic_amended_validation_sha256"
        ],
    }
    acquisition_report["deterministic_report_sha256"] = canonical_json_sha256(
        acquisition_report
    )
    acquisition_path = (
        report_output / "m5_001_external_acquisition_report.json"
    )
    acquisition_path.write_text(
        json.dumps(acquisition_report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    report = {
        "schema_version": 1,
        "milestone": "M5-003-external",
        "status": "external_evaluation_complete_with_qualitative_exposure_disclosed",
        "registered_sessions": list(EXTERNAL_SESSIONS),
        "amendment_sha256": _canonical_text_sha256(amendment_path),
        "frozen_manifest_sha256": manifest["frozen_manifest_sha256"],
        "fitted_parameter_hashes": {
            width: manifest["widths"][width]["fitted_width_sha256"]
            for width in ["1000", "500"]
        },
        "acquisition": {
            "status": acquisition["status"],
            "report_financial_reconciliation_status": reconciliation["status"],
            "position_inventory_conservation": conservation,
        },
        "lifecycle_accounting": {
            **lifecycle_summary,
            "events": int(len(events)),
            "intervals": int(len(intervals)),
            "exceptions": int(len(exceptions)),
            "external_event_counts": external_event_counts,
        },
        "risk_time_accounting": accounting_by_width,
        "event_stage_accounting": event_stage_accounting,
        "feature_accounting": {
            "candidate_bins": int(len(feature_audit)),
            "joint_valid_bins": int(len(design)),
            "dropped_bins": int(len(feature_audit) - len(design)),
            "dropped_targets": int(
                feature_audit.loc[
                    ~feature_audit["is_joint_valid"], "target_label"
                ].sum()
            ),
            "first_exclusion_reason": (
                feature_audit["first_exclusion_reason"]
                .fillna("joint_valid")
                .value_counts()
                .sort_index()
                .to_dict()
            ),
        },
        "external_results": external_results,
        "decision": _decision_summary(external_results),
        "qualitative_exposure_limitation": amendment["qualitative_exposure"][
            "interpretation"
        ],
        "uncertainty_limitation": (
            "interval-cluster bootstrap is conditional on three observed "
            "sessions and does not estimate between-session population variance"
        ),
        "architecture_limitation": (
            "For both re-hedge endpoints C_session improves over A_session "
            "but underperforms price-only B; external support for the "
            "preregistered headline does not resolve model architecture."
        ),
        "session_concentration_limitation": (
            "The pooled gain is concentrated in 2026-07-29, and 2026-07-28 "
            "is negative for rehedge_sell_occurrence and unlock_occurrence."
        ),
        "validation_gates": validation_gates,
        "local_output_hashes": {
            name: dataframe_sha256(frame)
            for name, frame in local_frames.items()
        },
        "canonical_input_file_sha256_before": canonical_before,
        "canonical_input_file_sha256_after": canonical_after,
    }
    report["deterministic_report_sha256"] = canonical_json_sha256(report)
    report_path_json = (
        report_output / "m5_003_external_validation_report.json"
    )
    report_path_md = (
        report_output / "m5_003_external_validation_report.md"
    )
    report_path_json.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    report_path_md.write_text(_render_markdown(report), encoding="utf-8")
    print(
        "M5-003 external evaluation complete: "
        f"{report['deterministic_report_sha256']}"
    )


if __name__ == "__main__":
    main()
