from __future__ import annotations

import pandas as pd

from xau_trigger.risk_time import (
    build_risk_time_audit,
    clip_fragments_to_daily_hours,
    detect_market_breaks,
    partition_risk_time,
    summarize_fragments,
    tradeable_elapsed_seconds,
)


def _intervals() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "interval_id": [13321],
            "start_time": [pd.Timestamp("2026-07-23 23:58:00")],
            "end_time": [pd.Timestamp("2026-07-24 01:02:00")],
            "duration_seconds": [3840.0],
            "state": ["ONE_SELL"],
            "preceding_event_type": ["UNLOCK_TO_SELL"],
            "following_event_type": ["REHEDGE_BUY"],
        }
    )


def _ticks() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-07-23 23:58:00",
                    "2026-07-23 23:59:00",
                    "2026-07-24 01:00:00",
                    "2026-07-24 01:02:00",
                ]
            )
        }
    )


def test_market_break_detection_uses_strict_locked_threshold() -> None:
    gaps = detect_market_breaks(_ticks(), threshold_seconds=60)

    assert len(gaps) == 2
    assert gaps.duration_seconds.tolist() == [3660.0, 120.0]
    assert gaps.exclusion_reason.unique().tolist() == [
        "market_break_no_tick_coverage"
    ]


def test_cross_midnight_interval_is_split_and_break_is_not_risk_time() -> None:
    breaks = pd.DataFrame(
        {
            "break_start": [pd.Timestamp("2026-07-23 23:59:00")],
            "break_end": [pd.Timestamp("2026-07-24 01:00:00")],
        }
    )
    fragments = partition_risk_time(
        _intervals(),
        coverage_start=pd.Timestamp("2026-07-23 23:58:00"),
        coverage_end=pd.Timestamp("2026-07-24 01:02:00"),
        breaks=breaks,
    )

    by_day = fragments.groupby("day").agg(
        raw=("duration_seconds", "sum"),
        tradeable=(
            "duration_seconds",
            lambda values: values[fragments.loc[values.index, "is_tradeable"]].sum(),
        ),
    )
    assert by_day.loc["2026-07-23"].to_dict() == {
        "raw": 120.0,
        "tradeable": 60.0,
    }
    assert by_day.loc["2026-07-24"].to_dict() == {
        "raw": 3720.0,
        "tradeable": 120.0,
    }
    assert fragments.interval_id.nunique() == 1
    assert fragments.is_cross_midnight.all()


def test_tradeable_state_age_pauses_inside_market_break() -> None:
    breaks = pd.DataFrame(
        {
            "break_start": [pd.Timestamp("2026-07-23 23:59:00")],
            "break_end": [pd.Timestamp("2026-07-24 01:00:00")],
        }
    )

    result = tradeable_elapsed_seconds(
        pd.Timestamp("2026-07-23 23:58:00"),
        pd.Timestamp("2026-07-24 01:02:00"),
        breaks,
    )

    assert result == 180.0


def test_common_hour_clipping_does_not_assign_overnight_risk() -> None:
    breaks = pd.DataFrame(
        {
            "break_start": [pd.Timestamp("2026-07-23 23:59:00")],
            "break_end": [pd.Timestamp("2026-07-24 01:00:00")],
        }
    )
    fragments = partition_risk_time(
        _intervals(),
        coverage_start=pd.Timestamp("2026-07-23 23:58:00"),
        coverage_end=pd.Timestamp("2026-07-24 13:00:00"),
        breaks=breaks,
    )

    common = clip_fragments_to_daily_hours(
        fragments,
        start_hour=12,
        end_hour=24,
    )

    assert common.day.unique().tolist() == ["2026-07-23"]
    assert common.duration_seconds.sum() == 120.0


def test_zero_duration_interval_is_preserved_for_accounting_only() -> None:
    interval = _intervals()
    interval.loc[0, "end_time"] = interval.loc[0, "start_time"]
    interval.loc[0, "duration_seconds"] = 0.0
    fragments = partition_risk_time(
        interval,
        coverage_start=pd.Timestamp("2026-07-23 23:00:00"),
        coverage_end=pd.Timestamp("2026-07-24 01:00:00"),
        breaks=pd.DataFrame(columns=["break_start", "break_end"]),
    )

    assert len(fragments) == 1
    assert fragments.exclusion_reason.tolist() == ["zero_duration"]
    assert not fragments.is_tradeable.any()

    summary = summarize_fragments(
        interval,
        fragments,
        coverage_start=pd.Timestamp("2026-07-23 23:00:00"),
        coverage_end=pd.Timestamp("2026-07-24 01:00:00"),
    )
    assert summary[0]["terminal_event_count"] == 1
    assert summary[0]["eligible_terminal_event_count"] == 0
    assert summary[0]["target_event_count"] == 0


def test_audit_hash_is_deterministic_and_records_boundary_case() -> None:
    ticks = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                [
                    "2026-07-23 23:58:00",
                    "2026-07-23 23:58:30",
                    "2026-07-24 01:00:00",
                    "2026-07-24 01:02:00",
                ]
            )
        }
    )

    first = build_risk_time_audit(_intervals(), ticks)
    second = build_risk_time_audit(_intervals(), ticks)

    assert first["deterministic_audit_sha256"] == second[
        "deterministic_audit_sha256"
    ]
    assert first["boundary_cases"]["cross_midnight_interval_ids"] == ["13321"]
    assert first["boundary_cases"]["market_break_intersection_interval_ids"] == [
        "13321"
    ]
    assert first["status"] == "pilot_accounting_only"
