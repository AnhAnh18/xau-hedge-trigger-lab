from __future__ import annotations

import numpy as np
import pandas as pd

from xau_trigger.price_features import (
    CausalTickFeatureEngine,
    _RangeMinMax,
    attach_first_exclusion_reason,
)


def test_vectorized_range_min_max_matches_half_open_slices() -> None:
    values = np.array([4.0, 1.0, 7.0, 2.0, 9.0])
    index = _RangeMinMax(values)

    minimum, maximum = index.query(
        np.array([0, 1, 2, 4]),
        np.array([5, 4, 3, 4]),
    )

    assert np.allclose(minimum[:3], [1.0, 1.0, 7.0])
    assert np.allclose(maximum[:3], [9.0, 7.0, 7.0])
    assert np.isnan(minimum[3])
    assert np.isnan(maximum[3])


def _ticks() -> pd.DataFrame:
    timestamp = pd.date_range("2026-07-23 12:00:00", periods=31, freq="500ms")
    mid = np.array(
        [
            100.0,
            100.1,
            100.2,
            100.4,
            100.3,
            100.2,
            100.5,
            100.7,
            100.6,
            100.4,
            100.3,
            100.2,
            100.4,
            100.8,
            101.0,
            100.9,
            100.7,
            100.6,
            100.5,
            100.4,
            100.6,
            100.8,
            101.1,
            101.3,
            101.2,
            101.0,
            100.9,
            100.8,
            100.7,
            100.6,
            100.5,
        ]
    )
    return pd.DataFrame(
        {
            "timestamp": timestamp,
            "mid": mid,
            "spread": np.full(len(timestamp), 0.2),
        }
    )


def test_causal_features_use_endpoint_sign_and_pre_anchor_touch() -> None:
    ticks = _ticks()
    engine = CausalTickFeatureEngine(ticks)
    bins = pd.DataFrame(
        {
            "risk_bin_id": ["sell", "buy", "unlock"],
            "endpoint": [
                "rehedge_sell_occurrence",
                "rehedge_buy_occurrence",
                "unlock_occurrence",
            ],
            "bin_start": [pd.Timestamp("2026-07-23 12:00:15")] * 3,
            "interval_start": [pd.Timestamp("2026-07-23 12:00:02")] * 3,
        }
    )

    result = engine.build(bins)

    assert result["all_features_valid"].all()
    assert result.loc[0, "signed_mid_change_2s"] == -result.loc[
        1, "signed_mid_change_2s"
    ]
    assert result.loc[2, "absolute_mid_change_2s"] == abs(
        result.loc[0, "signed_mid_change_2s"]
    )
    assert result.loc[0, "spread_at_anchor"] == 0.2
    assert result.loc[0, "absolute_state_start_displacement"] >= 0
    assert result.loc[2, "either_prior_boundary_touch_2s"] in {0.0, 1.0}


def test_gap_crossing_window_and_state_reference_are_invalid() -> None:
    ticks = _ticks()
    gaps = pd.DataFrame(
        {
            "break_start": [pd.Timestamp("2026-07-23 12:00:07")],
            "break_end": [pd.Timestamp("2026-07-23 12:00:12")],
        }
    )
    engine = CausalTickFeatureEngine(ticks, gaps)
    bins = pd.DataFrame(
        {
            "risk_bin_id": ["x"],
            "endpoint": ["unlock_occurrence"],
            "bin_start": [pd.Timestamp("2026-07-23 12:00:15")],
            "interval_start": [pd.Timestamp("2026-07-23 12:00:10")],
        }
    )

    result = engine.build(bins)

    assert not result.loc[0, "window_10s_valid"]
    assert not result.loc[0, "state_start_reference_valid"]
    assert not result.loc[0, "all_features_valid"]


def test_first_exclusion_waterfall_prioritizes_unlock_floor() -> None:
    audit = pd.DataFrame(
        {
            "unlock_before_floor_excluded": [True, False],
            "window_10s_valid": [False, True],
            "window_5s_valid": [False, True],
            "window_2s_valid": [False, True],
            "h2_5s_valid": [False, True],
            "h2_2s_valid": [False, True],
            "state_start_reference_valid": [False, True],
            "current_snapshot_valid": [False, True],
        }
    )

    result = attach_first_exclusion_reason(audit)

    assert result.loc[0, "first_exclusion_reason"] == "unlock_before_floor_excluded"
    assert result.loc[1, "is_joint_valid"]
