from __future__ import annotations

import pandas as pd

from xau_trigger.state_age_hazard import (
    MODEL_PREDICTOR_ALLOWLIST,
    build_design_matrix,
    coherent_timing_verdict,
    conditional_timing_deltas,
    deterministic_cluster_bootstrap,
    fit_state_age_baselines,
    per_session_base_hazard,
    predict_state_age_baselines,
)


def _bins() -> pd.DataFrame:
    records = []
    for endpoint, state_offset in [
        ("unlock_occurrence", 0.0),
        ("rehedge_sell_occurrence", 0.2),
        ("rehedge_buy_occurrence", 0.4),
    ]:
        for split, cohort, interval_offset in [
            ("development", "internal_2026_07_23_24", 0),
            ("holdout", "internal_2026_07_23_24", 10),
            ("supplemental", "supplemental_2026_07_20_22", 20),
        ]:
            for bin_index, age in enumerate([0.0, 1.0, 6.0, 8.0]):
                records.append(
                    {
                        "risk_bin_id": f"{endpoint}:{split}:{bin_index}",
                        "cohort_id": cohort,
                        "interval_id": f"{endpoint}:{interval_offset}",
                        "endpoint": endpoint,
                        "split": split,
                        "target_label": int(bin_index == 2),
                        "state_age_seconds": age + state_offset,
                        "is_primary_model_eligible": split != "supplemental",
                    }
                )
    return pd.DataFrame(records)


def test_model_allowlist_is_one_hot_and_contains_no_leakage() -> None:
    source = _bins()
    design = build_design_matrix(source)

    assert design.columns.tolist() == ["risk_bin_id", *MODEL_PREDICTOR_ALLOWLIST]
    assert (design[MODEL_PREDICTOR_ALLOWLIST].sum(axis=1) == 1).all()
    forbidden = {
        "endpoint",
        "target_label",
        "interval_id",
        "cohort_id",
        "split",
        "bin_start",
        "bin_end",
        "censor_reason",
    }
    assert forbidden.isdisjoint(MODEL_PREDICTOR_ALLOWLIST)


def test_fitting_is_development_only_and_supplemental_isolation_is_hashed() -> None:
    source = _bins()
    combined = fit_state_age_baselines(source)
    internal = fit_state_age_baselines(
        source[source["cohort_id"] == "internal_2026_07_23_24"]
    )
    changed_holdout = source.copy()
    changed_holdout.loc[changed_holdout["split"] == "holdout", "target_label"] = 0
    holdout_ignored = fit_state_age_baselines(changed_holdout)

    assert combined["fitted_parameter_sha256"] == internal[
        "fitted_parameter_sha256"
    ]
    assert combined["fitted_parameter_sha256"] == holdout_ignored[
        "fitted_parameter_sha256"
    ]


def test_age_bucket_amendment_separates_five_to_six_from_six_to_eight() -> None:
    source = _bins().iloc[:4].copy()
    source.loc[:, "state_age_seconds"] = [5.0, 5.999, 6.0, 7.999]
    source.loc[:, "target_label"] = [0, 0, 1, 1]
    parameters = fit_state_age_baselines(source)
    endpoint = parameters["endpoints"]["unlock_occurrence"]["age_buckets"]

    assert endpoint["age_5_6"]["exposure_bins"] == 2
    assert endpoint["age_5_6"]["target_events"] == 0
    assert endpoint["age_6_8"]["exposure_bins"] == 2
    assert endpoint["age_6_8"]["target_events"] == 2
    assert endpoint["age_5_6"]["probability"] > 0


def test_conditional_constant_hazard_is_exact_uniform_timing_null() -> None:
    predictions = pd.DataFrame(
        {
            "interval_id": ["x"] * 4,
            "endpoint": ["unlock_occurrence"] * 4,
            "target_label": [0, 0, 1, 0],
            "p_age": [0.1] * 4,
        }
    )

    result = conditional_timing_deltas(predictions).iloc[0]

    assert abs(result["conditional_minus_uniform"]) < 1e-12
    assert abs(result["conditional_event_probability"] - 0.25) < 1e-12


def test_predictions_use_frozen_parameters_for_holdout() -> None:
    source = _bins()
    parameters = fit_state_age_baselines(source)
    predictions = predict_state_age_baselines(source, parameters)

    assert len(predictions) == len(source)
    assert predictions["p_const"].between(0, 1, inclusive="neither").all()
    assert predictions["p_age"].between(0, 1, inclusive="neither").all()


def test_cluster_bootstrap_is_deterministic_with_5000_draws() -> None:
    first = deterministic_cluster_bootstrap([1.0, -0.5, 0.25], draws=5000, seed=7)
    second = deterministic_cluster_bootstrap([1.0, -0.5, 0.25], draws=5000, seed=7)

    assert first == second
    assert first["draws"] == 5000
    assert first["cluster_count"] == 3


def test_adjacent_width_null_results_are_inconclusive_not_mixed() -> None:
    one_second = {"ci95_low": -0.1, "ci95_high": 0.05, "mean": -0.02}
    half_second = {"ci95_low": -0.05, "ci95_high": 0.1, "mean": 0.01}

    assert coherent_timing_verdict(one_second, half_second) == (
        "inconclusive_external_pending"
    )


def test_supplemental_session_rates_use_common_hours_only() -> None:
    bins = pd.DataFrame(
        {
            "cohort_id": ["supplemental_2026_07_20_22"] * 2,
            "bin_start": pd.to_datetime(
                ["2026-07-20 02:00:00", "2026-07-20 12:00:00"]
            ),
            "endpoint": ["unlock_occurrence"] * 2,
            "target_label": [1, 0],
            "bin_width_ms": [1000, 1000],
            "is_common_hours": [False, True],
        }
    )

    records = per_session_base_hazard(bins)

    assert len(records) == 1
    assert records[0]["risk_bins"] == 1
    assert records[0]["target_events"] == 0
    assert records[0]["server_hours"] == "12:00-24:00"
