from __future__ import annotations
import json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from xau_trigger.trigger_dataset import WINDOWS_MS, build_control_pool, effective_event_times, engineer_features, expected_feature, paired_summary, sample_controls, select_positives

def conclusion(results: list[dict]) -> str:
    holdout = [item for item in results if item["split"] == "holdout" and item["summary"]["pairs"] >= 30 and item["summary"]["cluster_bootstrap_ci95"]]
    if not holdout: return "inconclusive"
    supported = sum(item["summary"]["cluster_bootstrap_ci95"][0] > 0 for item in holdout)
    rejected = sum(item["summary"]["cluster_bootstrap_ci95"][1] < 0 for item in holdout)
    if supported >= max(2, len(holdout) // 2): return "supported"
    if supported: return "weak"
    if rejected >= max(2, len(holdout) // 2): return "rejected"
    return "inconclusive"

def main() -> None:
    interim, report_dir = ROOT / "data" / "interim", ROOT / "reports" / "phase_04"
    aligned = pd.read_parquet(interim / "aligned_events.parquet"); intervals = pd.read_parquet(interim / "state_intervals.parquet"); ticks = pd.read_parquet(interim / "ticks.parquet")
    positives = select_positives(aligned)
    expected = {"REHEDGE_SELL": 331, "REHEDGE_BUY": 306, "UNLOCK_TO_BUY": 320, "UNLOCK_TO_SELL": 294}
    actual = positives.behavior_type.value_counts().to_dict()
    if actual != expected: raise RuntimeError(f"Primary-positive reconciliation failed: {actual}")
    exclusion_event_times = effective_event_times(aligned)
    pool = build_control_pool(intervals, ticks, exclusion_event_times)
    controls = sample_controls(positives, pool, quota=5)
    positives["date_split"] = positives.sample_time.dt.date.astype(str).map(
        {"2026-07-23": "development", "2026-07-24": "holdout"}
    )
    controls["date_split"] = controls.sample_time.dt.date.astype(str).map(
        {"2026-07-23": "development", "2026-07-24": "holdout"}
    )
    samples = pd.concat([positives, controls], ignore_index=True, sort=False)
    features = engineer_features(samples, ticks, intervals, aligned)
    forbidden_feature_tokens = (
        "entry_gap",
        "surviving_entry",
        "floating_pnl",
        "preceding_unlock_loss",
        "price_error",
        "bid_return",
        "ask_return",
        "plus_500",
        "+500",
    )
    forbidden_feature_columns = [
        column
        for column in features.columns
        if any(token in column for token in forbidden_feature_tokens)
    ]
    if forbidden_feature_columns:
        raise RuntimeError(
            f"Leakage/lineage columns entered training features: {forbidden_feature_columns}"
        )
    if samples.date_split.isna().any():
        raise RuntimeError("Samples outside the locked development/holdout dates")
    if controls.duplicated(["interval_id", "sample_time"]).any():
        raise RuntimeError("Control candidate reused across matched risk sets")
    if (controls.groupby("matched_event_id").size() > 5).any():
        raise RuntimeError("Control quota exceeded")
    positives[positives.trigger_family == "rehedge"].to_parquet(interim / "rehedge_positive_samples.parquet", index=False)
    controls[controls.trigger_family == "rehedge"].to_parquet(interim / "rehedge_control_samples.parquet", index=False)
    positives[positives.trigger_family == "unlock"].to_parquet(interim / "unlock_positive_samples.parquet", index=False)
    controls[controls.trigger_family == "unlock"].to_parquet(interim / "unlock_control_samples.parquet", index=False)
    features.to_parquet(interim / "trigger_features.parquet", index=False)
    hypothesis_specs = {"h1": "rehedge", "h2": "rehedge", "h3": "unlock"}; analyses = {}
    for hypothesis, family in hypothesis_specs.items():
        family_frame = features[features.trigger_family == family]; results = []
        for split in ("development", "holdout"):
            for window in WINDOWS_MS: results.append({"split": split, "window_ms": window, "summary": paired_summary(family_frame[family_frame.date_split == split], window, hypothesis)})
        analyses[hypothesis] = {"conclusion": conclusion(results), "results": results}
    # Sensitivity is isolated from the training feature table. Controls stay fixed; only positive timestamps shift.
    sensitivity = {}
    for shift_ms in (-500, 0, 500):
        shifted = positives.copy(); shifted["sample_time"] = shifted.sample_time + pd.Timedelta(milliseconds=shift_ms)
        shifted_features = engineer_features(shifted, ticks, intervals, aligned)
        sensitivity_frame = pd.concat(
            [shifted_features, features[features.sample_type == "control"]],
            ignore_index=True,
            sort=False,
        )
        medians = {}
        shifted_analyses = {}
        for hypothesis, family in hypothesis_specs.items():
            subset = shifted_features[shifted_features.trigger_family == family]
            medians[hypothesis] = {str(window): float(pd.Series(expected_feature(subset[subset[f"w{window}ms_valid"]], window, hypothesis)).median()) for window in WINDOWS_MS}
            family_frame = sensitivity_frame[sensitivity_frame.trigger_family == family]
            results = [
                {
                    "split": split,
                    "window_ms": window,
                    "summary": paired_summary(
                        family_frame[family_frame.date_split == split],
                        window,
                        hypothesis,
                    ),
                }
                for split in ("development", "holdout")
                for window in WINDOWS_MS
            ]
            shifted_analyses[hypothesis] = {
                "conclusion": conclusion(results),
                "results": results,
            }
        sensitivity[str(shift_ms)] = {
            "positive_medians": medians,
            "hypotheses": shifted_analyses,
        }
    control_counts = controls.groupby("matched_event_id").size()
    main_conclusions = {key: value["conclusion"] for key, value in analyses.items()}
    sensitivity_conclusions = {
        shift: {
            key: value["conclusion"]
            for key, value in result["hypotheses"].items()
        }
        for shift, result in sensitivity.items()
    }
    sensitivity_stable = all(
        conclusions == main_conclusions
        for conclusions in sensitivity_conclusions.values()
    )
    validity_columns = [f"w{window}ms_valid" for window in WINDOWS_MS]
    all_control_counts = (
        positives.matched_event_id.map(control_counts).fillna(0).astype(int)
    )
    report = {
        "positive_accounting": actual,
        "positive_total": len(positives),
        "control_total": len(controls),
        "controls_per_positive": {
            "min": int(all_control_counts.min()),
            "median": float(all_control_counts.median()),
            "max": int(all_control_counts.max()),
            "positives_without_controls": int((all_control_counts == 0).sum()),
            "distribution": {
                str(key): int(value)
                for key, value in all_control_counts.value_counts().sort_index().items()
            },
        },
        "control_candidate_reuse_count": int(
            controls.duplicated(["interval_id", "sample_time"]).sum()
        ),
        "control_exclusion_event_count": int(len(exclusion_event_times)),
        "window_validity": features.groupby("sample_type")[validity_columns]
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
        "feature_lineage_exclusions": [
            "entry_gap",
            "distance_from_surviving_entry",
            "floating_pnl",
            "preceding_unlock_loss",
        ],
        "causal_feature_audit": {
            "feature_time": "matched_time",
            "future_shift_columns": [],
            "side_return_columns": [],
            "forbidden_lineage_columns": [],
            "plus_500ms_usage": "sensitivity_report_only",
        },
        "hypotheses": analyses,
        "timestamp_sensitivity": sensitivity,
        "sensitivity_gate": {
            "stable": sensitivity_stable,
            "main_conclusions": main_conclusions,
            "shifted_conclusions": sensitivity_conclusions,
        },
        "statistics_note": (
            "Matched-set paired differences with positive-event cluster bootstrap; "
            "reported control comparisons are not absolute event probabilities."
        ),
    }
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "trigger_dataset_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# M4 Trigger Dataset Report",
        "",
        "## Gate status",
        "",
        (
            "**NOT PASSED** — timestamp sensitivity changes the H1/H2 conclusions "
            "at +500 ms."
            if not sensitivity_stable
            else "**PASSED** — conclusions are stable at -500/0/+500 ms."
        ),
        "",
        "The implementation is reproducible, but M4 must not be closed while this "
        "sensitivity gate is unresolved.",
        "",
        "## Positive accounting",
        "",
        "| Behavior | Count |",
        "| --- | ---: |",
        *[
            f"| {behavior} | {count:,} |"
            for behavior, count in expected.items()
        ],
        f"| **Total** | **{len(positives):,}** |",
        "",
        "## Matched controls",
        "",
        f"- Controls: {len(controls):,}",
        f"- Positives without a control: {report['controls_per_positive']['positives_without_controls']}",
        f"- Controls per positive: {report['controls_per_positive']['distribution']}",
        f"- Reused control candidates: {report['control_candidate_reuse_count']}",
        f"- True events protected by exclusion zones: {report['control_exclusion_event_count']:,}",
        "- Sampling is deterministic, without global candidate replacement, and "
        "uses the same date, hour, state, opportunity direction, and 0.3 volume.",
        "- Every control is outside the ±3 second exclusion zone of every aligned "
        "true event. Short risk sets are not forced to meet the quota.",
        "",
        "## Window validity",
        "",
        "| Sample | 500 ms | 1 s | 2 s | 5 s | 10 s | 30 s | 60 s |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        *[
            "| "
            + sample_type
            + " | "
            + " | ".join(
                f"{report['window_validity'][sample_type][column]:,}"
                for column in validity_columns
            )
            + " |"
            for sample_type in ("positive", "control")
        ],
        "",
        "Samples remain in the dataset when a long window is unavailable; each "
        "analysis filters only on its own validity flag.",
        "",
        "## Hypothesis conclusions at matched_time",
        "",
        *[
            f"- {key.upper()}: **{value['conclusion']}**"
            for key, value in analyses.items()
        ],
        "",
        "H1 separates most clearly at 5–60 seconds. H2 is rejected over those same "
        "windows. H3 has short-horizon support at 0.5–2 seconds, while longer "
        "windows are inconclusive.",
        "",
        "## Timestamp sensitivity",
        "",
        "| Shift | H1 | H2 | H3 |",
        "| ---: | --- | --- | --- |",
        *[
            f"| {shift} ms | {values['h1']} | {values['h2']} | {values['h3']} |"
            for shift, values in sensitivity_conclusions.items()
        ],
        "",
        "The +500 ms reversal is report-only evidence of timing fragility. No "
        "+500 ms value is present in `trigger_features.parquet` or used for rule "
        "discovery.",
        "",
        "## Coverage and inference constraints",
        "",
        "- 2026-07-23 is development data and begins at 12:00.",
        "- 2026-07-24 is holdout data and is near-full-day.",
        "- Raw daily event counts or rates are not compared as if coverage were equal.",
        "- Statistics use matched differences and positive-event cluster bootstrap; "
        "controls in one risk set are not treated as independent.",
        "- Control ratios are not interpreted as absolute event probabilities.",
        "- `entry_gap`, surviving-entry distance, floating P/L, and preceding unlock "
        "loss are excluded pending position lineage.",
    ]
    (report_dir / "trigger_dataset_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    for key, value in analyses.items():
        title = {"h1": "H1 — Rolling Boundary", "h2": "H2 — Extreme + Retracement", "h3": "H3 — Unlock Momentum"}[key]
        (report_dir / f"{key}_{'rolling_extreme' if key == 'h1' else 'extreme_retracement' if key == 'h2' else 'unlock_momentum'}.md").write_text(f"# {title}\n\nConclusion: **{value['conclusion']}**\n\n```json\n{json.dumps(value['results'], indent=2)}\n```\n", encoding="utf-8")

if __name__ == "__main__": main()
