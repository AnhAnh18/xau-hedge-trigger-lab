"""Blind structural intake for the untouched M5-004 external block."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Iterable

import pandas as pd

from xau_trigger.acquisition import (
    classify_recurring_gaps,
    detect_report_sections,
    sha256_file,
)
from xau_trigger.parsers.mt5_report import parse_report, parse_report_summary
from xau_trigger.parsers.tick_export import parse_ticks
from xau_trigger.risk_time import detect_coverage_gaps
from xau_trigger.state_reconstruction import merge_lifecycles
from xau_trigger.validation.dataset_checks import (
    inventory_conservation,
    reconcile_report,
)


SAFE_ALIAS = re.compile(r"^[a-z][a-z0-9_-]{2,63}$")
CRITICAL_LIFECYCLE_EXCEPTIONS = {
    "duplicate_closed_position",
    "open_snapshot_conflict",
}


def canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def canonical_text_sha256(path: str | Path) -> str:
    text = Path(path).read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return sha256(normalized.encode("utf-8")).hexdigest()


def verify_blind_infrastructure(root: Path, infrastructure: dict) -> None:
    stored = infrastructure.get("infrastructure_manifest_sha256")
    source = dict(infrastructure)
    source.pop("infrastructure_manifest_sha256", None)
    if not stored or canonical_json_sha256(source) != stored:
        raise AssertionError("External infrastructure manifest hash changed")
    for registry in (
        "runtime_canonical_text_sha256",
        "protected_canonical_text_sha256",
    ):
        for relative, expected in infrastructure[registry].items():
            if canonical_text_sha256(root / relative) != expected:
                raise AssertionError(
                    f"Frozen external infrastructure changed: {relative}"
                )


def load_external_contract(path: str | Path) -> dict:
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {
        "contract_id",
        "blocks",
        "tick_export",
        "trade_report",
        "gap_policy",
        "structural_failure_allowlist",
        "blind_output_forbidden_keys",
        "frozen_package",
        "evaluation",
    }
    missing = sorted(required - set(contract))
    if missing:
        raise ValueError(f"External intake contract missing keys: {missing}")
    if set(contract["blocks"]) != {"primary", "fallback"}:
        raise ValueError("External contract must define primary and fallback")
    for block in contract["blocks"].values():
        if len(block["sessions"]) != 5 or len(set(block["sessions"])) != 5:
            raise ValueError("Every external block must contain five sessions")
    if contract["gap_policy"]["interpolation_allowed"]:
        raise ValueError("External gap interpolation is forbidden")
    if contract["evaluation"]["bootstrap_draws"] != 5000:
        raise ValueError("M5-004 external bootstrap must use 5,000 draws")
    if contract["evaluation"]["bootstrap_seed"] != 5004:
        raise ValueError("M5-004 external bootstrap seed changed")
    return contract


def load_input_aliases(path: str | Path, contract: dict) -> dict:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    block_id = manifest.get("block_id")
    if block_id not in contract["blocks"]:
        raise ValueError("Input manifest uses an unregistered block")
    if manifest.get("data_origin") not in {"real_external", "synthetic_fixture"}:
        raise ValueError("Input manifest data_origin is invalid")
    if manifest.get("symbol") != contract["symbol"]:
        raise ValueError("Input manifest symbol differs from the contract")
    aliases = []
    for section in ("tick_exports", "replica_exports"):
        for item in manifest.get(section, []):
            aliases.append(item.get("alias", ""))
            if not item.get("export_run_id"):
                raise ValueError("Every tick export requires an export_run_id")
    report = manifest.get("report", {})
    aliases.append(report.get("alias", ""))
    if any(not SAFE_ALIAS.fullmatch(alias) for alias in aliases):
        raise ValueError("Input aliases must be generated privacy-safe identifiers")
    if len(aliases) != len(set(aliases)):
        raise ValueError("Input aliases must be unique")
    if not manifest.get("tick_exports"):
        raise ValueError("At least one primary tick export is required")
    if not report.get("path"):
        raise ValueError("Exactly one trade report is required")
    return manifest


def _safe_file_record(item: dict, kind: str) -> dict:
    path = Path(item["path"])
    if not path.is_file():
        raise ValueError(f"{item['alias']} is missing or is not a file")
    return {
        "alias": item["alias"],
        "kind": kind,
        "bytes": int(path.stat().st_size),
        "sha256": sha256_file(path),
        "parser_status": "PASS",
    }


def input_set_records(input_manifest: dict) -> list[dict]:
    records = [
        _safe_file_record(item, "ticks")
        for item in input_manifest.get("tick_exports", [])
    ]
    records.extend(
        _safe_file_record(item, "tick_replica")
        for item in input_manifest.get("replica_exports", [])
    )
    records.append(_safe_file_record(input_manifest["report"], "trade_report"))
    return sorted(records, key=lambda row: (row["kind"], row["alias"]))


def input_set_sha256(input_manifest: dict) -> str:
    return canonical_json_sha256(input_set_records(input_manifest))


def _load_tick_items(items: Iterable[dict]) -> tuple[pd.DataFrame, list[dict]]:
    frames = []
    records = []
    for item in sorted(items, key=lambda row: row["alias"]):
        path = Path(item["path"])
        record = _safe_file_record(item, "ticks")
        try:
            ticks = parse_ticks(path)
        except Exception as error:
            raise ValueError(
                f"{item['alias']} tick parser failed: {type(error).__name__}"
            ) from None
        ticks = ticks.copy()
        ticks["source_alias"] = item["alias"]
        ticks["source_row"] = range(len(ticks))
        frames.append(ticks)
        record.update(
            {
                "rows": int(len(ticks)),
                "first_timestamp": pd.Timestamp(
                    ticks["timestamp"].iloc[0]
                ).isoformat(),
                "last_timestamp": pd.Timestamp(
                    ticks["timestamp"].iloc[-1]
                ).isoformat(),
                "duplicate_millisecond_rows": int(
                    ticks["time_msc"].duplicated(keep=False).sum()
                ),
            }
        )
        records.append(record)
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(
        ["timestamp", "source_alias", "source_row"], kind="stable"
    ).reset_index(drop=True)
    return combined, records


def _clock_seconds(timestamp: pd.Timestamp) -> float:
    return (
        timestamp.hour * 3600
        + timestamp.minute * 60
        + timestamp.second
        + timestamp.microsecond / 1_000_000
    )


def _parse_clock(value: str) -> int:
    hour, minute, second = [int(part) for part in value.split(":")]
    return hour * 3600 + minute * 60 + second


def _boundary_signature(
    ticks: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> tuple | None:
    before = ticks[ticks["timestamp"].le(start)]
    after = ticks[ticks["timestamp"].ge(end)]
    if before.empty or after.empty:
        return None
    left = before.iloc[-1]
    right = after.iloc[0]
    return (
        pd.Timestamp(left["timestamp"]).isoformat(),
        float(left["bid"]),
        float(left["ask"]),
        pd.Timestamp(right["timestamp"]).isoformat(),
        float(right["bid"]),
        float(right["ask"]),
    )


def _replica_evidence(
    gap: pd.Series,
    primary_ticks: pd.DataFrame,
    input_manifest: dict,
) -> dict | None:
    start = pd.Timestamp(gap["break_start"])
    end = pd.Timestamp(gap["break_end"])
    day = start.strftime("%Y-%m-%d")
    primary_signature = _boundary_signature(primary_ticks, start, end)
    primary_runs = {
        str(item["export_run_id"])
        for item in input_manifest["tick_exports"]
        if day in item.get("server_dates", [day])
    }
    for item in sorted(
        input_manifest.get("replica_exports", []),
        key=lambda row: row["alias"],
    ):
        if day not in item.get("server_dates", [day]):
            continue
        if str(item["export_run_id"]) in primary_runs:
            continue
        try:
            replica = parse_ticks(item["path"])
        except Exception:
            continue
        replica_gaps = detect_coverage_gaps(
            replica[["timestamp"]], threshold_seconds=60
        )
        exact = replica_gaps[
            replica_gaps["break_start"].eq(start)
            & replica_gaps["break_end"].eq(end)
        ]
        if exact.empty:
            continue
        if _boundary_signature(replica, start, end) != primary_signature:
            continue
        return {
            "alias": item["alias"],
            "sha256": sha256_file(item["path"]),
            "export_run_id": str(item["export_run_id"]),
            "identical_boundary_ticks": True,
        }
    return None


def _inspect_ticks(
    input_manifest: dict,
    contract: dict,
    block: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, dict, list[str]]:
    ticks, file_records = _load_tick_items(input_manifest["tick_exports"])
    ticks["server_date"] = ticks["timestamp"].dt.strftime("%Y-%m-%d")
    required = list(block["sessions"])
    observed = set(ticks["server_date"].unique())
    failures = []
    unexpected = sorted(observed - set(required))
    if unexpected:
        failures.append("wrong_symbol_or_server_date")

    gap_policy = contract["gap_policy"]
    gaps = classify_recurring_gaps(
        detect_coverage_gaps(
            ticks[["timestamp"]],
            threshold_seconds=gap_policy["threshold_seconds"],
        ),
        minimum_sessions=gap_policy[
            "scheduled_classification_min_recurring_sessions"
        ],
        tolerance_seconds=gap_policy["same_server_clock_tolerance_seconds"],
    )
    accepted_gap_rows = []
    for _, gap in gaps.iterrows():
        classification = str(gap["gap_classification"])
        evidence = None
        if classification == "unknown_coverage_gap":
            evidence = _replica_evidence(gap, ticks, input_manifest)
            if evidence:
                classification = gap_policy[
                    "accepted_unscheduled_classification"
                ]
            else:
                failures.append("unknown_or_nonreplicated_material_quote_gap")
        accepted_gap_rows.append(
            {
                "gap_id": str(gap["break_id"]),
                "start": pd.Timestamp(gap["break_start"]).isoformat(),
                "end": pd.Timestamp(gap["break_end"]).isoformat(),
                "duration_seconds": round(float(gap["duration_seconds"]), 6),
                "classification": classification,
                "accepted": classification
                in {
                    "scheduled_market_closed",
                    gap_policy["accepted_unscheduled_classification"],
                },
                "interpolation_allowed": False,
                "replica_evidence": evidence,
            }
        )
    if len(gaps):
        gaps = gaps.copy()
        gaps["gap_classification"] = [
            row["classification"] for row in accepted_gap_rows
        ]
        gaps["exclusion_reason"] = gaps["gap_classification"]

    first_limit = _parse_clock(
        contract["tick_export"]["first_tick_no_later_than_server_time"]
    )
    last_limit = _parse_clock(
        contract["tick_export"]["last_tick_no_earlier_than_server_time"]
    )
    sessions = []
    for day in required:
        group = ticks[ticks["server_date"].eq(day)]
        if group.empty:
            failures.append("missing_or_unparseable_registered_session")
            sessions.append(
                {
                    "server_date": day,
                    "present": False,
                    "status": "FAIL",
                }
            )
            continue
        first = pd.Timestamp(group["timestamp"].iloc[0])
        last = pd.Timestamp(group["timestamp"].iloc[-1])
        boundary_pass = (
            _clock_seconds(first) <= first_limit
            and _clock_seconds(last) >= last_limit
        )
        if not boundary_pass:
            failures.append("boundary_coverage_failure")
        sessions.append(
            {
                "server_date": day,
                "present": True,
                "first_timestamp": first.isoformat(),
                "last_timestamp": last.isoformat(),
                "boundary_status": "PASS" if boundary_pass else "FAIL",
                "timestamp_order_status": "PASS",
                "rows": int(len(group)),
                "duplicate_millisecond_rows": int(
                    group["time_msc"].duplicated(keep=False).sum()
                ),
                "duplicate_preservation_status": "PASS",
                "status": "PASS" if boundary_pass else "FAIL",
            }
        )
    output = {
        "status": "PASS" if not failures else "FAIL",
        "files": file_records,
        "sessions": sessions,
        "unexpected_server_dates": unexpected,
        "gaps": accepted_gap_rows,
        "duplicate_policy": "preserve_and_report_never_deduplicate",
    }
    return ticks, gaps, output, failures


def _report_timestamps(tables: dict[str, pd.DataFrame]) -> pd.Series:
    values = []
    for name, columns in {
        "positions": ("open_time", "close_time"),
        "open_positions": ("open_time",),
        "orders": ("open_time", "completion_time"),
        "deals": ("time",),
    }.items():
        for column in columns:
            if column in tables[name]:
                values.extend(pd.to_datetime(tables[name][column]).dropna())
    return pd.Series(values, dtype="datetime64[ns]")


def _inspect_report(
    input_manifest: dict,
    contract: dict,
    block: dict,
    ticks: pd.DataFrame,
) -> tuple[dict[str, pd.DataFrame], dict, list[str]]:
    item = input_manifest["report"]
    failures = []
    if (
        item.get("declared_context_start") != block["report_context_start"]
        or item.get("declared_context_end") != block["report_context_end"]
    ):
        failures.append("report_context_incomplete")
    path = Path(item["path"])
    record = _safe_file_record(item, "trade_report")
    try:
        sections = detect_report_sections(path)
        tables = parse_report(path, report_id=item["alias"])
        summary = parse_report_summary(path)
    except Exception as error:
        raise ValueError(
            f"{item['alias']} report parser failed: {type(error).__name__}"
        ) from None
    missing = sorted(set(contract["trade_report"]["required_sections"]) - sections)
    if missing:
        failures.append("missing_or_unparseable_registered_session")

    symbols = set()
    for table in tables.values():
        if "symbol" in table:
            symbols.update(
                table["symbol"].dropna().astype(str).str.upper().loc[
                    lambda values: values.ne("")
                ]
            )
    if symbols - {contract["symbol"]}:
        failures.append("wrong_symbol_or_server_date")

    financial = reconcile_report(
        tables["positions"], summary["reported_net_profit"]
    )
    if financial["status"] != "PASS":
        failures.append("financial_reconciliation_failure")
    lifecycle, lifecycle_exceptions, lifecycle_summary = merge_lifecycles(
        tables["positions"], tables["open_positions"]
    )
    tick_start = pd.Timestamp(ticks["timestamp"].min())
    tick_end = pd.Timestamp(ticks["timestamp"].max())
    inventory_positions = lifecycle.copy()
    inventory_positions["close_time"] = pd.to_datetime(
        inventory_positions["close_time"]
    ).fillna(pd.Timestamp.max)
    inventory = inventory_conservation(
        inventory_positions, tick_start, tick_end
    )
    if inventory["status"] != "PASS":
        failures.append("inventory_reconciliation_failure")
    exception_types = (
        set(lifecycle_exceptions["exception_type"].astype(str))
        if not lifecycle_exceptions.empty
        else set()
    )
    closed_ids = set(tables["positions"]["position_id"].astype(str))
    open_only_ids = set(
        tables["open_positions"]["position_id"].astype(str)
    ) - closed_ids
    lifecycle_pass = not bool(
        exception_types & CRITICAL_LIFECYCLE_EXCEPTIONS
    ) and len(lifecycle) == len(tables["positions"]) + len(open_only_ids)
    if not lifecycle_pass:
        failures.append("lifecycle_completeness_failure")

    timestamps = _report_timestamps(tables)
    overlap = (
        not timestamps.empty
        and timestamps.max() >= tick_start
        and timestamps.min() <= tick_end
    )
    if not overlap:
        failures.append("report_context_incomplete")

    record.update(
        {
            "required_sections_status": "PASS" if not missing else "FAIL",
            "report_context_status": (
                "PASS"
                if "report_context_incomplete" not in failures
                else "FAIL"
            ),
            "symbol_status": (
                "PASS"
                if "wrong_symbol_or_server_date" not in failures
                else "FAIL"
            ),
        }
    )
    output = {
        "status": "PASS" if not failures else "FAIL",
        "file": record,
        "required_sections_status": record["required_sections_status"],
        "declared_context": {
            "start": item.get("declared_context_start"),
            "end": item.get("declared_context_end"),
            "status": record["report_context_status"],
        },
        "report_tick_overlap_status": "PASS" if overlap else "FAIL",
        "financial_reconciliation_status": financial["status"],
        "inventory_reconciliation_status": inventory["status"],
        "lifecycle_completeness": {
            "status": "PASS" if lifecycle_pass else "FAIL",
            "records_accounted": int(len(lifecycle)),
            "carry_over_records": int(lifecycle_summary["carry_over_positions"]),
            "critical_exception_count": int(
                len(exception_types & CRITICAL_LIFECYCLE_EXCEPTIONS)
            ),
        },
    }
    return tables, output, failures


def assert_blind_firewall(payload: dict, contract: dict) -> None:
    forbidden = tuple(
        str(value).lower()
        for value in contract["blind_output_forbidden_keys"]
    )

    def visit(value: object, path: str = "") -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                lowered = str(key).lower()
                if any(token in lowered for token in forbidden):
                    raise AssertionError(
                        f"Blind intake emitted forbidden field at {path}/{key}"
                    )
                visit(child, f"{path}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{path}/{index}")

    visit(payload)


def build_blind_intake(
    contract: dict,
    input_manifest: dict,
) -> tuple[dict, dict]:
    block_id = input_manifest["block_id"]
    block = contract["blocks"][block_id]
    ticks, gaps, tick_output, tick_failures = _inspect_ticks(
        input_manifest, contract, block
    )
    _, report_output, report_failures = _inspect_report(
        input_manifest, contract, block, ticks
    )
    failures = sorted(set(tick_failures + report_failures))
    allowlist = set(contract["structural_failure_allowlist"])
    if set(failures) - allowlist:
        raise AssertionError("Blind intake produced an unregistered failure code")
    records = input_set_records(input_manifest)
    payload = {
        "schema_version": 1,
        "contract_id": contract["contract_id"],
        "contract_sha256": canonical_json_sha256(contract),
        "block_id": block_id,
        "block_role": block["role"],
        "required_sessions": list(block["sessions"]),
        "files": records,
        "ticks": tick_output,
        "trade_report": report_output,
        "information_firewall": {
            "status": "PASS",
            "allowlist_rendering": True,
        },
        "structural_status": "accepted" if not failures else "structural_failure",
        "failure_codes": failures,
        "input_set_sha256": canonical_json_sha256(records),
        "data_origin": input_manifest["data_origin"],
    }
    payload["deterministic_intake_sha256"] = canonical_json_sha256(payload)
    assert_blind_firewall(payload, contract)
    local = {"ticks": ticks, "gaps": gaps}
    return payload, local


def build_structural_record(intake: dict, infrastructure_sha256: str) -> dict:
    accepted = intake["structural_status"] == "accepted"
    payload = {
        "schema_version": 1,
        "block_id": intake["block_id"],
        "accepted": accepted,
        "complete_five_session_block": (
            len(intake["required_sessions"]) == 5
            and all(row["present"] for row in intake["ticks"]["sessions"])
        ),
        "blind_intake_sha256": intake["deterministic_intake_sha256"],
        "input_set_sha256": intake["input_set_sha256"],
        "failure_codes": list(intake["failure_codes"]),
        "infrastructure_manifest_sha256": infrastructure_sha256,
        "fallback_authorized": False,
    }
    payload["record_id"] = canonical_json_sha256(payload)
    return payload


def validate_fallback_authorization(
    authorization: dict,
    primary_failure: dict,
    infrastructure_sha256: str,
) -> None:
    if primary_failure.get("block_id") != "primary":
        raise ValueError("Fallback requires a primary structural record")
    if primary_failure.get("accepted") is not False:
        raise ValueError("Fallback cannot follow an accepted primary block")
    if authorization.get("reviewed") is not True:
        raise ValueError("Fallback requires explicit reviewed authorization")
    if authorization.get("primary_failure_record_id") != primary_failure.get(
        "record_id"
    ):
        raise ValueError("Fallback authorization references another failure")
    if authorization.get("infrastructure_manifest_sha256") != infrastructure_sha256:
        raise ValueError("Fallback authorization infrastructure hash changed")
    if authorization.get("reason_codes") != primary_failure.get("failure_codes"):
        raise ValueError("Fallback authorization reason codes changed")
