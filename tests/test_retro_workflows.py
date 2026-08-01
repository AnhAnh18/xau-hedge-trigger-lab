from __future__ import annotations

import csv
from pathlib import Path

from scripts.analyze_retro_selected_case import tick_metrics
from scripts.build_retro_003_inventory import select_cases


def test_retro_003_selection_uses_fixed_strata_and_earliest_date() -> None:
    candidates = [
        {"server_date": "2025-12-10", "side": "buy", "start_time": "2025-12-10 02:00:00", "end_time": "2025-12-10 02:10:00", "duration_seconds": 600, "report_alias": "report-001.html"},
        {"server_date": "2025-11-12", "side": "sell", "start_time": "2025-11-12 02:00:00", "end_time": "2025-11-12 02:05:00", "duration_seconds": 300, "report_alias": "report-001.html"},
        {"server_date": "2026-03-10", "side": "buy", "start_time": "2026-03-10 02:00:00", "end_time": "2026-03-10 02:08:00", "duration_seconds": 480, "report_alias": "report-005.html"},
        {"server_date": "2026-07-01", "side": "buy", "start_time": "2026-07-01 02:00:00", "end_time": "2026-07-01 02:09:00", "duration_seconds": 540, "report_alias": "report-009.html"},
    ]

    selected, summary = select_cases(candidates)

    assert summary == {"eligible_date_count": 4, "selected_case_count": 3}
    assert [item["server_date"] for item in selected] == ["2025-11-12", "2026-03-10", "2026-07-01"]


def test_selected_case_tick_metrics_keep_clock_diagnostics_aggregate_only(tmp_path: Path) -> None:
    tick_path = tmp_path / "ticks.csv"
    with tick_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["time_utc", "bid", "ask"])
        writer.writerow(["2026-01-01T00:00:00.000+00:00", "100", "101"])
        writer.writerow(["2026-01-01T00:00:01.000+00:00", "99", "100"])
        writer.writerow(["2026-01-01T00:00:02.000+00:00", "98", "99"])

    config = {
        "window_start": "2026-01-01 02:00:00",
        "window_end": "2026-01-01 02:00:02",
        "start": "2026-01-01 02:00:00",
        "end": "2026-01-01 02:00:02",
        "side": "buy",
    }
    metrics = tick_metrics(tick_path, config, 2, 100.0)

    assert metrics["coverage"] == "present"
    assert metrics["boundary_alignment"] is True
    assert metrics["valid_tick_count"] == 3
    assert metrics["drawdown_band"] == "under_15"
