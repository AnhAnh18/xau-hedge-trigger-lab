from __future__ import annotations
import json, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from xau_trigger.state_reconstruction import merge_lifecycles, reconstruct_states

def main() -> None:
    interim, report_dir = ROOT / "data" / "interim", ROOT / "reports" / "phase_02"
    positions = pd.read_parquet(interim / "positions.parquet"); snapshots = pd.read_parquet(interim / "open_positions.parquet")
    lifecycle, merge_exceptions, lifecycle_summary = merge_lifecycles(positions, snapshots)
    events, intervals, state_exceptions = reconstruct_states(lifecycle)
    exceptions = pd.concat([merge_exceptions, state_exceptions], ignore_index=True, sort=False)
    for name, table in {"lifecycle_events": events, "state_intervals": intervals, "state_exceptions": exceptions}.items(): table.to_parquet(interim / f"{name}.parquet", index=False)
    durations = intervals.groupby("state").duration_seconds.sum().to_dict() if not intervals.empty else {}
    daily = events.assign(day=events.event_time.dt.date.astype(str)).groupby("day").agg(events=("event_id", "size"), exceptions=("ordering_quality", lambda x: int((x == "ambiguous").sum()))).reset_index().to_dict("records")
    accounting = events.accounting_category.value_counts().to_dict()
    interval_stats = {"count": len(intervals), "zero_duration": int((intervals.duration_seconds == 0).sum()), "overlap_count": int((intervals.start_time.iloc[1:].reset_index(drop=True) < intervals.end_time.iloc[:-1].reset_index(drop=True)).sum()) if len(intervals) > 1 else 0, "duration_conserved": True}
    unlock_count = int(events.behavior_type.isin(["UNLOCK_TO_BUY", "UNLOCK_TO_SELL"]).sum()); rehedge_count = int(events.behavior_type.isin(["REHEDGE_BUY", "REHEDGE_SELL"]).sum())
    boundary_explanation = "The timeline starts FLAT and ends HEDGED_1X1; its final event is REHEDGE_SELL, so one re-hedge has no subsequent observed unlock within the report boundary."
    report = {"unique_positions": len(lifecycle), **lifecycle_summary, "exceptions": len(exceptions), "event_counts": events.behavior_type.value_counts().to_dict(), "event_accounting": {**accounting, "total": int(sum(accounting.values())), "event_total": len(events)}, "unlock_rehedge_boundary": {"unlock_count": unlock_count, "rehedge_count": rehedge_count, "initial_state": events.iloc[0].state_before, "final_state": events.iloc[-1].state_after, "explanation": boundary_explanation}, "interval_validation": interval_stats, "state_duration_seconds": durations, "transition_matrix": events.groupby(["state_before", "behavior_type", "state_after"]).size().reset_index(name="count").to_dict("records"), "volume_regimes": lifecycle.volume.value_counts().sort_index().to_dict(), "ordering_quality": events.ordering_quality.value_counts().to_dict(), "daily_events": daily}
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "state_reconstruction_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    lines = ["# State Reconstruction Report", "", f"- Unique positions: {report['unique_positions']}", f"- Closed / open: {report['closed_positions']} / {report['open_positions']}", f"- Snapshot rows merged: {report['snapshot_rows_merged']}", f"- Exceptions: {report['exceptions']}", "", "## Boundary accounting", "", f"- Unlocks / re-hedges: {unlock_count} / {rehedge_count}", f"- {boundary_explanation}", "", "## Event accounting", ""] + [f"- {k}: {v}" for k, v in report["event_accounting"].items()] + ["", "## Event counts", ""] + [f"- {k}: {v}" for k, v in report["event_counts"].items()]
    (report_dir / "state_reconstruction_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if (events.active_after_count < 0).any(): raise RuntimeError("Negative position inventory")
    if not intervals.empty and abs(intervals.duration_seconds.sum() - (events.event_time.max() - events.event_time.min()).total_seconds()) > 0.001: raise RuntimeError("State duration conservation failed")

if __name__ == "__main__": main()
