"""Deterministic discrete-time price-increment models for M5-003."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Iterable

import numpy as np
import pandas as pd

from xau_trigger.state_age_hazard import (
    AGE_BUCKET_BOUNDS,
    AGE_BUCKET_LABELS,
    PRIMARY_ALPHA,
    PROBABILITY_EPSILON,
    attach_age_buckets,
)


LAMBDA_GRID = (0.0001, 0.001, 0.01, 0.1, 1.0, 10.0)
SESSION_BLOCKS = (
    ("server_12_16", 12, 16),
    ("server_16_20", 16, 20),
    ("server_20_24", 20, 24),
)


def _require_columns(frame: pd.DataFrame, required: Iterable[str]) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def _expit(values: np.ndarray) -> np.ndarray:
    source = np.asarray(values, dtype=float)
    output = np.empty_like(source)
    positive = source >= 0
    output[positive] = 1.0 / (1.0 + np.exp(-source[positive]))
    exponential = np.exp(source[~positive])
    output[~positive] = exponential / (1.0 + exponential)
    return np.clip(output, PROBABILITY_EPSILON, 1 - PROBABILITY_EPSILON)


def _logit(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(
        np.asarray(probabilities, dtype=float),
        PROBABILITY_EPSILON,
        1 - PROBABILITY_EPSILON,
    )
    return np.log(clipped) - np.log1p(-clipped)


def bernoulli_log_likelihood(
    labels: np.ndarray,
    probabilities: np.ndarray,
) -> np.ndarray:
    labels = np.asarray(labels, dtype=float)
    probabilities = np.clip(
        np.asarray(probabilities, dtype=float),
        PROBABILITY_EPSILON,
        1 - PROBABILITY_EPSILON,
    )
    return labels * np.log(probabilities) + (1 - labels) * np.log1p(-probabilities)


def fit_age_baseline(
    frame: pd.DataFrame,
    *,
    endpoint: str,
    alpha: float = PRIMARY_ALPHA,
) -> dict:
    """Fit the exact M5-002 bucket grid on one development subset."""
    _require_columns(frame, ["endpoint", "target_label", "state_age_seconds"])
    source = attach_age_buckets(frame)
    source = source[source["endpoint"].eq(endpoint)]
    if source.empty:
        raise ValueError(f"No development rows for endpoint: {endpoint}")
    buckets = {}
    for label in AGE_BUCKET_LABELS:
        group = source[source["state_age_bucket"].eq(label)]
        exposure = int(len(group))
        events = int(group["target_label"].sum())
        probability = (
            None
            if exposure == 0
            else float((events + alpha) / (exposure + 2 * alpha))
        )
        buckets[label] = {
            "exposure_bins": exposure,
            "target_events": events,
            "probability": probability,
        }
    payload = {
        "schema_version": 1,
        "endpoint": endpoint,
        "alpha": float(alpha),
        "bucket_bounds": [
            "inf" if np.isinf(value) else float(value) for value in AGE_BUCKET_BOUNDS
        ],
        "bucket_labels": list(AGE_BUCKET_LABELS),
        "age_buckets": buckets,
    }
    payload["fitted_parameter_sha256"] = _canonical_hash(payload)
    return payload


def predict_age_baseline(frame: pd.DataFrame, parameters: dict) -> np.ndarray:
    source = attach_age_buckets(frame)
    probabilities = []
    for label in source["state_age_bucket"].astype(str):
        bucket = parameters["age_buckets"][label]
        if bucket["exposure_bins"] == 0 or bucket["probability"] is None:
            raise ValueError(
                f"Active evaluation bucket has zero training exposure: {label}"
            )
        probabilities.append(float(bucket["probability"]))
    return np.asarray(probabilities, dtype=float)


def predict_common_baseline(frame: pd.DataFrame, endpoint_parameters: dict) -> np.ndarray:
    source = attach_age_buckets(frame)
    probabilities = []
    for label in source["state_age_bucket"].astype(str):
        probability = endpoint_parameters["age_buckets"][label]["probability"]
        if probability is None:
            raise ValueError(f"Frozen A_common has no probability for {label}")
        probabilities.append(float(probability))
    return np.asarray(probabilities, dtype=float)


def fit_scaler(frame: pd.DataFrame, feature_columns: Iterable[str]) -> dict:
    columns = list(feature_columns)
    values = frame[columns].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Model features must be finite before preprocessing")
    means = values.mean(axis=0)
    scales = values.std(axis=0, ddof=0)
    scales[scales == 0] = 1.0
    payload = {
        "feature_columns": columns,
        "means": [float(value) for value in means],
        "scales": [float(value) for value in scales],
    }
    payload["sha256"] = _canonical_hash(payload)
    return payload


def transform_features(frame: pd.DataFrame, scaler: dict) -> np.ndarray:
    values = frame[scaler["feature_columns"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Model features must be finite before preprocessing")
    return (values - np.asarray(scaler["means"])) / np.asarray(scaler["scales"])


def _penalized_objective(
    theta: np.ndarray,
    design: np.ndarray,
    labels: np.ndarray,
    offset: np.ndarray,
    penalty: np.ndarray,
) -> float:
    probabilities = _expit(offset + design @ theta)
    mean_negative_ll = -float(bernoulli_log_likelihood(labels, probabilities).mean())
    return mean_negative_ll + 0.5 * float(np.dot(penalty * theta, theta))


def fit_logistic_l2(
    features: np.ndarray,
    labels: np.ndarray,
    *,
    regularization: float,
    offset: np.ndarray | None = None,
    fit_intercept: bool,
    max_iterations: int = 100,
    tolerance: float = 1e-9,
) -> dict:
    """Fit a small deterministic L2 logistic hazard with Newton updates."""
    if regularization < 0:
        raise ValueError("Regularization cannot be negative")
    x = np.asarray(features, dtype=float)
    y = np.asarray(labels, dtype=float)
    if x.ndim != 2 or len(x) != len(y):
        raise ValueError("Feature matrix and labels must align")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("Logistic fit requires finite inputs")
    base_offset = np.zeros(len(y), dtype=float) if offset is None else np.asarray(offset, dtype=float)
    if len(base_offset) != len(y) or not np.isfinite(base_offset).all():
        raise ValueError("Offset must be finite and row-aligned")
    design = np.column_stack([np.ones(len(x)), x]) if fit_intercept else x
    penalty = np.full(design.shape[1], float(regularization), dtype=float)
    if fit_intercept:
        penalty[0] = 0.0
    theta = np.zeros(design.shape[1], dtype=float)
    converged = False
    objective = _penalized_objective(theta, design, y, base_offset, penalty)
    for iteration in range(1, max_iterations + 1):
        probabilities = _expit(base_offset + design @ theta)
        residual = probabilities - y
        gradient = design.T @ residual / len(y) + penalty * theta
        weights = probabilities * (1 - probabilities)
        hessian = (design.T * weights) @ design / len(y)
        hessian.flat[:: hessian.shape[0] + 1] += penalty
        try:
            step = np.linalg.solve(hessian, gradient)
        except np.linalg.LinAlgError:
            step = np.linalg.lstsq(hessian, gradient, rcond=None)[0]
        if float(np.max(np.abs(step))) <= tolerance:
            converged = True
            break
        scale = 1.0
        accepted = False
        for _ in range(30):
            candidate = theta - scale * step
            candidate_objective = _penalized_objective(
                candidate, design, y, base_offset, penalty
            )
            if candidate_objective <= objective + 1e-14:
                theta = candidate
                objective = candidate_objective
                accepted = True
                break
            scale *= 0.5
        if not accepted:
            if float(np.max(np.abs(gradient))) <= 1e-7:
                converged = True
                break
            raise RuntimeError("Logistic Newton line search failed")
        if float(np.max(np.abs(scale * step))) <= tolerance:
            converged = True
            break
    if not converged:
        raise RuntimeError("Logistic fit did not converge")
    intercept = float(theta[0]) if fit_intercept else None
    coefficients = theta[1:] if fit_intercept else theta
    payload = {
        "regularization": float(regularization),
        "objective_scale": "mean_negative_log_likelihood_plus_half_lambda_l2",
        "fit_intercept": bool(fit_intercept),
        "intercept": intercept,
        "coefficients": [float(value) for value in coefficients],
        "iterations": int(iteration),
        "converged": True,
    }
    payload["sha256"] = _canonical_hash(payload)
    return payload


def predict_logistic(
    features: np.ndarray,
    parameters: dict,
    *,
    offset: np.ndarray | None = None,
) -> np.ndarray:
    x = np.asarray(features, dtype=float)
    eta = x @ np.asarray(parameters["coefficients"], dtype=float)
    if parameters["fit_intercept"]:
        eta += float(parameters["intercept"])
    if offset is not None:
        eta += np.asarray(offset, dtype=float)
    return _expit(eta)


def fit_offset_intercept(labels: np.ndarray, offset_probabilities: np.ndarray) -> dict:
    y = np.asarray(labels, dtype=float)
    offset = _logit(offset_probabilities)
    alpha = 0.0
    for iteration in range(1, 101):
        probability = _expit(offset + alpha)
        gradient = float(np.mean(probability - y))
        hessian = float(np.mean(probability * (1 - probability)))
        if hessian <= 0:
            raise RuntimeError("Offset intercept has nonpositive Hessian")
        step = gradient / hessian
        alpha -= step
        if abs(step) <= 1e-10:
            break
    else:
        raise RuntimeError("Offset intercept did not converge")
    payload = {"intercept": float(alpha), "iterations": int(iteration)}
    payload["sha256"] = _canonical_hash(payload)
    return payload


def predict_offset_intercept(
    offset_probabilities: np.ndarray,
    parameters: dict,
) -> np.ndarray:
    return _expit(_logit(offset_probabilities) + float(parameters["intercept"]))


def session_block_design(frame: pd.DataFrame) -> np.ndarray:
    """Return the locked three-column server-time block design.

    All three block effects are represented explicitly.  With no free
    intercept this is equivalent to an intercept plus two treatment
    contrasts, and avoids accidentally fixing the first block effect at zero.
    """
    _require_columns(frame, ["bin_start"])
    timestamps = pd.to_datetime(frame["bin_start"], errors="raise")
    hours = timestamps.dt.hour.to_numpy(dtype=int)
    design = np.column_stack(
        [(hours >= start) & (hours < end) for _, start, end in SESSION_BLOCKS]
    ).astype(float)
    if len(design) and not np.all(design.sum(axis=1) == 1):
        invalid = sorted(set(int(value) for value in hours[design.sum(axis=1) != 1]))
        raise ValueError(
            "Session baseline is defined only on common server hours 12:00-24:00; "
            f"observed invalid hours: {invalid}"
        )
    return design


def fit_session_baseline(
    frame: pd.DataFrame,
    age_probabilities: np.ndarray,
) -> dict:
    """Fit unpenalized development-only block effects over A_dev."""
    _require_columns(frame, ["target_label", "bin_start"])
    parameters = fit_logistic_l2(
        session_block_design(frame),
        frame["target_label"].to_numpy(),
        regularization=0.0,
        offset=_logit(age_probabilities),
        fit_intercept=False,
    )
    payload = {
        "block_labels": [label for label, _, _ in SESSION_BLOCKS],
        "server_hour_bounds": [[start, end] for _, start, end in SESSION_BLOCKS],
        "parameterization": "three_one_hot_block_effects_no_intercept",
        "regularization": 0.0,
        "parameters": parameters,
    }
    payload["fitted_parameter_sha256"] = _canonical_hash(payload)
    return payload


def predict_session_baseline(
    frame: pd.DataFrame,
    age_probabilities: np.ndarray,
    parameters: dict,
) -> np.ndarray:
    if parameters["parameterization"] != "three_one_hot_block_effects_no_intercept":
        raise ValueError("Unsupported A_session parameterization")
    return predict_logistic(
        session_block_design(frame),
        parameters["parameters"],
        offset=_logit(age_probabilities),
    )


def deterministic_group_kfold(
    groups: Iterable[object],
    *,
    n_splits: int = 5,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Balance whole interval groups across deterministic validation folds."""
    values = np.asarray([str(value) for value in groups], dtype=object)
    unique, counts = np.unique(values, return_counts=True)
    if len(unique) < n_splits:
        raise ValueError("GroupKFold requires at least one group per fold")
    order = sorted(range(len(unique)), key=lambda index: (-int(counts[index]), unique[index]))
    totals = np.zeros(n_splits, dtype=np.int64)
    assignment: dict[str, int] = {}
    for index in order:
        fold = int(np.flatnonzero(totals == totals.min())[0])
        assignment[str(unique[index])] = fold
        totals[fold] += int(counts[index])
    row_folds = np.array([assignment[str(value)] for value in values], dtype=int)
    splits = []
    for fold in range(n_splits):
        validation = np.flatnonzero(row_folds == fold)
        training = np.flatnonzero(row_folds != fold)
        splits.append((training, validation))
    return splits


def mean_per_interval_log_likelihood(
    frame: pd.DataFrame,
    probabilities: np.ndarray,
) -> float:
    _require_columns(frame, ["interval_id", "target_label"])
    scored = pd.DataFrame(
        {
            "interval_id": frame["interval_id"].astype(str).to_numpy(),
            "log_likelihood": bernoulli_log_likelihood(
                frame["target_label"].to_numpy(), probabilities
            ),
        }
    )
    return float(scored.groupby("interval_id", sort=True)["log_likelihood"].sum().mean())


def select_regularization(
    development: pd.DataFrame,
    feature_columns: Iterable[str],
    *,
    endpoint: str,
    lambdas: Iterable[float] = LAMBDA_GRID,
    n_splits: int = 5,
) -> dict:
    """Select B, C_dev, and C_session penalties with interval GroupKFold."""
    source = development[development["endpoint"].eq(endpoint)].reset_index(drop=True)
    columns = list(feature_columns)
    splits = deterministic_group_kfold(source["interval_id"], n_splits=n_splits)
    prepared = []
    fold_proof = []
    for fold, (train_indices, validation_indices) in enumerate(splits):
        train = source.iloc[train_indices].reset_index(drop=True)
        validation = source.iloc[validation_indices].reset_index(drop=True)
        train_groups = set(train["interval_id"].astype(str))
        validation_groups = set(validation["interval_id"].astype(str))
        if train_groups & validation_groups:
            raise AssertionError("GroupKFold leaked an interval across train/validation")
        scaler = fit_scaler(train, columns)
        age = fit_age_baseline(train, endpoint=endpoint)
        train_age = predict_age_baseline(train, age)
        validation_age = predict_age_baseline(validation, age)
        session = fit_session_baseline(train, train_age)
        train_session = predict_session_baseline(train, train_age, session)
        validation_session = predict_session_baseline(
            validation, validation_age, session
        )
        prepared.append(
            {
                "train": train,
                "validation": validation,
                "x_train": transform_features(train, scaler),
                "x_validation": transform_features(validation, scaler),
                "train_age": train_age,
                "validation_age": validation_age,
                "train_session": train_session,
                "validation_session": validation_session,
            }
        )
        fold_proof.append(
            {
                "fold": fold,
                "training_rows": int(len(train)),
                "validation_rows": int(len(validation)),
                "training_intervals": int(len(train_groups)),
                "validation_intervals": int(len(validation_groups)),
                "group_overlap": 0,
            }
        )

    model_results = {}
    for model in ["B", "C_dev", "C_session"]:
        rows = []
        for regularization in lambdas:
            fold_scores = []
            for item in prepared:
                labels = item["train"]["target_label"].to_numpy()
                parameters = fit_logistic_l2(
                    item["x_train"],
                    labels,
                    regularization=float(regularization),
                    offset=(
                        _logit(item["train_age"])
                        if model == "C_dev"
                        else _logit(item["train_session"])
                        if model == "C_session"
                        else None
                    ),
                    fit_intercept=model == "B",
                )
                probabilities = predict_logistic(
                    item["x_validation"],
                    parameters,
                    offset=(
                        _logit(item["validation_age"])
                        if model == "C_dev"
                        else _logit(item["validation_session"])
                        if model == "C_session"
                        else None
                    ),
                )
                fold_scores.append(
                    mean_per_interval_log_likelihood(
                        item["validation"], probabilities
                    )
                )
            mean = float(np.mean(fold_scores))
            standard_error = float(np.std(fold_scores, ddof=1) / np.sqrt(len(fold_scores)))
            rows.append(
                {
                    "lambda": float(regularization),
                    "fold_scores": [float(value) for value in fold_scores],
                    "mean_score": mean,
                    "standard_error": standard_error,
                }
            )
        best = max(rows, key=lambda row: row["mean_score"])
        threshold = best["mean_score"] - best["standard_error"]
        selected = max(row["lambda"] for row in rows if row["mean_score"] >= threshold)
        model_results[model] = {
            "selected_lambda": float(selected),
            "best_lambda": float(best["lambda"]),
            "one_standard_error_threshold": float(threshold),
            "scores": rows,
        }
    payload = {
        "endpoint": endpoint,
        "folds": fold_proof,
        "models": model_results,
    }
    payload["sha256"] = _canonical_hash(payload)
    return payload


def fit_endpoint_bundle(
    development: pd.DataFrame,
    feature_columns: Iterable[str],
    *,
    endpoint: str,
    common_parameters: dict,
    regularization_selection: dict,
    shape_feature_columns: Iterable[str] | None = None,
) -> dict:
    source = development[development["endpoint"].eq(endpoint)].reset_index(drop=True)
    columns = list(feature_columns)
    scaler = fit_scaler(source, columns)
    x = transform_features(source, scaler)
    age = fit_age_baseline(source, endpoint=endpoint)
    p_dev = predict_age_baseline(source, age)
    session = fit_session_baseline(source, p_dev)
    p_session = predict_session_baseline(source, p_dev, session)
    p_common = predict_common_baseline(source, common_parameters)
    level = fit_offset_intercept(source["target_label"].to_numpy(), p_common)
    b = fit_logistic_l2(
        x,
        source["target_label"].to_numpy(),
        regularization=regularization_selection["models"]["B"]["selected_lambda"],
        fit_intercept=True,
    )
    c_dev = fit_logistic_l2(
        x,
        source["target_label"].to_numpy(),
        regularization=regularization_selection["models"]["C_dev"]["selected_lambda"],
        offset=_logit(p_dev),
        fit_intercept=False,
    )
    c_session = fit_logistic_l2(
        x,
        source["target_label"].to_numpy(),
        regularization=regularization_selection["models"]["C_session"][
            "selected_lambda"
        ],
        offset=_logit(p_session),
        fit_intercept=False,
    )
    shape_columns = list(shape_feature_columns or columns)
    shape_scaler = fit_scaler(source, shape_columns)
    c_shape = fit_logistic_l2(
        transform_features(source, shape_scaler),
        source["target_label"].to_numpy(),
        regularization=regularization_selection["models"]["C_session"][
            "selected_lambda"
        ],
        offset=_logit(p_session),
        fit_intercept=False,
    )
    payload = {
        "endpoint": endpoint,
        "feature_columns": columns,
        "A_dev": age,
        "A_session": session,
        "A_level": level,
        "scaler": scaler,
        "B": b,
        "C_dev": c_dev,
        "C_session": c_session,
        "shape_feature_columns": shape_columns,
        "shape_scaler": shape_scaler,
        "C_shape": c_shape,
        "regularization_selection_sha256": regularization_selection["sha256"],
    }
    payload["fitted_parameter_sha256"] = _canonical_hash(payload)
    return payload


def predict_endpoint_bundle(
    frame: pd.DataFrame,
    bundle: dict,
    common_parameters: dict,
) -> pd.DataFrame:
    endpoint = bundle["endpoint"]
    source = frame[frame["endpoint"].eq(endpoint)].reset_index(drop=True)
    x = transform_features(source, bundle["scaler"])
    p_common = predict_common_baseline(source, common_parameters)
    p_dev = predict_age_baseline(source, bundle["A_dev"])
    p_session = predict_session_baseline(source, p_dev, bundle["A_session"])
    output = source[
        [
            "risk_bin_id",
            "cohort_id",
            "interval_id",
            "endpoint",
            "bin_width_ms",
            "bin_start",
            "session_date",
            "analysis_role",
            "target_label",
            "state_age_seconds",
        ]
    ].copy()
    output["p_A_common"] = p_common
    output["p_A_level"] = predict_offset_intercept(p_common, bundle["A_level"])
    output["p_A_dev"] = p_dev
    output["p_A_session"] = p_session
    output["p_B"] = predict_logistic(x, bundle["B"])
    output["p_C_dev"] = predict_logistic(
        x,
        bundle["C_dev"],
        offset=_logit(p_dev),
    )
    output["p_C_session"] = predict_logistic(
        x,
        bundle["C_session"],
        offset=_logit(p_session),
    )
    output["p_C_shape"] = predict_logistic(
        transform_features(source, bundle["shape_scaler"]),
        bundle["C_shape"],
        offset=_logit(p_session),
    )
    return output


def interval_model_deltas(predictions: pd.DataFrame) -> pd.DataFrame:
    required = [
        "interval_id",
        "endpoint",
        "session_date",
        "analysis_role",
        "target_label",
        "p_A_common",
        "p_A_level",
        "p_A_dev",
        "p_A_session",
        "p_B",
        "p_C_dev",
        "p_C_session",
        "p_C_shape",
    ]
    _require_columns(predictions, required)
    source = predictions.copy()
    model_columns = [
        "A_common",
        "A_level",
        "A_dev",
        "A_session",
        "B",
        "C_dev",
        "C_session",
        "C_shape",
    ]
    for model in model_columns:
        source[f"ll_{model}"] = bernoulli_log_likelihood(
            source["target_label"].to_numpy(), source[f"p_{model}"].to_numpy()
        )
    aggregations = {f"ll_{model}": "sum" for model in model_columns}
    aggregations.update({"target_label": "sum", "risk_bin_id": "size"})
    grouped = source.groupby(
        ["endpoint", "interval_id", "session_date", "analysis_role"],
        sort=True,
        as_index=False,
    ).agg(aggregations).rename(
        columns={"target_label": "target_count", "risk_bin_id": "bin_count"}
    )
    grouped["C_dev_minus_A_dev"] = grouped["ll_C_dev"] - grouped["ll_A_dev"]
    grouped["C_dev_minus_B"] = grouped["ll_C_dev"] - grouped["ll_B"]
    grouped["A_session_minus_A_dev"] = (
        grouped["ll_A_session"] - grouped["ll_A_dev"]
    )
    grouped["C_session_minus_A_session"] = (
        grouped["ll_C_session"] - grouped["ll_A_session"]
    )
    grouped["C_session_minus_B"] = grouped["ll_C_session"] - grouped["ll_B"]
    grouped["C_shape_minus_A_session"] = (
        grouped["ll_C_shape"] - grouped["ll_A_session"]
    )
    grouped["A_level_minus_A_common"] = (
        grouped["ll_A_level"] - grouped["ll_A_common"]
    )
    grouped["A_dev_minus_A_level"] = grouped["ll_A_dev"] - grouped["ll_A_level"]
    return grouped


def deterministic_cluster_bootstrap(
    values: Iterable[float],
    *,
    draws: int = 5000,
    seed: int = 5003,
    one_sided_alpha: float = 0.016666666666666666,
) -> dict:
    array = np.asarray(list(values), dtype=float)
    if not len(array):
        return {
            "cluster_count": 0,
            "draws": draws,
            "mean": None,
            "ci95_low": None,
            "ci95_high": None,
            "familywise_one_sided_low": None,
        }
    rng = np.random.default_rng(seed)
    estimates = np.empty(draws, dtype=float)
    for start in range(0, draws, 250):
        end = min(start + 250, draws)
        indices = rng.integers(0, len(array), size=(end - start, len(array)))
        estimates[start:end] = array[indices].mean(axis=1)
    return {
        "cluster_count": int(len(array)),
        "draws": int(draws),
        "mean": float(array.mean()),
        "ci95_low": float(np.quantile(estimates, 0.025)),
        "ci95_high": float(np.quantile(estimates, 0.975)),
        "familywise_one_sided_low": float(np.quantile(estimates, one_sided_alpha)),
    }
