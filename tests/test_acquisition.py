from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pandas as pd

from xau_trigger.acquisition import (
    build_synthetic_acquisition_files,
    classify_recurring_gaps,
    load_acquisition_plan,
    validate_acquisition,
)


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "data" / "m5_acquisition_plan.json"
SUPPLEMENTAL_PLAN_PATH = ROOT / "data" / "m5_retrospective_support_plan.json"


def test_acquisition_plan_is_locked_before_external_sessions() -> None:
    plan = load_acquisition_plan(PLAN_PATH)

    assert plan["registered_on"] == "2026-07-26"
    assert plan["sessions"] == [
        "2026-07-27",
        "2026-07-28",
        "2026-07-29",
    ]
    assert plan["coverage_gap_policy"]["threshold_seconds"] == 60
    assert plan["coverage_gap_policy"]["retune_after_results"] is False
    assert plan["analysis_windows"]["primary_server_hours"] == [12, 24]
    assert plan["analysis_windows"]["secondary_can_override_primary"] is False


def test_retrospective_support_plan_is_non_gating_and_locked() -> None:
    plan = load_acquisition_plan(SUPPLEMENTAL_PLAN_PATH)

    assert plan["registered_on"] == "2026-07-26"
    assert plan["cohort_role"] == "retrospective_supplemental_non_gating"
    assert plan["sessions"] == [
        "2026-07-20",
        "2026-07-21",
        "2026-07-22",
    ]
    assert plan["trade_report"]["required_period_start"] == "2026-07-19"
    assert plan["trade_report"]["required_period_end"] == "2026-07-25"
    assert plan["tick_export"]["source_sha256_allowlist"] == [
        "d0f27a2090ad84db810c8d5ed5b2b1907743ba084684bc3aa1fdd46983ba5fa4"
    ]


def test_synthetic_acquisition_passes_and_is_deterministic(tmp_path: Path) -> None:
    plan = load_acquisition_plan(PLAN_PATH)
    tick_path, report_path = build_synthetic_acquisition_files(plan, tmp_path)

    first = validate_acquisition(plan, [tick_path], [report_path])
    second = validate_acquisition(plan, [tick_path], [report_path])

    assert first == second
    assert first["status"] == "PASS"
    assert first["deterministic_validation_sha256"] == (
        "2ab041565dfed4750e5740e2fe7335549bc37ecf34a8b548665a8aad1425f6b9"
    )
    assert all(
        session["status"] == "PASS" for session in first["ticks"]["sessions"]
    )
    assert all(
        session["status"] == "PASS"
        for session in first["trade_reports"]["sessions"]
    )


def test_missing_acquisition_is_incomplete_not_exception() -> None:
    plan = load_acquisition_plan(PLAN_PATH)

    result = validate_acquisition(plan, [], [])

    assert result["status"] == "INCOMPLETE"
    assert result["ticks"]["files"] == []
    assert result["trade_reports"]["files"] == []
    assert {
        session["status"] for session in result["ticks"]["sessions"]
    } == {"INCOMPLETE"}


def test_output_uses_aliases_and_does_not_leak_private_filename(
    tmp_path: Path,
) -> None:
    plan = load_acquisition_plan(PLAN_PATH)
    tick_path, report_path = build_synthetic_acquisition_files(plan, tmp_path)
    private_tick = tick_path.rename(tmp_path / "private-client-12345.tsv")
    private_report = report_path.rename(
        tmp_path / "Private Client 12345.html"
    )

    result = validate_acquisition(plan, [private_tick], [private_report])
    rendered = json.dumps(result)

    assert result["status"] == "PASS"
    assert "12345" not in rendered
    assert "Private Client" not in rendered
    assert str(tmp_path) not in rendered
    assert result["ticks"]["files"][0]["file_alias"] == "tick-001"
    assert result["trade_reports"]["files"][0]["file_alias"] == "report-001"


def test_duplicate_tick_timestamp_is_preserved_and_reported(
    tmp_path: Path,
) -> None:
    plan = load_acquisition_plan(PLAN_PATH)
    tick_path, report_path = build_synthetic_acquisition_files(plan, tmp_path)
    lines = tick_path.read_text(encoding="utf-8").splitlines()
    lines.insert(2, lines[1])
    tick_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = validate_acquisition(plan, [tick_path], [report_path])

    assert result["status"] == "PASS"
    assert result["ticks"]["files"][0]["rows"] == 4114
    assert result["ticks"]["files"][0]["duplicate_millisecond_rows"] == 2
    assert result["ticks"]["sessions"][0]["duplicate_millisecond_rows"] == 2


def test_malformed_report_fails_cleanly(tmp_path: Path) -> None:
    plan = load_acquisition_plan(PLAN_PATH)
    tick_path, report_path = build_synthetic_acquisition_files(plan, tmp_path)
    report_path.write_text(
        "<html><body><table><tr><th>Positions</th></tr></table></body></html>",
        encoding="utf-8",
    )

    result = validate_acquisition(plan, [tick_path], [report_path])

    assert result["status"] == "FAIL"
    assert result["trade_reports"]["files"][0]["status"] == "FAIL"
    assert "error_type" in result["trade_reports"]["files"][0]


def test_recurring_gap_classification_requires_registered_recurrence() -> None:
    gaps = pd.DataFrame(
        {
            "break_id": ["gap-001", "gap-002", "gap-003", "gap-004"],
            "break_start": pd.to_datetime(
                [
                    "2026-07-27 23:50:00",
                    "2026-07-28 23:49:30",
                    "2026-07-29 23:51:00",
                    "2026-07-28 14:00:00",
                ]
            ),
            "break_end": pd.to_datetime(
                [
                    "2026-07-28 01:00:00",
                    "2026-07-29 01:00:30",
                    "2026-07-30 01:01:00",
                    "2026-07-28 14:02:00",
                ]
            ),
            "duration_seconds": [4200.0, 4260.0, 4200.0, 120.0],
            "gap_classification": ["unknown_coverage_gap"] * 4,
            "exclusion_reason": ["unknown_coverage_gap"] * 4,
        }
    )

    classified = classify_recurring_gaps(
        gaps,
        minimum_sessions=3,
        tolerance_seconds=120,
    )

    assert classified.iloc[:3]["gap_classification"].tolist() == [
        "scheduled_market_closed",
        "scheduled_market_closed",
        "scheduled_market_closed",
    ]
    assert classified.iloc[3]["gap_classification"] == "unknown_coverage_gap"


def test_acquisition_cli_plan_only_and_dry_run() -> None:
    command = [sys.executable, "scripts/validate_m5_acquisition.py"]
    for option, expected_status in [
        ("--plan-only", "PLAN_VALID"),
        ("--dry-run", "PASS"),
    ]:
        completed = subprocess.run(
            [*command, option],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        assert json.loads(completed.stdout)["status"] == expected_status
