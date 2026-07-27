from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.acquisition import classify_recurring_gaps
from xau_trigger.hazard_bins import (
    build_wall_clock_risk_bins,
    canonicalize_cohort_support,
    dataframe_sha256,
)
from xau_trigger.price_features import (
    FEATURE_ALLOWLISTS,
    REHEDGE_FEATURES,
    UNLOCK_FEATURES,
    build_feature_audit,
    prepare_candidate_bins,
)
from xau_trigger.price_inference import (
    _logit,
    bernoulli_log_likelihood,
    deterministic_cluster_bootstrap,
    fit_endpoint_bundle,
    fit_logistic_l2,
    fit_scaler,
    interval_model_deltas,
    predict_age_baseline,
    predict_endpoint_bundle,
    predict_logistic,
    predict_session_baseline,
    select_regularization,
    transform_features,
)
from xau_trigger.risk_time import detect_coverage_gaps


INTERNAL_COHORT_ID = "internal_2026_07_23_24"
SUPPLEMENTAL_COHORT_ID = "supplemental_2026_07_20_22"
WIDTHS_MS = (1000, 500)
ENDPOINTS = (
    "rehedge_buy_occurrence",
    "rehedge_sell_occurrence",
    "unlock_occurrence",
)
DEVELOPMENT_DATES = (
    "2026-07-20",
    "2026-07-21",
    "2026-07-22",
    "2026-07-23",
)
INTERNAL_REUSE_DATE = "2026-07-24"
BOOTSTRAP_DRAWS = 5000
BOOTSTRAP_SEED = 5003


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_text_sha256(path: Path) -> str:
    """Hash committed text independent of checkout newline convention."""
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return sha256(normalized.encode("utf-8")).hexdigest()


def _json_hash(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def _stable_seed(*parts: object) -> int:
    encoded = "|".join(str(part) for part in parts).encode("utf-8")
    return BOOTSTRAP_SEED + int(sha256(encoded).hexdigest()[:8], 16) % 100000


def _input_snapshot() -> dict[str, str]:
    paths = [
        ROOT / "data" / "interim" / "state_intervals.parquet",
        ROOT / "data" / "interim" / "lifecycle_events.parquet",
        ROOT / "data" / "interim" / "ticks.parquet",
        ROOT / "data" / "interim" / "m5_002" / "m5_002_interval_audit.parquet",
        ROOT / "data" / "interim" / "m5_002" / "m5_002_risk_bin_audit.parquet",
        ROOT / "reports" / "phase_05" / "m5_002_state_age_pilot.json",
        ROOT / "reports" / "phase_05" / "m5_002_state_age_pilot.md",
    ]
    return {
        str(path.relative_to(ROOT)).replace("\\", "/"): _file_sha256(path)
        for path in paths
    }


def _normalize_roundtrip_values(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    for column in output.columns:
        if output[column].isna().any():
            output[column] = output[column].astype(object)
            output.loc[output[column].isna(), column] = "__MISSING__"
    return output


def _rebuild_m5_002_inputs(
    ticks: dict[str, pd.DataFrame],
    *,
    expected_bins_hash: str,
    expected_intervals_hash: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Reproduce pre-Parquet hashes and validate local round-trip artifacts."""
    interim = ROOT / "data" / "interim"
    local_bins_path = interim / "m5_002" / "m5_002_risk_bin_audit.parquet"
    local_intervals_path = interim / "m5_002" / "m5_002_interval_audit.parquet"
    attestation_path = interim / "m5_003" / "m5_002_rebuild_attestation.json"
    source_paths = [
        interim / "state_intervals.parquet",
        interim / "lifecycle_events.parquet",
        interim / "ticks.parquet",
        interim / "m5_002" / "ticks_supplemental_2026_07_20_22.parquet",
        local_bins_path,
        local_intervals_path,
    ]
    source_file_hashes = {
        str(path.relative_to(ROOT)).replace("\\", "/"): _file_sha256(path)
        for path in source_paths
    }
    if attestation_path.exists():
        cached = json.loads(attestation_path.read_text(encoding="utf-8"))
        if (
            cached.get("source_file_sha256") == source_file_hashes
            and cached.get("pre_parquet_risk_bin_dataframe_sha256")
            == expected_bins_hash
            and cached.get("pre_parquet_interval_audit_dataframe_sha256")
            == expected_intervals_hash
        ):
            return (
                pd.read_parquet(local_bins_path),
                pd.read_parquet(local_intervals_path),
                cached,
            )

    intervals = pd.read_parquet(interim / "state_intervals.parquet")
    lifecycle = pd.read_parquet(interim / "lifecycle_events.parquet")
    gap_frames = []
    for cohort_id, cohort_ticks in ticks.items():
        gaps = detect_coverage_gaps(cohort_ticks[["timestamp"]], threshold_seconds=60)
        gaps["cohort_id"] = cohort_id
        gap_frames.append(gaps)
    classified = classify_recurring_gaps(
        pd.concat(gap_frames, ignore_index=True),
        minimum_sessions=3,
        tolerance_seconds=120,
    )
    supports = {
        cohort_id: canonicalize_cohort_support(
            intervals,
            lifecycle,
            cohort_ticks,
            cohort_id=cohort_id,
            breaks=classified[classified["cohort_id"].eq(cohort_id)].copy(),
        )
        for cohort_id, cohort_ticks in ticks.items()
    }
    bins = []
    interval_audits = []
    for width_seconds in (1.0, 0.5):
        for support in supports.values():
            cohort_bins, interval_audit, _ = build_wall_clock_risk_bins(
                support,
                bin_width_seconds=width_seconds,
            )
            bins.append(cohort_bins)
            interval_audits.append(interval_audit)
    rebuilt_bins = pd.concat(bins, ignore_index=True)
    rebuilt_intervals = pd.concat(interval_audits, ignore_index=True)

    rebuilt_bins_hash = dataframe_sha256(rebuilt_bins)
    rebuilt_intervals_hash = dataframe_sha256(rebuilt_intervals)
    if rebuilt_bins_hash != expected_bins_hash:
        raise AssertionError("Rebuilt M5-002 risk-bin hash differs from preregistration")
    if rebuilt_intervals_hash != expected_intervals_hash:
        raise AssertionError("Rebuilt M5-002 interval hash differs from preregistration")
    local_bins = pd.read_parquet(local_bins_path)
    local_intervals = pd.read_parquet(local_intervals_path)
    pd.testing.assert_frame_equal(
        _normalize_roundtrip_values(rebuilt_bins),
        _normalize_roundtrip_values(local_bins),
        check_dtype=False,
    )
    pd.testing.assert_frame_equal(
        _normalize_roundtrip_values(rebuilt_intervals),
        _normalize_roundtrip_values(local_intervals),
        check_dtype=False,
    )
    attestation = {
        "schema_version": 1,
        "source_file_sha256": source_file_hashes,
        "pre_parquet_risk_bin_dataframe_sha256": rebuilt_bins_hash,
        "pre_parquet_interval_audit_dataframe_sha256": rebuilt_intervals_hash,
        "local_parquet_values_equal_after_null_normalization": True,
    }
    attestation_path.parent.mkdir(parents=True, exist_ok=True)
    attestation_path.write_text(
        json.dumps(attestation, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return local_bins, local_intervals, attestation


def _load_inputs() -> dict:
    prereg_path = ROOT / "data" / "m5_003_preregistration.json"
    m5_report_path = ROOT / "reports" / "phase_05" / "m5_002_state_age_pilot.json"
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    m5_report = json.loads(m5_report_path.read_text(encoding="utf-8"))
    interim = ROOT / "data" / "interim"
    ticks = {
        INTERNAL_COHORT_ID: pd.read_parquet(interim / "ticks.parquet"),
        SUPPLEMENTAL_COHORT_ID: pd.read_parquet(
            interim / "m5_002" / "ticks_supplemental_2026_07_20_22.parquet"
        ),
    }
    immutable = prereg["immutable_inputs"]
    bins, intervals, rebuild_attestation = _rebuild_m5_002_inputs(
        ticks,
        expected_bins_hash=immutable["m5_002_risk_bin_dataframe_sha256"],
        expected_intervals_hash=immutable[
            "m5_002_interval_audit_dataframe_sha256"
        ],
    )
    if immutable["m5_002_report_sha256"] != m5_report["deterministic_report_sha256"]:
        raise AssertionError("M5-002 report hash no longer matches preregistration")
    if immutable["m5_002_risk_bin_dataframe_sha256"] != rebuild_attestation[
        "pre_parquet_risk_bin_dataframe_sha256"
    ]:
        raise AssertionError("M5-002 risk-bin dataframe changed")
    if immutable["m5_002_interval_audit_dataframe_sha256"] != rebuild_attestation[
        "pre_parquet_interval_audit_dataframe_sha256"
    ]:
        raise AssertionError("M5-002 interval-audit dataframe changed")
    if immutable["m5_002_internal_tick_dataframe_sha256"] != dataframe_sha256(
        ticks[INTERNAL_COHORT_ID]
    ):
        raise AssertionError("Canonical internal ticks changed")
    for width in WIDTHS_MS:
        expected = immutable[f"a_common_{width}ms_parameter_sha256"]
        observed = m5_report["parameters_by_width"][str(width)][
            "fitted_parameter_sha256"
        ]
        if expected != observed:
            raise AssertionError(f"Frozen A_common {width} ms hash changed")
    raw_supplemental = (
        ROOT / "data" / "raw" / "ticks" / "XAUUSD_202607200100_202607222357.csv"
    )
    if _file_sha256(raw_supplemental) != immutable["supplemental_tick_source_sha256"]:
        raise AssertionError("Pinned supplemental raw tick checksum changed")

    registered = prereg["feature_allowlists"]
    if tuple(registered["rehedge"]) != REHEDGE_FEATURES:
        raise AssertionError("Re-hedge implementation allowlist differs from preregistration")
    if tuple(registered["unlock"]) != UNLOCK_FEATURES:
        raise AssertionError("Unlock implementation allowlist differs from preregistration")
    return {
        "prereg": prereg,
        "prereg_sha256": _canonical_text_sha256(prereg_path),
        "m5_report": m5_report,
        "bins": bins,
        "intervals": intervals,
        "ticks": ticks,
        "m5_002_rebuild_attestation": rebuild_attestation,
    }


def _account_features(audit: pd.DataFrame, design: pd.DataFrame) -> dict:
    feature_invalid = ~audit["all_features_valid"] & ~audit[
        "unlock_before_floor_excluded"
    ]
    internal_primary = audit[
        audit["cohort_id"].eq(INTERNAL_COHORT_ID)
        & audit["bin_width_ms"].eq(1000)
    ]
    internal_invalid = ~internal_primary["all_features_valid"] & ~internal_primary[
        "unlock_before_floor_excluded"
    ]
    expected_bins = int(
        audit.attrs.get("expected_internal_invalid_bins", 937)
    )
    expected_targets = int(
        audit.attrs.get("expected_internal_invalid_targets", 3)
    )
    observed_bins = int(internal_invalid.sum())
    observed_targets = int(
        internal_primary.loc[internal_invalid, "target_label"].sum()
    )
    if (observed_bins, observed_targets) != (expected_bins, expected_targets):
        raise AssertionError(
            "Full-allowlist internal support audit mismatch: "
            f"observed {(observed_bins, observed_targets)} expected "
            f"{(expected_bins, expected_targets)}"
        )
    july23_floor = audit[
        audit["session_date"].eq("2026-07-23")
        & audit["bin_width_ms"].eq(1000)
        & audit["unlock_before_floor_excluded"]
    ]
    if (len(july23_floor), int(july23_floor["target_label"].sum())) != (3115, 0):
        raise AssertionError("The registered July-23 unlock-floor audit changed")

    development_candidates = audit[
        audit["analysis_role"].eq("development")
        & audit["bin_width_ms"].eq(1000)
    ]
    observed_targets_by_endpoint = {
        str(endpoint): int(group["target_label"].sum())
        for endpoint, group in development_candidates.groupby("endpoint", sort=True)
    }
    expected_targets_by_endpoint = {
        key: int(value)
        for key, value in {
            "rehedge_buy_occurrence": 699,
            "rehedge_sell_occurrence": 687,
            "unlock_occurrence": 1448,
        }.items()
    }
    if observed_targets_by_endpoint != expected_targets_by_endpoint:
        raise AssertionError("Registered development target accounting changed")

    reason_records = []
    grouped = audit.groupby(
        [
            "bin_width_ms",
            "analysis_role",
            "session_date",
            "endpoint",
            "first_exclusion_reason",
        ],
        dropna=False,
        sort=True,
    )
    for keys, group in grouped:
        width, role, day, endpoint, reason = keys
        reason_records.append(
            {
                "bin_width_ms": int(width),
                "analysis_role": str(role),
                "session_date": str(day),
                "endpoint": str(endpoint),
                "first_exclusion_reason": (
                    "joint_valid" if pd.isna(reason) else str(reason)
                ),
                "bins": int(len(group)),
                "targets": int(group["target_label"].sum()),
            }
        )
    design_records = []
    for keys, group in design.groupby(
        ["bin_width_ms", "analysis_role", "session_date", "endpoint"],
        sort=True,
    ):
        width, role, day, endpoint = keys
        design_records.append(
            {
                "bin_width_ms": int(width),
                "analysis_role": str(role),
                "session_date": str(day),
                "endpoint": str(endpoint),
                "bins": int(len(group)),
                "targets": int(group["target_label"].sum()),
                "intervals": int(group["interval_id"].nunique()),
            }
        )
    return {
        "registered_internal_full_allowlist_audit": {
            "expected_dropped_bins": expected_bins,
            "observed_dropped_bins": observed_bins,
            "expected_dropped_targets": expected_targets,
            "observed_dropped_targets": observed_targets,
            "status": "PASS",
        },
        "july23_unlock_floor_audit": {
            "dropped_bins": int(len(july23_floor)),
            "dropped_targets": int(july23_floor["target_label"].sum()),
            "status": "PASS",
        },
        "development_targets_before_joint_validity": observed_targets_by_endpoint,
        "all_feature_invalid_excluding_floor": {
            "bins": int(feature_invalid.sum()),
            "targets": int(audit.loc[feature_invalid, "target_label"].sum()),
        },
        "first_reason_records": reason_records,
        "joint_valid_records": design_records,
    }


def _fit_ablation(
    development: pd.DataFrame,
    *,
    endpoint: str,
    full_bundle: dict,
    removed_features: list[str],
) -> dict:
    reduced = [
        column
        for column in full_bundle["feature_columns"]
        if column not in set(removed_features)
    ]
    dev = development[development["endpoint"].eq(endpoint)].reset_index(drop=True)
    scaler = fit_scaler(dev, reduced)
    x_dev = transform_features(dev, scaler)
    p_dev_age = predict_age_baseline(dev, full_bundle["A_dev"])
    p_dev_session = predict_session_baseline(
        dev, p_dev_age, full_bundle["A_session"]
    )
    parameters = fit_logistic_l2(
        x_dev,
        dev["target_label"].to_numpy(),
        regularization=full_bundle["C_session"]["regularization"],
        offset=_logit(p_dev_session),
        fit_intercept=False,
    )
    payload = {
        "removed_features": removed_features,
        "remaining_features": reduced,
        "scaler": scaler,
        "C_session": parameters,
    }
    payload["sha256"] = _json_hash(payload)
    return payload


def _predict_ablation(
    evaluation: pd.DataFrame,
    *,
    endpoint: str,
    full_bundle: dict,
    ablation: dict,
) -> np.ndarray:
    target = evaluation[evaluation["endpoint"].eq(endpoint)].reset_index(drop=True)
    x_target = transform_features(target, ablation["scaler"])
    p_target_age = predict_age_baseline(target, full_bundle["A_dev"])
    p_target_session = predict_session_baseline(
        target, p_target_age, full_bundle["A_session"]
    )
    return predict_logistic(
        x_target,
        ablation["C_session"],
        offset=_logit(p_target_session),
    )


def _fit_width(
    design: pd.DataFrame,
    *,
    width_ms: int,
    prereg: dict,
    m5_report: dict,
) -> dict:
    width_frame = design[design["bin_width_ms"].eq(width_ms)].copy()
    development = width_frame[width_frame["analysis_role"].eq("development")]
    endpoints = {}
    for endpoint in ENDPOINTS:
        feature_columns = FEATURE_ALLOWLISTS[endpoint]
        selection = select_regularization(
            development,
            feature_columns,
            endpoint=endpoint,
        )
        common = m5_report["parameters_by_width"][str(width_ms)]["endpoints"][
            endpoint
        ]
        bundle = fit_endpoint_bundle(
            development,
            feature_columns,
            endpoint=endpoint,
            common_parameters=common,
            regularization_selection=selection,
            shape_feature_columns=prereg["secondary_shape_diagnostic"][
                "feature_columns"
            ][endpoint],
        )
        ablations = {}
        family = "unlock" if endpoint == "unlock_occurrence" else "rehedge"
        for group_name, removed in prereg["feature_groups"][family].items():
            ablation = _fit_ablation(
                development,
                endpoint=endpoint,
                full_bundle=bundle,
                removed_features=list(removed),
            )
            ablations[group_name] = ablation
        endpoints[endpoint] = {
            "regularization_selection": selection,
            "fitted_bundle": bundle,
            "ablations": ablations,
        }
    development_rows = width_frame[width_frame["analysis_role"].eq("development")]
    identity_hash = dataframe_sha256(
        development_rows[
            [
                "risk_bin_id",
                "interval_id",
                "endpoint",
                "target_label",
                "state_age_seconds",
            ]
        ]
    )
    payload = {
        "bin_width_ms": width_ms,
        "development_sessions": list(DEVELOPMENT_DATES),
        "development_rows": int(len(development_rows)),
        "development_row_identity_sha256": identity_hash,
        "endpoints": endpoints,
    }
    payload["fitted_width_sha256"] = _json_hash(payload)
    return payload


def _predict_width(
    design: pd.DataFrame,
    *,
    width_ms: int,
    width_manifest: dict,
    m5_report: dict,
) -> pd.DataFrame:
    width_frame = design[design["bin_width_ms"].eq(width_ms)].copy()
    predictions = []
    for endpoint in ENDPOINTS:
        endpoint_manifest = width_manifest["endpoints"][endpoint]
        bundle = endpoint_manifest["fitted_bundle"]
        common = m5_report["parameters_by_width"][str(width_ms)]["endpoints"][
            endpoint
        ]
        endpoint_prediction = predict_endpoint_bundle(width_frame, bundle, common)
        for group_name, ablation in endpoint_manifest["ablations"].items():
            endpoint_prediction[
                f"p_C_session_without_{group_name}"
            ] = _predict_ablation(
                width_frame,
                endpoint=endpoint,
                full_bundle=bundle,
                ablation=ablation,
            )
        predictions.append(endpoint_prediction)
    return pd.concat(predictions, ignore_index=True).sort_values(
        ["endpoint", "analysis_role", "session_date", "bin_start", "interval_id"],
        kind="stable",
    ).reset_index(drop=True)


def _ablation_interval_deltas(predictions: pd.DataFrame, group_name: str) -> pd.DataFrame:
    probability = f"p_C_session_without_{group_name}"
    source = predictions.copy()
    source["full_ll"] = bernoulli_log_likelihood(
        source["target_label"].to_numpy(), source["p_C_session"].to_numpy()
    )
    source["ablated_ll"] = bernoulli_log_likelihood(
        source["target_label"].to_numpy(), source[probability].to_numpy()
    )
    grouped = source.groupby(
        ["endpoint", "interval_id", "session_date", "analysis_role"],
        sort=True,
        as_index=False,
    )[["full_ll", "ablated_ll"]].sum()
    grouped["full_minus_ablated"] = grouped["full_ll"] - grouped["ablated_ll"]
    return grouped


def _summarize_predictions(predictions: pd.DataFrame, prereg: dict) -> dict:
    output = {}
    for width_ms, width_frame in predictions.groupby("bin_width_ms", sort=False):
        width_key = str(int(width_ms))
        output[width_key] = {}
        interval_deltas = interval_model_deltas(width_frame)
        for role in ["development", "internal_reuse"]:
            output[width_key][role] = {}
            for endpoint in ENDPOINTS:
                bins = width_frame[
                    width_frame["analysis_role"].eq(role)
                    & width_frame["endpoint"].eq(endpoint)
                ]
                intervals = interval_deltas[
                    interval_deltas["analysis_role"].eq(role)
                    & interval_deltas["endpoint"].eq(endpoint)
                ]
                metrics = {}
                for comparison in [
                    "C_session_minus_A_session",
                    "C_session_minus_B",
                    "A_session_minus_A_dev",
                    "C_shape_minus_A_session",
                    "C_dev_minus_A_dev",
                    "C_dev_minus_B",
                    "A_level_minus_A_common",
                    "A_dev_minus_A_level",
                ]:
                    metrics[comparison] = deterministic_cluster_bootstrap(
                        intervals[comparison],
                        draws=BOOTSTRAP_DRAWS,
                        seed=_stable_seed(width_ms, role, endpoint, comparison),
                        one_sided_alpha=1 / 60,
                    )
                family = "unlock" if endpoint == "unlock_occurrence" else "rehedge"
                ablations = {}
                for group_name in prereg["feature_groups"][family]:
                    ablation_intervals = _ablation_interval_deltas(
                        bins, group_name
                    )
                    ablations[group_name] = deterministic_cluster_bootstrap(
                        ablation_intervals["full_minus_ablated"],
                        draws=BOOTSTRAP_DRAWS,
                        seed=_stable_seed(width_ms, role, endpoint, group_name),
                        one_sided_alpha=1 / 240,
                    )
                per_session = []
                for day, group in intervals.groupby("session_date", sort=True):
                    per_session.append(
                        {
                            "session_date": str(day),
                            "intervals": int(len(group)),
                            "C_dev_minus_A_dev_mean": float(
                                group["C_dev_minus_A_dev"].mean()
                            ),
                            "A_session_minus_A_dev_mean": float(
                                group["A_session_minus_A_dev"].mean()
                            ),
                            "C_session_minus_A_session_mean": float(
                                group["C_session_minus_A_session"].mean()
                            ),
                            "C_shape_minus_A_session_mean": float(
                                group["C_shape_minus_A_session"].mean()
                            ),
                            "C_dev_minus_B_mean": float(
                                group["C_dev_minus_B"].mean()
                            ),
                        }
                    )
                output[width_key][role][endpoint] = {
                    "bins": int(len(bins)),
                    "intervals": int(bins["interval_id"].nunique()),
                    "targets": int(bins["target_label"].sum()),
                    "observed_rate": float(bins["target_label"].mean()),
                    "mean_predictions": {
                        model: float(bins[f"p_{model}"].mean())
                        for model in [
                            "A_common",
                            "A_level",
                            "A_dev",
                            "A_session",
                            "B",
                            "C_dev",
                            "C_session",
                            "C_shape",
                        ]
                    },
                    "paired_interval_comparisons": metrics,
                    "ablations": ablations,
                    "per_session": per_session,
                    "role": "diagnostic_only_no_verdict",
                }
    return output


def _base_rate_stress(predictions: pd.DataFrame) -> dict:
    shift = -float(np.log(2.1))
    records = {}
    source = predictions[
        predictions["bin_width_ms"].eq(1000)
        & predictions["analysis_role"].eq("development")
    ]
    for endpoint, group in source.groupby("endpoint", sort=True):
        p_age_shift = 1 / (
            1 + np.exp(-(_logit(group["p_A_session"].to_numpy()) + shift))
        )
        p_c_shift = 1 / (
            1 + np.exp(-(_logit(group["p_C_session"].to_numpy()) + shift))
        )
        shifted = group.copy()
        shifted["age_ll"] = bernoulli_log_likelihood(
            shifted["target_label"].to_numpy(), p_age_shift
        )
        shifted["c_ll"] = bernoulli_log_likelihood(
            shifted["target_label"].to_numpy(), p_c_shift
        )
        shifted_interval = shifted.groupby("interval_id", sort=True)[
            ["age_ll", "c_ll"]
        ].sum()
        shifted_mean = float((shifted_interval["c_ll"] - shifted_interval["age_ll"]).mean())
        original_interval = interval_model_deltas(group)
        original_mean = float(
            original_interval["C_session_minus_A_session"].mean()
        )
        records[str(endpoint)] = {
            "fixed_logit_shift": shift,
            "original_mean_increment": original_mean,
            "shifted_mean_increment": shifted_mean,
            "relative_change": (
                float((shifted_mean - original_mean) / abs(original_mean))
                if original_mean != 0
                else None
            ),
            "role": "development_label_stress_only_non_gating",
        }
    return records


def _leave_one_session_out(
    design: pd.DataFrame,
    *,
    prereg: dict,
    m5_report: dict,
) -> list[dict]:
    primary = design[
        design["bin_width_ms"].eq(1000)
        & design["analysis_role"].eq("development")
    ]
    records = []
    for held_day in DEVELOPMENT_DATES:
        training = primary[~primary["session_date"].eq(held_day)]
        held = primary[primary["session_date"].eq(held_day)]
        for endpoint in ENDPOINTS:
            features = FEATURE_ALLOWLISTS[endpoint]
            selection = select_regularization(
                training,
                features,
                endpoint=endpoint,
            )
            common = m5_report["parameters_by_width"]["1000"]["endpoints"][endpoint]
            bundle = fit_endpoint_bundle(
                training,
                features,
                endpoint=endpoint,
                common_parameters=common,
                regularization_selection=selection,
                shape_feature_columns=prereg["secondary_shape_diagnostic"][
                    "feature_columns"
                ][endpoint],
            )
            prediction = predict_endpoint_bundle(held, bundle, common)
            deltas = interval_model_deltas(prediction)
            records.append(
                {
                    "held_out_session": held_day,
                    "endpoint": endpoint,
                    "training_sessions": [
                        day for day in DEVELOPMENT_DATES if day != held_day
                    ],
                    "held_out_bins": int(len(prediction)),
                    "held_out_targets": int(prediction["target_label"].sum()),
                    "held_out_intervals": int(prediction["interval_id"].nunique()),
                    "C_dev_minus_A_dev_mean": float(
                        deltas["C_dev_minus_A_dev"].mean()
                    ),
                    "A_session_minus_A_dev_mean": float(
                        deltas["A_session_minus_A_dev"].mean()
                    ),
                    "C_session_minus_A_session_mean": float(
                        deltas["C_session_minus_A_session"].mean()
                    ),
                    "C_shape_minus_A_session_mean": float(
                        deltas["C_shape_minus_A_session"].mean()
                    ),
                    "C_dev_minus_B_mean": float(deltas["C_dev_minus_B"].mean()),
                    "B_selected_lambda": selection["models"]["B"][
                        "selected_lambda"
                    ],
                    "C_dev_selected_lambda": selection["models"]["C_dev"][
                        "selected_lambda"
                    ],
                    "C_session_selected_lambda": selection["models"][
                        "C_session"
                    ]["selected_lambda"],
                    "role": "session_stability_diagnostic_only_no_selection_no_verdict",
                }
            )
    return records


def _validation_gates(
    audit: pd.DataFrame,
    design: pd.DataFrame,
    predictions: pd.DataFrame,
    manifest: dict,
    *,
    input_before: dict[str, str],
    input_after: dict[str, str],
) -> dict:
    model_rows_match = len(predictions) == len(design) and set(
        predictions["risk_bin_id"]
    ) == set(design["risk_bin_id"])
    feature_columns = set(REHEDGE_FEATURES) | set(UNLOCK_FEATURES)
    forbidden = {
        "target_label",
        "endpoint",
        "interval_id",
        "risk_bin_id",
        "bin_start",
        "bin_end",
        "session_date",
        "analysis_role",
        "following_event_type",
        "censor_reason",
    }
    development = design[design["analysis_role"].eq("development")]
    without_reuse = design[~design["analysis_role"].eq("internal_reuse")]
    development_from_without = without_reuse[
        without_reuse["analysis_role"].eq("development")
    ]
    gates = {
        "canonical_M2_through_M5_002_files_unchanged": input_before == input_after,
        "all_joint_valid_model_rows_have_finite_allowlisted_features": all(
            np.isfinite(
                design.loc[
                    design["endpoint"].eq(endpoint), list(columns)
                ].to_numpy(dtype=float)
            ).all()
            for endpoint, columns in FEATURE_ALLOWLISTS.items()
        ),
        "predictor_allowlists_exclude_identifiers_labels_and_timestamps": forbidden.isdisjoint(
            feature_columns
        ),
        "all_baselines_and_price_models_use_identical_rows": model_rows_match,
        "development_contains_only_registered_sessions": set(
            development["session_date"].unique()
        )
        == set(DEVELOPMENT_DATES),
        "internal_reuse_not_in_development_fit_hash": dataframe_sha256(
            development[["risk_bin_id", "interval_id", "endpoint", "target_label"]]
        )
        == dataframe_sha256(
            development_from_without[
                ["risk_bin_id", "interval_id", "endpoint", "target_label"]
            ]
        ),
        "all_C_dev_models_have_no_free_intercept": all(
            not endpoint["fitted_bundle"]["C_dev"]["fit_intercept"]
            for width in manifest["widths"].values()
            for endpoint in width["endpoints"].values()
        ),
        "all_C_session_and_C_shape_models_have_no_free_intercept": all(
            not endpoint["fitted_bundle"][model]["fit_intercept"]
            for width in manifest["widths"].values()
            for endpoint in width["endpoints"].values()
            for model in ["C_session", "C_shape"]
        ),
        "all_A_session_models_use_three_explicit_blocks": all(
            endpoint["fitted_bundle"]["A_session"]["parameterization"]
            == "three_one_hot_block_effects_no_intercept"
            and endpoint["fitted_bundle"]["A_session"]["server_hour_bounds"]
            == [[12, 16], [16, 20], [20, 24]]
            and len(
                endpoint["fitted_bundle"]["A_session"]["parameters"][
                    "coefficients"
                ]
            )
            == 3
            for width in manifest["widths"].values()
            for endpoint in width["endpoints"].values()
        ),
        "all_A_dev_models_use_eleven_buckets": all(
            len(endpoint["fitted_bundle"]["A_dev"]["bucket_labels"]) == 11
            for width in manifest["widths"].values()
            for endpoint in width["endpoints"].values()
        ),
        "full_allowlist_internal_audit_reconciles_937_bins_3_targets": (
            int(
                (
                    audit["cohort_id"].eq(INTERNAL_COHORT_ID)
                    & audit["bin_width_ms"].eq(1000)
                    & ~audit["all_features_valid"]
                    & ~audit["unlock_before_floor_excluded"]
                ).sum()
            )
            == 937
            and int(
                audit.loc[
                    audit["cohort_id"].eq(INTERNAL_COHORT_ID)
                    & audit["bin_width_ms"].eq(1000)
                    & ~audit["all_features_valid"]
                    & ~audit["unlock_before_floor_excluded"],
                    "target_label",
                ].sum()
            )
            == 3
        ),
        "external_sessions_absent_and_not_substituted": not bool(
            set(design["session_date"]) & {"2026-07-27", "2026-07-28", "2026-07-29"}
        ),
    }
    if not all(gates.values()):
        failed = sorted(name for name, passed in gates.items() if not passed)
        raise AssertionError(f"M5-003 validation gates failed: {failed}")
    return gates


def render_markdown(report: dict) -> str:
    lines = [
        "# M5-003 causal price-increment implementation",
        "",
        f"Status: `{report['status']}`",
        "",
        "This is a frozen engineering result, not a validated trading edge.",
        "Development and 2026-07-24 are diagnostic only; the registered",
        "2026-07-27..29 external sessions are still unavailable.",
        "",
        "## Contract and correction",
        "",
        "- M5-002 inputs and A_common hashes matched the preregistration.",
        "- A_dev uses the exact 11-bucket M5-002 grid, including `[5,6)`,",
        "  `[6,8)`, and `[8,10)`; seven buckets remain after the unlock floor.",
        "- `C_dev` has no free intercept; the headline is `C_dev - A_dev`.",
        "- Independent Claude re-review is required before merge.",
        "",
        "## Feature accounting",
        "",
    ]
    registered = report["feature_accounting"][
        "registered_internal_full_allowlist_audit"
    ]
    lines.extend(
        [
            f"- Full allowlist audit: {registered['observed_dropped_bins']:,} bins / "
            f"{registered['observed_dropped_targets']:,} targets removed — PASS.",
            f"- July-23 unlock floor: "
            f"{report['feature_accounting']['july23_unlock_floor_audit']['dropped_bins']:,} "
            "bins / 0 targets removed — PASS.",
            "",
            "### Joint-valid one-second cohorts",
            "",
            "| Role | Date | Endpoint | Bins | Targets | Intervals |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in report["feature_accounting"]["joint_valid_records"]:
        if row["bin_width_ms"] != 1000:
            continue
        lines.append(
            f"| {row['analysis_role']} | {row['session_date']} | {row['endpoint']} | "
            f"{row['bins']:,} | {row['targets']:,} | {row['intervals']:,} |"
        )

    lines.extend(["", "## Internal reuse diagnostics — no verdict", ""])
    for endpoint in ENDPOINTS:
        metric = report["model_diagnostics"]["1000"]["internal_reuse"][endpoint]
        headline = metric["paired_interval_comparisons"]["C_dev_minus_A_dev"]
        secondary = metric["paired_interval_comparisons"]["C_dev_minus_B"]
        lines.append(
            f"- `{endpoint}`: C_dev−A_dev mean {headline['mean']:.6f} "
            f"(95% CI {headline['ci95_low']:.6f}, {headline['ci95_high']:.6f}); "
            f"C_dev−B mean {secondary['mean']:.6f}. Diagnostic only."
        )

    lines.extend(
        [
            "",
            "## Session stability",
            "",
            "Leave-one-session-out refits A_dev, preprocessing, lambda selection,",
            "B, and C_dev using only the remaining sessions. It is diagnostic and",
            "does not estimate between-session population variance.",
            "",
            "| Held session | Endpoint | Bins | Targets | C_dev−A_dev |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in report["leave_one_session_out"]:
        lines.append(
            f"| {row['held_out_session']} | {row['endpoint']} | "
            f"{row['held_out_bins']:,} | {row['held_out_targets']:,} | "
            f"{row['C_dev_minus_A_dev_mean']:.6f} |"
        )

    lines.extend(["", "## Validation gates", ""])
    for name, passed in report["validation_gates"].items():
        lines.append(f"- `{name}`: {'PASS' if passed else 'FAIL'}")
    lines.extend(
        [
            "",
            "## Remaining gates",
            "",
            "- `independent_re_review_pending`: blocking merge until Claude review.",
            "- `external_2026_07_27_29_pending`: M5 remains open.",
            "- No supported/rejected price verdict is issued from development or",
            "  internal reuse data.",
            "- No P/L optimization or tradeable-edge claim was made.",
            "",
        ]
    )
    return "\n".join(lines)


def render_session_remediation_markdown(report: dict) -> str:
    """Render the review-remediated report with every registered family visible."""
    lines = [
        "# M5-003 causal price-increment implementation",
        "",
        f"Status: `{report['status']}`",
        "",
        "This is a frozen engineering result, not a validated trading edge.",
        "Development and 2026-07-24 are diagnostic only. The registered",
        "2026-07-27..29 external sessions remain unseen and pending.",
        "",
        "## Review-driven session remediation",
        "",
        "- `A_session = A_dev + server-time block effect` on fixed blocks",
        "  `[12,16)`, `[16,20)`, and `[20,24)`.",
        "- All three block effects are explicit one-hot columns with no intercept;",
        "  no reference block is silently fixed at zero.",
        "- `C_session` uses fixed `logit(A_session)` plus the full price allowlist,",
        "  has no free intercept, and reselects lambda using development-only",
        "  interval GroupKFold.",
        "- `C_dev - A_dev` is retained as a superseded audit diagnostic.",
        "- `C_shape` is review-driven, external-secondary, and cannot create an",
        "  independent verdict.",
        "- D-007 server UTC+3 remains an inference; market-session labels are",
        "  approximate and July-DST dependent.",
        "- A fresh independent Claude re-review is required after this code change.",
        "",
        "## Feature accounting",
        "",
    ]
    registered = report["feature_accounting"][
        "registered_internal_full_allowlist_audit"
    ]
    floor = report["feature_accounting"]["july23_unlock_floor_audit"]
    lines.extend(
        [
            f"- Full allowlist audit: {registered['observed_dropped_bins']:,} bins / "
            f"{registered['observed_dropped_targets']:,} targets removed — PASS.",
            f"- July-23 unlock floor: {floor['dropped_bins']:,} bins / "
            f"{floor['dropped_targets']:,} targets removed — PASS.",
            "",
            "### Joint-valid one-second cohorts",
            "",
            "| Role | Date | Endpoint | Bins | Targets | Intervals |",
            "| --- | --- | --- | ---: | ---: | ---: |",
        ]
    )
    for row in report["feature_accounting"]["joint_valid_records"]:
        if row["bin_width_ms"] == 1000:
            lines.append(
                f"| {row['analysis_role']} | {row['session_date']} | "
                f"{row['endpoint']} | {row['bins']:,} | {row['targets']:,} | "
                f"{row['intervals']:,} |"
            )

    lines.extend(
        [
            "",
            "## One-second paired comparisons — diagnostics only",
            "",
            "| Role | Endpoint | C_session−A_session | 95% CI | "
            "A_session−A_dev | C_shape−A_session | old C_dev−A_dev |",
            "| --- | --- | ---: | --- | ---: | ---: | ---: |",
        ]
    )
    for role in ["development", "internal_reuse"]:
        for endpoint in ENDPOINTS:
            metrics = report["model_diagnostics"]["1000"][role][endpoint][
                "paired_interval_comparisons"
            ]
            headline = metrics["C_session_minus_A_session"]
            lines.append(
                f"| {role} | {endpoint} | {headline['mean']:.6f} | "
                f"[{headline['ci95_low']:.6f}, {headline['ci95_high']:.6f}] | "
                f"{metrics['A_session_minus_A_dev']['mean']:.6f} | "
                f"{metrics['C_shape_minus_A_session']['mean']:.6f} | "
                f"{metrics['C_dev_minus_A_dev']['mean']:.6f} |"
            )

    lines.extend(
        [
            "",
            "### Required secondary comparison",
            "",
            "| Role | Endpoint | C_session−B | 95% CI | Familywise one-sided low |",
            "| --- | --- | ---: | --- | ---: |",
        ]
    )
    for role in ["development", "internal_reuse"]:
        for endpoint in ENDPOINTS:
            metric = report["model_diagnostics"]["1000"][role][endpoint][
                "paired_interval_comparisons"
            ]["C_session_minus_B"]
            lines.append(
                f"| {role} | {endpoint} | {metric['mean']:.6f} | "
                f"[{metric['ci95_low']:.6f}, {metric['ci95_high']:.6f}] | "
                f"{metric['familywise_one_sided_low']:.6f} |"
            )

    lines.extend(
        [
            "",
            "### Registered one-second ablations",
            "",
            "Positive values mean the full `C_session` scored above the model",
            "with that group removed. Correlated-group ablations are not additive",
            "or causal decompositions.",
            "",
            "| Role | Endpoint | Removed group | Full−ablated | 95% CI | "
            "Familywise one-sided low |",
            "| --- | --- | --- | ---: | --- | ---: |",
        ]
    )
    for role in ["development", "internal_reuse"]:
        for endpoint in ENDPOINTS:
            ablations = report["model_diagnostics"]["1000"][role][endpoint][
                "ablations"
            ]
            for group_name, metric in ablations.items():
                lines.append(
                    f"| {role} | {endpoint} | {group_name} | "
                    f"{metric['mean']:.6f} | "
                    f"[{metric['ci95_low']:.6f}, {metric['ci95_high']:.6f}] | "
                    f"{metric['familywise_one_sided_low']:.6f} |"
                )

    lines.extend(
        [
            "",
            "### 500 ms causal-anchor sensitivity",
            "",
            "This moves the anchor to `T−500 ms`; it is not an independent",
            "discretization robustness sample and cannot override one second.",
            "",
            "| Role | Endpoint | C_session−A_session | 95% CI |",
            "| --- | --- | ---: | --- |",
        ]
    )
    for role in ["development", "internal_reuse"]:
        for endpoint in ENDPOINTS:
            metric = report["model_diagnostics"]["500"][role][endpoint][
                "paired_interval_comparisons"
            ]["C_session_minus_A_session"]
            lines.append(
                f"| {role} | {endpoint} | {metric['mean']:.6f} | "
                f"[{metric['ci95_low']:.6f}, {metric['ci95_high']:.6f}] |"
            )

    lines.extend(
        [
            "",
            "## Multiplicity registry",
            "",
            "| Family | Comparisons | Per-comparison alpha | Gate role |",
            "| --- | ---: | ---: | --- |",
            "| C_session−A_session at 1 s | 3 | 0.0166667 | external headline |",
            "| C_session−B at 1 s | 3 | 0.0166667 | required secondary |",
            "| C_session leave-one-group-out | 12 | 0.0041667 | required ablation |",
            "| C_session−A_session at 500 ms | 3 | 0.0166667 | non-gating sensitivity |",
            "| C_shape−A_session | 3 | n/a | descriptive, no verdict |",
            "",
            "## Fixed base-rate shift stress",
            "",
            "The preregistered `-log(2.1)` development-label stress is",
            "non-gating and does not recalibrate internal or external labels.",
            "Its observed direction and magnitude are reported rather than",
            "replaced by the earlier approximate 7% expectation.",
            "",
            "| Endpoint | Original increment | Shifted increment | Relative change |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for endpoint in ENDPOINTS:
        stress = report["base_rate_attenuation_stress"][endpoint]
        lines.append(
            f"| {endpoint} | {stress['original_mean_increment']:.6f} | "
            f"{stress['shifted_mean_increment']:.6f} | "
            f"{stress['relative_change']:.3%} |"
        )

    lines.extend(
        [
            "",
            "## Leave-one-development-session-out",
            "",
            "Every fold refits `A_dev`, all three `A_session` effects,",
            "preprocessing, nested lambda selection, and all price models.",
            "The spread is diagnostic and does not estimate a session-population",
            "variance from only four development sessions.",
            "",
            "| Held session | Endpoint | Bins | Targets | "
            "A_session−A_dev | C_session−A_session | C_shape−A_session |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in report["leave_one_session_out"]:
        lines.append(
            f"| {row['held_out_session']} | {row['endpoint']} | "
            f"{row['held_out_bins']:,} | {row['held_out_targets']:,} | "
            f"{row['A_session_minus_A_dev_mean']:.6f} | "
            f"{row['C_session_minus_A_session_mean']:.6f} | "
            f"{row['C_shape_minus_A_session_mean']:.6f} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "On the single 2026-07-24 internal-reuse session, the session-block",
            "increment exceeded the residual full-price increment for two of three",
            "endpoints. Rehedge-sell had the smallest residual price increment and",
            "its ordinary 95% interval crossed zero. These are internal diagnostics,",
            "not endpoint verdicts or causal decompositions. Time-of-day may proxy",
            "market regime, operating schedule, or execution behavior.",
            "",
            "## Validation and remaining gates",
            "",
        ]
    )
    for name, passed in report["validation_gates"].items():
        lines.append(f"- `{name}`: {'PASS' if passed else 'FAIL'}")
    lines.extend(
        [
            "- `independent_re_review_pending`: blocking merge after remediation.",
            "- `external_2026_07_27_29_pending`: M5 remains open.",
            "- No supported/rejected result is issued from development or internal reuse.",
            "- No P/L optimization or tradeable-edge claim was made.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    loaded = _load_inputs()
    prereg = loaded["prereg"]
    input_before = _input_snapshot()
    candidates = prepare_candidate_bins(loaded["bins"], loaded["intervals"])
    gaps = {
        cohort_id: detect_coverage_gaps(ticks[["timestamp"]], threshold_seconds=60)
        for cohort_id, ticks in loaded["ticks"].items()
    }
    audit, design = build_feature_audit(candidates, loaded["ticks"], gaps)
    feature_accounting = _account_features(audit, design)

    widths = {}
    for width_ms in WIDTHS_MS:
        width_manifest = _fit_width(
            design,
            width_ms=width_ms,
            prereg=prereg,
            m5_report=loaded["m5_report"],
        )
        widths[str(width_ms)] = width_manifest

    manifest = {
        "schema_version": 1,
        "milestone": "M5-003",
        "status": "frozen_external_pending",
        "preregistration_sha256": loaded["prereg_sha256"],
        "immutable_inputs": prereg["immutable_inputs"],
        "development_sessions": list(DEVELOPMENT_DATES),
        "internal_reuse_session": INTERNAL_REUSE_DATE,
        "external_sessions": prereg["cohorts"]["external"]["sessions"],
        "feature_allowlists": {
            endpoint: list(columns) for endpoint, columns in FEATURE_ALLOWLISTS.items()
        },
        "session_baseline_contract": prereg["review_driven_session_amendment"],
        "shape_feature_allowlists": prereg["secondary_shape_diagnostic"][
            "feature_columns"
        ],
        "widths": widths,
        "internal_reuse_loaded_for_fit": False,
        "external_loaded_for_fit_or_evaluation": False,
    }
    manifest["frozen_manifest_sha256"] = _json_hash(manifest)

    local_output = ROOT / "data" / "interim" / "m5_003"
    report_output = ROOT / "reports" / "phase_05"
    local_output.mkdir(parents=True, exist_ok=True)
    report_output.mkdir(parents=True, exist_ok=True)
    manifest_path = report_output / "m5_003_frozen_model_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    predictions = [
        _predict_width(
            design,
            width_ms=width_ms,
            width_manifest=widths[str(width_ms)],
            m5_report=loaded["m5_report"],
        )
        for width_ms in WIDTHS_MS
    ]
    all_predictions = pd.concat(predictions, ignore_index=True)
    local_paths = {
        "feature_audit": local_output / "m5_003_feature_audit.parquet",
        "joint_valid_design_matrix": (
            local_output / "m5_003_joint_valid_design_matrix.parquet"
        ),
        "predictions": local_output / "m5_003_predictions.parquet",
    }
    audit.to_parquet(local_paths["feature_audit"], index=False)
    design.to_parquet(local_paths["joint_valid_design_matrix"], index=False)
    all_predictions.to_parquet(local_paths["predictions"], index=False)

    input_after = _input_snapshot()
    validation_gates = _validation_gates(
        audit,
        design,
        all_predictions,
        manifest,
        input_before=input_before,
        input_after=input_after,
    )
    diagnostics = _summarize_predictions(all_predictions, prereg)
    loso = _leave_one_session_out(
        design,
        prereg=prereg,
        m5_report=loaded["m5_report"],
    )
    report = {
        "schema_version": 1,
        "milestone": "M5-003",
        "status": "pipeline_frozen_external_pending_zero_validated_price_results",
        "preregistration_sha256": loaded["prereg_sha256"],
        "frozen_manifest_sha256": manifest["frozen_manifest_sha256"],
        "m5_002_rebuild_attestation": loaded["m5_002_rebuild_attestation"],
        "feature_accounting": feature_accounting,
        "model_diagnostics": diagnostics,
        "leave_one_session_out": loso,
        "base_rate_attenuation_stress": _base_rate_stress(all_predictions),
        "review_driven_session_amendment": prereg[
            "review_driven_session_amendment"
        ],
        "multiplicity_registry": {
            "headline_family": prereg["inference"]["headline_family"],
            "c_session_minus_b_family": prereg["inference"][
                "c_session_minus_b_family"
            ],
            "ablation_family": prereg["inference"]["ablation_family"],
            "secondary_anchor_family": prereg["inference"][
                "secondary_anchor_family"
            ],
            "shape_diagnostic": prereg["secondary_shape_diagnostic"][
                "external_multiplicity"
            ],
        },
        "validation_gates": validation_gates,
        "uncertainty_limitation": (
            "interval-cluster bootstrap is conditional on observed sessions and "
            "does not estimate between-session population variance"
        ),
        "decision": {
            "development_verdict_allowed": False,
            "internal_reuse_verdict_allowed": False,
            "external_verdict_available": False,
            "price_information_verdict": "not_available_external_pending",
            "tradeable_edge_claimed": False,
        },
        "merge_readiness": {
            "engineering_gates_pass": True,
            "independent_re_review": "independent_re_review_pending",
            "ready_to_merge": False,
        },
        "external_gate": {
            "registered_sessions": prereg["cohorts"]["external"]["sessions"],
            "data_available": False,
            "satisfied": False,
            "m5_closed": False,
        },
        "output_hashes": {
            name: dataframe_sha256(frame)
            for name, frame in {
                "feature_audit": audit,
                "joint_valid_design_matrix": design,
                "predictions": all_predictions,
            }.items()
        },
        "canonical_input_file_sha256_before": input_before,
        "canonical_input_file_sha256_after": input_after,
    }
    report["deterministic_report_sha256"] = _json_hash(report)

    report_path = report_output / "m5_003_price_increment_report.json"
    markdown_path = report_output / "m5_003_price_increment_report.md"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_session_remediation_markdown(report), encoding="utf-8"
    )
    print(
        "M5-003 price-increment pipeline frozen: "
        f"{report['deterministic_report_sha256']}"
    )


if __name__ == "__main__":
    main()
