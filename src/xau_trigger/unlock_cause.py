"""M5-004 event-level unlock-cause features and deterministic models."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Iterable

import numpy as np
import pandas as pd

from xau_trigger.price_features import CausalTickFeatureEngine, _timestamp_ns
from xau_trigger.price_inference import (
    _logit,
    bernoulli_log_likelihood,
    deterministic_cluster_bootstrap,
    deterministic_group_kfold,
    fit_logistic_l2,
    predict_logistic,
)


CAUSE_FEATURES = (
    "mid_change_2s",
    "mid_change_5s",
    "tick_imbalance_2s",
    "tick_imbalance_5s",
    "range_position_2s",
    "range_position_5s",
    "range_position_10s",
    "prior_upper_boundary_touch_2s",
    "prior_lower_boundary_touch_2s",
    "prior_upper_boundary_touch_5s",
    "prior_lower_boundary_touch_5s",
    "state_start_displacement",
)

BINARY_TOUCH_FEATURES = (
    "prior_upper_boundary_touch_2s",
    "prior_lower_boundary_touch_2s",
    "prior_upper_boundary_touch_5s",
    "prior_lower_boundary_touch_5s",
)

FEATURE_GROUPS = {
    "momentum": (
        "mid_change_2s",
        "mid_change_5s",
        "tick_imbalance_2s",
        "tick_imbalance_5s",
    ),
    "range_location": (
        "range_position_2s",
        "range_position_5s",
        "range_position_10s",
    ),
    "boundary_side": BINARY_TOUCH_FEATURES,
    "state_path": ("state_start_displacement",),
}

AGE_BUCKET_BOUNDS = (5.0, 6.0, 8.0, 10.0, 20.0, 30.0, 60.0, np.inf)
AGE_BUCKET_LABELS = (
    "age_5_6",
    "age_6_8",
    "age_8_10",
    "age_10_20",
    "age_20_30",
    "age_30_60",
    "age_60_inf",
)
LAMBDA_GRID = (0.0001, 0.001, 0.01, 0.1, 1.0, 10.0)


def canonical_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def _require_columns(frame: pd.DataFrame, required: Iterable[str]) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def _sample_id(cohort_id: object, interval_id: object, width_ms: object) -> str:
    encoded = f"{cohort_id}|{interval_id}|{int(width_ms)}".encode("utf-8")
    return sha256(encoded).hexdigest()


def prepare_unlock_events(feature_audit: pd.DataFrame) -> pd.DataFrame:
    """Select the one terminal row for every registered unlock event."""
    required = [
        "risk_bin_id",
        "cohort_id",
        "interval_id",
        "endpoint",
        "bin_width_ms",
        "bin_start",
        "bin_end",
        "session_date",
        "analysis_role",
        "state_age_seconds",
        "target_label",
        "following_event_type",
        "interval_start",
        "is_common_hours",
        "is_cross_split_interval",
    ]
    _require_columns(feature_audit, required)
    source = feature_audit[
        feature_audit["endpoint"].eq("unlock_occurrence")
        & feature_audit["target_label"].eq(1)
    ].copy()
    if source.empty:
        raise ValueError("No unlock target events found")
    unexpected = ~source["following_event_type"].isin(
        ["UNLOCK_TO_BUY", "UNLOCK_TO_SELL"]
    )
    if unexpected.any():
        values = sorted(source.loc[unexpected, "following_event_type"].astype(str).unique())
        raise AssertionError(f"Unexpected unlock target causes: {values}")
    if not source["is_common_hours"].all():
        raise AssertionError("M5-004 source contains a non-common-hour event")
    if source["is_cross_split_interval"].any():
        raise AssertionError("M5-004 source contains a cross-split interval")
    source["interval_id"] = source["interval_id"].astype(str)
    duplicate_keys = ["cohort_id", "interval_id", "bin_width_ms"]
    if source.duplicated(duplicate_keys, keep=False).any():
        raise AssertionError("Duplicate M5-004 event key")
    source["cause_label"] = source["following_event_type"].eq(
        "UNLOCK_TO_BUY"
    ).astype(int)
    source["group_id"] = (
        source["cohort_id"].astype(str) + ":" + source["interval_id"]
    )
    source["sample_id"] = [
        _sample_id(row.cohort_id, row.interval_id, row.bin_width_ms)
        for row in source.itertuples(index=False)
    ]
    if source["sample_id"].duplicated().any():
        raise AssertionError("Generated M5-004 sample IDs are not unique")
    return source.sort_values(
        ["bin_width_ms", "cohort_id", "bin_start", "interval_id"],
        kind="stable",
    ).reset_index(drop=True)


def _cohort_feature_frame(
    events: pd.DataFrame,
    ticks: pd.DataFrame,
    gaps: pd.DataFrame | None,
) -> pd.DataFrame:
    engine = CausalTickFeatureEngine(ticks, gaps)
    anchors_ns = _timestamp_ns(events["bin_start"])
    interval_start_ns = _timestamp_ns(events["interval_start"])
    rolling = {
        window: engine.rolling_stats(anchors_ns, window)
        for window in (2, 5, 10)
    }
    touches = {
        window: engine.h2_touches(anchors_ns, window)
        for window in (2, 5)
    }
    reference_valid, reference_mid = engine.state_start_reference(
        interval_start_ns
    )
    # The state-start displacement is itself a variable-length causal
    # lookback.  A quote gap anywhere between state start and anchor makes
    # that predictor invalid, even when the short rolling windows are valid.
    reference_valid &= ~engine._crosses_gap(interval_start_ns, anchors_ns)
    output = pd.DataFrame({"sample_id": events["sample_id"].astype(str)})
    for window in (2, 5, 10):
        stats = rolling[window]
        width = stats.maximum_mid - stats.minimum_mid
        output[f"window_{window}s_valid"] = stats.valid
        output[f"range_position_{window}s"] = np.divide(
            stats.current_mid - stats.minimum_mid,
            width,
            out=np.full(len(events), 0.5, dtype=float),
            where=width != 0,
        )
        output.loc[
            ~stats.valid, f"range_position_{window}s"
        ] = np.nan
    for window in (2, 5):
        stats = rolling[window]
        output[f"mid_change_{window}s"] = (
            stats.current_mid - stats.first_mid
        )
        output[f"tick_imbalance_{window}s"] = stats.tick_imbalance
        valid, high_touch, low_touch = touches[window]
        output[f"h2_{window}s_valid"] = valid
        output[f"prior_upper_boundary_touch_{window}s"] = high_touch.astype(
            float
        )
        output[f"prior_lower_boundary_touch_{window}s"] = low_touch.astype(
            float
        )
        for column in [
            f"mid_change_{window}s",
            f"tick_imbalance_{window}s",
        ]:
            output.loc[~stats.valid, column] = np.nan
        for column in [
            f"prior_upper_boundary_touch_{window}s",
            f"prior_lower_boundary_touch_{window}s",
        ]:
            output.loc[~valid, column] = np.nan
    current_mid = rolling[10].current_mid
    output["state_start_reference_valid"] = reference_valid
    output["current_snapshot_valid"] = (
        np.isfinite(current_mid) & np.isfinite(rolling[10].spread)
    )
    output["state_start_displacement"] = current_mid - reference_mid
    output.loc[
        ~reference_valid, "state_start_displacement"
    ] = np.nan
    output["anchor_mid"] = current_mid
    output["spread_at_anchor"] = rolling[10].spread
    return output


def build_unlock_cause_dataset(
    feature_audit: pd.DataFrame,
    ticks_by_cohort: dict[str, pd.DataFrame],
    gaps_by_cohort: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build separated audit, predictor, target, and model-design tables."""
    events = prepare_unlock_events(feature_audit)
    feature_frames = []
    for cohort_id, group in events.groupby("cohort_id", sort=True):
        if cohort_id not in ticks_by_cohort:
            raise ValueError(f"Missing ticks for cohort: {cohort_id}")
        feature_frames.append(
            _cohort_feature_frame(
                group.reset_index(drop=True),
                ticks_by_cohort[cohort_id],
                gaps_by_cohort.get(cohort_id),
            )
        )
    features = pd.concat(feature_frames, ignore_index=True)
    recomputed_columns = [
        column for column in features.columns if column != "sample_id"
    ]
    source_events = events.drop(
        columns=[
            column
            for column in recomputed_columns
            if column in events.columns
        ]
    )
    source = source_events.merge(
        # M5-004 deliberately recomputes its raw-directional features and
        # validity flags from ticks.  Do not retain same-named M5-003 columns,
        # which belong to the earlier endpoint-specific feature contract.
        features,
        on="sample_id",
        how="left",
        validate="one_to_one",
    )
    source["first_exclusion_reason"] = None
    rules = [
        ("state_age_before_5s", source["state_age_seconds"].lt(5.0)),
        ("window_10s_invalid", ~source["window_10s_valid"]),
        ("window_5s_invalid", ~source["window_5s_valid"]),
        ("window_2s_invalid", ~source["window_2s_valid"]),
        ("h2_5s_invalid", ~source["h2_5s_valid"]),
        ("h2_2s_invalid", ~source["h2_2s_valid"]),
        (
            "state_start_reference_invalid",
            ~source["state_start_reference_valid"],
        ),
        ("current_snapshot_invalid", ~source["current_snapshot_valid"]),
    ]
    for reason, mask in rules:
        assign = source["first_exclusion_reason"].isna() & mask
        source.loc[assign, "first_exclusion_reason"] = reason
    all_features_valid = source[list(CAUSE_FEATURES)].notna().all(axis=1)
    source["is_joint_valid"] = (
        source["first_exclusion_reason"].isna() & all_features_valid
    )
    if not (
        source.loc[source["is_joint_valid"], list(CAUSE_FEATURES)]
        .notna()
        .all()
        .all()
    ):
        raise AssertionError("Joint-valid cause rows contain missing predictors")

    audit_columns = [
        "sample_id",
        "risk_bin_id",
        "cohort_id",
        "interval_id",
        "group_id",
        "bin_width_ms",
        "bin_start",
        "bin_end",
        "session_date",
        "analysis_role",
        "state_age_seconds",
        "following_event_type",
        "cause_label",
        "anchor_mid",
        "spread_at_anchor",
        "window_2s_valid",
        "window_5s_valid",
        "window_10s_valid",
        "h2_2s_valid",
        "h2_5s_valid",
        "state_start_reference_valid",
        "current_snapshot_valid",
        "first_exclusion_reason",
        "is_joint_valid",
    ]
    audit = source[audit_columns].copy()
    valid = source[source["is_joint_valid"]].copy()
    predictors = valid[["sample_id", *CAUSE_FEATURES]].copy()
    targets = valid[["sample_id", "cause_label"]].copy()
    design_columns = [
        "sample_id",
        "cohort_id",
        "interval_id",
        "group_id",
        "bin_width_ms",
        "bin_start",
        "session_date",
        "analysis_role",
        "state_age_seconds",
        "cause_label",
        *CAUSE_FEATURES,
    ]
    design = valid[design_columns].copy()
    return audit, predictors, targets, design


def attach_cause_age_bucket(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["cause_age_bucket"] = pd.cut(
        output["state_age_seconds"].astype(float),
        bins=AGE_BUCKET_BOUNDS,
        labels=AGE_BUCKET_LABELS,
        right=False,
    )
    if output["cause_age_bucket"].isna().any():
        raise ValueError("Cause row lies outside the registered age buckets")
    return output


def fit_const_cause(frame: pd.DataFrame, *, alpha: float = 0.5) -> dict:
    labels = frame["cause_label"].to_numpy(dtype=float)
    n = int(len(labels))
    positive = int(labels.sum())
    if not n:
        raise ValueError("Cannot fit cause prior without development events")
    payload = {
        "alpha": float(alpha),
        "events": n,
        "unlock_to_buy": positive,
        "probability": float((positive + alpha) / (n + 2 * alpha)),
    }
    payload["fitted_parameter_sha256"] = canonical_hash(payload)
    return payload


def fit_age_cause(frame: pd.DataFrame, *, alpha: float = 0.5) -> dict:
    source = attach_cause_age_bucket(frame)
    buckets = {}
    for label in AGE_BUCKET_LABELS:
        group = source[source["cause_age_bucket"].eq(label)]
        events = int(len(group))
        positive = int(group["cause_label"].sum())
        buckets[label] = {
            "events": events,
            "unlock_to_buy": positive,
            "probability": (
                None
                if events == 0
                else float((positive + alpha) / (events + 2 * alpha))
            ),
        }
    payload = {
        "alpha": float(alpha),
        "bucket_bounds": [
            "inf" if np.isinf(value) else float(value)
            for value in AGE_BUCKET_BOUNDS
        ],
        "bucket_labels": list(AGE_BUCKET_LABELS),
        "age_buckets": buckets,
    }
    payload["fitted_parameter_sha256"] = canonical_hash(payload)
    return payload


def predict_age_cause(frame: pd.DataFrame, parameters: dict) -> np.ndarray:
    source = attach_cause_age_bucket(frame)
    probabilities = []
    for label in source["cause_age_bucket"].astype(str):
        bucket = parameters["age_buckets"][label]
        if bucket["events"] == 0 or bucket["probability"] is None:
            raise ValueError(
                f"Active evaluation age bucket has zero training events: {label}"
            )
        probabilities.append(float(bucket["probability"]))
    return np.asarray(probabilities, dtype=float)


def fit_cause_preprocessor(
    frame: pd.DataFrame,
    feature_columns: Iterable[str],
) -> dict:
    columns = list(feature_columns)
    values = frame[columns].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Cause predictors must be finite")
    means = values.mean(axis=0)
    scales = values.std(axis=0, ddof=0)
    for index, column in enumerate(columns):
        if column in BINARY_TOUCH_FEATURES:
            means[index] = 0.0
            scales[index] = 1.0
        elif scales[index] == 0:
            scales[index] = 1.0
    payload = {
        "feature_columns": columns,
        "binary_unchanged": list(
            column for column in columns if column in BINARY_TOUCH_FEATURES
        ),
        "means": [float(value) for value in means],
        "scales": [float(value) for value in scales],
    }
    payload["sha256"] = canonical_hash(payload)
    return payload


def transform_cause_features(frame: pd.DataFrame, preprocessor: dict) -> np.ndarray:
    values = frame[preprocessor["feature_columns"]].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Cause predictors must be finite")
    return (
        values - np.asarray(preprocessor["means"], dtype=float)
    ) / np.asarray(preprocessor["scales"], dtype=float)


def _score_per_event(
    frame: pd.DataFrame,
    probabilities: np.ndarray,
) -> float:
    return float(
        bernoulli_log_likelihood(
            frame["cause_label"].to_numpy(),
            probabilities,
        ).mean()
    )


def select_cause_regularization(
    development: pd.DataFrame,
    *,
    feature_columns: Iterable[str] = CAUSE_FEATURES,
    lambdas: Iterable[float] = LAMBDA_GRID,
    n_splits: int = 5,
) -> dict:
    columns = list(feature_columns)
    groups = development["group_id"].astype(str)
    splits = deterministic_group_kfold(groups, n_splits=n_splits)
    prepared = []
    fold_proof = []
    for fold, (train_index, validation_index) in enumerate(splits):
        train = development.iloc[train_index].reset_index(drop=True)
        validation = development.iloc[validation_index].reset_index(drop=True)
        train_groups = set(train["group_id"].astype(str))
        validation_groups = set(validation["group_id"].astype(str))
        if train_groups & validation_groups:
            raise AssertionError("Cause GroupKFold leaked a source interval")
        preprocessor = fit_cause_preprocessor(train, columns)
        age = fit_age_cause(train)
        train_age = predict_age_cause(train, age)
        validation_age = predict_age_cause(validation, age)
        prepared.append(
            {
                "train": train,
                "validation": validation,
                "x_train": transform_cause_features(train, preprocessor),
                "x_validation": transform_cause_features(
                    validation, preprocessor
                ),
                "train_age": train_age,
                "validation_age": validation_age,
            }
        )
        fold_proof.append(
            {
                "fold": fold,
                "training_events": int(len(train)),
                "validation_events": int(len(validation)),
                "training_groups": int(len(train_groups)),
                "validation_groups": int(len(validation_groups)),
                "group_overlap": 0,
            }
        )

    models = {}
    for model in ("B_price_cause", "C_age_price_cause"):
        scores = []
        for regularization in lambdas:
            fold_scores = []
            for item in prepared:
                parameters = fit_logistic_l2(
                    item["x_train"],
                    item["train"]["cause_label"].to_numpy(),
                    regularization=float(regularization),
                    offset=(
                        _logit(item["train_age"])
                        if model == "C_age_price_cause"
                        else None
                    ),
                    fit_intercept=model == "B_price_cause",
                )
                probabilities = predict_logistic(
                    item["x_validation"],
                    parameters,
                    offset=(
                        _logit(item["validation_age"])
                        if model == "C_age_price_cause"
                        else None
                    ),
                )
                fold_scores.append(
                    _score_per_event(item["validation"], probabilities)
                )
            mean = float(np.mean(fold_scores))
            standard_error = float(
                np.std(fold_scores, ddof=1) / np.sqrt(len(fold_scores))
            )
            scores.append(
                {
                    "lambda": float(regularization),
                    "fold_scores": [float(value) for value in fold_scores],
                    "mean_score": mean,
                    "standard_error": standard_error,
                }
            )
        best = max(scores, key=lambda row: row["mean_score"])
        threshold = best["mean_score"] - best["standard_error"]
        selected = max(
            row["lambda"]
            for row in scores
            if row["mean_score"] >= threshold
        )
        models[model] = {
            "selected_lambda": float(selected),
            "best_lambda": float(best["lambda"]),
            "one_standard_error_threshold": float(threshold),
            "scores": scores,
        }
    payload = {
        "folds": fold_proof,
        "models": models,
        "group": "cohort_id_colon_interval_id",
    }
    payload["sha256"] = canonical_hash(payload)
    return payload


def fit_cause_bundle(
    development: pd.DataFrame,
    regularization_selection: dict,
    *,
    feature_columns: Iterable[str] = CAUSE_FEATURES,
) -> dict:
    columns = list(feature_columns)
    preprocessor = fit_cause_preprocessor(development, columns)
    x = transform_cause_features(development, preprocessor)
    labels = development["cause_label"].to_numpy()
    a_const = fit_const_cause(development)
    a_age = fit_age_cause(development)
    p_age = predict_age_cause(development, a_age)
    b = fit_logistic_l2(
        x,
        labels,
        regularization=regularization_selection["models"][
            "B_price_cause"
        ]["selected_lambda"],
        fit_intercept=True,
    )
    c = fit_logistic_l2(
        x,
        labels,
        regularization=regularization_selection["models"][
            "C_age_price_cause"
        ]["selected_lambda"],
        offset=_logit(p_age),
        fit_intercept=False,
    )
    ablations = {}
    for group, removed in FEATURE_GROUPS.items():
        remaining = [column for column in columns if column not in removed]
        ablation_preprocessor = fit_cause_preprocessor(
            development, remaining
        )
        ablations[group] = {
            "removed_features": list(removed),
            "remaining_features": remaining,
            "preprocessor": ablation_preprocessor,
            "C_age_price_cause": fit_logistic_l2(
                transform_cause_features(
                    development, ablation_preprocessor
                ),
                labels,
                regularization=regularization_selection["models"][
                    "C_age_price_cause"
                ]["selected_lambda"],
                offset=_logit(p_age),
                fit_intercept=False,
            ),
        }
    payload = {
        "feature_columns": columns,
        "A_const_cause": a_const,
        "A_age_cause": a_age,
        "preprocessor": preprocessor,
        "B_price_cause": b,
        "C_age_price_cause": c,
        "ablations": ablations,
        "regularization_selection_sha256": regularization_selection["sha256"],
    }
    payload["fitted_parameter_sha256"] = canonical_hash(payload)
    return payload


def predict_cause_bundle(frame: pd.DataFrame, bundle: dict) -> pd.DataFrame:
    x = transform_cause_features(frame, bundle["preprocessor"])
    p_age = predict_age_cause(frame, bundle["A_age_cause"])
    output = frame[
        [
            "sample_id",
            "cohort_id",
            "interval_id",
            "group_id",
            "bin_width_ms",
            "bin_start",
            "session_date",
            "analysis_role",
            "state_age_seconds",
            "cause_label",
        ]
    ].copy()
    output["p_A_const_cause"] = bundle["A_const_cause"]["probability"]
    output["p_A_age_cause"] = p_age
    output["p_B_price_cause"] = predict_logistic(
        x, bundle["B_price_cause"]
    )
    output["p_C_age_price_cause"] = predict_logistic(
        x,
        bundle["C_age_price_cause"],
        offset=_logit(p_age),
    )
    for group, ablation in bundle["ablations"].items():
        output[f"p_C_without_{group}"] = predict_logistic(
            transform_cause_features(frame, ablation["preprocessor"]),
            ablation["C_age_price_cause"],
            offset=_logit(p_age),
        )
    return output


def _auc(labels: np.ndarray, probabilities: np.ndarray) -> float | None:
    y = np.asarray(labels, dtype=int)
    positives = int(y.sum())
    negatives = int(len(y) - positives)
    if positives == 0 or negatives == 0:
        return None
    ranks = pd.Series(probabilities).rank(method="average").to_numpy()
    positive_rank_sum = float(ranks[y == 1].sum())
    return float(
        (positive_rank_sum - positives * (positives + 1) / 2)
        / (positives * negatives)
    )


def descriptive_classification_metrics(
    labels: np.ndarray,
    probabilities: np.ndarray,
) -> dict:
    y = np.asarray(labels, dtype=int)
    p = np.asarray(probabilities, dtype=float)
    predicted = (p >= 0.5).astype(int)
    calibration = []
    edges = np.linspace(0.0, 1.0, 11)
    for index in range(10):
        mask = (p >= edges[index]) & (
            p <= edges[index + 1] if index == 9 else p < edges[index + 1]
        )
        if mask.any():
            calibration.append(
                {
                    "bin": index,
                    "count": int(mask.sum()),
                    "mean_prediction": float(p[mask].mean()),
                    "observed_fraction": float(y[mask].mean()),
                }
            )
    return {
        "events": int(len(y)),
        "unlock_to_buy": int(y.sum()),
        "unlock_to_sell": int(len(y) - y.sum()),
        "auc": _auc(y, p),
        "brier_score": float(np.mean(np.square(p - y))),
        "accuracy_at_fixed_0_5": float(np.mean(predicted == y)),
        "confusion_matrix_at_fixed_0_5": {
            "true_negative": int(((y == 0) & (predicted == 0)).sum()),
            "false_positive": int(((y == 0) & (predicted == 1)).sum()),
            "false_negative": int(((y == 1) & (predicted == 0)).sum()),
            "true_positive": int(((y == 1) & (predicted == 1)).sum()),
        },
        "calibration": calibration,
    }


def summarize_cause_predictions(
    predictions: pd.DataFrame,
    *,
    bootstrap_draws: int = 5000,
    bootstrap_seed: int = 5004,
) -> dict:
    source = predictions.copy()
    labels = source["cause_label"].to_numpy()
    probability_columns = {
        "A_const_cause": "p_A_const_cause",
        "A_age_cause": "p_A_age_cause",
        "B_price_cause": "p_B_price_cause",
        "C_age_price_cause": "p_C_age_price_cause",
    }
    for name, column in probability_columns.items():
        source[f"ll_{name}"] = bernoulli_log_likelihood(
            labels, source[column].to_numpy()
        )
    source["C_minus_A"] = (
        source["ll_C_age_price_cause"] - source["ll_A_age_cause"]
    )
    source["C_minus_B"] = (
        source["ll_C_age_price_cause"] - source["ll_B_price_cause"]
    )
    grouped = source.groupby("group_id", sort=True, as_index=False)[
        ["C_minus_A", "C_minus_B"]
    ].sum()
    comparisons = {
        "C_age_price_cause_minus_A_age_cause": deterministic_cluster_bootstrap(
            grouped["C_minus_A"],
            draws=bootstrap_draws,
            seed=bootstrap_seed,
            one_sided_alpha=0.05,
        ),
        "C_age_price_cause_minus_B_price_cause": deterministic_cluster_bootstrap(
            grouped["C_minus_B"],
            draws=bootstrap_draws,
            seed=bootstrap_seed + 1,
            one_sided_alpha=0.05,
        ),
    }
    ablations = {}
    for index, group in enumerate(FEATURE_GROUPS):
        ll_ablation = bernoulli_log_likelihood(
            labels, source[f"p_C_without_{group}"].to_numpy()
        )
        values = pd.DataFrame(
            {
                "group_id": source["group_id"].astype(str),
                "delta": source["ll_C_age_price_cause"] - ll_ablation,
            }
        ).groupby("group_id", sort=True)["delta"].sum()
        ablations[group] = deterministic_cluster_bootstrap(
            values,
            draws=bootstrap_draws,
            seed=bootstrap_seed + 100 + index,
            one_sided_alpha=0.0125,
        )
    daily = []
    for session_date, day in source.groupby("session_date", sort=True):
        daily.append(
            {
                "session_date": str(session_date),
                "events": int(len(day)),
                "C_age_price_cause_minus_A_age_cause_mean": float(
                    day["C_minus_A"].mean()
                ),
                "C_age_price_cause_minus_B_price_cause_mean": float(
                    day["C_minus_B"].mean()
                ),
            }
        )
    return {
        "events": int(len(source)),
        "groups": int(source["group_id"].nunique()),
        "comparisons": comparisons,
        "ablations": ablations,
        "daily": daily,
        "classification": {
            name: descriptive_classification_metrics(
                labels, source[column].to_numpy()
            )
            for name, column in probability_columns.items()
        },
    }
