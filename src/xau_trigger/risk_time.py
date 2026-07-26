"""Canonical tradeable-risk-time accounting for M5.

This module deliberately stops before risk-bin construction or modelling.  It
defines the time support that later M5 datasets must use.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Iterable

import pandas as pd


COVERAGE_GAP_THRESHOLD_SECONDS = 60.0
COMMON_SERVER_HOUR_START = 12
COMMON_SERVER_HOUR_END = 24
ELIGIBLE_STATES = ("HEDGED_1X1", "ONE_BUY", "ONE_SELL")
TARGET_ENDPOINTS = {
    "HEDGED_1X1": {"UNLOCK_TO_BUY", "UNLOCK_TO_SELL"},
    "ONE_BUY": {"REHEDGE_SELL"},
    "ONE_SELL": {"REHEDGE_BUY"},
}

FRAGMENT_COLUMNS = [
    "segment_id",
    "interval_id",
    "segment_start",
    "segment_end",
    "day",
    "duration_seconds",
    "state",
    "preceding_event_type",
    "following_event_type",
    "is_tradeable",
    "exclusion_reason",
    "is_left_truncated",
    "is_right_censored",
    "is_cross_midnight",
    "is_primary_inference_eligible",
]


def _require_columns(frame: pd.DataFrame, required: Iterable[str]) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _rounded(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def detect_coverage_gaps(
    ticks: pd.DataFrame,
    *,
    threshold_seconds: float = COVERAGE_GAP_THRESHOLD_SECONDS,
) -> pd.DataFrame:
    """Return consecutive-tick gaps strictly longer than the locked threshold."""
    if threshold_seconds <= 0:
        raise ValueError("threshold_seconds must be positive")
    _require_columns(ticks, ["timestamp"])
    timestamps = pd.to_datetime(ticks["timestamp"], errors="raise")
    if timestamps.isna().any():
        raise ValueError("Tick timestamps must not be null")
    if not timestamps.is_monotonic_increasing:
        raise ValueError("Tick timestamps must be monotonically non-decreasing")

    previous = timestamps.shift(1)
    duration = (timestamps - previous).dt.total_seconds()
    mask = duration > threshold_seconds
    gaps = pd.DataFrame(
        {
            "break_start": previous[mask].to_numpy(),
            "break_end": timestamps[mask].to_numpy(),
            "duration_seconds": duration[mask].to_numpy(),
        }
    ).reset_index(drop=True)
    gaps.insert(0, "break_id", [f"gap-{index:03d}" for index in range(1, len(gaps) + 1)])
    gaps["gap_classification"] = "unknown_coverage_gap"
    gaps["exclusion_reason"] = "unknown_coverage_gap"
    return gaps


def _break_records(
    breaks: pd.DataFrame,
) -> list[tuple[pd.Timestamp, pd.Timestamp, str]]:
    if breaks.empty:
        return []
    _require_columns(breaks, ["break_start", "break_end"])
    records = []
    for row in breaks.itertuples(index=False):
        start = pd.Timestamp(row.break_start)
        end = pd.Timestamp(row.break_end)
        if end <= start:
            raise ValueError("Coverage-gap end must be after its start")
        reason = getattr(row, "exclusion_reason", "unknown_coverage_gap")
        records.append((start, end, str(reason)))
    return sorted(records, key=lambda item: (item[0], item[1], item[2]))


def append_right_censored_tail(
    intervals: pd.DataFrame,
    lifecycle_events: pd.DataFrame,
    *,
    coverage_end: pd.Timestamp,
) -> pd.DataFrame:
    """Append the state after the last event through the merged coverage end.

    M2 intervals are event-to-event and therefore omit the state after the
    final event.  M5 adds one synthetic, explicitly censored interval without
    mutating the canonical M2 output.
    """
    _require_columns(
        intervals,
        [
            "interval_id",
            "start_time",
            "end_time",
            "state",
            "preceding_event_type",
            "following_event_type",
        ],
    )
    _require_columns(
        lifecycle_events,
        ["event_time", "state_after", "behavior_type"],
    )
    end_bound = pd.Timestamp(coverage_end)
    frame = intervals.copy()
    frame["start_time"] = pd.to_datetime(frame["start_time"], errors="raise")
    frame["end_time"] = pd.to_datetime(frame["end_time"], errors="raise")
    if "terminal_kind" not in frame:
        frame["terminal_kind"] = "event"
    else:
        frame["terminal_kind"] = frame["terminal_kind"].fillna("event")
    if "is_synthetic_tail" not in frame:
        frame["is_synthetic_tail"] = False
    else:
        frame["is_synthetic_tail"] = frame["is_synthetic_tail"].fillna(False)

    covering = frame[
        (frame["start_time"] <= end_bound) & (frame["end_time"] >= end_bound)
    ]
    if not covering.empty:
        return frame

    events = lifecycle_events.copy()
    events["event_time"] = pd.to_datetime(events["event_time"], errors="raise")
    events = events[events["event_time"] <= end_bound]
    if events.empty:
        return frame
    sort_columns = ["event_time"] + (
        ["event_sequence"] if "event_sequence" in events.columns else []
    )
    last_event = events.sort_values(sort_columns, kind="stable").iloc[-1]
    tail_start = pd.Timestamp(last_event["event_time"])
    if tail_start >= end_bound:
        return frame
    if pd.isna(last_event["state_after"]):
        raise ValueError("Cannot synthesize censored tail without state_after")

    event_key = (
        last_event["event_id"]
        if "event_id" in last_event.index
        else last_event.get("event_sequence", "last")
    )
    tail = {column: pd.NA for column in frame.columns}
    tail.update(
        {
            "interval_id": f"m5-tail-{event_key}",
            "start_time": tail_start,
            "end_time": end_bound,
            "duration_seconds": (end_bound - tail_start).total_seconds(),
            "state": last_event["state_after"],
            "preceding_event_type": last_event["behavior_type"],
            "following_event_type": pd.NA,
            "terminal_kind": "right_censored",
            "is_synthetic_tail": True,
        }
    )
    return pd.concat([frame, pd.DataFrame([tail])], ignore_index=True)


def _midnights_between(start: pd.Timestamp, end: pd.Timestamp) -> list[pd.Timestamp]:
    boundary = start.normalize() + pd.Timedelta(days=1)
    output = []
    while boundary < end:
        output.append(boundary)
        boundary += pd.Timedelta(days=1)
    return output


def partition_risk_time(
    intervals: pd.DataFrame,
    *,
    coverage_start: pd.Timestamp,
    coverage_end: pd.Timestamp,
    breaks: pd.DataFrame,
) -> pd.DataFrame:
    """Clip intervals, split them at midnight/gaps, and label exclusions.

    Zero-duration source intervals are preserved as accounting-only fragments.
    Positive-duration fragments inside a detected coverage gap are excluded
    from risk time; all other fragments remain tradeable.
    """
    required = [
        "interval_id",
        "start_time",
        "end_time",
        "state",
        "preceding_event_type",
        "following_event_type",
    ]
    _require_columns(intervals, required)
    start_bound = pd.Timestamp(coverage_start)
    end_bound = pd.Timestamp(coverage_end)
    if end_bound <= start_bound:
        raise ValueError("coverage_end must be after coverage_start")

    frame = intervals.copy()
    frame["start_time"] = pd.to_datetime(frame["start_time"], errors="raise")
    frame["end_time"] = pd.to_datetime(frame["end_time"], errors="raise")
    if (frame["end_time"] < frame["start_time"]).any():
        raise ValueError("State intervals must not have negative duration")

    gap_records = _break_records(breaks)
    fragments: list[dict] = []
    for row in frame.itertuples(index=False):
        source_start = pd.Timestamp(row.start_time)
        source_end = pd.Timestamp(row.end_time)
        if source_end < start_bound or source_start > end_bound:
            continue

        clipped_start = max(source_start, start_bound)
        clipped_end = min(source_end, end_bound)
        left_truncated = source_start < start_bound
        terminal_kind = getattr(row, "terminal_kind", "event")
        right_censored = (
            source_end > end_bound or terminal_kind == "right_censored"
        )
        cross_midnight = source_start.normalize() != source_end.normalize()

        base = {
            "interval_id": row.interval_id,
            "state": row.state,
            "preceding_event_type": row.preceding_event_type,
            "following_event_type": row.following_event_type,
            "is_left_truncated": left_truncated,
            "is_right_censored": right_censored,
            "is_cross_midnight": cross_midnight,
        }
        if clipped_end == clipped_start:
            fragments.append(
                {
                    **base,
                    "segment_id": f"{row.interval_id}:000",
                    "segment_start": clipped_start,
                    "segment_end": clipped_end,
                    "day": clipped_start.strftime("%Y-%m-%d"),
                    "duration_seconds": 0.0,
                    "is_tradeable": False,
                    "exclusion_reason": "zero_duration",
                    "is_primary_inference_eligible": False,
                }
            )
            continue

        boundaries = {clipped_start, clipped_end}
        boundaries.update(_midnights_between(clipped_start, clipped_end))
        for gap_start, gap_end, _ in gap_records:
            if gap_end <= clipped_start or gap_start >= clipped_end:
                continue
            boundaries.add(max(gap_start, clipped_start))
            boundaries.add(min(gap_end, clipped_end))

        ordered = sorted(boundaries)
        for fragment_index, (segment_start, segment_end) in enumerate(
            zip(ordered, ordered[1:]),
            start=1,
        ):
            gap_reason = next(
                (
                    reason
                    for gap_start, gap_end, reason in gap_records
                    if segment_start < gap_end and segment_end > gap_start
                ),
                None,
            )
            is_tradeable = gap_reason is None
            fragments.append(
                {
                    **base,
                    "segment_id": f"{row.interval_id}:{fragment_index:03d}",
                    "segment_start": segment_start,
                    "segment_end": segment_end,
                    "day": segment_start.strftime("%Y-%m-%d"),
                    "duration_seconds": (segment_end - segment_start).total_seconds(),
                    "is_tradeable": is_tradeable,
                    "exclusion_reason": gap_reason,
                    "is_primary_inference_eligible": (
                        is_tradeable
                        and not left_truncated
                        and row.state in ELIGIBLE_STATES
                    ),
                }
            )

    if not fragments:
        return pd.DataFrame(columns=FRAGMENT_COLUMNS)
    return (
        pd.DataFrame(fragments)[FRAGMENT_COLUMNS]
        .sort_values(["segment_start", "segment_id"], kind="stable")
        .reset_index(drop=True)
    )


def clip_fragments_to_daily_hours(
    fragments: pd.DataFrame,
    *,
    start_hour: int,
    end_hour: int,
) -> pd.DataFrame:
    """Restrict midnight-split fragments to a fixed daily server-hour window."""
    if not 0 <= start_hour < end_hour <= 24:
        raise ValueError("Expected 0 <= start_hour < end_hour <= 24")
    if fragments.empty:
        return fragments.copy()

    output: list[dict] = []
    for row in fragments.itertuples(index=False):
        day_start = pd.Timestamp(row.segment_start).normalize()
        window_start = day_start + pd.Timedelta(hours=start_hour)
        window_end = day_start + pd.Timedelta(hours=end_hour)
        segment_start = max(pd.Timestamp(row.segment_start), window_start)
        segment_end = min(pd.Timestamp(row.segment_end), window_end)
        is_zero = row.duration_seconds == 0 and window_start <= segment_start <= window_end
        if segment_end < segment_start or (segment_end == segment_start and not is_zero):
            continue
        item = row._asdict()
        item["segment_start"] = segment_start
        item["segment_end"] = segment_end
        item["day"] = segment_start.strftime("%Y-%m-%d")
        item["duration_seconds"] = max(
            0.0,
            (segment_end - segment_start).total_seconds(),
        )
        output.append(item)
    if not output:
        return pd.DataFrame(columns=fragments.columns)
    return pd.DataFrame(output)[fragments.columns].reset_index(drop=True)


def tradeable_elapsed_seconds(
    start: pd.Timestamp,
    end: pd.Timestamp,
    breaks: pd.DataFrame,
) -> float:
    """Return elapsed seconds after pausing the clock inside coverage gaps."""
    start_time = pd.Timestamp(start)
    end_time = pd.Timestamp(end)
    if end_time < start_time:
        raise ValueError("end must not precede start")
    elapsed = (end_time - start_time).total_seconds()
    excluded = 0.0
    for gap_start, gap_end, _ in _break_records(breaks):
        overlap_start = max(start_time, gap_start)
        overlap_end = min(end_time, gap_end)
        if overlap_end > overlap_start:
            excluded += (overlap_end - overlap_start).total_seconds()
    return elapsed - excluded


def _event_mask(
    intervals: pd.DataFrame,
    *,
    day: str,
    start_hour: int,
    end_hour: int,
    coverage_start: pd.Timestamp,
    coverage_end: pd.Timestamp,
) -> pd.Series:
    day_start = pd.Timestamp(day)
    window_start = max(day_start + pd.Timedelta(hours=start_hour), coverage_start)
    window_end = min(day_start + pd.Timedelta(hours=end_hour), coverage_end)
    time_mask = (intervals["end_time"] > window_start) & (
        intervals["end_time"] <= window_end
    )
    if "terminal_kind" in intervals:
        return time_mask & intervals["terminal_kind"].eq("event")
    return time_mask & intervals["following_event_type"].notna()


def summarize_fragments(
    intervals: pd.DataFrame,
    fragments: pd.DataFrame,
    *,
    coverage_start: pd.Timestamp,
    coverage_end: pd.Timestamp,
    start_hour: int = 0,
    end_hour: int = 24,
) -> list[dict]:
    """Build privacy-safe day/state aggregate risk-time accounting."""
    restricted = clip_fragments_to_daily_hours(
        fragments,
        start_hour=start_hour,
        end_hour=end_hour,
    )
    if restricted.empty:
        return []

    source = intervals.copy()
    source["start_time"] = pd.to_datetime(source["start_time"], errors="raise")
    source["end_time"] = pd.to_datetime(source["end_time"], errors="raise")
    records: list[dict] = []
    for (day, state), group in restricted.groupby(["day", "state"], sort=True):
        all_events = source[
            (source["state"] == state)
            & _event_mask(
                source,
                day=day,
                start_hour=start_hour,
                end_hour=end_hour,
                coverage_start=pd.Timestamp(coverage_start),
                coverage_end=pd.Timestamp(coverage_end),
            )
        ]
        primary_interval_ids = set(
            group.loc[
                group["is_primary_inference_eligible"]
                & (group["duration_seconds"] > 0),
                "interval_id",
            ].tolist()
        )
        events = all_events[
            all_events["interval_id"].isin(primary_interval_ids)
        ]
        target_endpoints = TARGET_ENDPOINTS.get(state, set())
        target_count = int(events["following_event_type"].isin(target_endpoints).sum())
        terminal_count = int(len(all_events))
        eligible_terminal_count = int(len(events))
        tradeable_seconds = _rounded(
            group.loc[group["is_tradeable"], "duration_seconds"].sum()
        )
        primary_risk_seconds = _rounded(
            group.loc[
                group["is_primary_inference_eligible"],
                "duration_seconds",
            ].sum()
        )
        excluded_seconds = _rounded(
            group.loc[~group["is_tradeable"], "duration_seconds"].sum()
        )
        records.append(
            {
                "day": day,
                "state": state,
                "source_interval_count": int(group["interval_id"].nunique()),
                "tradeable_segment_count": int(group["is_tradeable"].sum()),
                "primary_risk_segment_count": int(
                    group["is_primary_inference_eligible"].sum()
                ),
                "zero_duration_interval_count": int(
                    group.loc[
                        group["exclusion_reason"] == "zero_duration",
                        "interval_id",
                    ].nunique()
                ),
                "terminal_event_count": terminal_count,
                "eligible_terminal_event_count": eligible_terminal_count,
                "nonrisk_terminal_event_count": (
                    terminal_count - eligible_terminal_count
                ),
                "target_event_count": target_count,
                "competing_event_count": eligible_terminal_count - target_count,
                "raw_overlap_seconds": _rounded(group["duration_seconds"].sum()),
                "excluded_break_seconds": excluded_seconds,
                "tradeable_risk_seconds": tradeable_seconds,
                "primary_risk_seconds": primary_risk_seconds,
                "target_events_per_1000_primary_risk_seconds": (
                    _rounded(1000.0 * target_count / primary_risk_seconds)
                    if primary_risk_seconds
                    else None
                ),
            }
        )
    return records


def legacy_start_date_summary(
    intervals: pd.DataFrame,
    *,
    coverage_start: pd.Timestamp,
    coverage_end: pd.Timestamp,
) -> list[dict]:
    """Reproduce the pre-M5 start-date accounting for explicit comparison."""
    frame = intervals.copy()
    frame["start_time"] = pd.to_datetime(frame["start_time"], errors="raise")
    frame["end_time"] = pd.to_datetime(frame["end_time"], errors="raise")
    overlap = frame[
        (frame["end_time"] >= pd.Timestamp(coverage_start))
        & (frame["start_time"] <= pd.Timestamp(coverage_end))
    ].copy()
    overlap["day"] = overlap["start_time"].dt.strftime("%Y-%m-%d")
    records = []
    for day, group in overlap.groupby("day", sort=True):
        risk_seconds = _rounded(group["duration_seconds"].sum())
        interval_count = int(len(group))
        records.append(
            {
                "day": day,
                "interval_count": interval_count,
                "unclipped_start_date_assigned_seconds": risk_seconds,
                "event_density_percent": (
                    _rounded(100.0 * interval_count / risk_seconds)
                    if risk_seconds
                    else None
                ),
            }
        )
    return records


def _aggregate_day_state(records: list[dict]) -> list[dict]:
    if not records:
        return []
    frame = pd.DataFrame(records)
    frame = frame[frame["state"].isin(ELIGIBLE_STATES)]
    output = []
    for day, group in frame.groupby("day", sort=True):
        tradeable_seconds = _rounded(group["tradeable_risk_seconds"].sum())
        primary_risk_seconds = _rounded(group["primary_risk_seconds"].sum())
        target_count = int(group["target_event_count"].sum())
        output.append(
            {
                "day": day,
                "source_interval_count": int(group["source_interval_count"].sum()),
                "terminal_event_count": int(group["terminal_event_count"].sum()),
                "eligible_terminal_event_count": int(
                    group["eligible_terminal_event_count"].sum()
                ),
                "nonrisk_terminal_event_count": int(
                    group["nonrisk_terminal_event_count"].sum()
                ),
                "target_event_count": target_count,
                "competing_event_count": int(group["competing_event_count"].sum()),
                "raw_overlap_seconds": _rounded(group["raw_overlap_seconds"].sum()),
                "excluded_break_seconds": _rounded(
                    group["excluded_break_seconds"].sum()
                ),
                "tradeable_risk_seconds": tradeable_seconds,
                "primary_risk_seconds": primary_risk_seconds,
                "target_event_density_percent": (
                    _rounded(100.0 * target_count / primary_risk_seconds)
                    if primary_risk_seconds
                    else None
                ),
            }
        )
    return output


def build_risk_time_audit(
    intervals: pd.DataFrame,
    ticks: pd.DataFrame,
    lifecycle_events: pd.DataFrame,
    *,
    gap_threshold_seconds: float = COVERAGE_GAP_THRESHOLD_SECONDS,
) -> dict:
    """Return the deterministic M5-000 risk-time audit payload."""
    _require_columns(ticks, ["timestamp"])
    if ticks.empty:
        raise ValueError("Cannot audit risk time without ticks")
    timestamps = pd.to_datetime(ticks["timestamp"], errors="raise")
    coverage_start = pd.Timestamp(timestamps.min())
    coverage_end = pd.Timestamp(timestamps.max())
    canonical_intervals = append_right_censored_tail(
        intervals,
        lifecycle_events,
        coverage_end=coverage_end,
    )
    breaks = detect_coverage_gaps(
        ticks,
        threshold_seconds=gap_threshold_seconds,
    )
    fragments = partition_risk_time(
        canonical_intervals,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        breaks=breaks,
    )

    full_by_state = summarize_fragments(
        canonical_intervals,
        fragments,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
    )
    common_by_state = summarize_fragments(
        canonical_intervals,
        fragments,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        start_hour=COMMON_SERVER_HOUR_START,
        end_hour=COMMON_SERVER_HOUR_END,
    )
    early_by_state = summarize_fragments(
        canonical_intervals,
        fragments,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
        start_hour=1,
        end_hour=COMMON_SERVER_HOUR_START,
    )
    full_by_day = _aggregate_day_state(full_by_state)
    common_by_day = _aggregate_day_state(common_by_state)
    early_by_day = _aggregate_day_state(early_by_state)

    overlap_mask = (
        pd.to_datetime(canonical_intervals["end_time"]) >= coverage_start
    ) & (
        pd.to_datetime(canonical_intervals["start_time"]) <= coverage_end
    )
    overlap = canonical_intervals.loc[overlap_mask].copy()
    overlap["start_time"] = pd.to_datetime(overlap["start_time"])
    overlap["end_time"] = pd.to_datetime(overlap["end_time"])
    original_overlap_mask = (
        pd.to_datetime(intervals["end_time"]) >= coverage_start
    ) & (pd.to_datetime(intervals["start_time"]) <= coverage_end)
    original_overlap = intervals.loc[original_overlap_mask].copy()
    original_overlap["start_time"] = pd.to_datetime(original_overlap["start_time"])
    original_overlap["end_time"] = pd.to_datetime(original_overlap["end_time"])

    zero_duration = original_overlap[
        original_overlap["end_time"] == original_overlap["start_time"]
    ].copy()
    zero_target_mask = pd.Series(
        [
            endpoint in TARGET_ENDPOINTS.get(state, set())
            for state, endpoint in zip(
                zero_duration["state"],
                zero_duration["following_event_type"],
            )
        ],
        index=zero_duration.index,
        dtype=bool,
    )
    zero_target = zero_duration.loc[zero_target_mask]
    common_zero_target = zero_target[
        zero_target["end_time"].dt.hour >= COMMON_SERVER_HOUR_START
    ]

    right_censored_mask = overlap["terminal_kind"].eq("right_censored") | (
        overlap["end_time"] > coverage_end
    )
    boundary_cases = {
        "left_truncated_interval_ids": sorted(
            overlap.loc[overlap["start_time"] < coverage_start, "interval_id"]
            .astype(str)
            .tolist()
        ),
        "right_censored_interval_ids": sorted(
            overlap.loc[right_censored_mask, "interval_id"]
            .astype(str)
            .tolist()
        ),
        "right_censored_tail_seconds": _rounded(
            overlap.loc[
                overlap["terminal_kind"].eq("right_censored"),
                "duration_seconds",
            ].sum()
        ),
        "cross_midnight_interval_ids": sorted(
            overlap.loc[
                overlap["start_time"].dt.normalize()
                != overlap["end_time"].dt.normalize(),
                "interval_id",
            ]
            .astype(str)
            .tolist()
        ),
        "zero_duration_interval_count": int(
            (overlap["end_time"] == overlap["start_time"]).sum()
        ),
        "coverage_gap_intersection_interval_ids": sorted(
            fragments.loc[
                fragments["exclusion_reason"].notna()
                & (fragments["exclusion_reason"] != "zero_duration"),
                "interval_id",
            ]
            .astype(str)
            .unique()
            .tolist()
        ),
        "left_truncated_excluded_from_primary": True,
    }

    common_lookup = {row["day"]: row for row in common_by_day}
    common_days = sorted(common_lookup)
    development_day = common_days[0]
    holdout_day = common_days[-1]
    development_density = common_lookup[development_day][
        "target_event_density_percent"
    ]
    holdout_density = common_lookup[holdout_day][
        "target_event_density_percent"
    ]
    base_rate_ratio = (
        _rounded(development_density / holdout_density)
        if development_density is not None and holdout_density
        else None
    )
    early_lookup = {row["day"]: row for row in early_by_day}
    holdout_early_density = early_lookup.get(holdout_day, {}).get(
        "target_event_density_percent"
    )
    holdout_session_ratio = (
        _rounded(holdout_density / holdout_early_density)
        if holdout_density is not None and holdout_early_density
        else None
    )

    tick_differences = timestamps.diff().dt.total_seconds().dropna()
    subthreshold = tick_differences[tick_differences <= gap_threshold_seconds]
    tick_counts = (
        pd.DataFrame({"hour": timestamps.dt.hour})
        .groupby("hour", as_index=False)
        .size()
        .sort_values(["size", "hour"], ascending=[False, True], kind="stable")
    )
    payload = {
        "schema_version": 2,
        "milestone": "M5-000",
        "status": "pilot_accounting_only",
        "configuration": {
            "coverage_start": coverage_start.isoformat(),
            "coverage_end": coverage_end.isoformat(),
            "coverage_gap_rule": (
                f"exclude full consecutive-tick gaps > "
                f"{gap_threshold_seconds:g} seconds"
            ),
            "coverage_gap_threshold_seconds": gap_threshold_seconds,
            "common_server_hours": [
                COMMON_SERVER_HOUR_START,
                COMMON_SERVER_HOUR_END,
            ],
            "eligible_states": list(ELIGIBLE_STATES),
            "state_age_clock": "elapsed time minus excluded coverage-gap overlap",
            "left_truncation_scope": "merged_tick_coverage_not_individual_files",
        },
        "coverage": {
            "tick_count": int(len(ticks)),
            "m2_source_interval_count": int(len(original_overlap)),
            "canonical_source_interval_count": int(len(overlap)),
            "synthetic_right_censored_interval_count": int(
                overlap["terminal_kind"].eq("right_censored").sum()
            ),
            "positive_duration_interval_count": int(
                (overlap["end_time"] > overlap["start_time"]).sum()
            ),
            "days": sorted(fragments["day"].unique().tolist()),
        },
        "legacy_start_date_accounting": legacy_start_date_summary(
            intervals,
            coverage_start=coverage_start,
            coverage_end=coverage_end,
        ),
        "canonical_full_coverage_by_day": full_by_day,
        "canonical_common_hours_by_day": common_by_day,
        "canonical_holdout_hours_01_12_by_day": early_by_day,
        "canonical_full_coverage_by_day_and_state": full_by_state,
        "canonical_common_hours_by_day_and_state": common_by_state,
        "cohort_comparability": {
            "development_day": development_day,
            "holdout_day": holdout_day,
            "development_common_hour_density_percent": development_density,
            "holdout_common_hour_density_percent": holdout_density,
            "development_to_holdout_density_ratio": base_rate_ratio,
            "holdout_hours_01_12_density_percent": holdout_early_density,
            "holdout_12_24_to_01_12_density_ratio": holdout_session_ratio,
            "coverage_support_aligned": True,
            "base_rate_aligned": False,
            "development_weekday": pd.Timestamp(development_day).day_name(),
            "holdout_weekday": pd.Timestamp(holdout_day).day_name(),
            "external_validation_weekdays": [
                "Monday",
                "Tuesday",
                "Wednesday",
            ],
            "day_of_week_perfectly_confounded": True,
        },
        "inference_protocol": {
            "primary_occurrence_model": "discrete_time_hazard",
            "co_primary_timing_comparisons": [
                "paired_per_interval_log_likelihood_C_minus_A_common_and_C_minus_B",
                "within_interval_conditional_likelihood_given_one_representable_event",
            ],
            "conditional_event_probability": (
                "exp(eta_event_bin) / sum(exp(eta_bin)) within interval"
            ),
            "raw_calibration_role": "descriptive_only",
            "posthoc_intercept_recalibration": (
                "diagnostic_only_uses_holdout_labels_no_verdict_or_gate"
            ),
            "primary_server_hours": [12, 24],
            "secondary_external_analysis": (
                "full_session_2026_07_27_to_2026_07_29_non_gating"
            ),
        },
        "primary_estimand": {
            "description": (
                "Transition timing among eligible states with at least one "
                "complete causal risk bin on merged tick coverage"
            ),
            "primary_bin_width_seconds": 1.0,
            "zero_duration_target_events_excluded_full_coverage": int(
                len(zero_target)
            ),
            "zero_duration_target_events_excluded_common_hours": int(
                len(common_zero_target)
            ),
            "left_truncated_interval_ids_excluded": boundary_cases[
                "left_truncated_interval_ids"
            ],
            "structural_support_issue": (
                "https://github.com/AnhAnh18/xau-hedge-trigger-lab/issues/3"
            ),
        },
        "coverage_gaps": [
            {
                "break_id": row.break_id,
                "break_start": pd.Timestamp(row.break_start).isoformat(),
                "break_end": pd.Timestamp(row.break_end).isoformat(),
                "duration_seconds": _rounded(row.duration_seconds),
                "gap_classification": row.gap_classification,
                "exclusion_reason": row.exclusion_reason,
                "schedule_note": (
                    "Consistent with a daily halt under D-007, but remains "
                    "unknown until repeated across additional sessions."
                ),
            }
            for row in breaks.itertuples(index=False)
        ],
        "coverage_gap_threshold_diagnostic": {
            "maximum_subthreshold_gap_seconds": (
                _rounded(subthreshold.max()) if not subthreshold.empty else None
            ),
            "gap_count_from_10_to_60_seconds": int(
                (
                    (tick_differences >= 10.0)
                    & (tick_differences <= gap_threshold_seconds)
                ).sum()
            ),
            "scope_note": (
                "Threshold robustness is established only for the current "
                "tick window and is not retuned after external data arrive."
            ),
        },
        "boundary_cases": boundary_cases,
        "timezone_decision": {
            "server_timezone": "UTC+03:00",
            "status": "inferred_high_confidence_for_2026_07_window",
            "globally_confirmed": False,
            "observed_long_gap_server_clock": (
                [
                    pd.Timestamp(breaks.iloc[0]["break_start"]).strftime("%H:%M:%S.%f"),
                    pd.Timestamp(breaks.iloc[0]["break_end"]).strftime("%H:%M:%S.%f"),
                ]
                if len(breaks) == 1
                else None
            ),
            "highest_tick_count_server_hours": [
                int(hour) for hour in tick_counts.head(3)["hour"].tolist()
            ],
            "scope_note": (
                "The inference is propagated to reports from the same account "
                "server in the 2026 summer period; it does not establish a "
                "year-round DST rule."
            ),
        },
        "limitations": [
            "Common hours align coverage support but do not align the development and holdout base rates.",
            "Primary M5 v1 inference is restricted to server hours 12-23 and does not generalize to the Asian session.",
            "Day of week is perfectly confounded with the current development, holdout, and external-validation split.",
            "A pre-registered full-session external analysis is secondary and cannot override the primary 12-23 verdict.",
            "Raw calibration is descriptive; any holdout-label intercept recalibration is post-hoc diagnostic only.",
            "Paired likelihood increments remain base-rate sensitive; a within-interval conditional statistic is co-primary for timing comparison.",
            "Only one partial-plus-one-near-full tick session is available.",
            "This audit defines support only and does not fit or evaluate a model.",
        ],
    }
    hash_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    payload["deterministic_audit_sha256"] = sha256(
        hash_payload.encode("utf-8")
    ).hexdigest()
    return payload
