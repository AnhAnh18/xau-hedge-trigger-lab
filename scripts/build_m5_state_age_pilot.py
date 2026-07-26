from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.acquisition import classify_recurring_gaps, load_acquisition_plan
from xau_trigger.hazard_bins import (
    build_wall_clock_risk_bins,
    canonicalize_cohort_support,
    dataframe_sha256,
    load_tick_cohort,
)
from xau_trigger.risk_time import detect_coverage_gaps
from xau_trigger.state_age_hazard import (
    MODEL_PREDICTOR_ALLOWLIST,
    PRIMARY_ALPHA,
    SMOOTHING_SENSITIVITY,
    build_design_matrix,
    evaluate_holdout,
    fit_state_age_baselines,
    holdout_oracle_conditional_diagnostic,
    occurrence_verdict,
    per_session_base_hazard,
    predict_state_age_baselines,
)


INTERNAL_COHORT_ID = "internal_2026_07_23_24"
SUPPLEMENTAL_COHORT_ID = "supplemental_2026_07_20_22"
BIN_WIDTHS = (1.0, 0.5)
BOOTSTRAP_DRAWS = 5000


def _classified_cohort_breaks(cohort_ticks: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    frames = []
    for cohort_id, ticks in cohort_ticks.items():
        gaps = detect_coverage_gaps(ticks[["timestamp"]], threshold_seconds=60)
        gaps["cohort_id"] = cohort_id
        frames.append(gaps)
    all_gaps = pd.concat(frames, ignore_index=True)
    classified = classify_recurring_gaps(
        all_gaps,
        minimum_sessions=3,
        tolerance_seconds=120,
    )
    return {
        cohort_id: classified[classified["cohort_id"] == cohort_id].copy()
        for cohort_id in cohort_ticks
    }


def _summarize_a_cohorts(bins: pd.DataFrame) -> dict:
    records = []
    source = bins[bins["bin_width_ms"] == 1000].copy()
    for (cohort_id, endpoint), group in source.groupby(
        ["cohort_id", "endpoint"], sort=True
    ):
        records.append(
            {
                "cohort_id": str(cohort_id),
                "endpoint": str(endpoint),
                "risk_bins": int(len(group)),
                "target_events": int(group["target_label"].sum()),
                "events_per_1000_risk_seconds": float(
                    1000 * group["target_label"].sum() / len(group)
                ),
                "role": (
                    "A_all_known_age_internal_descriptive"
                    if cohort_id == INTERNAL_COHORT_ID
                    else "supplemental_descriptive_non_gating"
                ),
            }
        )
    common = source[source["is_primary_model_eligible"]]
    common_records = []
    for (split, endpoint), group in common.groupby(["split", "endpoint"], sort=True):
        common_records.append(
            {
                "split": str(split),
                "endpoint": str(endpoint),
                "risk_bins": int(len(group)),
                "target_events": int(group["target_label"].sum()),
                "events_per_1000_risk_seconds": float(
                    1000 * group["target_label"].sum() / len(group)
                ),
                "role": "A_common_primary_internal",
            }
        )
    return {"A_all": records, "A_common": common_records}


def _boundary_accounting(interval_audit: pd.DataFrame) -> dict:
    primary_width = interval_audit[interval_audit["bin_width_ms"] == 1000]
    records = {}
    for cohort_id, group in primary_width.groupby("cohort_id", sort=True):
        records[str(cohort_id)] = {
            "source_intervals": int(len(group)),
            "left_truncated_interval_ids": sorted(
                group.loc[group["is_left_truncated"], "interval_id"]
                .astype(str)
                .tolist()
            ),
            "right_censored_interval_ids": sorted(
                group.loc[group["is_right_censored"], "interval_id"]
                .astype(str)
                .tolist()
            ),
            "synthetic_right_censored_interval_ids": sorted(
                group.loc[group["is_synthetic_tail"], "interval_id"]
                .astype(str)
                .tolist()
            ),
            "cross_split_interval_ids": sorted(
                group.loc[group["is_cross_split_interval"], "interval_id"]
                .astype(str)
                .tolist()
            ),
            "no_complete_bin_interval_count": int(
                group["model_exclusion_reason"].eq("no_complete_bin").sum()
            ),
        }
    return records


def _m5_000_support_bridge(accounting: list[dict]) -> dict:
    source = json.loads(
        (
            ROOT / "reports" / "phase_05" / "m5_000_risk_time_audit.json"
        ).read_text(encoding="utf-8")
    )
    day_rows = source["canonical_full_coverage_by_day"]
    tradeable = round(
        sum(row["tradeable_risk_seconds"] for row in day_rows),
        6,
    )
    primary = round(
        sum(row["primary_risk_seconds"] for row in day_rows),
        6,
    )
    left_truncated = round(tradeable - primary, 6)
    internal = next(
        row
        for row in accounting
        if row["cohort_id"] == INTERNAL_COHORT_ID
        and row["bin_width_ms"] == 1000
    )
    bridge_delta = round(
        tradeable
        - left_truncated
        - internal["representable_bin_seconds"]
        - internal["dropped_partial_seconds"],
        9,
    )
    if primary != internal["eligible_fragment_seconds"] or abs(bridge_delta) > 1e-9:
        raise AssertionError("M5-000 to M5-002 support bridge does not reconcile")
    return {
        "m5_000_tradeable_risk_seconds": tradeable,
        "left_truncated_excluded_seconds": left_truncated,
        "m5_000_primary_known_age_seconds": primary,
        "m5_002_eligible_fragment_seconds": internal[
            "eligible_fragment_seconds"
        ],
        "representable_bin_seconds": internal["representable_bin_seconds"],
        "dropped_partial_seconds": internal["dropped_partial_seconds"],
        "reconciliation_delta_seconds": bridge_delta,
        "left_truncated_scope": (
            "retained_in_interval_audit_excluded_from_all_age_model_bins"
        ),
        "a_all_scope": "known_age_eligible_support_only",
    }


def _validation_gates(
    all_bins: pd.DataFrame,
    accounting: list[dict],
    supports: dict,
    design: pd.DataFrame,
    *,
    m5_000_bridge: dict,
    canonical_ticks_unchanged: bool,
    supplemental_isolation: bool,
) -> dict:
    gap_crossings = 0
    for cohort_id, support in supports.items():
        cohort_bins = all_bins[all_bins["cohort_id"] == cohort_id]
        for gap in support["breaks"].itertuples(index=False):
            gap_crossings += int(
                (
                    (cohort_bins["bin_start"] < pd.Timestamp(gap.break_end))
                    & (cohort_bins["bin_end"] > pd.Timestamp(gap.break_start))
                ).sum()
            )
    forbidden = {
        "endpoint",
        "target_label",
        "following_event_type",
        "competing_event_type",
        "censor_reason",
        "bin_start",
        "bin_end",
        "risk_bin_id",
        "interval_id",
        "cohort_id",
        "split",
    }
    gates = {
        "support_seconds_reconcile": all(
            abs(row["reconciliation_delta_seconds"]) <= 1e-9
            for row in accounting
        ),
        "m5_000_tradeable_to_primary_to_bins_reconcile": abs(
            m5_000_bridge["reconciliation_delta_seconds"]
        )
        <= 1e-9,
        "no_nonpositive_bins": bool((all_bins["bin_end"] > all_bins["bin_start"]).all()),
        "no_gap_crossing_bins": gap_crossings == 0,
        "no_cross_split_primary_bins": not bool(
            (
                all_bins["is_cross_split_interval"]
                & all_bins["is_primary_model_eligible"]
            ).any()
        ),
        "target_only_at_last_representable_bin": bool(
            all_bins.loc[all_bins["target_label"] == 1, "is_last_representable_bin"].all()
        ),
        "competing_bins_are_zero_label": bool(
            (
                all_bins.loc[
                    all_bins["is_competing_terminal_bin"], "target_label"
                ]
                == 0
            ).all()
        ),
        "canonical_ticks_unchanged": canonical_ticks_unchanged,
        "supplemental_fit_isolation": supplemental_isolation,
        "predictor_allowlist_has_no_forbidden_fields": forbidden.isdisjoint(
            MODEL_PREDICTOR_ALLOWLIST
        ),
        "design_matrix_matches_allowlist": design.columns.tolist()
        == ["risk_bin_id", *MODEL_PREDICTOR_ALLOWLIST],
    }
    if not all(gates.values()):
        failed = sorted(key for key, value in gates.items() if not value)
        raise AssertionError(f"M5-002 validation gates failed: {failed}")
    return gates


def _timer_floor_report(intervals: pd.DataFrame) -> dict:
    source = intervals.copy()
    source["end_time"] = pd.to_datetime(source["end_time"])
    source["session_date"] = source["end_time"].dt.strftime("%Y-%m-%d")
    observed_days = {f"2026-07-{day:02d}" for day in range(20, 25)}
    endpoints = {
        "unlock_occurrence": (
            source["state"].eq("HEDGED_1X1")
            & source["following_event_type"].isin(
                ["UNLOCK_TO_BUY", "UNLOCK_TO_SELL"]
            )
        ),
        "rehedge_sell_occurrence": (
            source["state"].eq("ONE_BUY")
            & source["following_event_type"].eq("REHEDGE_SELL")
        ),
        "rehedge_buy_occurrence": (
            source["state"].eq("ONE_SELL")
            & source["following_event_type"].eq("REHEDGE_BUY")
        ),
    }
    per_session = []
    month_wide = {}
    for endpoint, mask in endpoints.items():
        group = source[mask]
        month_wide[endpoint] = {
            "events": int(len(group)),
            "under_six_seconds": int((group["duration_seconds"] < 6).sum()),
            "under_six_percent": float(
                100 * (group["duration_seconds"] < 6).mean()
            ),
            "minimum_seconds": float(group["duration_seconds"].min()),
        }
        observed = group[group["session_date"].isin(observed_days)]
        for day, day_group in observed.groupby("session_date", sort=True):
            per_session.append(
                {
                    "session_date": str(day),
                    "endpoint": endpoint,
                    "events": int(len(day_group)),
                    "under_six_seconds": int(
                        (day_group["duration_seconds"] < 6).sum()
                    ),
                    "under_six_percent": float(
                        100 * (day_group["duration_seconds"] < 6).mean()
                    ),
                }
            )
    competing = source[
        source["state"].eq("HEDGED_1X1")
        & source["following_event_type"].astype("string").str.startswith(
            "OPEN_ADDITIONAL", na=False
        )
    ]
    return {
        "finding_id": "F-007",
        "interpretation": "approximate_six_second_unlock_floor_not_absolute_zero",
        "month_wide": month_wide,
        "per_calendar_session_m2": per_session,
        "hedged_competing_endpoints": {
            "events": int(len(competing)),
            "under_six_seconds": int((competing["duration_seconds"] < 6).sum()),
            "under_six_percent": float(
                100 * (competing["duration_seconds"] < 6).mean()
            ),
            "event_types": {
                str(key): int(value)
                for key, value in competing["following_event_type"]
                .value_counts()
                .sort_index()
                .items()
            },
        },
    }


def _pilot_verdict(inference_by_width: dict) -> dict:
    primary = inference_by_width["1000"]
    sensitivity = inference_by_width["500"]
    output = {}
    endpoints = sorted(set(primary) & set(sensitivity))
    for endpoint in endpoints:
        first = primary[endpoint]["primary_occurrence_likelihood"]
        second = sensitivity[endpoint]["primary_occurrence_likelihood"]
        output[endpoint] = {
            "verdict": occurrence_verdict(first),
            "one_second_mean": first["mean"],
            "one_second_ci95_low": first["ci95_low"],
            "one_second_ci95_high": first["ci95_high"],
            "five_hundred_ms_mean": second["mean"],
            "five_hundred_ms_role": "discretization_sensitivity_non_independent",
            "external_gate_satisfied": False,
            "tradeable_edge_claimed": False,
        }
    return output


def render_markdown(report: dict) -> str:
    lines = [
        "# M5-002 State-Age Hazard Pilot",
        "",
        f"- Status: `{report['status']}`",
        f"- Internal fitted-parameter hash: "
        f"`{report['primary_parameters']['fitted_parameter_sha256']}`",
        f"- Deterministic report SHA-256: `{report['deterministic_report_sha256']}`",
        "- External gate satisfied: **no**",
        "- Price predictors/P&L optimization/tradeable-edge claim: **none**",
        "",
        "## Contract and data isolation",
        "",
        "- Internal 2026-07-23..24 and supplemental 2026-07-20..22 use "
        "separate support cohorts.",
        "- The canonical M2-M4 `ticks.parquet` was not rebuilt or extended.",
        "- Bins use complete wall-clock grid cells; state age uses the paused "
        "tradeable clock at bin start.",
        "- Supplemental rows do not enter fitting; parameter hashes are equal "
        "with and without supplemental input.",
        "- Supplemental raw tick input is selected by its pre-registered "
        "SHA-256 checksum, not by directory glob order.",
        "",
        "## Support reconciliation",
        "",
        "| Cohort | Width | Eligible seconds | Representable seconds | "
        "Dropped partial seconds | Delta |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["support_accounting"]:
        lines.append(
            f"| {row['cohort_id']} | {row['bin_width_ms']} ms | "
            f"{row['eligible_fragment_seconds']:,.3f} | "
            f"{row['representable_bin_seconds']:,.3f} | "
            f"{row['dropped_partial_seconds']:,.3f} | "
            f"{row['reconciliation_delta_seconds']:.6f} |"
        )

    bridge = report["m5_000_support_bridge"]
    lines.extend(
        [
            "",
            "The internal one-second bridge back to M5-000 is explicit:",
            "",
            "```text",
            f"M5-000 tradeable risk             "
            f"{bridge['m5_000_tradeable_risk_seconds']:,.3f}",
            f"- left-truncated unknown age      "
            f"{bridge['left_truncated_excluded_seconds']:,.3f}",
            f"= M5-000 primary / M5-002 eligible "
            f"{bridge['m5_000_primary_known_age_seconds']:,.3f}",
            f"= {bridge['representable_bin_seconds']:,.3f} representable "
            f"+ {bridge['dropped_partial_seconds']:,.3f} partial",
            "```",
            "",
            "`A_all` is descriptive known-age eligible support. The "
            "left-truncated interval remains in audit but is excluded from "
            "all state-age model bins because its true age is unknown.",
        ]
    )

    lines.extend(
        [
            "",
            "## Development-only age buckets (1-second primary)",
            "",
            "Zero-event buckets have observed exposure and therefore are not "
            "called prior-only. Jeffreys smoothing remains finite; raw event "
            "and exposure counts are shown.",
            "",
            "| Endpoint | Bucket | Exposure bins | Events | Jeffreys p | "
            "Zero dev events |",
            "| --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for endpoint, parameters in report["primary_parameters"]["endpoints"].items():
        for bucket, values in parameters["age_buckets"].items():
            probability = values["probability"]
            lines.append(
                f"| {endpoint} | {bucket} | {values['exposure_bins']:,} | "
                f"{values['target_events']:,} | "
                f"{probability:.8f} | "
                f"{str(values['has_zero_development_events']).lower()} |"
            )

    lines.extend(["", "## Frozen holdout occurrence inference", ""])
    for width, endpoints in report["holdout_inference"].items():
        lines.extend([f"### {width} ms bins", ""])
        for endpoint, metrics in endpoints.items():
            primary = metrics["primary_occurrence_likelihood"]
            diagnostic = metrics[
                "noninferential_age_only_conditional_diagnostic"
            ]
            lines.append(
                f"- `{endpoint}`: primary occurrence LL mean "
                f"{primary['mean']:.6f} "
                f"(95% CI {primary['ci95_low']:.6f}, {primary['ci95_high']:.6f}; "
                f"{primary['cluster_count']} intervals); non-inferential "
                f"age-only conditional diagnostic "
                f"{diagnostic['mean']:.6f}."
            )

    lines.extend(
        [
            "",
            "The conditional diagnostic cannot score the age-only model: "
            "each event-to-event interval ends at its observed event, the "
            "target is always in the last bin, and the within-interval risk "
            "set is therefore outcome-truncated. It affects no verdict or "
            "merge gate and is deferred until M5-003 risk-set design.",
            "",
            "As an audit, the age buckets were refit on the holdout labels. "
            "The resulting oracle conditional means still remain below the "
            "uniform null, confirming that this statistic does not score "
            "age-only model quality:",
            "",
            "| Width | Endpoint | Holdout-oracle conditional mean |",
            "| ---: | --- | ---: |",
        ]
    )
    for width, audit in report["conditional_degeneracy_audit"].items():
        for endpoint, mean in audit["oracle_conditional_mean"].items():
            lines.append(f"| {width} ms | {endpoint} | {mean:.6f} |")

    lines.extend(
        [
            "",
            "The 500 ms result is a discretization sensitivity on the same "
            "risk support, not independent replication.",
            "",
            "## Smoothing sensitivity",
            "",
            "| Width | Alpha | Endpoint | Occurrence LL mean |",
            "| ---: | ---: | --- | ---: |",
        ]
    )
    for width, alpha_results in report["smoothing_sensitivity"].items():
        for alpha, result in alpha_results.items():
            for endpoint, metrics in result["holdout_inference"].items():
                mean = metrics["primary_occurrence_likelihood"]["mean"]
                lines.append(f"| {width} ms | {alpha} | {endpoint} | {mean:.6f} |")

    lines.extend(
        [
            "",
            "## F-007 timer-floor verification",
            "",
            "The M2 month-wide data contain one sub-six-second unlock, so the "
            "pattern is reported as an approximate dwell floor rather than an "
            "absolute structural zero.",
            "",
            "| Endpoint | Events | Under 6s | Percent |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for endpoint, row in report["timer_floor_verification"]["month_wide"].items():
        lines.append(
            f"| {endpoint} | {row['events']:,} | {row['under_six_seconds']:,} | "
            f"{row['under_six_percent']:.3f}% |"
        )

    lines.extend(
        [
            "",
            "## Supplemental named deliverable: per-session base hazard",
            "",
            "These are descriptive common-hour weekday/session rates. "
            "Supplemental days do not fit, validate, or promote the internal "
            "pilot. One session per weekday cannot identify a weekday effect.",
            "",
            "| Date | Weekday | Endpoint | Risk seconds | Events | "
            "Events/1000s | Role |",
            "| --- | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in report["supplemental_named_deliverable"]["records"]:
        lines.append(
            f"| {row['session_date']} | {row['weekday']} | {row['endpoint']} | "
            f"{row['risk_bins']:,} | {row['target_events']:,} | "
            f"{row['events_per_1000_risk_seconds']:.6f} | {row['role']} |"
        )

    lines.extend(
        [
            "",
            "## Pilot interpretation",
            "",
        ]
    )
    for endpoint, item in report["pilot_verdict"].items():
        lines.append(f"- `{endpoint}`: `{item['verdict']}`.")
    lines.extend(
        [
            "",
            "Cause-specific occurrence likelihood is primary for this bounded "
            "state-age-only pilot. It remains base-rate-sensitive, so the "
            "result is internal and external validation is still required. "
            "The approximate unlock timer floor transports to holdout; no "
            "standalone tradeable edge is claimed.",
            "",
            "## Explicit deferrals",
            "",
            "- M4 matched-timestamp anchor offset: deferred until price-feature work.",
            "- Unlock direction P(cause | occurrence): deferred.",
            "- External temporal validation: pending 2026-07-27..29 acquisition.",
            "",
            "## Validation gates",
            "",
        ]
    )
    for gate, passed in report["validation_gates"].items():
        lines.append(f"- `{gate}`: {'PASS' if passed else 'FAIL'}")
    lines.extend(
        [
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    interim = ROOT / "data" / "interim"
    local_output = interim / "m5_002"
    report_output = ROOT / "reports" / "phase_05"
    intervals = pd.read_parquet(interim / "state_intervals.parquet")
    lifecycle_events = pd.read_parquet(interim / "lifecycle_events.parquet")
    internal_ticks = pd.read_parquet(interim / "ticks.parquet")
    canonical_tick_hash_before = dataframe_sha256(internal_ticks)

    supplemental_plan = load_acquisition_plan(
        ROOT / "data" / "m5_retrospective_support_plan.json"
    )
    raw_tick_paths = sorted((ROOT / "data" / "raw" / "ticks").glob("*.csv"))
    supplemental_ticks = load_tick_cohort(
        raw_tick_paths,
        supplemental_plan["sessions"],
        expected_sha256=supplemental_plan["tick_export"][
            "source_sha256_allowlist"
        ],
    )
    local_output.mkdir(parents=True, exist_ok=True)
    supplemental_tick_path = (
        local_output / "ticks_supplemental_2026_07_20_22.parquet"
    )
    supplemental_ticks.to_parquet(supplemental_tick_path, index=False)

    cohort_ticks = {
        INTERNAL_COHORT_ID: internal_ticks,
        SUPPLEMENTAL_COHORT_ID: supplemental_ticks,
    }
    classified_breaks = _classified_cohort_breaks(cohort_ticks)
    supports = {
        cohort_id: canonicalize_cohort_support(
            intervals,
            lifecycle_events,
            ticks,
            cohort_id=cohort_id,
            breaks=classified_breaks[cohort_id],
        )
        for cohort_id, ticks in cohort_ticks.items()
    }

    bins_by_width: dict[int, pd.DataFrame] = {}
    interval_audits = []
    accounting = []
    for width in BIN_WIDTHS:
        cohort_bins = []
        for support in supports.values():
            bins, interval_audit, support_accounting = build_wall_clock_risk_bins(
                support,
                bin_width_seconds=width,
            )
            cohort_bins.append(bins)
            interval_audits.append(interval_audit)
            accounting.append(support_accounting)
        bins_by_width[int(round(width * 1000))] = pd.concat(
            cohort_bins,
            ignore_index=True,
        )

    all_bins = pd.concat(bins_by_width.values(), ignore_index=True)
    all_interval_audit = pd.concat(interval_audits, ignore_index=True)
    primary_bins = bins_by_width[1000]
    internal_primary_bins = primary_bins[
        primary_bins["cohort_id"].eq(INTERNAL_COHORT_ID)
        & primary_bins["is_primary_model_eligible"]
    ].copy()

    primary_parameters = fit_state_age_baselines(
        primary_bins,
        alpha=PRIMARY_ALPHA,
    )
    isolation_parameters = fit_state_age_baselines(
        primary_bins[primary_bins["cohort_id"] == INTERNAL_COHORT_ID],
        alpha=PRIMARY_ALPHA,
    )
    if primary_parameters["fitted_parameter_sha256"] != isolation_parameters[
        "fitted_parameter_sha256"
    ]:
        raise AssertionError("Supplemental data changed internal fitted parameters")

    parameters_by_width = {}
    inference_by_width = {}
    predictions_by_width = {}
    smoothing_sensitivity = {}
    for width_ms, bins in bins_by_width.items():
        parameters = fit_state_age_baselines(bins, alpha=PRIMARY_ALPHA)
        internal_bins = bins[
            bins["cohort_id"].eq(INTERNAL_COHORT_ID)
            & bins["is_primary_model_eligible"]
        ]
        predictions = predict_state_age_baselines(internal_bins, parameters)
        parameters_by_width[str(width_ms)] = parameters
        predictions_by_width[width_ms] = predictions
        inference_by_width[str(width_ms)] = evaluate_holdout(
            predictions,
            draws=BOOTSTRAP_DRAWS,
            seed=5002 + width_ms,
        )
        alpha_results = {}
        for alpha in SMOOTHING_SENSITIVITY:
            alpha_parameters = fit_state_age_baselines(bins, alpha=alpha)
            alpha_predictions = predict_state_age_baselines(
                internal_bins,
                alpha_parameters,
            )
            alpha_results[str(alpha)] = {
                "fitted_parameter_sha256": alpha_parameters[
                    "fitted_parameter_sha256"
                ],
                "holdout_inference": evaluate_holdout(
                    alpha_predictions,
                    draws=BOOTSTRAP_DRAWS,
                    seed=7000 + width_ms + int(alpha * 100),
                ),
            }
        smoothing_sensitivity[str(width_ms)] = alpha_results

    design = build_design_matrix(internal_primary_bins)
    primary_predictions = predictions_by_width[1000]
    pilot_verdict = _pilot_verdict(inference_by_width)

    local_paths = {
        "interval_audit": local_output / "m5_002_interval_audit.parquet",
        "risk_bin_audit": local_output / "m5_002_risk_bin_audit.parquet",
        "design_matrix": local_output / "m5_002_design_matrix.parquet",
        "predictions": local_output / "m5_002_predictions.parquet",
    }
    all_interval_audit.to_parquet(local_paths["interval_audit"], index=False)
    all_bins.to_parquet(local_paths["risk_bin_audit"], index=False)
    design.to_parquet(local_paths["design_matrix"], index=False)
    primary_predictions.to_parquet(local_paths["predictions"], index=False)

    canonical_tick_hash_after = dataframe_sha256(
        pd.read_parquet(interim / "ticks.parquet")
    )
    if canonical_tick_hash_before != canonical_tick_hash_after:
        raise AssertionError("Canonical M2-M4 ticks changed during M5-002")

    supplemental_isolation = primary_parameters[
        "fitted_parameter_sha256"
    ] == isolation_parameters["fitted_parameter_sha256"]
    m5_000_bridge = _m5_000_support_bridge(accounting)
    validation_gates = _validation_gates(
        all_bins,
        accounting,
        supports,
        design,
        m5_000_bridge=m5_000_bridge,
        canonical_ticks_unchanged=canonical_tick_hash_before
        == canonical_tick_hash_after,
        supplemental_isolation=supplemental_isolation,
    )

    report = {
        "schema_version": 1,
        "milestone": "M5-002",
        "status": "pilot_complete_external_pending",
        "configuration": {
            "primary_bin_width_ms": 1000,
            "sensitivity_bin_width_ms": 500,
            "bin_grid": "wall_clock_complete_cells_inside_tradeable_fragments",
            "state_age_clock": "elapsed_minus_excluded_gap_overlap_at_bin_start",
            "primary_server_hours": [12, 24],
            "bootstrap_cluster": "interval_id",
            "bootstrap_draws": BOOTSTRAP_DRAWS,
            "primary_smoothing_alpha": PRIMARY_ALPHA,
            "smoothing_sensitivity": list(SMOOTHING_SENSITIVITY),
        },
        "data_isolation": {
            "internal_cohort": INTERNAL_COHORT_ID,
            "supplemental_cohort": SUPPLEMENTAL_COHORT_ID,
            "canonical_tick_rows": int(len(internal_ticks)),
            "supplemental_tick_rows": int(len(supplemental_ticks)),
            "canonical_tick_hash_before": canonical_tick_hash_before,
            "canonical_tick_hash_after": canonical_tick_hash_after,
            "canonical_ticks_unchanged": canonical_tick_hash_before
            == canonical_tick_hash_after,
            "parameter_hash_with_supplemental": primary_parameters[
                "fitted_parameter_sha256"
            ],
            "parameter_hash_internal_only": isolation_parameters[
                "fitted_parameter_sha256"
            ],
            "supplemental_fit_isolation_pass": primary_parameters[
                "fitted_parameter_sha256"
            ]
            == isolation_parameters["fitted_parameter_sha256"],
            "supplemental_role": "per_session_base_hazard_variation_non_gating",
            "supplemental_source_sha256_allowlist": supplemental_plan[
                "tick_export"
            ]["source_sha256_allowlist"],
        },
        "support_accounting": accounting,
        "m5_000_support_bridge": m5_000_bridge,
        "boundary_accounting": _boundary_accounting(all_interval_audit),
        "cohort_summaries": _summarize_a_cohorts(all_bins),
        "primary_parameters": primary_parameters,
        "parameters_by_width": parameters_by_width,
        "predictor_allowlist": MODEL_PREDICTOR_ALLOWLIST,
        "predictor_allowlist_excludes": [
            "endpoint",
            "target_label",
            "following_event_type",
            "competing_event_type",
            "censor_reason",
            "bin_start",
            "bin_end",
            "risk_bin_id",
            "interval_id",
            "cohort_id",
            "split",
        ],
        "holdout_inference": inference_by_width,
        "conditional_degeneracy_audit": {
            str(width_ms): {
                "role": "holdout_label_oracle_audit_only_non_gating",
                "oracle_conditional_mean": (
                    holdout_oracle_conditional_diagnostic(predictions)
                ),
            }
            for width_ms, predictions in predictions_by_width.items()
        },
        "smoothing_sensitivity": smoothing_sensitivity,
        "supplemental_named_deliverable": {
            "name": "per_session_base_hazard_variation_2026_07_20_24",
            "role": "descriptive_non_gating",
            "server_hours": [12, 24],
            "limitation": (
                "one_session_per_weekday_cannot_identify_a_day_of_week_effect"
            ),
            "records": per_session_base_hazard(all_bins),
        },
        "timer_floor_verification": _timer_floor_report(intervals),
        "pilot_verdict": pilot_verdict,
        "validation_gates": validation_gates,
        "diagnostic_roles": {
            "raw_calibration": "descriptive_only",
            "event_rank": "descriptive_only",
            "paired_occurrence_likelihood": "primary_base_rate_sensitive",
            "conditional_timing": (
                "noninferential_for_age_only_outcome_truncated_risk_set"
            ),
            "five_hundred_ms": (
                "discretization_sensitivity_not_independent_replication"
            ),
        },
        "explicit_deferrals": {
            "m4_matched_timestamp_anchor_offset": "deferred_to_price_feature_work",
            "unlock_direction_given_occurrence": "deferred",
            "conditional_timing_risk_set_redesign": "deferred_to_M5_003",
            "external_temporal_validation": "pending_2026_07_27_29",
        },
        "external_gate_satisfied": False,
        "m5_closed": False,
        "tradeable_edge_claimed": False,
        "output_hashes": {
            "interval_audit": dataframe_sha256(all_interval_audit),
            "risk_bin_audit": dataframe_sha256(all_bins),
            "design_matrix": dataframe_sha256(design),
            "predictions": dataframe_sha256(primary_predictions),
        },
    }
    encoded = json.dumps(report, sort_keys=True, separators=(",", ":"))
    report["deterministic_report_sha256"] = sha256(
        encoded.encode("utf-8")
    ).hexdigest()
    report_output.mkdir(parents=True, exist_ok=True)
    (report_output / "m5_002_state_age_pilot.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (report_output / "m5_002_state_age_pilot.md").write_text(
        render_markdown(report),
        encoding="utf-8",
    )
    print(
        "M5-002 state-age pilot complete: "
        f"{report['deterministic_report_sha256']}"
    )


if __name__ == "__main__":
    main()
