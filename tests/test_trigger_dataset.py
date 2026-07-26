from __future__ import annotations

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from xau_trigger.trigger_dataset import (
    BOOTSTRAP_DRAWS,
    TickFeatureEngine,
    attach_pretransition_state,
    build_control_pool,
    build_model_matrix,
    coherent_conclusion,
    effective_event_times,
    expected_feature,
    model_output_columns,
    paired_summary,
    sample_controls,
    select_positives,
)


def _ticks(periods: int = 17, frequency: str = "250ms") -> pd.DataFrame:
    timestamp = pd.date_range(
        "2026-07-23 12:00:00",
        periods=periods,
        freq=frequency,
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


def _aligned_rows() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_id": [1, 2, 3],
            "behavior_type": ["REHEDGE_SELL", "UNLOCK_TO_BUY", "OTHER"],
            "is_primary_trigger_sample": [True, False, True],
            "matched_timestamp": pd.to_datetime(
                [
                    "2026-07-23 12:00:10.250",
                    "2026-07-23 12:00:20.250",
                    "2026-07-23 12:00:30.250",
                ]
            ),
            "reported_time": pd.to_datetime(
                [
                    "2026-07-23 12:00:10",
                    "2026-07-23 12:00:20",
                    "2026-07-23 12:00:30",
                ]
            ),
            "volume": [0.3, 0.3, 0.3],
            "match_quality": ["HIGH", "HIGH", "HIGH"],
            "match_tier": ["A", "A", "A"],
            "time_error_ms": [250.0, 250.0, 250.0],
            "price_error": [0.0, 0.0, 0.0],
        }
    )


def test_select_positives_separates_price_and_state_anchors() -> None:
    result = select_positives(_aligned_rows())

    assert result.matched_event_id.tolist() == [1]
    assert result.required_state.tolist() == ["ONE_BUY"]
    assert result.price_anchor_time.iloc[0] == pd.Timestamp(
        "2026-07-23 12:00:10.250"
    )
    assert result.state_anchor_time.iloc[0] == pd.Timestamp(
        "2026-07-23 12:00:10"
    )


def test_pretransition_state_age_uses_exact_m2_lineage() -> None:
    positive = select_positives(_aligned_rows())
    intervals = pd.DataFrame(
        {
            "interval_id": [7],
            "start_time": [pd.Timestamp("2026-07-23 12:00:02")],
            "end_time": [pd.Timestamp("2026-07-23 12:00:10")],
            "state": ["ONE_BUY"],
            "following_event_type": ["REHEDGE_SELL"],
        }
    )

    result = attach_pretransition_state(positive, intervals)

    assert result.state_age_pretransition_seconds.tolist() == [8.0]
    assert result.pretransition_interval_id.tolist() == [7]
    assert result.state_lineage_source.tolist() == ["m2_interval_lineage"]


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
            "state_age_pretransition_seconds": [12.0, 14.0],
            "state_age_stratum": ["10-30s", "10-30s"],
            "eligible_control_count": [8, 8],
            "is_control_supported": [True, True],
            "control_support_reason": ["supported", "supported"],
        }
    )
    pool = pd.DataFrame(
        {
            "pretransition_interval_id": ["i-1"] * 8,
            "sample_time": pd.date_range(
                "2026-07-23 12:01:00",
                periods=8,
                freq="1s",
            ),
            "price_anchor_time": pd.date_range(
                "2026-07-23 12:01:00",
                periods=8,
                freq="1s",
            ),
            "state_anchor_time": pd.date_range(
                "2026-07-23 12:01:00",
                periods=8,
                freq="1s",
            ),
            "required_state": ["ONE_BUY"] * 8,
            "volume": [0.3] * 8,
            "state_age_pretransition_seconds": range(8),
            "state_age_stratum": ["0-6s"] * 7 + ["7-10s"],
            "state_lineage_source": ["m2_interval_membership"] * 8,
            "date": ["2026-07-23"] * 8,
            "hour": [12] * 8,
        }
    )

    first = sample_controls(positives, pool, quota=3)
    second = sample_controls(positives, pool, quota=3)

    assert_frame_equal(first, second)
    assert len(first) == 6
    assert not first.duplicated(
        ["pretransition_interval_id", "sample_time"]
    ).any()
    assert first.state_age_pretransition_seconds.notna().all()


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
    assert not TickFeatureEngine(ticks).features_at(target, 60000)[
        "w60000ms_valid"
    ]


def test_h2_uses_disjoint_prior_boundary_and_causal_retracement() -> None:
    timestamps = pd.date_range(
        "2026-07-23 12:00:00",
        periods=9,
        freq="500ms",
    )
    mids = pd.Series([100, 101, 102, 101, 103, 104, 103, 102, 101], dtype=float)
    ticks = pd.DataFrame(
        {
            "timestamp": timestamps,
            "bid": mids - 0.05,
            "ask": mids + 0.05,
            "mid": mids,
            "spread": 0.1,
        }
    )

    features = TickFeatureEngine(ticks).h2_sequence_features_at(
        timestamps[-1],
        2000,
    )

    assert features["h2_w2000ms_valid"]
    assert features["h2_w2000ms_prior_boundary_high"] == 102.0
    assert features["h2_w2000ms_high_touched_before_event"]
    assert features["h2_w2000ms_retracement_after_high_fraction"] > 0
    assert features["h2_w2000ms_high_sequence_complete"]


def test_h2_is_not_identically_one_minus_h1() -> None:
    frame = pd.DataFrame(
        {
            "behavior_type": ["REHEDGE_SELL", "REHEDGE_SELL", "REHEDGE_BUY"],
            "w2000ms_range_position": [0.9, 0.2, 0.1],
            "h2_w2000ms_high_sequence_complete": [1, 0, 0],
            "h2_w2000ms_low_sequence_complete": [0, 0, 1],
        }
    )
    h1 = expected_feature(frame, 2000, "h1")
    h2 = expected_feature(frame, 2000, "h2")

    assert not np.allclose(h1 + h2, 1.0)


def test_model_matrix_uses_explicit_allowlist_and_blocks_sampling_leakage() -> None:
    data = {column: [0] for column in model_output_columns()}
    data.update(
        {
            "sample_id": ["p-1"],
            "sample_type": ["positive"],
            "behavior_type": ["REHEDGE_SELL"],
            "trigger_family": ["rehedge"],
            "date_split": ["development"],
            "control_sampling_reason": [None],
            "control_distance_seconds": [0.0],
            "time_since_previous_event_seconds": [0.1],
            "feature_at_plus_500ms": [999.0],
        }
    )

    result = build_model_matrix(pd.DataFrame(data))

    assert list(result.columns) == list(model_output_columns())
    assert "control_sampling_reason" not in result
    assert "control_distance_seconds" not in result
    assert "time_since_previous_event_seconds" not in result
    assert "feature_at_plus_500ms" not in result


def _result(window: int, low: float, high: float) -> dict:
    return {
        "window_ms": window,
        "summary": {
            "pairs": 100,
            "cluster_bootstrap_ci95": [low, high],
        },
    }


def test_mixed_window_conclusion_uses_adjacent_coherence() -> None:
    rejected = [
        _result(1, 0.1, 0.2),
        _result(2, -0.2, -0.1),
        _result(3, -0.3, -0.2),
    ]
    mixed = [
        _result(1, 0.1, 0.2),
        _result(2, 0.1, 0.2),
        _result(3, -0.2, -0.1),
        _result(4, -0.3, -0.2),
    ]

    assert coherent_conclusion(rejected) == "rejected"
    assert coherent_conclusion(mixed) == "mixed"
    assert coherent_conclusion([_result(1, 0.1, 0.2)]) == "weak"


def test_paired_bootstrap_uses_locked_draw_count() -> None:
    frame = pd.DataFrame(
        {
            "matched_event_id": [1, 1, 2, 2],
            "sample_type": ["positive", "control", "positive", "control"],
            "date_split": ["holdout"] * 4,
            "behavior_type": ["UNLOCK_TO_BUY"] * 4,
            "w500ms_valid": [True] * 4,
            "w500ms_mid_return": [0.2, 0.1, 0.3, 0.1],
        }
    )

    summary = paired_summary(frame, 500, "h3")

    assert summary["bootstrap_draws"] == BOOTSTRAP_DRAWS == 5000
