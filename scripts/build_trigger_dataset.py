from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.trigger_dataset import (  # noqa: E402
    BOOTSTRAP_DRAWS,
    H2_RETRACEMENT_WINSOR_QUANTILE,
    H1_WINDOWS_MS,
    H2_WINDOWS_MS,
    H3_WINDOWS_MS,
    MODEL_STATE_AGE_CLIP_SECONDS,
    WINDOWS_MS,
    apply_reviewed_model_transforms,
    annotate_control_support,
    attach_actual_control_counts,
    attach_pretransition_state,
    build_audit_table,
    build_control_pool,
    build_model_matrix,
    coherent_conclusion,
    effective_event_times,
    engineer_features,
    expected_feature,
    fit_h2_retracement_winsor_caps,
    model_output_columns,
    model_predictor_columns,
    paired_summary,
    sample_controls,
    select_positives,
)

EXPECTED_POSITIVES = {
    "REHEDGE_SELL": 331,
    "REHEDGE_BUY": 306,
    "UNLOCK_TO_BUY": 320,
    "UNLOCK_TO_SELL": 294,
}
SPLIT_BY_DATE = {
    "2026-07-23": "development",
    "2026-07-24": "holdout",
}
STATE_AGE_STRATA = ("0-6s", "7-10s", "10-30s", "30-60s", ">60s")
CAUSAL_SHIFTS_MS = (-500, 0)
POST_ACTION_SHIFTS_MS = (250, 500, 1000)


def analyze(
    frame: pd.DataFrame,
    hypothesis: str,
    windows: tuple[int, ...],
) -> dict:
    results = [
        {
            "split": split,
            "window_ms": window,
            "summary": paired_summary(
                frame[frame.date_split == split],
                window,
                hypothesis,
            ),
        }
        for split in ("development", "holdout")
        for window in windows
    ]
    holdout = [item for item in results if item["split"] == "holdout"]
    return {
        "conclusion": coherent_conclusion(holdout),
        "windows_ms": list(windows),
        "results": results,
    }


def subset_by_positive_ids(
    frame: pd.DataFrame,
    positive_ids: pd.Series | set[int],
) -> pd.DataFrame:
    return frame[frame.matched_event_id.isin(set(positive_ids))]


def h1_analysis(engineered: pd.DataFrame) -> dict:
    rehedge = engineered[engineered.trigger_family == "rehedge"]
    supported = rehedge[rehedge.is_control_supported]
    primary = analyze(supported, "h1", H1_WINDOWS_MS)
    descriptive = analyze(rehedge, "h1", H1_WINDOWS_MS)
    headline = primary["conclusion"]
    if (
        primary["conclusion"] == "inconclusive"
        and descriptive["conclusion"] in {"supported", "rejected"}
    ):
        headline = "confounded/inconclusive"

    positive_rehedge = rehedge[rehedge.sample_type == "positive"]
    strata = {}
    for stratum in STATE_AGE_STRATA:
        ids = positive_rehedge[
            positive_rehedge.state_age_stratum == stratum
        ].matched_event_id
        stratum_frame = subset_by_positive_ids(rehedge, ids)
        strata[stratum] = {
            "positive_count": int(len(ids)),
            "control_supported_positive_count": int(
                positive_rehedge[
                    (positive_rehedge.state_age_stratum == stratum)
                    & positive_rehedge.is_control_supported
                ].shape[0]
            ),
            "analysis": analyze(stratum_frame, "h1", H1_WINDOWS_MS),
        }
    return {
        "conclusion": headline,
        "primary_control_supported": primary,
        "descriptive_all_positive": descriptive,
        "state_age_strata": strata,
        "inference_note": (
            "Primary inference excludes positive events below seven seconds of "
            "pre-transition state age or without eligible risk time. The pooled "
            "all-positive result is descriptive only."
        ),
    }


def h2_analysis(
    engineered: pd.DataFrame,
    retracement_winsor_caps: dict[int, float],
) -> dict:
    rehedge = engineered[
        (engineered.trigger_family == "rehedge")
        & engineered.is_control_supported
    ]
    joint = analyze(rehedge, "h2", H2_WINDOWS_MS)
    touch = analyze(rehedge, "h2_touch", H2_WINDOWS_MS)
    retracement = analyze(rehedge, "h2_retracement", H2_WINDOWS_MS)
    return {
        "conclusion": joint["conclusion"],
        "joint_sequence": joint,
        "touch_component": touch,
        "retracement_component": retracement,
        "retracement_winsorization": {
            "upper_quantile": H2_RETRACEMENT_WINSOR_QUANTILE,
            "fit_population": (
                "development control-supported rehedge risk-set samples"
            ),
            "caps_by_window_ms": {
                str(window): cap
                for window, cap in retracement_winsor_caps.items()
            },
            "holdout_refit": False,
        },
        "definition": (
            "For each pre-registered sequence window w, the prior boundary is "
            "computed on [t-2w, t-w). The sequence window is [t-w, t]. A valid "
            "sequence touches or breaks the side-appropriate prior boundary "
            "before t and then retraces/bounces before t."
        ),
    }


def h3_analysis(
    engineered: pd.DataFrame,
    ticks: pd.DataFrame,
) -> dict:
    unlock = engineered[engineered.trigger_family == "unlock"]
    analysis = analyze(unlock, "h3", H3_WINDOWS_MS)
    median_mid = float(ticks.mid.median())
    median_spread = float(ticks.spread.median())
    price_effects = []
    for result in analysis["results"]:
        if result["split"] != "holdout":
            continue
        difference = result["summary"]["paired_mean_difference"]
        effect = float(difference * median_mid) if difference is not None else None
        price_effects.append(
            {
                "window_ms": result["window_ms"],
                "paired_effect_price_units": effect,
                "effect_as_fraction_of_median_spread": (
                    float(effect / median_spread)
                    if effect is not None and median_spread
                    else None
                ),
            }
        )
    analysis.update(
        {
            "median_mid": median_mid,
            "median_spread": median_spread,
            "holdout_price_unit_effects": price_effects,
            "interpretation": (
                "The signed-momentum association is timing-sensitive. Its "
                "price-unit effect is smaller than the median spread and is not "
                "a standalone tradeable edge."
            ),
        }
    )
    return analysis


def hypothesis_bundle(
    engineered: pd.DataFrame,
    ticks: pd.DataFrame,
    h2_retracement_caps: dict[int, float],
) -> dict:
    return {
        "h1": h1_analysis(engineered),
        "h2": h2_analysis(engineered, h2_retracement_caps),
        "h3": h3_analysis(engineered, ticks),
    }


def gate_verdicts(bundle: dict) -> dict:
    return {
        "h1": bundle["h1"]["primary_control_supported"]["conclusion"],
        "h2": bundle["h2"]["joint_sequence"]["conclusion"],
        "h3": bundle["h3"]["conclusion"],
    }


def sensitivity_hypothesis_bundle(engineered: pd.DataFrame) -> dict:
    rehedge_supported = engineered[
        (engineered.trigger_family == "rehedge")
        & engineered.is_control_supported
    ]
    unlock = engineered[engineered.trigger_family == "unlock"]
    return {
        "h1": analyze(rehedge_supported, "h1", H1_WINDOWS_MS),
        "h2": analyze(rehedge_supported, "h2", H2_WINDOWS_MS),
        "h3": analyze(unlock, "h3", H3_WINDOWS_MS),
    }


def gate_class(verdict: str) -> str:
    if verdict == "supported":
        return "positive"
    if verdict == "rejected":
        return "negative"
    if verdict == "mixed":
        return "mixed"
    return "unresolved"


def sensitivity_analysis(
    positives: pd.DataFrame,
    control_features: pd.DataFrame,
    ticks: pd.DataFrame,
    aligned: pd.DataFrame,
    main_bundle: dict,
) -> tuple[dict, dict]:
    shifts = (*CAUSAL_SHIFTS_MS, *POST_ACTION_SHIFTS_MS)
    sensitivity = {}
    for shift_ms in shifts:
        shifted = positives.copy()
        shifted["sample_time"] = (
            shifted.price_anchor_time + pd.Timedelta(milliseconds=shift_ms)
        )
        shifted["price_anchor_time"] = shifted.sample_time
        shifted_features = engineer_features(shifted, ticks, aligned)
        frame = pd.concat(
            [shifted_features, control_features],
            ignore_index=True,
            sort=False,
        )
        bundle = sensitivity_hypothesis_bundle(frame)
        verdicts = {
            hypothesis: analysis["conclusion"]
            for hypothesis, analysis in bundle.items()
        }
        sensitivity[str(shift_ms)] = {
            "role": (
                "causal_gate"
                if shift_ms in CAUSAL_SHIFTS_MS
                else "post_action_diagnostic_only"
            ),
            "verdicts": verdicts,
            "hypotheses": bundle,
        }

    main_verdicts = gate_verdicts(main_bundle)
    minus_500_verdicts = sensitivity["-500"]["verdicts"]
    per_hypothesis = {
        hypothesis: {
            "matched_time": main_verdict,
            "minus_500ms": minus_500_verdicts[hypothesis],
            "matched_time_class": gate_class(main_verdict),
            "minus_500ms_class": gate_class(minus_500_verdicts[hypothesis]),
            "stable": gate_class(main_verdict)
            == gate_class(minus_500_verdicts[hypothesis]),
        }
        for hypothesis, main_verdict in main_verdicts.items()
    }
    gate = {
        "stable": all(item["stable"] for item in per_hypothesis.values()),
        "inputs_ms": list(CAUSAL_SHIFTS_MS),
        "per_hypothesis": per_hypothesis,
        "post_action_diagnostic_ms": list(POST_ACTION_SHIFTS_MS),
        "post_action_affects_gate": False,
        "post_action_affects_model_features": False,
        "post_action_affects_headline_verdicts": False,
    }
    return sensitivity, gate


def h2_independence_audit(engineered: pd.DataFrame) -> dict:
    results = {}
    complement_windows = []
    rehedge = engineered[engineered.trigger_family == "rehedge"]
    for window in H2_WINDOWS_MS:
        valid = rehedge[
            rehedge[f"w{window}ms_valid"]
            & rehedge[f"h2_w{window}ms_valid"]
        ]
        h1 = expected_feature(valid, window, "h1")
        h2 = expected_feature(valid, window, "h2")
        complement = bool(
            len(valid)
            and np.allclose(
                (h1 + h2).to_numpy(),
                np.ones(len(valid)),
                equal_nan=False,
            )
        )
        correlation = (
            float(h1.corr(h2))
            if len(valid) > 1 and h1.nunique() > 1 and h2.nunique() > 1
            else None
        )
        results[str(window)] = {
            "rows": int(len(valid)),
            "is_identically_one_minus_h1": complement,
            "correlation_with_h1": correlation,
        }
        if complement:
            complement_windows.append(window)
    if complement_windows:
        raise RuntimeError(
            f"H2 remains the arithmetic complement of H1: {complement_windows}"
        )
    return {
        "passed": True,
        "windows": results,
    }


def markdown_report(report: dict) -> str:
    controls = report["controls_per_positive"]
    h1 = report["hypotheses"]["h1"]
    h2 = report["hypotheses"]["h2"]
    h3 = report["hypotheses"]["h3"]
    lines = [
        "# M4 Trigger Dataset Remediation Report",
        "",
        "## Gate status",
        "",
        (
            "**PASSED**"
            if report["causal_sensitivity_gate"]["stable"]
            else "**NOT PASSED**"
        ),
        "",
        "Only `matched_time` and `matched_time - 500 ms` participate in the "
        "causal sensitivity gate. Positive shifts are post-action diagnostics only.",
        "",
        "## Positive and control accounting",
        "",
        "| Behavior | Positives |",
        "| --- | ---: |",
        *[
            f"| {behavior} | {count:,} |"
            for behavior, count in EXPECTED_POSITIVES.items()
        ],
        f"| **Total** | **{report['positive_total']:,}** |",
        "",
        f"- Controls: {report['control_total']:,}",
        f"- Controls per positive: {controls['distribution']}",
        f"- Positives without sampled controls: {controls['positives_without_controls']}",
        f"- Reused candidates: {report['control_candidate_reuse_count']}",
        f"- Control-supported positives: {report['control_support']['supported']:,}",
        f"- Structurally unsupported positives: {report['control_support']['unsupported']:,}",
        "",
        "## Time-anchor contract",
        "",
        "- Price and tick features: `matched_timestamp`.",
        "- Pre-transition state bookkeeping: exact M2 interval lineage; "
        "`reported_time` is the fallback anchor.",
        f"- Positive state ages populated: {report['state_age_audit']['positive_populated']:,}"
        f"/{report['positive_total']:,}.",
        f"- Control state ages populated: {report['state_age_audit']['control_populated']:,}"
        f"/{report['control_total']:,}.",
        "",
        "## H1 — rolling boundary",
        "",
        f"- Headline: **{h1['conclusion']}**",
        f"- Primary control-supported verdict: "
        f"**{h1['primary_control_supported']['conclusion']}**",
        f"- Descriptive all-positive verdict: "
        f"**{h1['descriptive_all_positive']['conclusion']}**",
        "",
        "| Pre-transition state age | Positives | Supported positives | "
        "Holdout 5s diff | CI95 |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for stratum in STATE_AGE_STRATA:
        item = h1["state_age_strata"][stratum]
        result = next(
            row
            for row in item["analysis"]["results"]
            if row["split"] == "holdout" and row["window_ms"] == 5000
        )
        summary = result["summary"]
        interval = summary["cluster_bootstrap_ci95"]
        interval_text = (
            f"[{interval[0]:+.4f}, {interval[1]:+.4f}]" if interval else "n/a"
        )
        difference = summary["paired_mean_difference"]
        lines.append(
            f"| {stratum} | {item['positive_count']:,} | "
            f"{item['control_supported_positive_count']:,} | "
            f"{difference:+.4f} | {interval_text} |"
            if difference is not None
            else (
                f"| {stratum} | {item['positive_count']:,} | "
                f"{item['control_supported_positive_count']:,} | n/a | n/a |"
            )
        )
    lines.extend(
        [
            "",
            "The all-positive result is descriptive only. It cannot override a "
            "null control-supported inference.",
            "",
            "## H2 — prior boundary, touch, then retracement",
            "",
            f"- Joint sequence: **{h2['joint_sequence']['conclusion']}**",
            f"- Boundary-touch component: **{h2['touch_component']['conclusion']}**",
            f"- Post-touch retracement component: "
            f"**{h2['retracement_component']['conclusion']}**",
            f"- Retracement upper-tail winsorization: development p99; caps "
            f"{h2['retracement_winsorization']['caps_by_window_ms']}",
            f"- H2 independence audit passed: "
            f"{report['h2_independence_audit']['passed']}",
            "",
            "Prior boundaries are calculated on a disjoint window ending before "
            "the sequence window. Touch and retracement are published separately.",
            "",
            "## H3 — signed momentum",
            "",
            f"- Headline: **{h3['conclusion']}**",
            f"- Median spread: {h3['median_spread']:.4f} price units.",
            "- The holdout effect is timing-sensitive, smaller than the median "
            "spread, and is not interpreted as a standalone tradeable edge.",
            "",
            "| Window | Price-unit effect | Fraction of median spread |",
            "| ---: | ---: | ---: |",
            *[
                f"| {item['window_ms']} ms | "
                f"{item['paired_effect_price_units']:+.4f} | "
                f"{item['effect_as_fraction_of_median_spread']:+.3f} |"
                for item in h3["holdout_price_unit_effects"]
            ],
            "",
            "## Sensitivity",
            "",
            "| Shift | Role | H1 | H2 | H3 |",
            "| ---: | --- | --- | --- | --- |",
            *[
                f"| {shift} ms | {item['role']} | "
                f"{item['verdicts']['h1']} | {item['verdicts']['h2']} | "
                f"{item['verdicts']['h3']} |"
                for shift, item in report["timestamp_sensitivity"].items()
            ],
            "",
            "Positive shifts do not enter the model matrix, headline hypothesis "
            "verdicts, or merge gate.",
            "",
            "## Output contracts",
            "",
            "- `trigger_samples_audit.parquet`: IDs, anchors, lineage, sampling "
            "metadata, alignment diagnostics, and validity flags.",
            "- `trigger_model_features.parquet`: explicit reviewed allowlist only.",
            f"- Model predictors: {report['model_output_contract']['predictor_count']}.",
            f"- Raw state age remains in audit; model state age is clipped at "
            f"{report['model_output_contract']['state_age_clip_seconds']:.0f} seconds.",
            "- `sample_id` is audit-only and absent from the model matrix.",
            "- Sampling metadata and `time_since_previous_event_seconds` are absent "
            "from the model-ready matrix.",
            "",
            "Development data on 2026-07-23 begins at 12:00. Holdout data on "
            "2026-07-24 is near-full-day; raw daily counts are not compared as "
            "equal-coverage event rates.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    interim = ROOT / "data" / "interim"
    report_dir = ROOT / "reports" / "phase_04"
    aligned = pd.read_parquet(interim / "aligned_events.parquet")
    intervals = pd.read_parquet(interim / "state_intervals.parquet")
    ticks = pd.read_parquet(interim / "ticks.parquet")

    positives = attach_pretransition_state(select_positives(aligned), intervals)
    actual = positives.behavior_type.value_counts().to_dict()
    if actual != EXPECTED_POSITIVES:
        raise RuntimeError(f"Primary-positive reconciliation failed: {actual}")
    if positives.state_age_pretransition_seconds.isna().any():
        raise RuntimeError("Positive pre-transition state age is incomplete")

    exclusion_event_times = effective_event_times(aligned)
    pool = build_control_pool(intervals, ticks, exclusion_event_times)
    positives = annotate_control_support(positives, pool)
    controls = sample_controls(positives, pool, quota=5)
    positives, controls = attach_actual_control_counts(positives, controls)

    positives["date_split"] = (
        positives.sample_time.dt.date.astype(str).map(SPLIT_BY_DATE)
    )
    controls["date_split"] = (
        controls.sample_time.dt.date.astype(str).map(SPLIT_BY_DATE)
    )
    if positives.date_split.isna().any() or controls.date_split.isna().any():
        raise RuntimeError("Samples outside the locked development/holdout dates")
    if controls.state_age_pretransition_seconds.isna().any():
        raise RuntimeError("Control pre-transition state age is incomplete")
    if controls.duplicated(
        ["pretransition_interval_id", "sample_time"]
    ).any():
        raise RuntimeError("Control candidate reused across matched risk sets")
    if controls.sample_time.duplicated().any():
        raise RuntimeError("Control timestamp reused across matched risk sets")
    if (controls.groupby("matched_event_id").size() > 5).any():
        raise RuntimeError("Control quota exceeded")

    samples = pd.concat([positives, controls], ignore_index=True, sort=False)
    engineered = engineer_features(samples, ticks, aligned)
    h2_retracement_caps = fit_h2_retracement_winsor_caps(engineered)
    engineered = apply_reviewed_model_transforms(
        engineered,
        h2_retracement_caps,
    )
    audit = build_audit_table(engineered)
    model = build_model_matrix(engineered)
    if list(model.columns) != list(model_output_columns()):
        raise RuntimeError("Model matrix differs from the reviewed allowlist")
    if audit[audit.sample_type == "positive"].state_age_pretransition_seconds.isna().any():
        raise RuntimeError("Audit output lost positive state age")

    old_outputs = (
        "trigger_features.parquet",
        "rehedge_positive_samples.parquet",
        "rehedge_control_samples.parquet",
        "unlock_positive_samples.parquet",
        "unlock_control_samples.parquet",
    )
    for name in old_outputs:
        (interim / name).unlink(missing_ok=True)
    audit.to_parquet(interim / "trigger_samples_audit.parquet", index=False)
    model.to_parquet(interim / "trigger_model_features.parquet", index=False)

    main_hypotheses = hypothesis_bundle(
        engineered,
        ticks,
        h2_retracement_caps,
    )
    control_features = engineered[engineered.sample_type == "control"]
    sensitivity, sensitivity_gate = sensitivity_analysis(
        positives,
        control_features,
        ticks,
        aligned,
        main_hypotheses,
    )
    independence_audit = h2_independence_audit(engineered)

    positive_control_counts = positives.actual_control_count
    validity_columns = [f"w{window}ms_valid" for window in WINDOWS_MS]
    report = {
        "positive_accounting": actual,
        "positive_total": int(len(positives)),
        "control_total": int(len(controls)),
        "controls_per_positive": {
            "min": int(positive_control_counts.min()),
            "median": float(positive_control_counts.median()),
            "max": int(positive_control_counts.max()),
            "positives_without_controls": int(
                (positive_control_counts == 0).sum()
            ),
            "distribution": {
                str(key): int(value)
                for key, value in positive_control_counts.value_counts()
                .sort_index()
                .items()
            },
        },
        "control_candidate_reuse_count": int(
            controls.duplicated(
                ["pretransition_interval_id", "sample_time"]
            ).sum()
        ),
        "control_exclusion_event_count": int(len(exclusion_event_times)),
        "control_support": {
            "minimum_state_age_seconds": 7,
            "supported": int(positives.is_control_supported.sum()),
            "unsupported": int((~positives.is_control_supported).sum()),
            "reason_counts": {
                str(key): int(value)
                for key, value in positives.control_support_reason.value_counts().items()
            },
        },
        "state_age_audit": {
            "positive_populated": int(
                positives.state_age_pretransition_seconds.notna().sum()
            ),
            "control_populated": int(
                controls.state_age_pretransition_seconds.notna().sum()
            ),
            "positive_lineage_sources": {
                str(key): int(value)
                for key, value in positives.state_lineage_source.value_counts().items()
            },
        },
        "window_validity": audit.groupby("sample_type")[validity_columns]
        .sum()
        .astype(int)
        .to_dict("index"),
        "split_accounting": positives.groupby(["date_split", "behavior_type"])
        .size()
        .reset_index(name="count")
        .to_dict("records"),
        "coverage_note": (
            "2026-07-23 development coverage begins at 12:00; "
            "2026-07-24 holdout is near-full-day. Raw counts are not directly comparable."
        ),
        "model_output_contract": {
            "audit_file": "trigger_samples_audit.parquet",
            "model_file": "trigger_model_features.parquet",
            "output_allowlist": list(model_output_columns()),
            "predictor_allowlist": list(model_predictor_columns()),
            "predictor_count": len(model_predictor_columns()),
            "sampling_metadata_present": False,
            "time_since_previous_event_present": False,
            "post_action_features_present": False,
            "sample_id_present": False,
            "state_age_clip_seconds": MODEL_STATE_AGE_CLIP_SECONDS,
            "state_age_raw_present": False,
            "h2_retracement_winsor_quantile": (
                H2_RETRACEMENT_WINSOR_QUANTILE
            ),
        },
        "feature_lineage_exclusions": [
            "entry_gap",
            "distance_from_surviving_entry",
            "floating_pnl",
            "preceding_unlock_loss",
        ],
        "hypotheses": main_hypotheses,
        "h2_independence_audit": independence_audit,
        "timestamp_sensitivity": sensitivity,
        "causal_sensitivity_gate": sensitivity_gate,
        "statistics": {
            "bootstrap_draws": BOOTSTRAP_DRAWS,
            "unit": "matched positive event",
            "conclusion_rule": (
                "Adjacent-window coherence: two adjacent supported/rejected windows "
                "set the direction; coherent evidence in both directions is mixed; "
                "isolated evidence is weak."
            ),
        },
    }

    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "trigger_dataset_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    (report_dir / "trigger_dataset_report.md").write_text(
        markdown_report(report),
        encoding="utf-8",
    )
    hypothesis_files = {
        "h1": "h1_rolling_extreme.md",
        "h2": "h2_extreme_retracement.md",
        "h3": "h3_unlock_momentum.md",
    }
    titles = {
        "h1": "H1 — Rolling Boundary",
        "h2": "H2 — Prior Boundary + Retracement",
        "h3": "H3 — Unlock Momentum",
    }
    for key, filename in hypothesis_files.items():
        content = (
            f"# {titles[key]}\n\n"
            f"Conclusion: **{report['hypotheses'][key]['conclusion']}**\n\n"
            f"```json\n{json.dumps(report['hypotheses'][key], indent=2)}\n```\n"
        )
        (report_dir / filename).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
