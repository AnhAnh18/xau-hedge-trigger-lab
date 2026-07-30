from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from xau_trigger.unlock_cause import (
    BINARY_TOUCH_FEATURES,
    CAUSE_FEATURES,
    build_unlock_cause_dataset,
    fit_cause_bundle,
    fit_cause_preprocessor,
    predict_cause_bundle,
    select_cause_regularization,
    transform_cause_features,
)


def _ticks() -> pd.DataFrame:
    timestamps = pd.date_range("2026-07-20 12:00:00", periods=41, freq="1s")
    mid = np.arange(41, dtype=float) + 4000.0
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "mid": mid,
            "spread": np.full(41, 0.2),
        }
    )


def _feature_audit(*, duplicate: bool = False) -> pd.DataFrame:
    rows = [
        {
            "risk_bin_id": "risk-1",
            "cohort_id": "cohort-a",
            "interval_id": "interval-1",
            "endpoint": "unlock_occurrence",
            "bin_width_ms": 1000,
            "bin_start": pd.Timestamp("2026-07-20 12:00:20"),
            "bin_end": pd.Timestamp("2026-07-20 12:00:21"),
            "session_date": "2026-07-20",
            "analysis_role": "development",
            "state_age_seconds": 15.0,
            "target_label": 1,
            "following_event_type": "UNLOCK_TO_BUY",
            "interval_start": pd.Timestamp("2026-07-20 12:00:05"),
            "is_common_hours": True,
            "is_cross_split_interval": False,
        }
    ]
    if duplicate:
        rows.append({**rows[0], "risk_bin_id": "risk-duplicate"})
    return pd.DataFrame(rows)


def test_build_unlock_cause_dataset_uses_raw_directional_features() -> None:
    audit, predictors, targets, design = build_unlock_cause_dataset(
        _feature_audit(),
        {"cohort-a": _ticks()},
        {"cohort-a": pd.DataFrame()},
    )

    assert len(audit) == len(predictors) == len(targets) == len(design) == 1
    assert list(predictors.columns) == ["sample_id", *CAUSE_FEATURES]
    assert list(targets.columns) == ["sample_id", "cause_label"]
    assert targets.loc[0, "cause_label"] == 1
    assert predictors.loc[0, "mid_change_2s"] == pytest.approx(2.0)
    assert predictors.loc[0, "mid_change_5s"] == pytest.approx(5.0)
    assert predictors.loc[0, "tick_imbalance_2s"] == pytest.approx(1.0)
    assert predictors.loc[0, "range_position_10s"] == pytest.approx(1.0)
    assert predictors.loc[0, "prior_upper_boundary_touch_2s"] == 1.0
    assert predictors.loc[0, "prior_lower_boundary_touch_2s"] == 0.0
    assert predictors.loc[0, "state_start_displacement"] == pytest.approx(15.0)
    assert "following_event_type" not in predictors.columns
    assert "interval_id" not in predictors.columns


def test_duplicate_unlock_event_key_is_fatal() -> None:
    with pytest.raises(AssertionError, match="Duplicate M5-004 event key"):
        build_unlock_cause_dataset(
            _feature_audit(duplicate=True),
            {"cohort-a": _ticks()},
            {"cohort-a": pd.DataFrame()},
        )


def test_state_path_crossing_quote_gap_is_excluded() -> None:
    gaps = pd.DataFrame(
        {
            "break_start": [pd.Timestamp("2026-07-20 12:00:08")],
            "break_end": [pd.Timestamp("2026-07-20 12:00:09")],
        }
    )
    audit, predictors, targets, design = build_unlock_cause_dataset(
        _feature_audit(),
        {"cohort-a": _ticks()},
        {"cohort-a": gaps},
    )

    assert audit.loc[0, "first_exclusion_reason"] == (
        "state_start_reference_invalid"
    )
    assert not audit.loc[0, "is_joint_valid"]
    assert predictors.empty
    assert targets.empty
    assert design.empty


def _model_frame() -> pd.DataFrame:
    rows = []
    ages = [5.2, 6.5, 8.5, 12.0, 24.0, 45.0, 75.0]
    for index in range(140):
        row = {
            "sample_id": f"sample-{index}",
            "cohort_id": "development",
            "interval_id": f"interval-{index}",
            "group_id": f"development:interval-{index}",
            "bin_width_ms": 1000,
            "bin_start": pd.Timestamp("2026-07-20 12:00:00")
            + pd.Timedelta(seconds=index),
            "session_date": f"2026-07-{20 + index % 4:02d}",
            "analysis_role": "development",
            "state_age_seconds": ages[index % len(ages)],
            "cause_label": index % 2,
        }
        for feature_index, feature in enumerate(CAUSE_FEATURES):
            if feature in BINARY_TOUCH_FEATURES:
                row[feature] = float((index + feature_index) % 2)
            else:
                row[feature] = float(
                    np.sin((index + 1) * (feature_index + 1) / 17.0)
                )
        rows.append(row)
    return pd.DataFrame(rows)


def test_binary_touches_are_not_standardized() -> None:
    frame = _model_frame()
    preprocessor = fit_cause_preprocessor(frame, CAUSE_FEATURES)
    transformed = transform_cause_features(frame, preprocessor)
    for column in BINARY_TOUCH_FEATURES:
        index = list(CAUSE_FEATURES).index(column)
        assert preprocessor["means"][index] == 0.0
        assert preprocessor["scales"][index] == 1.0
        np.testing.assert_array_equal(
            transformed[:, index], frame[column].to_numpy()
        )


def test_cause_fit_is_development_only_and_grouped() -> None:
    development = _model_frame()
    selection = select_cause_regularization(development)
    bundle = fit_cause_bundle(development, selection)
    augmented_holdout = _model_frame().assign(
        cohort_id="holdout",
        group_id=lambda frame: "holdout:" + frame["interval_id"],
        analysis_role="internal_reuse",
        cause_label=lambda frame: 1 - frame["cause_label"],
    )

    assert all(fold["group_overlap"] == 0 for fold in selection["folds"])
    assert bundle["fitted_parameter_sha256"] == fit_cause_bundle(
        development, select_cause_regularization(development)
    )["fitted_parameter_sha256"]
    # Merely constructing or scoring holdout rows cannot mutate the frozen fit.
    predictions = predict_cause_bundle(augmented_holdout, bundle)
    assert bundle["fitted_parameter_sha256"] == fit_cause_bundle(
        development, selection
    )["fitted_parameter_sha256"]
    assert predictions.filter(regex=r"^p_").apply(
        lambda column: column.between(0.0, 1.0).all()
    ).all()
