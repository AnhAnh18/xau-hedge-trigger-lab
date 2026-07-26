from __future__ import annotations

import pandas as pd
from pandas.testing import assert_frame_equal

from xau_trigger.trigger_dataset import (
    TickFeatureEngine,
    build_control_pool,
    effective_event_times,
    engineer_features,
    sample_controls,
    select_positives,
)


def _ticks(periods: int = 9) -> pd.DataFrame:
    timestamp = pd.date_range(
        "2026-07-23 12:00:00",
        periods=periods,
        freq="250ms",
    )
    mid = pd.Series([100.0 + index * 0.1 for index in range(periods)])
    return pd.DataFrame(
        {
            "timestamp": timestamp,
            "bid": mid - 0.05,
            "ask": mid + 0.05,
            "mid": mid,
            "spread": 0.1,
        }
    )


def test_select_positives_keeps_only_locked_primary_cohort() -> None:
    aligned = pd.DataFrame(
        {
            "event_id": [1, 2, 3],
            "behavior_type": ["REHEDGE_SELL", "UNLOCK_TO_BUY", "OTHER"],
            "is_primary_trigger_sample": [True, False, True],
            "matched_timestamp": pd.to_datetime(
                [
                    "2026-07-23 12:00:01",
                    "2026-07-23 12:00:02",
                    "2026-07-23 12:00:03",
                ]
            ),
            "volume": [0.3, 0.3, 0.3],
            "price_error": [0.0, 0.0, 0.0],
        }
    )

    result = select_positives(aligned)

    assert result.matched_event_id.tolist() == [1]
    assert result.required_state.tolist() == ["ONE_BUY"]
    assert "price_error" not in result.columns


def test_control_sampling_is_deterministic_and_without_replacement() -> None:
    positives = pd.DataFrame(
        {
            "matched_event_id": [10, 11],
            "sample_time": pd.to_datetime(
                ["2026-07-23 12:00:20", "2026-07-23 12:00:30"]
            ),
            "behavior_type": ["REHEDGE_SELL", "REHEDGE_SELL"],
            "trigger_family": ["rehedge", "rehedge"],
            "required_state": ["ONE_BUY", "ONE_BUY"],
        }
    )
    pool = pd.DataFrame(
        {
            "interval_id": ["i-1"] * 8,
            "sample_time": pd.date_range(
                "2026-07-23 12:01:00",
                periods=8,
                freq="1s",
            ),
            "required_state": ["ONE_BUY"] * 8,
            "volume": [0.3] * 8,
            "state_age_seconds": range(8),
            "date": ["2026-07-23"] * 8,
            "hour": [12] * 8,
        }
    )

    first = sample_controls(positives, pool, quota=3)
    second = sample_controls(positives, pool, quota=3)

    assert_frame_equal(first, second)
    assert len(first) == 6
    assert not first.duplicated(["interval_id", "sample_time"]).any()


def test_control_pool_excludes_every_true_event_zone() -> None:
    ticks = _ticks(periods=81)
    intervals = pd.DataFrame(
        {
            "interval_id": ["i-1"],
            "state": ["ONE_BUY"],
            "buy_volume": [0.3],
            "sell_volume": [0.0],
            "start_time": [ticks.timestamp.iloc[0]],
            "end_time": [ticks.timestamp.iloc[-1]],
        }
    )
    event_time = pd.Series([pd.Timestamp("2026-07-23 12:00:10")])

    pool = build_control_pool(intervals, ticks, event_time, exclusion_seconds=3)

    distance = (pool.sample_time - event_time.iloc[0]).abs().dt.total_seconds()
    assert len(pool)
    assert (distance > 3).all()


def test_unmatched_event_uses_reported_time_for_exclusion() -> None:
    aligned = pd.DataFrame(
        {
            "matched_timestamp": [pd.NaT, pd.Timestamp("2026-07-23 12:00:02")],
            "reported_time": pd.to_datetime(
                ["2026-07-23 12:00:01", "2026-07-23 12:00:02"]
            ),
        }
    )

    assert effective_event_times(aligned).tolist() == [
        pd.Timestamp("2026-07-23 12:00:01"),
        pd.Timestamp("2026-07-23 12:00:02"),
    ]


def test_tick_features_are_past_only_and_have_per_window_validity() -> None:
    ticks = _ticks()
    target = pd.Timestamp("2026-07-23 12:00:01")
    baseline = TickFeatureEngine(ticks).features_at(target, 1000)
    future = pd.concat(
        [
            ticks,
            pd.DataFrame(
                {
                    "timestamp": [target + pd.Timedelta(milliseconds=1)],
                    "bid": [999.9],
                    "ask": [1000.1],
                    "mid": [1000.0],
                    "spread": [0.2],
                }
            ),
        ],
        ignore_index=True,
    )

    assert baseline == TickFeatureEngine(future).features_at(target, 1000)
    assert baseline["w1000ms_valid"]
    assert not TickFeatureEngine(ticks).features_at(target, 60000)["w60000ms_valid"]
    assert "w1000ms_bid_return" not in baseline
    assert "w1000ms_ask_return" not in baseline


def test_training_features_drop_alignment_and_future_only_columns() -> None:
    ticks = _ticks()
    samples = pd.DataFrame(
        {
            "sample_id": ["p-1"],
            "sample_type": ["positive"],
            "matched_event_id": [1],
            "sample_time": [pd.Timestamp("2026-07-23 12:00:01")],
            "behavior_type": ["REHEDGE_SELL"],
            "trigger_family": ["rehedge"],
            "required_state": ["ONE_BUY"],
            "volume": [0.3],
            "state_age_seconds": [10.0],
            "date_split": ["development"],
            "price_error": [0.0],
            "feature_at_plus_500ms": [999.0],
        }
    )
    intervals = pd.DataFrame(
        columns=[
            "start_time",
            "end_time",
            "state",
        ]
    )
    aligned = pd.DataFrame(
        {"matched_timestamp": [pd.Timestamp("2026-07-23 12:00:00.500")]}
    )

    result = engineer_features(samples, ticks, intervals, aligned)

    assert "price_error" not in result.columns
    assert "feature_at_plus_500ms" not in result.columns
    assert not any("plus_500" in column or "+500" in column for column in result)
