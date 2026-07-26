from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import pandas as pd

from xau_trigger.hazard_bins import (
    build_wall_clock_risk_bins,
    canonicalize_cohort_support,
    load_tick_cohort,
)


def _events(event_time: str = "2026-07-23 12:00:05") -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_id": [1],
            "event_sequence": [1],
            "event_time": [pd.Timestamp(event_time)],
            "state_after": ["ONE_BUY"],
            "behavior_type": ["UNLOCK_TO_BUY"],
        }
    )


def _interval(
    *,
    start: str = "2026-07-23 12:00:00",
    end: str = "2026-07-23 12:00:05",
    state: str = "HEDGED_1X1",
    following: str = "UNLOCK_TO_BUY",
    interval_id: int = 1,
) -> pd.DataFrame:
    start_time = pd.Timestamp(start)
    end_time = pd.Timestamp(end)
    return pd.DataFrame(
        {
            "interval_id": [interval_id],
            "start_time": [start_time],
            "end_time": [end_time],
            "duration_seconds": [(end_time - start_time).total_seconds()],
            "state": [state],
            "preceding_event_type": ["REHEDGE_SELL"],
            "following_event_type": [following],
        }
    )


def _support(
    interval: pd.DataFrame,
    *,
    coverage_start: str,
    coverage_end: str,
    breaks: pd.DataFrame | None = None,
) -> dict:
    ticks = pd.DataFrame(
        {
            "timestamp": [pd.Timestamp(coverage_start), pd.Timestamp(coverage_end)],
        }
    )
    if breaks is None:
        breaks = pd.DataFrame(columns=["break_start", "break_end"])
    return canonicalize_cohort_support(
        interval,
        _events(coverage_end),
        ticks,
        cohort_id="internal_2026_07_23_24",
        breaks=breaks,
    )


def test_wall_clock_bins_pause_state_age_and_never_cross_gap() -> None:
    gap = pd.DataFrame(
        {
            "break_start": [pd.Timestamp("2026-07-23 12:00:02")],
            "break_end": [pd.Timestamp("2026-07-23 12:00:03.500")],
        }
    )
    support = _support(
        _interval(),
        coverage_start="2026-07-23 12:00:00",
        coverage_end="2026-07-23 12:00:05",
        breaks=gap,
    )

    bins, _, accounting = build_wall_clock_risk_bins(
        support,
        bin_width_seconds=1.0,
    )

    assert bins["bin_start"].tolist() == pd.to_datetime(
        [
            "2026-07-23 12:00:00",
            "2026-07-23 12:00:01",
            "2026-07-23 12:00:04",
        ]
    ).tolist()
    assert bins["state_age_seconds"].tolist() == [0.0, 1.0, 2.5]
    assert bins.iloc[-1]["target_label"] == 1
    assert accounting["eligible_fragment_seconds"] == 3.5
    assert accounting["representable_bin_seconds"] == 3.0
    assert accounting["dropped_partial_seconds"] == 0.5
    assert accounting["reconciliation_delta_seconds"] == 0.0


def test_half_second_bins_use_complete_absolute_grid_cells() -> None:
    support = _support(
        _interval(start="2026-07-23 12:00:00.250", end="2026-07-23 12:00:02"),
        coverage_start="2026-07-23 12:00:00.250",
        coverage_end="2026-07-23 12:00:02",
    )

    bins, _, accounting = build_wall_clock_risk_bins(
        support,
        bin_width_seconds=0.5,
    )

    assert bins["bin_start"].tolist() == pd.to_datetime(
        [
            "2026-07-23 12:00:00.500",
            "2026-07-23 12:00:01.000",
            "2026-07-23 12:00:01.500",
        ]
    ).tolist()
    assert accounting["representable_bin_seconds"] == 1.5
    assert accounting["dropped_partial_seconds"] == 0.25


def test_left_truncated_interval_is_audit_only() -> None:
    intervals = pd.concat(
        [
            _interval(
                start="2026-07-23 11:59:58",
                end="2026-07-23 12:00:05",
                interval_id=1,
            ),
            _interval(
                start="2026-07-23 12:00:05",
                end="2026-07-23 12:00:10",
                interval_id=2,
            ),
        ],
        ignore_index=True,
    )
    support = _support(
        intervals,
        coverage_start="2026-07-23 12:00:00",
        coverage_end="2026-07-23 12:00:10",
    )

    bins, interval_audit, _ = build_wall_clock_risk_bins(
        support,
        bin_width_seconds=1.0,
    )

    assert set(bins["interval_id"]) == {"2"}
    left = interval_audit[interval_audit["interval_id"] == "1"].iloc[0]
    assert left["is_left_truncated"]
    assert left["representable_bin_count"] == 0
    assert left["model_exclusion_reason"] == "left_truncated"


def test_competing_terminal_bin_is_retained_as_zero_then_censored() -> None:
    support = _support(
        _interval(following="OPEN_ADDITIONAL_BUY"),
        coverage_start="2026-07-23 12:00:00",
        coverage_end="2026-07-23 12:00:05",
    )

    bins, interval_audit, accounting = build_wall_clock_risk_bins(
        support,
        bin_width_seconds=1.0,
    )

    assert len(bins) == 5
    assert bins["target_label"].sum() == 0
    assert bins.iloc[-1]["is_competing_terminal_bin"]
    assert bins.iloc[-1]["competing_event_type"] == "OPEN_ADDITIONAL_BUY"
    assert bins.iloc[-1]["censor_reason"] == "competing_endpoint"
    assert interval_audit.iloc[0]["representable_competing_count"] == 1
    assert accounting["competing_terminal_bin_count"] == 1


def test_cross_development_holdout_interval_is_excluded_from_both() -> None:
    interval = _interval(
        start="2026-07-23 23:59:58",
        end="2026-07-24 00:00:02",
    )
    support = _support(
        interval,
        coverage_start="2026-07-23 23:59:58",
        coverage_end="2026-07-24 00:00:02",
    )

    bins, interval_audit, accounting = build_wall_clock_risk_bins(
        support,
        bin_width_seconds=1.0,
    )

    assert set(bins["split"]) == {"development", "holdout"}
    assert bins["is_cross_split_interval"].all()
    assert not bins["is_primary_model_eligible"].any()
    assert interval_audit.iloc[0]["model_exclusion_reason"] == (
        "cross_development_holdout"
    )
    assert accounting["cross_split_interval_ids"] == ["1"]


def test_canonical_build_script_locks_original_tick_export() -> None:
    text = (Path(__file__).parents[1] / "scripts" / "build_dataset.py").read_text(
        encoding="utf-8"
    )

    assert 'CANONICAL_TICK_EXPORT = "XAUUSD_202607231200_202607242356.csv"' in text
    assert "ticks[0]" not in text


def test_supplemental_tick_loader_uses_pinned_checksum(tmp_path: Path) -> None:
    header = "<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\t<FLAGS>\n"
    wanted = tmp_path / "wanted.csv"
    extra = tmp_path / "extra.csv"
    wanted.write_text(
        header + "2026.07.20\t12:00:00.000\t1\t2\t1\t1\t4\n",
        encoding="utf-8",
    )
    extra.write_text(
        header + "2026.07.20\t12:00:01.000\t3\t4\t3\t1\t4\n",
        encoding="utf-8",
    )
    digest = sha256(wanted.read_bytes()).hexdigest()

    ticks = load_tick_cohort(
        [extra, wanted],
        ["2026-07-20"],
        expected_sha256=[digest],
    )

    assert len(ticks) == 1
    assert ticks.iloc[0]["bid"] == 1


def test_supplemental_tick_loader_fails_when_pinned_checksum_is_missing(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ticks.csv"
    path.write_text(
        "<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\t<FLAGS>\n"
        "2026.07.20\t12:00:00.000\t1\t2\t1\t1\t4\n",
        encoding="utf-8",
    )

    try:
        load_tick_cohort(
            [path],
            ["2026-07-20"],
            expected_sha256=["0" * 64],
        )
    except ValueError as error:
        assert "exactly one file" in str(error)
    else:
        raise AssertionError("Missing pinned checksum should fail cleanly")
