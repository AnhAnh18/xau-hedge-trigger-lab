"""State-age-only baseline models and inference for M5-002."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Iterable

import numpy as np
import pandas as pd


AGE_BUCKET_BOUNDS = [0, 1, 2, 3, 5, 6, 8, 10, 20, 30, 60, np.inf]
AGE_BUCKET_LABELS = [
    "age_0_1",
    "age_1_2",
    "age_2_3",
    "age_3_5",
    "age_5_6",
    "age_6_8",
    "age_8_10",
    "age_10_20",
    "age_20_30",
    "age_30_60",
    "age_60_inf",
]
MODEL_PREDICTOR_ALLOWLIST = [f"bucket__{label}" for label in AGE_BUCKET_LABELS]
FIT_COHORT = "internal_2026_07_23_24"
FIT_SPLIT = "development"
PRIMARY_ALPHA = 0.5
SMOOTHING_SENSITIVITY = (0.0, 0.5, 1.0)
PROBABILITY_EPSILON = 1e-12


def _require_columns(frame: pd.DataFrame, required: Iterable[str]) -> None:
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing required columns: {missing}")


def attach_age_buckets(bins: pd.DataFrame) -> pd.DataFrame:
    _require_columns(bins, ["state_age_seconds"])
    output = bins.copy()
    output["state_age_bucket"] = pd.cut(
        output["state_age_seconds"],
        bins=AGE_BUCKET_BOUNDS,
        labels=AGE_BUCKET_LABELS,
        right=False,
        include_lowest=True,
    ).astype("string")
    if output["state_age_bucket"].isna().any():
        raise ValueError("Every non-negative state age must map to a bucket")
    return output


def build_design_matrix(bins: pd.DataFrame) -> pd.DataFrame:
    """Return row identity plus the explicit reviewed predictor allowlist."""
    _require_columns(bins, ["risk_bin_id", "state_age_seconds"])
    bucketed = attach_age_buckets(bins)
    output = pd.DataFrame({"risk_bin_id": bucketed["risk_bin_id"].astype(str)})
    for label, predictor in zip(AGE_BUCKET_LABELS, MODEL_PREDICTOR_ALLOWLIST):
        output[predictor] = bucketed["state_age_bucket"].eq(label).astype("int8")
    if not (output[MODEL_PREDICTOR_ALLOWLIST].sum(axis=1) == 1).all():
        raise AssertionError("Exactly one state-age bucket must be active")
    return output


def _smoothed_probability(events: int, exposure: int, alpha: float) -> float | None:
    if alpha < 0:
        raise ValueError("Smoothing alpha cannot be negative")
    if exposure == 0:
        return None
    return float((events + alpha) / (exposure + 2 * alpha))


def _parameter_hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def fit_state_age_baselines(
    bins: pd.DataFrame,
    *,
    alpha: float = PRIMARY_ALPHA,
) -> dict:
    """Fit endpoint-specific constants and age buckets on development only."""
    required = [
        "cohort_id",
        "split",
        "endpoint",
        "target_label",
        "state_age_seconds",
        "is_primary_model_eligible",
    ]
    _require_columns(bins, required)
    source = attach_age_buckets(bins)
    development = source[
        source["cohort_id"].eq(FIT_COHORT)
        & source["split"].eq(FIT_SPLIT)
        & source["is_primary_model_eligible"]
    ].copy()
    if development.empty:
        raise ValueError("No eligible internal development bins")

    endpoints = {}
    for endpoint, group in development.groupby("endpoint", sort=True):
        total_bins = int(len(group))
        total_events = int(group["target_label"].sum())
        constant_probability = _smoothed_probability(
            total_events,
            total_bins,
            alpha,
        )
        buckets = {}
        for label in AGE_BUCKET_LABELS:
            bucket = group[group["state_age_bucket"] == label]
            exposure = int(len(bucket))
            events = int(bucket["target_label"].sum())
            probability = _smoothed_probability(events, exposure, alpha)
            buckets[label] = {
                "exposure_bins": exposure,
                "target_events": events,
                "probability": probability,
                "has_zero_development_events": exposure > 0 and events == 0,
                "has_no_development_exposure": exposure == 0,
            }
        endpoints[str(endpoint)] = {
            "constant": {
                "exposure_bins": total_bins,
                "target_events": total_events,
                "probability": constant_probability,
            },
            "age_buckets": buckets,
        }

    payload = {
        "schema_version": 1,
        "fit_cohort": FIT_COHORT,
        "fit_split": FIT_SPLIT,
        "alpha": float(alpha),
        "bucket_bounds": [
            "inf" if np.isinf(value) else float(value)
            for value in AGE_BUCKET_BOUNDS
        ],
        "bucket_labels": AGE_BUCKET_LABELS,
        "endpoints": endpoints,
    }
    payload["fitted_parameter_sha256"] = _parameter_hash(payload)
    return payload


def predict_state_age_baselines(bins: pd.DataFrame, parameters: dict) -> pd.DataFrame:
    required = [
        "risk_bin_id",
        "cohort_id",
        "interval_id",
        "endpoint",
        "split",
        "target_label",
        "state_age_seconds",
        "is_primary_model_eligible",
    ]
    _require_columns(bins, required)
    source = attach_age_buckets(bins)
    records = []
    for row in source.itertuples(index=False):
        endpoint = parameters["endpoints"].get(str(row.endpoint))
        if endpoint is None:
            raise ValueError(f"Endpoint missing from fitted parameters: {row.endpoint}")
        constant = endpoint["constant"]["probability"]
        bucket = endpoint["age_buckets"][str(row.state_age_bucket)]
        age_probability = bucket["probability"]
        used_fallback = age_probability is None
        if used_fallback:
            age_probability = constant
        records.append(
            {
                "risk_bin_id": str(row.risk_bin_id),
                "cohort_id": str(row.cohort_id),
                "interval_id": str(row.interval_id),
                "endpoint": str(row.endpoint),
                "split": str(row.split),
                "target_label": int(row.target_label),
                "state_age_bucket": str(row.state_age_bucket),
                "is_primary_model_eligible": bool(row.is_primary_model_eligible),
                "p_const": float(constant),
                "p_age": float(age_probability),
                "age_bucket_constant_fallback": bool(used_fallback),
            }
        )
    output = pd.DataFrame(records)
    for column in ["p_const", "p_age"]:
        output[column] = output[column].clip(
            lower=PROBABILITY_EPSILON,
            upper=1 - PROBABILITY_EPSILON,
        )
    return output


def _bernoulli_log_likelihood(labels: np.ndarray, probabilities: np.ndarray) -> float:
    probabilities = np.clip(
        probabilities.astype(float),
        PROBABILITY_EPSILON,
        1 - PROBABILITY_EPSILON,
    )
    labels = labels.astype(float)
    return float(
        np.sum(labels * np.log(probabilities) + (1 - labels) * np.log1p(-probabilities))
    )


def interval_occurrence_deltas(predictions: pd.DataFrame) -> pd.DataFrame:
    """Paired per-interval occurrence LL increments A_age - A_const."""
    _require_columns(
        predictions,
        ["interval_id", "endpoint", "target_label", "p_const", "p_age"],
    )
    records = []
    for (endpoint, interval_id), group in predictions.groupby(
        ["endpoint", "interval_id"], sort=True
    ):
        labels = group["target_label"].to_numpy()
        constant_ll = _bernoulli_log_likelihood(labels, group["p_const"].to_numpy())
        age_ll = _bernoulli_log_likelihood(labels, group["p_age"].to_numpy())
        records.append(
            {
                "endpoint": str(endpoint),
                "interval_id": str(interval_id),
                "constant_log_likelihood": constant_ll,
                "age_log_likelihood": age_ll,
                "age_minus_constant": age_ll - constant_ll,
                "target_count": int(labels.sum()),
                "bin_count": int(len(group)),
            }
        )
    return pd.DataFrame(records)


def _logsumexp(values: np.ndarray) -> float:
    maximum = float(np.max(values))
    return maximum + float(np.log(np.exp(values - maximum).sum()))


def conditional_timing_deltas(predictions: pd.DataFrame) -> pd.DataFrame:
    """Conditional event-bin log probability versus uniform timing."""
    _require_columns(
        predictions,
        ["interval_id", "endpoint", "target_label", "p_age"],
    )
    records = []
    for (endpoint, interval_id), group in predictions.groupby(
        ["endpoint", "interval_id"], sort=True
    ):
        if int(group["target_label"].sum()) != 1:
            continue
        event_position = int(np.flatnonzero(group["target_label"].to_numpy() == 1)[0])
        probabilities = np.clip(
            group["p_age"].to_numpy(dtype=float),
            PROBABILITY_EPSILON,
            1 - PROBABILITY_EPSILON,
        )
        eta = np.log(probabilities) - np.log1p(-probabilities)
        event_log_probability = float(eta[event_position] - _logsumexp(eta))
        uniform_log_probability = -float(np.log(len(group)))
        event_probability = float(np.exp(event_log_probability))
        rank = int((probabilities > probabilities[event_position]).sum()) + 1
        records.append(
            {
                "endpoint": str(endpoint),
                "interval_id": str(interval_id),
                "conditional_event_log_probability": event_log_probability,
                "uniform_event_log_probability": uniform_log_probability,
                "conditional_minus_uniform": (
                    event_log_probability - uniform_log_probability
                ),
                "conditional_event_probability": event_probability,
                "event_rank": rank,
                "bin_count": int(len(group)),
            }
        )
    return pd.DataFrame(records)


def deterministic_cluster_bootstrap(
    values: Iterable[float],
    *,
    draws: int = 5000,
    seed: int = 5002,
) -> dict:
    array = np.asarray(list(values), dtype=float)
    if not len(array):
        return {
            "cluster_count": 0,
            "draws": draws,
            "mean": None,
            "ci95_low": None,
            "ci95_high": None,
        }
    rng = np.random.default_rng(seed)
    estimates = np.empty(draws, dtype=float)
    chunk_size = 250
    for start in range(0, draws, chunk_size):
        end = min(start + chunk_size, draws)
        indices = rng.integers(0, len(array), size=(end - start, len(array)))
        estimates[start:end] = array[indices].mean(axis=1)
    return {
        "cluster_count": int(len(array)),
        "draws": int(draws),
        "mean": float(array.mean()),
        "ci95_low": float(np.quantile(estimates, 0.025)),
        "ci95_high": float(np.quantile(estimates, 0.975)),
    }


def evaluate_holdout(
    predictions: pd.DataFrame,
    *,
    draws: int = 5000,
    seed: int = 5002,
) -> dict:
    """Evaluate frozen parameters on internal primary holdout only."""
    holdout = predictions[
        predictions["cohort_id"].eq(FIT_COHORT)
        & predictions["split"].eq("holdout")
        & predictions["is_primary_model_eligible"]
    ].copy()
    output = {}
    for endpoint_index, endpoint in enumerate(sorted(holdout["endpoint"].unique())):
        group = holdout[holdout["endpoint"] == endpoint]
        occurrence = interval_occurrence_deltas(group)
        conditional = conditional_timing_deltas(group)
        endpoint_seed = seed + endpoint_index * 100
        output[str(endpoint)] = {
            "holdout_bins": int(len(group)),
            "holdout_intervals": int(group["interval_id"].nunique()),
            "holdout_target_events": int(group["target_label"].sum()),
            "primary_conditional_timing": deterministic_cluster_bootstrap(
                conditional["conditional_minus_uniform"] if not conditional.empty else [],
                draws=draws,
                seed=endpoint_seed + 1,
            ),
            "secondary_occurrence_likelihood": deterministic_cluster_bootstrap(
                occurrence["age_minus_constant"] if not occurrence.empty else [],
                draws=draws,
                seed=endpoint_seed + 2,
            ),
            "diagnostic_event_rank_mean": (
                float(conditional["event_rank"].mean())
                if not conditional.empty
                else None
            ),
            "diagnostic_raw_calibration": {
                "observed_rate": float(group["target_label"].mean()),
                "mean_p_const": float(group["p_const"].mean()),
                "mean_p_age": float(group["p_age"].mean()),
            },
        }
    return output


def per_session_base_hazard(bins: pd.DataFrame) -> list[dict]:
    """Comparable common-hour session variation; never used for fitting."""
    _require_columns(
        bins,
        [
            "cohort_id",
            "bin_start",
            "endpoint",
            "target_label",
            "bin_width_ms",
            "is_common_hours",
        ],
    )
    one_second = bins[
        (bins["bin_width_ms"] == 1000) & bins["is_common_hours"]
    ].copy()
    one_second["session_date"] = pd.to_datetime(one_second["bin_start"]).dt.strftime(
        "%Y-%m-%d"
    )
    records = []
    for (day, endpoint), group in one_second.groupby(
        ["session_date", "endpoint"], sort=True
    ):
        events = int(group["target_label"].sum())
        exposure = int(len(group))
        records.append(
            {
                "session_date": str(day),
                "weekday": pd.Timestamp(day).day_name(),
                "endpoint": str(endpoint),
                "risk_bins": exposure,
                "target_events": events,
                "events_per_1000_risk_seconds": (
                    float(1000 * events / exposure) if exposure else None
                ),
                "role": (
                    "internal"
                    if str(day) in {"2026-07-23", "2026-07-24"}
                    else "retrospective_supplemental_non_gating"
                ),
                "server_hours": "12:00-24:00",
            }
        )
    return records


def coherent_timing_verdict(
    one_second: dict,
    five_hundred_ms: dict,
) -> str:
    """Classify adjacent-width coherence without overcalling null estimates."""
    if one_second["ci95_low"] is None or five_hundred_ms["ci95_low"] is None:
        return "inconclusive"
    if one_second["ci95_low"] > 0 and five_hundred_ms["ci95_low"] > 0:
        return "internal_timing_supported_external_pending"
    if one_second["ci95_high"] < 0 and five_hundred_ms["ci95_high"] < 0:
        return "internal_timing_rejected_external_pending"
    one_straddles = one_second["ci95_low"] <= 0 <= one_second["ci95_high"]
    half_straddles = (
        five_hundred_ms["ci95_low"] <= 0 <= five_hundred_ms["ci95_high"]
    )
    if one_straddles and half_straddles:
        return "inconclusive_external_pending"
    if (
        one_second["ci95_low"] > 0
        and five_hundred_ms["ci95_high"] < 0
    ) or (
        one_second["ci95_high"] < 0
        and five_hundred_ms["ci95_low"] > 0
    ):
        return "mixed_across_adjacent_widths"
    return "weak_or_inconclusive_external_pending"
