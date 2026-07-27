from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from xau_trigger.price_inference import (
    deterministic_group_kfold,
    fit_age_baseline,
    fit_logistic_l2,
    fit_offset_intercept,
    fit_scaler,
    fit_session_baseline,
    interval_model_deltas,
    predict_age_baseline,
    predict_logistic,
    predict_offset_intercept,
    predict_session_baseline,
    session_block_design,
    transform_features,
)


def test_age_baseline_uses_exact_eleven_bucket_grid() -> None:
    ages = [0.2, 1.2, 2.2, 3.2, 5.2, 6.2, 8.2, 12, 22, 42, 80]
    frame = pd.DataFrame(
        {
            "endpoint": ["unlock_occurrence"] * len(ages),
            "target_label": [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0],
            "state_age_seconds": ages,
        }
    )

    parameters = fit_age_baseline(frame, endpoint="unlock_occurrence")
    probabilities = predict_age_baseline(frame, parameters)

    assert len(parameters["bucket_labels"]) == 11
    assert parameters["bucket_labels"][4:7] == [
        "age_5_6",
        "age_6_8",
        "age_8_10",
    ]
    assert np.isfinite(probabilities).all()


def test_zero_training_exposure_bucket_fails_on_evaluation() -> None:
    training = pd.DataFrame(
        {
            "endpoint": ["rehedge_buy_occurrence"] * 2,
            "target_label": [0, 1],
            "state_age_seconds": [0.2, 0.8],
        }
    )
    evaluation = pd.DataFrame(
        {
            "endpoint": ["rehedge_buy_occurrence"],
            "target_label": [0],
            "state_age_seconds": [6.5],
        }
    )

    parameters = fit_age_baseline(training, endpoint="rehedge_buy_occurrence")

    with pytest.raises(ValueError, match="zero training exposure"):
        predict_age_baseline(evaluation, parameters)


def test_logistic_models_are_deterministic_and_intercept_contract_is_explicit() -> None:
    rng = np.random.default_rng(7)
    x = rng.normal(size=(500, 2))
    probability = 1 / (1 + np.exp(-(-1.5 + 0.8 * x[:, 0] - 0.3 * x[:, 1])))
    labels = (rng.random(500) < probability).astype(int)

    with_intercept = fit_logistic_l2(
        x,
        labels,
        regularization=0.01,
        fit_intercept=True,
    )
    repeated = fit_logistic_l2(
        x,
        labels,
        regularization=0.01,
        fit_intercept=True,
    )
    offset = np.full(len(labels), -1.0)
    without_intercept = fit_logistic_l2(
        x,
        labels,
        regularization=0.01,
        offset=offset,
        fit_intercept=False,
    )

    assert with_intercept["sha256"] == repeated["sha256"]
    assert with_intercept["intercept"] is not None
    assert without_intercept["intercept"] is None
    assert np.isfinite(predict_logistic(x, with_intercept)).all()
    assert np.isfinite(
        predict_logistic(x, without_intercept, offset=offset)
    ).all()


def test_offset_level_fit_changes_only_one_intercept() -> None:
    baseline = np.full(200, 0.1)
    labels = np.array([1] * 40 + [0] * 160)

    parameters = fit_offset_intercept(labels, baseline)
    calibrated = predict_offset_intercept(baseline, parameters)

    assert abs(calibrated.mean() - labels.mean()) < 1e-9
    assert parameters["intercept"] > 0


def test_group_kfold_is_deterministic_and_never_splits_interval() -> None:
    groups = np.repeat([f"g{index}" for index in range(20)], np.arange(1, 21))

    first = deterministic_group_kfold(groups, n_splits=5)
    second = deterministic_group_kfold(groups, n_splits=5)

    for (train, validation), (train_again, validation_again) in zip(first, second):
        assert np.array_equal(train, train_again)
        assert np.array_equal(validation, validation_again)
        assert not set(groups[train]) & set(groups[validation])


def test_scaler_uses_only_supplied_training_rows() -> None:
    training = pd.DataFrame({"x": [0.0, 2.0], "constant": [1.0, 1.0]})
    holdout = pd.DataFrame({"x": [100.0], "constant": [1.0]})

    scaler = fit_scaler(training, ["x", "constant"])
    transformed = transform_features(holdout, scaler)

    assert scaler["means"] == [1.0, 1.0]
    assert scaler["scales"] == [1.0, 1.0]
    assert transformed[0, 0] == 99.0


def test_session_baseline_uses_three_explicit_blocks_without_reference_omission() -> None:
    frame = pd.DataFrame(
        {
            "bin_start": pd.to_datetime(
                [
                    "2026-07-23 12:30:00",
                    "2026-07-23 12:31:00",
                    "2026-07-23 16:30:00",
                    "2026-07-23 16:31:00",
                    "2026-07-23 20:30:00",
                    "2026-07-23 20:31:00",
                ]
            ),
            "target_label": [0, 1, 0, 1, 0, 1],
        }
    )
    design = session_block_design(frame)
    parameters = fit_session_baseline(frame, np.full(6, 0.2))
    probabilities = predict_session_baseline(
        frame, np.full(6, 0.2), parameters
    )

    assert np.array_equal(design, np.repeat(np.eye(3), 2, axis=0))
    assert parameters["parameterization"] == (
        "three_one_hot_block_effects_no_intercept"
    )
    assert parameters["server_hour_bounds"] == [[12, 16], [16, 20], [20, 24]]
    assert parameters["parameters"]["fit_intercept"] is False
    assert len(parameters["parameters"]["coefficients"]) == 3
    assert np.isfinite(probabilities).all()


def test_session_baseline_rejects_rows_outside_common_hours() -> None:
    frame = pd.DataFrame(
        {
            "bin_start": pd.to_datetime(["2026-07-23 11:59:59"]),
            "target_label": [0],
        }
    )

    with pytest.raises(ValueError, match="common server hours"):
        session_block_design(frame)


def test_interval_deltas_pair_models_on_identical_rows() -> None:
    predictions = pd.DataFrame(
        {
            "risk_bin_id": ["a", "b", "c"],
            "interval_id": ["i1", "i1", "i2"],
            "endpoint": ["unlock_occurrence"] * 3,
            "session_date": ["2026-07-24"] * 3,
            "analysis_role": ["internal_reuse"] * 3,
            "target_label": [0, 1, 0],
            "p_A_common": [0.1, 0.1, 0.1],
            "p_A_level": [0.1, 0.1, 0.1],
            "p_A_dev": [0.2, 0.2, 0.2],
            "p_A_session": [0.18, 0.18, 0.18],
            "p_B": [0.15, 0.25, 0.15],
            "p_C_dev": [0.1, 0.4, 0.1],
            "p_C_session": [0.1, 0.45, 0.1],
            "p_C_shape": [0.12, 0.35, 0.12],
        }
    )

    result = interval_model_deltas(predictions)

    assert len(result) == 2
    event_interval = result[result["interval_id"].eq("i1")].iloc[0]
    assert event_interval["C_dev_minus_A_dev"] > 0
    assert event_interval["C_session_minus_A_session"] > 0
