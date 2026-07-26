from __future__ import annotations

import pandas as pd

from xau_trigger.risk_time import (
    append_right_censored_tail,
    build_risk_time_audit,
    clip_fragments_to_daily_hours,
    detect_coverage_gaps,
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


def _events() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_id": [1],
            "event_sequence": [1],
            "event_time": [pd.Timestamp("2026-07-24 01:02:00")],
            "state_after": ["HEDGED_1X1"],
            "behavior_type": ["REHEDGE_BUY"],
        }
    )


def test_coverage_gap_detection_uses_strict_locked_threshold() -> None:
    gaps = detect_coverage_gaps(_ticks(), threshold_seconds=60)

    assert len(gaps) == 2
    assert gaps.duration_seconds.tolist() == [3660.0, 120.0]
    assert gaps.exclusion_reason.unique().tolist() == [
        "unknown_coverage_gap"
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


def test_tradeable_state_age_pauses_inside_coverage_gap() -> None:
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


def test_left_truncation_is_flagged_and_excluded_from_primary_inference() -> None:
    interval = _intervals()
    interval.loc[0, "start_time"] = pd.Timestamp("2026-07-23 11:58:00")
    interval.loc[0, "end_time"] = pd.Timestamp("2026-07-23 12:01:00")
    interval.loc[0, "duration_seconds"] = 180.0
    fragments = partition_risk_time(
        interval,
        coverage_start=pd.Timestamp("2026-07-23 12:00:00"),
        coverage_end=pd.Timestamp("2026-07-23 12:02:00"),
        breaks=pd.DataFrame(columns=["break_start", "break_end"]),
    )

    assert fragments.segment_start.min() == pd.Timestamp("2026-07-23 12:00:00")
    assert fragments.is_left_truncated.all()
    assert not fragments.is_primary_inference_eligible.any()


def test_synthetic_tail_is_right_censored_and_not_a_competing_event() -> None:
    coverage_end = pd.Timestamp("2026-07-24 01:05:00")
    canonical = append_right_censored_tail(
        _intervals(),
        _events(),
        coverage_end=coverage_end,
    )
    tail = canonical.loc[canonical["terminal_kind"] == "right_censored"].iloc[0]

    assert tail["state"] == "HEDGED_1X1"
    assert tail["duration_seconds"] == 180.0
    assert pd.isna(tail["following_event_type"])
    repeated = append_right_censored_tail(
        canonical,
        _events(),
        coverage_end=coverage_end,
    )
    assert len(repeated) == len(canonical)
    assert repeated.terminal_kind.tolist().count("right_censored") == 1

    fragments = partition_risk_time(
        canonical,
        coverage_start=pd.Timestamp("2026-07-23 23:58:00"),
        coverage_end=coverage_end,
        breaks=pd.DataFrame(columns=["break_start", "break_end"]),
    )
    summary = summarize_fragments(
        canonical,
        fragments,
        coverage_start=pd.Timestamp("2026-07-23 23:58:00"),
        coverage_end=coverage_end,
    )
    hedged = next(row for row in summary if row["state"] == "HEDGED_1X1")

    assert fragments.loc[
        fragments["interval_id"].astype(str).str.startswith("m5-tail"),
        "is_right_censored",
    ].all()
    assert hedged["terminal_event_count"] == 0
    assert hedged["target_event_count"] == 0
    assert hedged["competing_event_count"] == 0
    assert hedged["primary_risk_seconds"] == 180.0


def test_multi_day_unknown_gap_is_split_and_fully_pauses_state_age() -> None:
    start = pd.Timestamp("2026-07-24 23:59:00")
    gap_end = pd.Timestamp("2026-07-27 01:00:00")
    end = pd.Timestamp("2026-07-27 01:01:00")
    interval = pd.DataFrame(
        {
            "interval_id": [99],
            "start_time": [start],
            "end_time": [end],
            "duration_seconds": [(end - start).total_seconds()],
            "state": ["HEDGED_1X1"],
            "preceding_event_type": ["REHEDGE_SELL"],
            "following_event_type": ["UNLOCK_TO_BUY"],
        }
    )
    gap = detect_coverage_gaps(
        pd.DataFrame({"timestamp": [start, gap_end, end]}),
        threshold_seconds=60,
    )

    assert len(gap) == 1
    assert gap.exclusion_reason.tolist() == ["unknown_coverage_gap"]
    fragments = partition_risk_time(
        interval,
        coverage_start=start,
        coverage_end=end,
        breaks=gap,
    )

    assert fragments.day.unique().tolist() == [
        "2026-07-24",
        "2026-07-25",
        "2026-07-26",
        "2026-07-27",
    ]
    assert (
        fragments.loc[~fragments.is_tradeable, "duration_seconds"].sum()
        == (gap_end - start).total_seconds()
    )
    assert tradeable_elapsed_seconds(start, end, gap) == 60.0


def test_ineligible_states_do_not_dilute_primary_density() -> None:
    intervals = pd.DataFrame(
        {
            "interval_id": [1, 2],
            "start_time": pd.to_datetime(
                ["2026-07-23 12:00:00", "2026-07-23 12:10:00"]
            ),
            "end_time": pd.to_datetime(
                ["2026-07-23 12:10:00", "2026-07-23 13:00:00"]
            ),
            "duration_seconds": [600.0, 3000.0],
            "state": ["ONE_BUY", "MULTI_POSITION"],
            "preceding_event_type": ["UNLOCK_TO_BUY", "REHEDGE_SELL"],
            "following_event_type": ["REHEDGE_SELL", "OPEN_ADDITIONAL_BUY"],
        }
    )
    ticks = pd.DataFrame(
        {
            "timestamp": pd.date_range(
                "2026-07-23 12:00:00",
                "2026-07-23 13:00:00",
                freq="30s",
            )
        }
    )
    events = pd.DataFrame(
        {
            "event_id": [1, 2],
            "event_sequence": [1, 2],
            "event_time": pd.to_datetime(
                ["2026-07-23 12:10:00", "2026-07-23 13:00:00"]
            ),
            "state_after": ["MULTI_POSITION", "MULTI_POSITION"],
            "behavior_type": ["REHEDGE_SELL", "OPEN_ADDITIONAL_BUY"],
        }
    )

    report = build_risk_time_audit(intervals, ticks, events)
    day = report["canonical_common_hours_by_day"][0]

    assert day["source_interval_count"] == 1
    assert day["primary_risk_seconds"] == 600.0
    assert day["target_event_count"] == 1
    assert day["target_event_density_percent"] == 0.166667


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

    first = build_risk_time_audit(_intervals(), ticks, _events())
    second = build_risk_time_audit(_intervals(), ticks, _events())

    assert first["deterministic_audit_sha256"] == second[
        "deterministic_audit_sha256"
    ]
    assert first["boundary_cases"]["cross_midnight_interval_ids"] == ["13321"]
    assert first["boundary_cases"]["coverage_gap_intersection_interval_ids"] == [
        "13321"
    ]
    assert (
        first["inference_protocol"]["raw_calibration_role"]
        == "descriptive_only"
    )
    assert first["status"] == "pilot_accounting_only"
