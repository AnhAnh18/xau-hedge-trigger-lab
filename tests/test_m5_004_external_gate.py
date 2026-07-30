from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

from xau_trigger.acquisition import build_synthetic_acquisition_files
from xau_trigger.m5_004_external_intake import (
    assert_blind_firewall,
    build_blind_intake,
    build_structural_record,
    canonical_json_sha256,
    load_external_contract,
    load_input_aliases,
    validate_fallback_authorization,
)
from xau_trigger.m5_004_frozen_evaluator import (
    acquire_evaluation_guard,
    build_frozen_external_predictions,
    consume_evaluation,
    deterministic_evaluation_id,
    external_cause_verdict,
    local_frame_hashes,
    summarize_frozen_external,
    verify_infrastructure_manifest,
    verify_intake_and_acceptance,
    verify_frozen_package,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "data" / "m5_004_external_intake_contract.json"


def _contract() -> dict:
    return load_external_contract(CONTRACT_PATH)


def _synthetic_inputs(tmp_path: Path) -> tuple[dict, dict]:
    contract = _contract()
    block = contract["blocks"]["primary"]
    plan = {
        "sessions": block["sessions"],
        "tick_export": contract["tick_export"],
        "trade_report": {
            **contract["trade_report"],
            "required_period_start": block["report_context_start"],
            "required_period_end": block["report_context_end"],
        },
        "coverage_gap_policy": {
            "threshold_seconds": 60,
            "scheduled_classification_min_recurring_sessions": 3,
            "same_server_clock_tolerance_seconds": 120,
        },
    }
    tick_path, report_path = build_synthetic_acquisition_files(plan, tmp_path)
    # The shared generic fixture has a deliberately arbitrary summary. M5-004
    # intake needs a financially reconciled fixture: five positions x 1.00.
    report_path.write_text(
        report_path.read_text(encoding="utf-8").replace(
            "Total Net Profit:</td><td>3.00",
            "Total Net Profit:</td><td>5.00",
        ),
        encoding="utf-8",
    )
    inputs = {
        "schema_version": 1,
        "block_id": "primary",
        "data_origin": "synthetic_fixture",
        "symbol": "XAUUSD",
        "tick_exports": [
            {
                "alias": "primary_ticks",
                "path": str(tick_path),
                "export_run_id": "primary-run-a",
                "server_dates": block["sessions"],
            }
        ],
        "replica_exports": [],
        "report": {
            "alias": "primary_report",
            "path": str(report_path),
            "declared_context_start": block["report_context_start"],
            "declared_context_end": block["report_context_end"],
        },
    }
    return contract, inputs


def _cause_fixture_inputs(tmp_path: Path) -> tuple[dict, dict]:
    contract = _contract()
    block = contract["blocks"]["primary"]
    tick_path = tmp_path / "cause_ticks.tsv"
    timestamps = set()
    for day in block["sessions"]:
        timestamps.update(
            pd.date_range(
                f"{day} 01:00:00",
                f"{day} 23:50:00",
                freq="60s",
            )
        )
        for hour in (12, 13):
            timestamps.update(
                pd.date_range(
                    f"{day} {hour:02d}:00:00",
                    periods=36,
                    freq="1s",
                )
            )
    tick_lines = [
        "<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\t<FLAGS>"
    ]
    for index, timestamp in enumerate(sorted(timestamps)):
        bid = 4000.0 + 0.01 * np.sin(index / 7)
        tick_lines.append(
            f"{timestamp:%Y.%m.%d}\t{timestamp:%H:%M:%S}.000"
            f"\t{bid:.5f}\t{bid + 0.20:.5f}\t\t0\t6"
        )
    tick_path.write_text("\n".join(tick_lines) + "\n", encoding="utf-8")

    report_path = tmp_path / "cause_report.html"
    lines = [
        "<html><body><table>",
        '<tr><th colspan="14">Positions</th></tr>',
        "<tr><th>Time</th><th>Position</th><th>Symbol</th><th>Type</th>"
        "<th>Volume</th><th>Price</th><th>S / L</th><th>T / P</th>"
        "<th>Time</th><th>Price</th><th>Commission</th><th>Swap</th>"
        "<th>Profit</th></tr>",
    ]
    position_id = 1000
    for day in block["sessions"]:
        date = day.replace("-", ".")
        sequences = [
            ("12:00:00", "12:00:30", "buy"),
            ("12:00:05", "12:00:20", "sell"),
            ("13:00:00", "13:00:30", "sell"),
            ("13:00:05", "13:00:20", "buy"),
        ]
        for opened, closed, side in sequences:
            position_id += 1
            lines.append(
                f"<tr><td>{date} {opened}</td><td>{position_id}</td>"
                f"<td>XAUUSD</td><td>{side}</td><td>0.3</td>"
                "<td>4000.00</td><td></td><td></td>"
                f"<td>{date} {closed}</td><td>4000.00</td>"
                "<td>0.00</td><td>0.00</td><td>0.00</td></tr>"
            )
    lines.extend(
        [
            '<tr><th colspan="11">Orders</th></tr>',
            "<tr><th>Open Time</th><th>Order</th><th>Symbol</th>"
            "<th>Type</th><th>Volume</th><th>Price</th><th>S / L</th>"
            "<th>T / P</th><th>Time</th><th>State</th><th>Comment</th></tr>",
            '<tr><th colspan="15">Deals</th></tr>',
            "<tr><th>Time</th><th>Deal</th><th>Symbol</th><th>Type</th>"
            "<th>Direction</th><th>Volume</th><th>Price</th><th>Order</th>"
            "<th>Cost</th><th>Commission</th><th>Fee</th><th>Swap</th>"
            "<th>Profit</th><th>Balance</th><th>Comment</th></tr>",
            '<tr><th colspan="12">Open Positions</th></tr>',
            "<tr><th>Time</th><th>Position</th><th>Symbol</th><th>Type</th>"
            "<th>Volume</th><th>Price</th><th>S / L</th><th>T / P</th>"
            "<th>Market Price</th><th>Swap</th><th>Profit</th>"
            "<th>Comment</th></tr>",
            "<tr><td>Total Net Profit:</td><td>0.00</td></tr>",
            "</table></body></html>",
        ]
    )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    inputs = {
        "schema_version": 1,
        "block_id": "primary",
        "data_origin": "synthetic_fixture",
        "symbol": "XAUUSD",
        "tick_exports": [
            {
                "alias": "cause_ticks",
                "path": str(tick_path),
                "export_run_id": "cause-run-a",
                "server_dates": block["sessions"],
            }
        ],
        "replica_exports": [],
        "report": {
            "alias": "cause_report",
            "path": str(report_path),
            "declared_context_start": block["report_context_start"],
            "declared_context_end": block["report_context_end"],
        },
    }
    return contract, inputs


def test_external_contract_pins_distinct_raw_and_canonical_hashes() -> None:
    contract = _contract()
    package = contract["frozen_package"]

    assert package["manifest_canonical_sha256"] == (
        "38169823c993529c746f0f4775536ab140effd3638f0e45a4b1002adbf561709"
    )
    assert package["manifest_raw_file_sha256"] == (
        "6c5b111265771d510600b248613a006cf4e99e73cc0d3ee3c1b883a7e875082b"
    )
    assert package["manifest_canonical_sha256"] != package[
        "manifest_raw_file_sha256"
    ]
    verify_frozen_package(ROOT, contract)


def test_infrastructure_manifest_reconciles_runtime_hashes() -> None:
    path = (
        ROOT
        / "reports"
        / "phase_05"
        / "m5_004_external_infrastructure_manifest.json"
    )
    infrastructure = json.loads(path.read_text(encoding="utf-8"))

    verify_infrastructure_manifest(ROOT, infrastructure)
    assert infrastructure["external_data_seen"] is False
    assert infrastructure["external_evaluation_consumed"] is False
    assert infrastructure["m6_started"] is False


def test_intake_has_no_model_import_and_evaluator_has_no_fit_path() -> None:
    intake_source = (
        ROOT / "src" / "xau_trigger" / "m5_004_external_intake.py"
    ).read_text(encoding="utf-8")
    evaluator_source = (
        ROOT / "src" / "xau_trigger" / "m5_004_frozen_evaluator.py"
    ).read_text(encoding="utf-8")
    cli_source = (
        ROOT / "scripts" / "evaluate_m5_004_external.py"
    ).read_text(encoding="utf-8")

    assert "unlock_cause" not in intake_source
    assert "frozen_evaluator" not in intake_source
    for forbidden in (
        "fit_cause_bundle",
        "select_cause_regularization",
        "fit_logistic_l2",
        ".fit(",
        "fit_transform",
    ):
        assert forbidden not in evaluator_source
        assert forbidden not in cli_source
    assert cli_source.index("acquire_evaluation_guard(") < cli_source.index(
        "build_frozen_external_predictions("
    )


def test_blind_intake_accepts_complete_fixture_and_is_deterministic(
    tmp_path: Path,
) -> None:
    contract, inputs = _synthetic_inputs(tmp_path)

    first, _ = build_blind_intake(contract, inputs)
    second, _ = build_blind_intake(contract, inputs)

    assert first == second
    assert first["structural_status"] == "accepted"
    assert len(first["ticks"]["sessions"]) == 5
    assert all(row["present"] for row in first["ticks"]["sessions"])
    assert first["trade_report"]["financial_reconciliation_status"] == "PASS"
    assert first["trade_report"]["inventory_reconciliation_status"] == "PASS"
    assert_blind_firewall(first, contract)
    rendered = json.dumps(first).lower()
    assert "unlock_to_buy" not in rendered
    assert "unlock_to_sell" not in rendered
    assert str(tmp_path).lower() not in rendered


def test_missing_session_is_structural_failure(tmp_path: Path) -> None:
    contract, inputs = _synthetic_inputs(tmp_path)
    tick_path = Path(inputs["tick_exports"][0]["path"])
    lines = tick_path.read_text(encoding="utf-8").splitlines()
    tick_path.write_text(
        "\n".join(
            line for line in lines if not line.startswith("2026.08.05")
        )
        + "\n",
        encoding="utf-8",
    )

    intake, _ = build_blind_intake(contract, inputs)

    assert intake["structural_status"] == "structural_failure"
    assert "missing_or_unparseable_registered_session" in intake["failure_codes"]


def test_duplicate_milliseconds_are_preserved(tmp_path: Path) -> None:
    contract, inputs = _synthetic_inputs(tmp_path)
    tick_path = Path(inputs["tick_exports"][0]["path"])
    lines = tick_path.read_text(encoding="utf-8").splitlines()
    lines.insert(2, lines[1])
    tick_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    intake, _ = build_blind_intake(contract, inputs)

    assert intake["structural_status"] == "accepted"
    assert intake["ticks"]["files"][0]["duplicate_millisecond_rows"] == 2
    assert intake["ticks"]["sessions"][0][
        "duplicate_preservation_status"
    ] == "PASS"


def _insert_replicated_gap(
    inputs: dict,
    *,
    include_replica: bool,
) -> None:
    primary = Path(inputs["tick_exports"][0]["path"])
    lines = primary.read_text(encoding="utf-8").splitlines()
    filtered = [
        line
        for line in lines
        if not (
            line.startswith("2026.08.03")
            and (
                "12:01:00.000" in line
                or "12:02:00.000" in line
            )
        )
    ]
    primary.write_text("\n".join(filtered) + "\n", encoding="utf-8")
    if include_replica:
        replica = primary.with_name("independent_replica.tsv")
        shutil.copyfile(primary, replica)
        inputs["replica_exports"] = [
            {
                "alias": "primary_ticks_replica",
                "path": str(replica),
                "export_run_id": "independent-run-b",
                "server_dates": ["2026-08-03"],
            }
        ]


def test_unknown_material_gap_requires_replica(tmp_path: Path) -> None:
    contract, inputs = _synthetic_inputs(tmp_path)
    _insert_replicated_gap(inputs, include_replica=False)

    intake, _ = build_blind_intake(contract, inputs)

    assert intake["structural_status"] == "structural_failure"
    assert "unknown_or_nonreplicated_material_quote_gap" in intake[
        "failure_codes"
    ]


def test_identical_independent_replica_accepts_material_gap(
    tmp_path: Path,
) -> None:
    contract, inputs = _synthetic_inputs(tmp_path)
    _insert_replicated_gap(inputs, include_replica=True)

    intake, _ = build_blind_intake(contract, inputs)

    assert intake["structural_status"] == "accepted"
    replicated = [
        gap
        for gap in intake["ticks"]["gaps"]
        if gap["classification"] == "replicated_source_quote_gap"
    ]
    assert len(replicated) == 1
    assert replicated[0]["replica_evidence"]["identical_boundary_ticks"]
    assert replicated[0]["interpolation_allowed"] is False


def test_report_context_declaration_is_locked(tmp_path: Path) -> None:
    contract, inputs = _synthetic_inputs(tmp_path)
    inputs["report"]["declared_context_end"] = "2026-08-07"

    intake, _ = build_blind_intake(contract, inputs)

    assert "report_context_incomplete" in intake["failure_codes"]


def test_firewall_rejects_directional_or_performance_field() -> None:
    contract = _contract()
    for key in ("cause_label", "unlock_to_buy_count", "prediction_score", "auc"):
        with pytest.raises(AssertionError, match="forbidden field"):
            assert_blind_firewall({"safe": {key: 1}}, contract)


def test_guard_requires_explicit_identical_resume_and_refuses_consumed(
    tmp_path: Path,
) -> None:
    payload = {
        "evaluation_id": "evaluation-abc",
        "block_id": "primary",
        "acceptance_id": "acceptance-abc",
        "input_set_sha256": "input-abc",
        "frozen_manifest_sha256": "manifest-abc",
        "infrastructure_manifest_sha256": "infra-abc",
        "status": "started",
    }
    acquire_evaluation_guard(tmp_path, payload)
    with pytest.raises(RuntimeError, match="explicit identical-hash resume"):
        acquire_evaluation_guard(tmp_path, payload)
    acquire_evaluation_guard(tmp_path, payload, resume=True)
    changed = {**payload, "input_set_sha256": "changed"}
    with pytest.raises(RuntimeError, match="hashes differ"):
        acquire_evaluation_guard(tmp_path, changed, resume=True)
    receipt = consume_evaluation(tmp_path, payload, {"report": "hash"})
    assert receipt["status"] == "consumed"
    with pytest.raises(RuntimeError, match="consumed"):
        acquire_evaluation_guard(tmp_path, payload, resume=True)


def test_consume_rejects_tampered_started_guard(tmp_path: Path) -> None:
    payload = {
        "evaluation_id": "evaluation-tamper",
        "block_id": "primary",
        "acceptance_id": "acceptance-abc",
        "input_set_sha256": "input-abc",
        "frozen_manifest_sha256": "manifest-abc",
        "infrastructure_manifest_sha256": "infra-abc",
        "status": "started",
    }
    started = acquire_evaluation_guard(tmp_path, payload)
    started.write_text(
        json.dumps({**payload, "input_set_sha256": "changed"}),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="guard hashes changed"):
        consume_evaluation(tmp_path, payload, {"report": "hash"})


def test_evaluation_id_binds_acceptance_input_model_and_runtime() -> None:
    acceptance = {
        "block_id": "primary",
        "record_id": "acceptance-a",
        "input_set_sha256": "input-a",
    }
    first = deterministic_evaluation_id(acceptance, "model-a", "infra-a")
    assert first != deterministic_evaluation_id(
        {**acceptance, "input_set_sha256": "input-b"},
        "model-a",
        "infra-a",
    )
    assert first != deterministic_evaluation_id(
        acceptance, "model-b", "infra-a"
    )
    assert first != deterministic_evaluation_id(
        acceptance, "model-a", "infra-b"
    )


@pytest.mark.parametrize(
    ("mean", "low", "high", "daily", "expected"),
    [
        (0.1, 0.01, 0.2, [1, 1, 1, -1, -1], "supported"),
        (0.1, 0.01, 0.2, [1, 1, -1, -1, -1], "mixed/inconclusive"),
        (-0.1, -0.2, 0.0, [-1] * 5, "rejected_for_this_design"),
        (0.1, -0.01, 0.2, [1] * 5, "weak/inconclusive"),
        (-0.01, -0.1, 0.1, [None] * 5, "inconclusive"),
    ],
)
def test_exact_five_day_verdict_logic(
    mean: float,
    low: float,
    high: float,
    daily: list[float | None],
    expected: str,
) -> None:
    metric = {
        "mean": mean,
        "familywise_one_sided_low": low,
        "ci95_high": high,
    }
    assert external_cause_verdict(metric, daily)["verdict"] == expected


def _synthetic_predictions() -> pd.DataFrame:
    rows = []
    for width in (1000, 500):
        for day_index, day in enumerate(
            ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06"]
        ):
            for index in range(4):
                label = index % 2
                row = {
                    "sample_id": f"{width}-{day}-{index}",
                    "cohort_id": "primary",
                    "interval_id": f"{day}-{index}",
                    "group_id": f"primary:{day}-{index}",
                    "bin_width_ms": width,
                    "bin_start": pd.Timestamp(day) + pd.Timedelta(hours=12),
                    "session_date": day,
                    "analysis_role": "external",
                    "state_age_seconds": 10.0,
                    "cause_label": label,
                    "p_A_const_cause": 0.5,
                    "p_A_age_cause": 0.5,
                    "p_B_price_cause": 0.5,
                    "p_C_age_price_cause": 0.55 if label else 0.45,
                }
                for group in (
                    "momentum",
                    "range_location",
                    "boundary_side",
                    "state_path",
                ):
                    row[f"p_C_without_{group}"] = 0.52 if label else 0.48
                rows.append(row)
    return pd.DataFrame(rows)


def test_summary_publishes_zero_event_day_as_null_and_500ms_is_nongating() -> None:
    contract = _contract()
    predictions = _synthetic_predictions()
    intake = {
        "block_id": "primary",
        "input_set_sha256": "input-a",
    }
    acceptance = {
        "record_id": "accept-a",
        "accepted": True,
        "complete_five_session_block": True,
    }

    report = summarize_frozen_external(
        contract,
        intake,
        acceptance,
        predictions,
        {"synthetic": True},
        contract["frozen_package"]["manifest_canonical_sha256"],
        "infra-a",
    )

    assert report["widths"]["500"]["role"] == "timing_sensitivity_non_gating"
    assert "headline_decision" not in report["widths"]["500"]
    missing_day = report["widths"]["1000"]["daily"][-1]
    assert missing_day["server_date"] == "2026-08-07"
    assert missing_day["events"] == 0
    assert missing_day["C_age_price_cause_minus_A_age_cause_mean"] is None
    loso = report["widths"]["1000"]["leave_one_session_out"]
    assert len(loso) == 5
    assert {row["omitted_server_date"] for row in loso} == set(
        contract["blocks"]["primary"]["sessions"]
    )
    assert all(row["role"] == "descriptive_non_gating_no_refit" for row in loso)
    assert report["validation_gates"]["loso_five_sessions_published"] is True


def test_frozen_end_to_end_fixture_scores_without_refit(
    tmp_path: Path,
) -> None:
    contract, inputs = _cause_fixture_inputs(tmp_path)
    intake, _ = build_blind_intake(contract, inputs)
    infrastructure = json.loads(
        (
            ROOT
            / "reports"
            / "phase_05"
            / "m5_004_external_infrastructure_manifest.json"
        ).read_text(encoding="utf-8")
    )
    acceptance = build_structural_record(
        intake, infrastructure["infrastructure_manifest_sha256"]
    )
    manifest, _ = verify_frozen_package(ROOT, contract)

    frames, accounting = build_frozen_external_predictions(
        contract, inputs, intake, manifest
    )
    report = summarize_frozen_external(
        contract,
        intake,
        acceptance,
        frames["unlock_cause_predictions"],
        accounting,
        manifest["frozen_manifest_sha256"],
        infrastructure["infrastructure_manifest_sha256"],
    )
    repeated_frames, repeated_accounting = build_frozen_external_predictions(
        contract, inputs, intake, manifest
    )
    repeated_report = summarize_frozen_external(
        contract,
        intake,
        acceptance,
        repeated_frames["unlock_cause_predictions"],
        repeated_accounting,
        manifest["frozen_manifest_sha256"],
        infrastructure["infrastructure_manifest_sha256"],
    )

    predictions = frames["unlock_cause_predictions"]
    assert intake["structural_status"] == "accepted"
    assert set(predictions["bin_width_ms"]) == {500, 1000}
    assert predictions.groupby("bin_width_ms").size().to_dict() == {
        500: 10,
        1000: 10,
    }
    assert len(report["widths"]["1000"]["daily"]) == 5
    assert report["widths"]["500"]["role"] == "timing_sensitivity_non_gating"
    assert all(
        value["dataframe_sha256"]
        for value in local_frame_hashes(frames).values()
    )
    assert report == repeated_report
    assert local_frame_hashes(frames) == local_frame_hashes(repeated_frames)


def test_two_stage_cli_fixture_and_consumption_guard(tmp_path: Path) -> None:
    _, inputs = _cause_fixture_inputs(tmp_path)
    inputs_path = tmp_path / "input_aliases.local.json"
    inputs_path.write_text(
        json.dumps(inputs, indent=2), encoding="utf-8"
    )
    output = tmp_path / "reports"
    intake_command = [
        sys.executable,
        "scripts/intake_m5_004_external.py",
        "--inputs",
        str(inputs_path),
        "--output-dir",
        str(output),
        "--allow-synthetic-fixture",
    ]
    intake_run = subprocess.run(
        intake_command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "unlock_to_buy" not in intake_run.stdout.lower()
    assert "prediction" not in intake_run.stdout.lower()

    evaluate_command = [
        sys.executable,
        "scripts/evaluate_m5_004_external.py",
        "--inputs",
        str(inputs_path),
        "--intake",
        str(output / "m5_004_primary_blind_intake.json"),
        "--acceptance",
        str(output / "m5_004_primary_structural_acceptance.json"),
        "--output-dir",
        str(output),
        "--local-dir",
        str(tmp_path / "local"),
        "--guard-dir",
        str(tmp_path / "guard"),
        "--allow-synthetic-fixture",
    ]
    first = subprocess.run(
        evaluate_command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(first.stdout)["status"] == "consumed"
    repeated = subprocess.run(
        evaluate_command,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert repeated.returncode != 0
    assert "consumed" in (repeated.stderr + repeated.stdout).lower()


def test_fallback_requires_reviewed_primary_failure() -> None:
    primary = {
        "block_id": "primary",
        "accepted": False,
        "failure_codes": ["boundary_coverage_failure"],
    }
    primary["record_id"] = canonical_json_sha256(primary)
    authorization = {
        "reviewed": True,
        "primary_failure_record_id": primary["record_id"],
        "infrastructure_manifest_sha256": "infra-a",
        "reason_codes": ["boundary_coverage_failure"],
    }
    validate_fallback_authorization(authorization, primary, "infra-a")
    with pytest.raises(ValueError, match="explicit reviewed"):
        validate_fallback_authorization(
            {**authorization, "reviewed": False}, primary, "infra-a"
        )
    with pytest.raises(ValueError, match="record hash changed"):
        validate_fallback_authorization(
            authorization,
            {**primary, "failure_codes": ["financial_reconciliation_failure"]},
            "infra-a",
        )


def test_structural_record_does_not_auto_authorize_fallback(
    tmp_path: Path,
) -> None:
    contract, inputs = _synthetic_inputs(tmp_path)
    intake, _ = build_blind_intake(contract, inputs)

    record = build_structural_record(intake, "infra-a")

    assert record["accepted"] is True
    assert record["fallback_authorized"] is False
    assert record["record_id"] == canonical_json_sha256(
        {key: value for key, value in record.items() if key != "record_id"}
    )


def test_intake_or_acceptance_tampering_is_rejected(tmp_path: Path) -> None:
    contract, inputs = _synthetic_inputs(tmp_path)
    intake, _ = build_blind_intake(contract, inputs)
    acceptance = build_structural_record(intake, "infra-a")
    verify_intake_and_acceptance(
        contract, inputs, intake, acceptance, "infra-a"
    )

    changed_intake = {**intake, "structural_status": "structural_failure"}
    with pytest.raises(AssertionError, match="intake deterministic hash"):
        verify_intake_and_acceptance(
            contract, inputs, changed_intake, acceptance, "infra-a"
        )
    changed_acceptance = {**acceptance, "accepted": False}
    with pytest.raises(AssertionError, match="acceptance record hash"):
        verify_intake_and_acceptance(
            contract, inputs, intake, changed_acceptance, "infra-a"
        )
