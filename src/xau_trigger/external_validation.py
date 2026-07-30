"""Frozen-model external validation helpers for M5-003."""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Iterable

import pandas as pd

from xau_trigger.price_inference import (
    deterministic_cluster_bootstrap,
    interval_model_deltas,
)


EXTERNAL_SESSIONS = ("2026-07-27", "2026-07-28", "2026-07-29")


def canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def verify_frozen_manifest(manifest: dict) -> None:
    expected = manifest.get("frozen_manifest_sha256")
    if not expected:
        raise ValueError("Frozen manifest hash is missing")
    source = dict(manifest)
    source.pop("frozen_manifest_sha256")
    if canonical_json_sha256(source) != expected:
        raise AssertionError("Frozen M5-003 manifest hash does not reconcile")
    if manifest.get("external_loaded_for_fit_or_evaluation") is not False:
        raise AssertionError("Frozen fit manifest must predate external evaluation")


def apply_external_acquisition_amendment(
    validation: dict,
    amendment: dict,
) -> dict:
    """Accept only the exact replicated quote gap registered pre-prediction."""
    output = deepcopy(validation)
    raw_validation_hash = output.pop("deterministic_validation_sha256", None)
    if not raw_validation_hash:
        raise AssertionError("Raw acquisition validation hash is missing")
    expected_sessions = list(amendment["external_decision_contract"]["registered_sessions"])
    if output["sessions"] != expected_sessions:
        raise AssertionError("Acquisition sessions differ from the amendment")
    if output["trade_reports"]["status"] != "PASS":
        raise AssertionError("External trade-report acquisition did not pass")
    if any(row["status"] != "PASS" for row in output["ticks"]["files"]):
        raise AssertionError("An external tick file failed structural validation")

    expected_gap = amendment["replicated_source_quote_gap"]
    gap_session = str(expected_gap["session"])
    sessions = {row["date"]: row for row in output["ticks"]["sessions"]}
    if set(sessions) != set(expected_sessions):
        raise AssertionError("External tick sessions are incomplete")
    for day in expected_sessions:
        row = sessions[day]
        if day != gap_session and row["status"] != "PASS":
            raise AssertionError(f"Unexpected acquisition failure on {day}")

    gap_row = sessions[gap_session]
    gaps = gap_row["coverage_gaps"]
    if len(gaps) != 1:
        raise AssertionError("Expected exactly one replicated external quote gap")
    observed = gaps[0]
    comparisons = {
        "start": expected_gap["start"],
        "end": expected_gap["end"],
        "duration_seconds": expected_gap["duration_seconds"],
    }
    for key, expected in comparisons.items():
        observed_value = observed[key]
        if key == "duration_seconds":
            if abs(float(observed_value) - float(expected)) > 1e-9:
                raise AssertionError("Replicated quote-gap duration changed")
        elif str(observed_value) != str(expected):
            raise AssertionError(f"Replicated quote-gap {key} changed")

    observed["classification"] = expected_gap["classification"]
    observed["replicated_by_independent_export"] = True
    gap_row["status"] = "PASS_WITH_REPLICATED_SOURCE_QUOTE_GAP"
    gap_row["has_no_intraday_coverage_gap"] = False
    output["ticks"]["status"] = "PASS_WITH_REPLICATED_SOURCE_QUOTE_GAP"
    output["status"] = "PASS_WITH_REPLICATED_SOURCE_QUOTE_GAP"
    output["amendment_id"] = amendment["amendment_id"]
    output["gap_policy"] = {
        "interpolation_allowed": False,
        "risk_support_policy": expected_gap["risk_support_policy"],
        "event_policy": expected_gap["event_policy"],
    }
    output["raw_deterministic_validation_sha256"] = raw_validation_hash
    output["deterministic_amended_validation_sha256"] = canonical_json_sha256(
        output
    )
    return output


def external_endpoint_verdict(
    metric: dict,
    per_session_means: Iterable[float],
) -> dict:
    means = [float(value) for value in per_session_means]
    if len(means) != 3:
        raise ValueError("External verdict requires exactly three sessions")
    positive_sessions = sum(value > 0 for value in means)
    mean = float(metric["mean"])
    family_low = float(metric["familywise_one_sided_low"])
    ci_high = float(metric["ci95_high"])

    if mean > 0 and family_low > 0 and positive_sessions >= 2:
        verdict = "supported"
    elif mean > 0 and family_low > 0 and positive_sessions < 2:
        verdict = "mixed/inconclusive"
    elif ci_high <= 0:
        verdict = "rejected"
    elif mean > 0:
        verdict = "weak/inconclusive"
    else:
        verdict = "inconclusive"
    return {
        "verdict": verdict,
        "positive_external_sessions": int(positive_sessions),
        "required_positive_external_sessions": 2,
        "pooled_mean_positive": mean > 0,
        "familywise_one_sided_lower_bound_positive": family_low > 0,
        "ordinary_ci_upper_non_positive": ci_high <= 0,
    }


def summarize_external_predictions(
    predictions: pd.DataFrame,
    *,
    endpoint_names: Iterable[str],
    bootstrap_draws: int = 5000,
    seed: int = 5003,
) -> dict:
    required_sessions = set(EXTERNAL_SESSIONS)
    observed_sessions = set(predictions["session_date"].astype(str).unique())
    if observed_sessions != required_sessions:
        raise AssertionError(
            f"External sessions mismatch: {sorted(observed_sessions)}"
        )
    if set(predictions["analysis_role"].unique()) != {"external"}:
        raise AssertionError("External predictions must have only the external role")

    output: dict[str, dict] = {}
    for width_ms, width_frame in predictions.groupby("bin_width_ms", sort=True):
        width_key = str(int(width_ms))
        output[width_key] = {}
        interval_day_deltas = interval_model_deltas(width_frame)
        for endpoint in endpoint_names:
            bins = width_frame[width_frame["endpoint"].eq(endpoint)]
            interval_days = interval_day_deltas[
                interval_day_deltas["endpoint"].eq(endpoint)
            ]
            comparison_columns = [
                "C_session_minus_A_session",
                "C_session_minus_B",
                "C_shape_minus_A_session",
            ]
            # The preregistered cluster unit is the source interval, not a
            # midnight fragment. Sum interval-day fragments before resampling.
            intervals = (
                interval_days.groupby("interval_id", sort=True, as_index=False)[
                    comparison_columns
                ]
                .sum()
            )

            def stable_seed(*parts: object) -> int:
                encoded = "|".join(str(part) for part in parts).encode("utf-8")
                return seed + int(sha256(encoded).hexdigest()[:8], 16) % 100000

            headline = deterministic_cluster_bootstrap(
                intervals["C_session_minus_A_session"],
                draws=bootstrap_draws,
                seed=stable_seed(width_ms, endpoint, "external_headline"),
                one_sided_alpha=1 / 60,
            )
            secondary = deterministic_cluster_bootstrap(
                intervals["C_session_minus_B"],
                draws=bootstrap_draws,
                seed=stable_seed(width_ms, endpoint, "external_secondary"),
                one_sided_alpha=1 / 60,
            )
            shape = deterministic_cluster_bootstrap(
                intervals["C_shape_minus_A_session"],
                draws=bootstrap_draws,
                seed=stable_seed(width_ms, endpoint, "external_shape"),
                one_sided_alpha=1 / 60,
            )
            per_session = []
            for day in EXTERNAL_SESSIONS:
                day_rows = interval_days[interval_days["session_date"].eq(day)]
                per_session.append(
                    {
                        "session_date": day,
                        "intervals": int(len(day_rows)),
                        "C_session_minus_A_session_mean": float(
                            day_rows["C_session_minus_A_session"].mean()
                        ),
                        "C_session_minus_B_mean": float(
                            day_rows["C_session_minus_B"].mean()
                        ),
                        "C_shape_minus_A_session_mean": float(
                            day_rows["C_shape_minus_A_session"].mean()
                        ),
                    }
                )
            endpoint_result = {
                "bins": int(len(bins)),
                "intervals": int(bins["interval_id"].nunique()),
                "interval_day_fragments": int(len(interval_days)),
                "targets": int(bins["target_label"].sum()),
                "observed_rate": float(bins["target_label"].mean()),
                "paired_interval_comparisons": {
                    "C_session_minus_A_session": headline,
                    "C_session_minus_B": secondary,
                    "C_shape_minus_A_session": shape,
                },
                "per_session": per_session,
            }
            if int(width_ms) == 1000:
                endpoint_result["headline_decision"] = external_endpoint_verdict(
                    headline,
                    [
                        row["C_session_minus_A_session_mean"]
                        for row in per_session
                    ],
                )
            else:
                endpoint_result["role"] = (
                    "causal_anchor_sensitivity_no_independent_verdict"
                )
            output[width_key][str(endpoint)] = endpoint_result
    return output
