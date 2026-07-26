from __future__ import annotations

import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.risk_time import build_risk_time_audit


def _fmt(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{value:,.{digits}f}"


def render_markdown(report: dict) -> str:
    lines = [
        "# M5-000 Risk-Time Audit",
        "",
        f"- Status: `{report['status']}`",
        f"- Tick coverage: {report['configuration']['coverage_start']} to "
        f"{report['configuration']['coverage_end']}",
        f"- M2 intervals touching coverage: "
        f"{report['coverage']['m2_source_interval_count']:,}",
        f"- Synthetic right-censored tails: "
        f"{report['coverage']['synthetic_right_censored_interval_count']:,}",
        f"- Positive-duration intervals: "
        f"{report['coverage']['positive_duration_interval_count']:,}",
        f"- Deterministic audit SHA-256: "
        f"`{report['deterministic_audit_sha256']}`",
        "",
        "## Why the earlier counts differ",
        "",
        "The legacy calculation assigns each interval's entire un-clipped "
        "duration to its start date. It therefore assigns the after-midnight "
        "part of a cross-midnight interval to the prior day and counts the "
        "maintenance break as risk time.",
        "",
        "| Day | Intervals | Legacy seconds | Event density |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in report["legacy_start_date_accounting"]:
        lines.append(
            f"| {row['day']} | {row['interval_count']:,} | "
            f"{_fmt(row['unclipped_start_date_assigned_seconds'])} | "
            f"{_fmt(row['event_density_percent'])}% |"
        )

    lines.extend(
        [
            "",
            "## Canonical full-coverage accounting",
            "",
            "Intervals are clipped to observed tick coverage, split at "
            "midnight, and stripped of excluded coverage-gap time.",
            "",
            "| Day | Interval-day memberships | Target events | Raw seconds | "
            "Gap seconds | Tradeable seconds | Primary risk seconds | "
            "Target density |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in report["canonical_full_coverage_by_day"]:
        lines.append(
            f"| {row['day']} | {row['source_interval_count']:,} | "
            f"{row['target_event_count']:,} | "
            f"{_fmt(row['raw_overlap_seconds'])} | "
            f"{_fmt(row['excluded_break_seconds'])} | "
            f"{_fmt(row['tradeable_risk_seconds'])} | "
            f"{_fmt(row['primary_risk_seconds'])} | "
            f"{_fmt(row['target_event_density_percent'])}% |"
        )

    lines.extend(
        [
            "",
            "## Comparable cohort: server hours 12-23",
            "",
            "All later A/B/C headline comparisons must use this common "
            "server-hour support. Full-range results remain descriptive.",
            "",
            "| Day | Interval-day memberships | Target events | Tradeable seconds | "
            "Primary risk seconds | Target density |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in report["canonical_common_hours_by_day"]:
        lines.append(
            f"| {row['day']} | {row['source_interval_count']:,} | "
            f"{row['target_event_count']:,} | "
            f"{_fmt(row['tradeable_risk_seconds'])} | "
            f"{_fmt(row['primary_risk_seconds'])} | "
            f"{_fmt(row['target_event_density_percent'])}% |"
        )

    comparison = report["cohort_comparability"]
    lines.extend(
        [
            "",
            "## Cohort comparability warning",
            "",
            f"- Development / holdout common-hour density ratio: "
            f"**{_fmt(comparison['development_to_holdout_density_ratio'])}x**.",
            f"- Holdout 12–24 / 01–12 density ratio: "
            f"**{_fmt(comparison['holdout_12_24_to_01_12_density_ratio'])}x**.",
            "- Common hours align observed coverage, but they do not align base "
            "rates or remove the Thursday/Friday/day-of-week confound.",
            "- Primary M5 v1 inference remains fixed to server hours 12–24. "
            "A full-session analysis on the external dates is pre-registered "
            "as secondary.",
            "",
            "## Coverage-gap accounting",
            "",
        ]
    )
    for row in report["coverage_gaps"]:
        lines.append(
            f"- `{row['break_start']}` to `{row['break_end']}`: "
            f"{_fmt(row['duration_seconds'])} seconds excluded "
            f"(`{row['gap_classification']}`)."
        )

    cases = report["boundary_cases"]
    lines.extend(
        [
            "",
            "## Boundary cases",
            "",
            f"- Left-truncated interval IDs: "
            f"{', '.join(cases['left_truncated_interval_ids']) or 'none'}",
            f"- Right-censored interval IDs: "
            f"{', '.join(cases['right_censored_interval_ids']) or 'none'}",
            f"- Cross-midnight interval IDs: "
            f"{', '.join(cases['cross_midnight_interval_ids']) or 'none'}",
            f"- Coverage-gap intersection interval IDs: "
            f"{', '.join(cases['coverage_gap_intersection_interval_ids']) or 'none'}",
            f"- Right-censored tail seconds: "
            f"{_fmt(cases['right_censored_tail_seconds'])}",
            f"- Zero-duration intervals in coverage: "
            f"{cases['zero_duration_interval_count']:,}",
            "- Left-truncated intervals are retained in audit accounting but "
            "excluded from primary inference.",
            "",
            "## Primary estimand",
            "",
            "- Transition timing in eligible states with at least one complete "
            "causal risk bin on merged tick coverage.",
            f"- Zero-duration target events excluded (full/common): "
            f"{report['primary_estimand']['zero_duration_target_events_excluded_full_coverage']}"
            f" / "
            f"{report['primary_estimand']['zero_duration_target_events_excluded_common_hours']}.",
            "- The structural zero/early-state support limitation remains "
            "tracked in issue #3.",
            "",
            "## Timezone decision",
            "",
            "- Server timezone: `UTC+03:00`.",
            "- Status: high-confidence inference for the July 2026 data "
            "window, not a globally confirmed broker/DST rule.",
            f"- Highest tick-count server hours: "
            f"{', '.join(map(str, report['timezone_decision']['highest_tick_count_server_hours']))}.",
            "",
            "## Gate",
            "",
            "M5-000 defines accounting and acquisition prerequisites only. "
            "No model verdict is allowed from this report, and M5 cannot "
            "close without pre-registered additional tick sessions.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    interim = ROOT / "data" / "interim"
    report_dir = ROOT / "reports" / "phase_05"
    interval_path = interim / "state_intervals.parquet"
    tick_path = interim / "ticks.parquet"
    event_path = interim / "lifecycle_events.parquet"
    if (
        not interval_path.exists()
        or not tick_path.exists()
        or not event_path.exists()
    ):
        raise FileNotFoundError(
            "Build M2 events/intervals and canonical ticks before M5-000 audit"
        )

    intervals = pd.read_parquet(interval_path)
    ticks = pd.read_parquet(tick_path)
    lifecycle_events = pd.read_parquet(event_path)
    report = build_risk_time_audit(intervals, ticks, lifecycle_events)
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "m5_000_risk_time_audit.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (report_dir / "m5_000_risk_time_audit.md").write_text(
        render_markdown(report),
        encoding="utf-8",
    )
    print(
        "M5-000 risk-time audit complete: "
        f"{report['deterministic_audit_sha256']}"
    )


if __name__ == "__main__":
    main()
