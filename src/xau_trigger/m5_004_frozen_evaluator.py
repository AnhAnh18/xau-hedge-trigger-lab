"""Frozen, one-time external evaluation for M5-004."""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
from typing import Iterable

import pandas as pd

from xau_trigger.hazard_bins import (
    build_wall_clock_risk_bins,
    canonicalize_cohort_support,
    dataframe_sha256,
)
from xau_trigger.m5_004_external_intake import (
    assert_blind_firewall,
    build_blind_intake,
    build_structural_record,
    canonical_json_sha256,
    canonical_text_sha256,
    input_set_records,
    runtime_environment_fingerprint,
    snapshot_input_manifest,
)
from xau_trigger.parsers.mt5_report import parse_report
from xau_trigger.parsers.tick_export import parse_ticks
from xau_trigger.price_features import build_feature_audit, prepare_candidate_bins
from xau_trigger.state_reconstruction import merge_lifecycles, reconstruct_states
from xau_trigger.unlock_cause import (
    CAUSE_FEATURES,
    build_unlock_cause_dataset,
    predict_cause_bundle,
    summarize_cause_predictions,
)


def verify_frozen_package(root: Path, contract: dict) -> tuple[dict, dict]:
    package = contract["frozen_package"]
    manifest_path = root / package["manifest_path"]
    report_path = root / package["development_report_path"]
    if canonical_text_sha256(manifest_path) != package[
        "manifest_canonical_text_file_sha256"
    ]:
        raise AssertionError("Frozen M5-004 manifest text hash changed")
    if canonical_text_sha256(report_path) != package[
        "development_report_canonical_text_file_sha256"
    ]:
        raise AssertionError("Frozen M5-004 development report text hash changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    manifest_source = dict(manifest)
    stored_manifest_hash = manifest_source.pop("frozen_manifest_sha256", None)
    if (
        stored_manifest_hash != package["manifest_canonical_sha256"]
        or canonical_json_sha256(manifest_source) != stored_manifest_hash
    ):
        raise AssertionError("Frozen M5-004 manifest canonical hash changed")
    if (
        report.get("deterministic_report_sha256")
        != package["development_report_deterministic_sha256"]
    ):
        raise AssertionError("Frozen M5-004 development report hash changed")
    if manifest.get("future_external_loaded_before_freeze") is not False:
        raise AssertionError("Frozen manifest does not predate future external data")
    return manifest, report


def verify_infrastructure_manifest(
    root: Path,
    infrastructure: dict,
    contract: dict,
) -> None:
    stored = infrastructure.get("infrastructure_manifest_sha256")
    source = dict(infrastructure)
    source.pop("infrastructure_manifest_sha256", None)
    if not stored or canonical_json_sha256(source) != stored:
        raise AssertionError("External infrastructure manifest hash changed")
    if (
        infrastructure.get("contract_id") != contract.get("contract_id")
        or infrastructure.get("contract_canonical_sha256")
        != canonical_json_sha256(contract)
    ):
        raise AssertionError("Selected external contract differs from frozen infrastructure")
    if infrastructure.get("runtime_environment") != runtime_environment_fingerprint():
        raise AssertionError("Frozen external runtime environment changed")
    for registry, label in (
        ("runtime_canonical_text_sha256", "runtime"),
        ("protected_canonical_text_sha256", "protected artifact"),
    ):
        for relative, expected in infrastructure[registry].items():
            if canonical_text_sha256(root / relative) != expected:
                raise AssertionError(
                    f"Frozen external {label} changed: {relative}"
                )


def deterministic_evaluation_id(
    acceptance: dict,
    manifest_sha256: str,
    infrastructure_sha256: str,
) -> str:
    """Return the one permitted scoring identity for a registered block."""
    return canonical_json_sha256(
        {
            "block_id": acceptance["block_id"],
            "manifest_sha256": manifest_sha256,
            "infrastructure_sha256": infrastructure_sha256,
        }
    )


def acquire_evaluation_guard(
    guard_dir: str | Path,
    guard_payload: dict,
    *,
    resume: bool = False,
) -> Path:
    directory = Path(guard_dir)
    directory.mkdir(parents=True, exist_ok=True)
    evaluation_id = guard_payload["evaluation_id"]
    started = directory / f"{evaluation_id}.started.json"
    consumed = directory / f"{evaluation_id}.consumed.json"
    if consumed.exists():
        raise RuntimeError("This deterministic external evaluation is consumed")
    rendered = json.dumps(guard_payload, indent=2, sort_keys=True) + "\n"
    try:
        with started.open("x", encoding="utf-8") as handle:
            handle.write(rendered)
    except FileExistsError:
        existing = json.loads(started.read_text(encoding="utf-8"))
        if not resume:
            raise RuntimeError(
                "Evaluation already started; explicit identical-hash resume required"
            ) from None
        if existing != guard_payload:
            raise RuntimeError("Evaluation resume hashes differ from the started run")
    return started


@contextmanager
def hold_evaluation_lock(guard_dir: str | Path, evaluation_id: str):
    """Hold a process-wide lock while an evaluation derives external labels."""
    directory = Path(guard_dir)
    directory.mkdir(parents=True, exist_ok=True)
    lock_path = directory / f"{evaluation_id}.lock"
    handle = lock_path.open("a+b")
    try:
        handle.seek(0)
        if not handle.read(1):
            handle.seek(0)
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RuntimeError("External evaluation is already running") from error
            unlock = lambda: msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise RuntimeError("External evaluation is already running") from error
            unlock = lambda: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        try:
            yield
        finally:
            handle.seek(0)
            unlock()
    finally:
        handle.close()


def verify_active_evaluation_guard(
    guard_dir: str | Path,
    guard_payload: dict,
) -> None:
    directory = Path(guard_dir)
    evaluation_id = guard_payload["evaluation_id"]
    started = directory / f"{evaluation_id}.started.json"
    consumed = directory / f"{evaluation_id}.consumed.json"
    if consumed.exists():
        raise RuntimeError("This deterministic external evaluation is consumed")
    if not started.exists() or json.loads(started.read_text(encoding="utf-8")) != guard_payload:
        raise RuntimeError("Started evaluation guard hashes changed before scoring")


def consume_evaluation(
    guard_dir: str | Path,
    guard_payload: dict,
    result_hashes: dict,
) -> dict:
    directory = Path(guard_dir)
    evaluation_id = guard_payload["evaluation_id"]
    started = directory / f"{evaluation_id}.started.json"
    consumed = directory / f"{evaluation_id}.consumed.json"
    if not started.exists():
        raise RuntimeError("Cannot consume an evaluation that never started")
    if consumed.exists():
        raise RuntimeError("External evaluation is already consumed")
    if json.loads(started.read_text(encoding="utf-8")) != guard_payload:
        raise RuntimeError("Started evaluation guard hashes changed before consume")
    receipt = {
        "schema_version": 1,
        "evaluation_id": evaluation_id,
        "block_id": guard_payload["block_id"],
        "status": "consumed",
        "acceptance_id": guard_payload["acceptance_id"],
        "input_set_sha256": guard_payload["input_set_sha256"],
        "frozen_manifest_sha256": guard_payload["frozen_manifest_sha256"],
        "infrastructure_manifest_sha256": guard_payload[
            "infrastructure_manifest_sha256"
        ],
        "result_hashes": result_hashes,
    }
    receipt["receipt_sha256"] = canonical_json_sha256(receipt)
    temporary = consumed.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(consumed)
    return receipt


def external_cause_verdict(
    metric: dict,
    daily_means: Iterable[float | None],
    *,
    required_positive_days: int = 3,
) -> dict:
    means = list(daily_means)
    if len(means) != 5:
        raise ValueError("M5-004 verdict requires exactly five registered days")
    positive_days = sum(value is not None and float(value) > 0 for value in means)
    mean = float(metric["mean"])
    lower = float(metric["familywise_one_sided_low"])
    upper = float(metric["ci95_high"])
    if mean > 0 and lower > 0 and positive_days >= required_positive_days:
        verdict = "supported"
    elif mean > 0 and lower > 0 and positive_days < required_positive_days:
        verdict = "mixed/inconclusive"
    elif upper <= 0:
        verdict = "rejected_for_this_design"
    elif mean > 0:
        verdict = "weak/inconclusive"
    else:
        verdict = "inconclusive"
    return {
        "verdict": verdict,
        "positive_daily_means": int(positive_days),
        "required_positive_daily_means": int(required_positive_days),
        "pooled_mean_positive": mean > 0,
        "one_sided_95pct_lower_positive": lower > 0,
        "ordinary_95pct_upper_non_positive": upper <= 0,
    }


def _load_ticks(items: list[dict]) -> pd.DataFrame:
    frames = []
    for item in sorted(items, key=lambda row: row["alias"]):
        frame = parse_ticks(item["path"]).copy()
        frame["source_alias"] = item["alias"]
        frame["source_row"] = range(len(frame))
        frames.append(frame)
    return pd.concat(frames, ignore_index=True).sort_values(
        ["timestamp", "source_alias", "source_row"], kind="stable"
    ).reset_index(drop=True)


def _gaps_from_intake(intake: dict) -> pd.DataFrame:
    rows = []
    for item in intake["ticks"]["gaps"]:
        rows.append(
            {
                "break_id": item["gap_id"],
                "break_start": pd.Timestamp(item["start"]),
                "break_end": pd.Timestamp(item["end"]),
                "duration_seconds": float(item["duration_seconds"]),
                "gap_classification": item["classification"],
                "exclusion_reason": item["classification"],
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "break_id",
            "break_start",
            "break_end",
            "duration_seconds",
            "gap_classification",
            "exclusion_reason",
        ],
    )


def build_frozen_external_predictions(
    contract: dict,
    input_manifest: dict,
    intake: dict,
    manifest: dict,
) -> tuple[dict[str, pd.DataFrame], dict]:
    block_id = intake["block_id"]
    block = contract["blocks"][block_id]
    cohort_id = f"m5_004_{block_id}_external"
    ticks = _load_ticks(input_manifest["tick_exports"])
    gaps = _gaps_from_intake(intake)
    tables = parse_report(
        input_manifest["report"]["path"],
        report_id=input_manifest["report"]["alias"],
    )
    lifecycle, merge_exceptions, lifecycle_summary = merge_lifecycles(
        tables["positions"], tables["open_positions"]
    )
    events, intervals, state_exceptions = reconstruct_states(lifecycle)
    support = canonicalize_cohort_support(
        intervals,
        events,
        ticks,
        cohort_id=cohort_id,
        breaks=gaps,
    )
    all_bins = []
    all_interval_audits = []
    risk_accounting = {}
    for width_ms in contract["evaluation"]["widths_ms"]:
        bins, interval_audit, accounting = build_wall_clock_risk_bins(
            support, bin_width_seconds=width_ms / 1000
        )
        all_bins.append(bins)
        all_interval_audits.append(interval_audit)
        risk_accounting[str(width_ms)] = accounting
    risk_bins = pd.concat(all_bins, ignore_index=True)
    interval_audit = pd.concat(all_interval_audits, ignore_index=True)
    candidates = prepare_candidate_bins(
        risk_bins,
        interval_audit,
        role_by_date={day: "external" for day in block["sessions"]},
    )
    m5_003_feature_audit, _ = build_feature_audit(
        candidates,
        {cohort_id: ticks},
        {cohort_id: gaps},
    )
    audit, predictors, targets, design = build_unlock_cause_dataset(
        m5_003_feature_audit,
        {cohort_id: ticks},
        {cohort_id: gaps},
    )
    predictions = []
    for width_ms in contract["evaluation"]["widths_ms"]:
        width_design = design[
            design["bin_width_ms"].eq(width_ms)
        ].reset_index(drop=True)
        prediction = predict_cause_bundle(
            width_design,
            manifest["widths"][str(width_ms)]["fitted_bundle"],
        )
        predictions.append(prediction)
    prediction_frame = pd.concat(predictions, ignore_index=True).sort_values(
        ["bin_width_ms", "session_date", "bin_start", "sample_id"],
        kind="stable",
    ).reset_index(drop=True)
    frames = {
        "ticks": ticks,
        "lifecycle_events": events,
        "state_intervals": intervals,
        "coverage_gaps": gaps,
        "risk_bin_audit": risk_bins,
        "interval_audit": interval_audit,
        "unlock_cause_audit": audit,
        "unlock_cause_predictors": predictors,
        "unlock_cause_targets": targets,
        "unlock_cause_predictions": prediction_frame,
    }
    accounting = {
        "lifecycle": {
            **lifecycle_summary,
            "merge_exception_count": int(len(merge_exceptions)),
            "state_exception_count": int(len(state_exceptions)),
        },
        "risk_time": risk_accounting,
    }
    return frames, accounting


def summarize_frozen_external(
    contract: dict,
    intake: dict,
    acceptance: dict,
    predictions: pd.DataFrame,
    accounting: dict,
    manifest_sha256: str,
    infrastructure_sha256: str,
) -> dict:
    block = contract["blocks"][intake["block_id"]]
    widths = {}
    for width_ms in contract["evaluation"]["widths_ms"]:
        frame = predictions[predictions["bin_width_ms"].eq(width_ms)].copy()
        summary = summarize_cause_predictions(
            frame,
            bootstrap_draws=contract["evaluation"]["bootstrap_draws"],
            bootstrap_seed=contract["evaluation"]["bootstrap_seed"],
        )
        daily_by_date = {
            row["session_date"]: row for row in summary["daily"]
        }
        daily = []
        for day in block["sessions"]:
            row = daily_by_date.get(day)
            daily.append(
                {
                    "server_date": day,
                    "events": 0 if row is None else int(row["events"]),
                    "C_age_price_cause_minus_A_age_cause_mean": (
                        None
                        if row is None
                        else row[
                            "C_age_price_cause_minus_A_age_cause_mean"
                        ]
                    ),
                    "C_age_price_cause_minus_B_price_cause_mean": (
                        None
                        if row is None
                        else row[
                            "C_age_price_cause_minus_B_price_cause_mean"
                        ]
                    ),
                }
            )
        result = {
            **summary,
            "daily": daily,
            "leave_one_session_out": [],
            "role": (
                "headline_external_gate"
                if width_ms == contract["evaluation"]["headline_width_ms"]
                else "timing_sensitivity_non_gating"
            ),
        }
        for omitted_day in block["sessions"]:
            retained = frame[~frame["session_date"].eq(omitted_day)].copy()
            if retained.empty:
                omitted_events = 0
                omitted_groups = 0
                omitted_comparisons = None
                omitted_status = "undefined_no_retained_events"
            else:
                omitted_summary = summarize_cause_predictions(
                    retained,
                    bootstrap_draws=contract["evaluation"]["bootstrap_draws"],
                    bootstrap_seed=contract["evaluation"]["bootstrap_seed"],
                )
                omitted_events = int(omitted_summary["events"])
                omitted_groups = int(omitted_summary["groups"])
                omitted_comparisons = omitted_summary["comparisons"]
                omitted_status = "computed"
            result["leave_one_session_out"].append(
                {
                    "omitted_server_date": omitted_day,
                    "events": omitted_events,
                    "groups": omitted_groups,
                    "comparisons": omitted_comparisons,
                    "status": omitted_status,
                    "role": "descriptive_non_gating_no_refit",
                }
            )
        if width_ms == contract["evaluation"]["headline_width_ms"]:
            result["headline_decision"] = external_cause_verdict(
                summary["comparisons"][
                    "C_age_price_cause_minus_A_age_cause"
                ],
                [
                    row["C_age_price_cause_minus_A_age_cause_mean"]
                    for row in daily
                ],
                required_positive_days=contract["evaluation"][
                    "required_positive_daily_means"
                ],
            )
        widths[str(width_ms)] = result
    payload = {
        "schema_version": 1,
        "milestone": "M5-004-external",
        "status": "external_evaluation_consumed",
        "block_id": intake["block_id"],
        "acceptance_id": acceptance["record_id"],
        "input_set_sha256": intake["input_set_sha256"],
        "frozen_manifest_sha256": manifest_sha256,
        "infrastructure_manifest_sha256": infrastructure_sha256,
        "bootstrap": {
            "draws": contract["evaluation"]["bootstrap_draws"],
            "seed": contract["evaluation"]["bootstrap_seed"],
            "cluster_key": contract["evaluation"]["cluster_key"],
        },
        "widths": widths,
        "accounting": accounting,
        "claims": dict(contract["claims"]),
        "validation_gates": {
            "accepted_complete_five_session_block": (
                acceptance["accepted"]
                and acceptance["complete_five_session_block"]
            ),
            "frozen_manifest_used_without_fit": True,
            "one_row_per_joint_valid_unlock": not predictions.duplicated(
                ["cohort_id", "interval_id", "bin_width_ms"]
            ).any(),
            "all_registered_days_published": all(
                len(width["daily"]) == 5 for width in widths.values()
            ),
            "loso_five_sessions_published": all(
                len(width["leave_one_session_out"]) == 5
                and {
                    row["omitted_server_date"]
                    for row in width["leave_one_session_out"]
                }
                == set(block["sessions"])
                and all(
                    row["role"] == "descriptive_non_gating_no_refit"
                    for row in width["leave_one_session_out"]
                )
                for width in widths.values()
            ),
            "sensitivity_non_gating": widths["500"]["role"]
            == "timing_sensitivity_non_gating",
            "tradeable_edge_claim_absent": (
                contract["claims"].get("tradeable_edge") == "not_claimed"
                and contract["claims"].get("profitability") == "not_tested"
                and contract["claims"].get("causality") == "not_claimed"
            ),
        },
    }
    if not all(payload["validation_gates"].values()):
        failed = [
            key
            for key, passed in payload["validation_gates"].items()
            if not passed
        ]
        raise AssertionError(f"Frozen external evaluation failed: {failed}")
    payload["deterministic_report_sha256"] = canonical_json_sha256(payload)
    return payload


def local_frame_hashes(frames: dict[str, pd.DataFrame]) -> dict:
    return {
        name: {
            "rows": int(len(frame)),
            "dataframe_sha256": dataframe_sha256(frame),
        }
        for name, frame in sorted(frames.items())
    }


def verify_input_set(input_manifest: dict, acceptance: dict) -> None:
    observed = canonical_json_sha256(input_set_records(input_manifest))
    if observed != acceptance["input_set_sha256"]:
        raise AssertionError("External input set changed after blind acceptance")


def verify_intake_and_acceptance(
    contract: dict,
    input_manifest: dict,
    intake: dict,
    acceptance: dict,
    infrastructure_sha256: str,
) -> None:
    intake_source = dict(intake)
    stored_intake_hash = intake_source.pop("deterministic_intake_sha256", None)
    if not stored_intake_hash or canonical_json_sha256(intake_source) != stored_intake_hash:
        raise AssertionError("Blind intake deterministic hash changed")
    acceptance_source = dict(acceptance)
    stored_record_id = acceptance_source.pop("record_id", None)
    if not stored_record_id or canonical_json_sha256(acceptance_source) != stored_record_id:
        raise AssertionError("Structural acceptance record hash changed")
    if acceptance.get("blind_intake_sha256") != stored_intake_hash:
        raise AssertionError("Acceptance references another blind intake")
    if acceptance.get("input_set_sha256") != intake.get("input_set_sha256"):
        raise AssertionError("Acceptance input hash differs from blind intake")
    if acceptance.get("infrastructure_manifest_sha256") != infrastructure_sha256:
        raise AssertionError("Acceptance infrastructure hash changed")
    if input_manifest.get("block_id") != intake.get("block_id") or intake.get(
        "block_id"
    ) != acceptance.get("block_id"):
        raise AssertionError("External block identity changed after intake")
    if input_manifest.get("data_origin") != intake.get("data_origin"):
        raise AssertionError("External data-origin marker changed after intake")
    if intake.get("contract_sha256") != canonical_json_sha256(contract):
        raise AssertionError("Blind intake contract hash changed")
    if not acceptance.get("accepted") or not acceptance.get(
        "complete_five_session_block"
    ):
        raise AssertionError("Frozen evaluation requires an accepted full block")
    verify_input_set(input_manifest, acceptance)
    rebuilt_intake, _ = build_blind_intake(contract, input_manifest)
    assert_blind_firewall(rebuilt_intake, contract)
    if rebuilt_intake != intake:
        raise AssertionError("Blind intake does not reproduce from external inputs")
    rebuilt_acceptance = build_structural_record(
        rebuilt_intake, infrastructure_sha256
    )
    if rebuilt_acceptance != acceptance:
        raise AssertionError("Structural acceptance does not reproduce from blind intake")
