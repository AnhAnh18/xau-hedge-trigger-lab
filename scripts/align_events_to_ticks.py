from __future__ import annotations
import json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from xau_trigger.event_tick_alignment import align_events

def main() -> None:
    interim, report_dir = ROOT / "data" / "interim", ROOT / "reports" / "phase_03"
    events, ticks = pd.read_parquet(interim / "lifecycle_events.parquet"), pd.read_parquet(interim / "ticks.parquet")
    aligned, candidates, unmatched = align_events(events, ticks)
    for name, table in {"aligned_events": aligned, "event_tick_candidates": candidates, "unmatched_events": unmatched}.items(): table.to_parquet(interim / f"{name}.parquet", index=False)
    matched = aligned[aligned.match_quality != "UNMATCHED"]
    stats = lambda series: {"median": float(series.median()), "p90": float(series.quantile(.90)), "p95": float(series.quantile(.95)), "max": float(series.max())} if len(series) else {}
    high_medium = aligned[aligned.match_quality.isin(["HIGH", "MEDIUM"])]
    excluded = high_medium[~high_medium.is_primary_trigger_sample]
    exclusion_reasons = {"m2_ambiguous_ordering": int((excluded.accounting_category == "ambiguous_ordering").sum()), "wrong_volume_regime": int((excluded.volume != 0.3).sum()), "non_primary_state": int((~(excluded.state_before.isin(["HEDGED_1X1", "ONE_BUY", "ONE_SELL"]) | excluded.state_after.isin(["HEDGED_1X1", "ONE_BUY", "ONE_SELL"]))).sum())}
    exclusion_reasons = {key: value for key, value in exclusion_reasons.items() if value}
    unmatched_profile = {"by_operation": unmatched.groupby(["event_type", "side"]).size().reset_index(name="count").to_dict("records"), "by_date": unmatched.assign(date=unmatched.event_time.dt.date.astype(str)).groupby("date").size().reset_index(name="count").to_dict("records"), "by_hour": unmatched.assign(hour=unmatched.event_time.dt.hour).groupby("hour").size().reset_index(name="count").to_dict("records")}
    operation_metrics = []
    for (event_type, side), group in matched.groupby(["event_type", "side"]):
        operation_metrics.append({"event_type": event_type, "side": side, "count": len(group), "median_time_error_ms": float(group.time_error_ms.abs().median()), "p95_time_error_ms": float(group.time_error_ms.abs().quantile(.95)), "median_price_error": float(group.price_error.median()), "p95_price_error": float(group.price_error.quantile(.95))})
    m2_ambiguous_total = int((events.ordering_quality == "ambiguous").sum()); m2_ambiguous_overlap = int((aligned.m2_ordering_quality == "ambiguous").sum())
    report = {"overlap_events": len(aligned), "open_events": int((aligned.event_type == "POSITION_OPEN").sum()), "close_events": int((aligned.event_type == "POSITION_CLOSE").sum()), "quality": aligned.match_quality.value_counts().to_dict(), "tier": aligned.match_tier.value_counts(dropna=False).to_dict(), "price_error": stats(matched.price_error), "time_error_ms": stats(matched.time_error_ms.abs()), "signed_time_error_ms": stats(matched.time_error_ms), "primary_cohort_accounting": {"high_medium": len(high_medium), "primary": int(aligned.is_primary_trigger_sample.sum()), "excluded": len(excluded), "exclusion_reasons": exclusion_reasons}, "unmatched_profile": unmatched_profile, "m2_ambiguity_accounting": {"total_month": m2_ambiguous_total, "in_tick_coverage": m2_ambiguous_overlap, "resolved": int((aligned.m3_ordering_quality == "resolved").sum()), "remaining": int((aligned.m3_ordering_quality == "still_ambiguous").sum()), "outside_tick_coverage": m2_ambiguous_total - m2_ambiguous_overlap}, "primary_trigger_samples": int(aligned.is_primary_trigger_sample.sum()), "operation_error_metrics": operation_metrics, "by_operation": aligned.groupby(["event_type", "side", "match_quality"]).size().reset_index(name="count").to_dict("records")}
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "event_tick_alignment_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    ambiguity = report["m2_ambiguity_accounting"]
    lines = ["# Event–Tick Alignment Report", "", f"- Overlapping events: {report['overlap_events']}", f"- Open / close: {report['open_events']} / {report['close_events']}", f"- Primary trigger samples: {report['primary_trigger_samples']}", "", "## Primary cohort accounting", "", f"- HIGH/MEDIUM: {len(high_medium)}", f"- Primary: {report['primary_trigger_samples']}", f"- Excluded: {len(excluded)}", *[f"- {key}: {value}" for key, value in exclusion_reasons.items()], "", "## M2 ambiguity lineage", "", f"- Total month: {ambiguity['total_month']}", f"- In tick coverage: {ambiguity['in_tick_coverage']}", f"- Resolved / remaining: {ambiguity['resolved']} / {ambiguity['remaining']}", f"- Outside tick coverage: {ambiguity['outside_tick_coverage']}", "", "## Match quality", ""] + [f"- {key}: {value}" for key, value in report["quality"].items()]
    (report_dir / "event_tick_alignment_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if len(aligned) != int(events.event_time.between(ticks.timestamp.min(), ticks.timestamp.max()).sum()): raise RuntimeError("Event accounting mismatch")

if __name__ == "__main__": main()
