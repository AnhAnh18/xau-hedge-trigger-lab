"""Blind structural intake for the untouched M5-004 external block."""
from __future__ import annotations

from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import re
import shutil
import sys
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
PRIMARY_INTAKE_REGISTRATION_SCHEMA_VERSION = 1


def primary_intake_registration_path(root: str | Path) -> Path:
    return (
        Path(root)
        / "data"
        / "interim"
        / "m5_004_external"
        / "primary_intake_registration.json"
    )


def canonical_json_sha256(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return sha256(encoded.encode("utf-8")).hexdigest()


def canonical_text_sha256(path: str | Path) -> str:
    text = Path(path).read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return sha256(normalized.encode("utf-8")).hexdigest()


def runtime_environment_fingerprint() -> dict:
    """Pin the interpreter and numeric/parser packages used by frozen code."""
    return {
        "python": ".".join(str(value) for value in sys.version_info[:3]),
        "packages": {
            distribution: version(distribution)
            for distribution in ("lxml", "numpy", "pandas", "pyarrow")
        },
    }


def verify_blind_infrastructure(
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
    if contract["gap_policy"].get("maximum_accepted_gap_seconds", 0) <= 0:
        raise ValueError("External gaps require a positive maximum duration")
    if contract["evaluation"]["bootstrap_draws"] != 5000:
        raise ValueError("M5-004 external bootstrap must use 5,000 draws")
    if contract["evaluation"]["bootstrap_seed"] != 5004:
        raise ValueError("M5-004 external bootstrap seed changed")
    return contract


def validate_input_aliases(manifest: dict, contract: dict) -> dict:
    block_id = manifest.get("block_id")
    if block_id not in contract["blocks"]:
        raise ValueError("Input manifest uses an unregistered block")
    if manifest.get("data_origin") not in {"real_external", "synthetic_fixture"}:
        raise ValueError("Input manifest data_origin is invalid")
    if manifest.get("symbol") != contract["symbol"]:
        raise ValueError("Input manifest symbol differs from the contract")
    aliases = []
    registered_sessions = set(contract["blocks"][block_id]["sessions"])
    for section in ("tick_exports", "replica_exports"):
        for item in manifest.get(section, []):
            aliases.append(item.get("alias", ""))
            if not item.get("export_run_id"):
                raise ValueError("Every tick export requires an export_run_id")
            server_dates = item.get("server_dates")
            if (
                not isinstance(server_dates, list)
                or not server_dates
                or len(server_dates) != len(set(server_dates))
                or not set(server_dates).issubset(registered_sessions)
            ):
                raise ValueError("Tick export server_dates must be registered and unique")
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
    allowed_tick_suffixes = {
        suffix.lower() for suffix in contract["tick_export"]["allowed_suffixes"]
    }
    for item in [
        *manifest.get("tick_exports", []),
        *manifest.get("replica_exports", []),
    ]:
        if Path(item["path"]).suffix.lower() not in allowed_tick_suffixes:
            raise ValueError("Tick export suffix is not allowed by the contract")
        provenance_path = item.get("provenance_path")
        allowed_provenance_suffixes = {
            suffix.lower()
            for suffix in contract["tick_export"]["provenance"][
                "allowed_suffixes"
            ]
        }
        if provenance_path and (
            Path(provenance_path).suffix.lower()
            not in allowed_provenance_suffixes
        ):
            raise ValueError("Tick export requires a JSON provenance sidecar")
    allowed_report_suffixes = {
        suffix.lower() for suffix in contract["trade_report"]["allowed_suffixes"]
    }
    if Path(report["path"]).suffix.lower() not in allowed_report_suffixes:
        raise ValueError("Trade report suffix is not allowed by the contract")
    return manifest


def load_input_aliases(path: str | Path, contract: dict) -> dict:
    manifest = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_input_aliases(manifest, contract)


def _safe_file_record(item: dict, kind: str) -> dict:
    path = Path(item["path"])
    if not path.is_file():
        return {
            "alias": item["alias"],
            "kind": kind,
            "bytes": None,
            "sha256": None,
            "parser_status": "FAIL",
        }
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
    records.extend(
        _safe_file_record(
            {
                "alias": item["alias"],
                "path": item.get("provenance_path", ""),
            },
            "tick_provenance",
        )
        for item in [
            *input_manifest.get("tick_exports", []),
            *input_manifest.get("replica_exports", []),
        ]
    )
    records.append(_safe_file_record(input_manifest["report"], "trade_report"))
    return sorted(records, key=lambda row: (row["kind"], row["alias"]))


def input_set_sha256(input_manifest: dict) -> str:
    return canonical_json_sha256(input_set_records(input_manifest))


def snapshot_input_manifest(
    input_manifest: dict,
    destination: str | Path,
    *,
    expected_input_set_sha256: str | None = None,
) -> dict:
    """Copy a stable, byte-verified input set before parsing private raw files."""
    source_hash = input_set_sha256(input_manifest)
    if expected_input_set_sha256 and source_hash != expected_input_set_sha256:
        raise AssertionError("External input set changed before snapshot")
    snapshot_root = Path(destination)
    snapshot_root.mkdir(parents=True, exist_ok=True)
    snapshot = dict(input_manifest)
    for section, kind in (("tick_exports", "ticks"), ("replica_exports", "replica")):
        copied = []
        for item in input_manifest.get(section, []):
            source = Path(item["path"])
            if not source.is_file():
                copied.append(dict(item))
                continue
            target = snapshot_root / f"{kind}-{item['alias']}{source.suffix.lower()}"
            if not target.exists():
                temporary = target.with_suffix(target.suffix + ".partial")
                shutil.copyfile(source, temporary)
                temporary.replace(target)
            copied_item = {**item, "path": str(target)}
            provenance_source = Path(item.get("provenance_path", ""))
            if provenance_source.is_file():
                provenance_target = (
                    snapshot_root / f"{kind}-{item['alias']}.provenance.json"
                )
                if not provenance_target.exists():
                    temporary = provenance_target.with_suffix(".partial")
                    shutil.copyfile(provenance_source, temporary)
                    temporary.replace(provenance_target)
                copied_item["provenance_path"] = str(provenance_target)
            copied.append(copied_item)
        snapshot[section] = copied
    report = input_manifest["report"]
    report_source = Path(report["path"])
    if not report_source.is_file():
        snapshot["report"] = dict(report)
        return snapshot
    report_target = snapshot_root / f"report-{report['alias']}{report_source.suffix.lower()}"
    if not report_target.exists():
        temporary = report_target.with_suffix(report_target.suffix + ".partial")
        shutil.copyfile(report_source, temporary)
        temporary.replace(report_target)
    snapshot["report"] = {**report, "path": str(report_target)}
    if input_set_sha256(snapshot) != source_hash:
        raise AssertionError("External input snapshot differs from source input")
    if input_set_sha256(input_manifest) != source_hash:
        raise AssertionError("External input set changed during snapshot")
    return snapshot


def _tick_provenance_status(item: dict, contract: dict) -> tuple[bool, str | None]:
    """Verify the content-bound sidecar required by symbol-free MT5 ticks."""
    provenance_path = item.get("provenance_path")
    if not provenance_path:
        return False, "MissingTickProvenance"
    try:
        payload = json.loads(Path(provenance_path).read_text(encoding="utf-8"))
    except Exception as error:
        return False, type(error).__name__
    policy = contract["tick_export"]["provenance"]
    required = set(policy["required_fields"])
    if not required.issubset(payload):
        return False, "MissingTickProvenanceField"
    if (
        payload["schema_version"] != policy["schema_version"]
        or payload["source"] != policy["source"]
        or payload["symbol"] != contract["symbol"]
        or str(payload["export_run_id"]) != str(item["export_run_id"])
        or payload["server_dates"] != item["server_dates"]
    ):
        return False, "TickProvenanceMismatch"
    tick_path = Path(item["path"])
    if not tick_path.is_file() or payload[policy["content_sha256_field"]] != sha256_file(
        tick_path
    ):
        return False, "TickProvenanceHashMismatch"
    return True, None


def _load_tick_items(
    items: Iterable[dict],
    contract: dict,
) -> tuple[pd.DataFrame, list[dict], list[str]]:
    frames = []
    records = []
    failures = []
    for item in sorted(items, key=lambda row: row["alias"]):
        path = Path(item["path"])
        record = _safe_file_record(item, "ticks")
        provenance_ok, provenance_error = _tick_provenance_status(item, contract)
        record["provenance_status"] = "PASS" if provenance_ok else "FAIL"
        if provenance_error:
            record["provenance_error_type"] = provenance_error
            failures.append("wrong_symbol_or_server_date")
        try:
            ticks = parse_ticks(path)
        except Exception as error:
            record.update(
                {
                    "parser_status": "FAIL",
                    "parser_error_type": type(error).__name__,
                }
            )
            records.append(record)
            failures.append("missing_or_unparseable_registered_session")
            continue
        if ticks.empty:
            record.update(
                {
                    "parser_status": "FAIL",
                    "parser_error_type": "EmptyTickExport",
                }
            )
            records.append(record)
            failures.append("missing_or_unparseable_registered_session")
            continue
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
    if not frames:
        empty = pd.DataFrame(
            columns=[
                "timestamp",
                "time_msc",
                "bid",
                "ask",
                "mid",
                "spread",
                "last",
                "volume",
                "flags",
                "source_alias",
                "source_row",
            ]
        )
        empty["timestamp"] = pd.Series(dtype="datetime64[ns]")
        return empty, records, failures
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(
        ["timestamp", "source_alias", "source_row"], kind="stable"
    ).reset_index(drop=True)
    return combined, records, failures


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
    contract: dict,
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
        provenance_ok, _ = _tick_provenance_status(item, contract)
        if not provenance_ok:
            continue
        try:
            replica = parse_ticks(item["path"])
        except Exception:
            continue
        if replica.empty:
            continue
        replica["server_date"] = replica["timestamp"].dt.strftime("%Y-%m-%d")
        if set(replica["server_date"].unique()) != set(item["server_dates"]):
            continue
        replica_day = replica[replica["server_date"].eq(day)]
        if replica_day.empty:
            continue
        first = pd.Timestamp(replica_day["timestamp"].iloc[0])
        last = pd.Timestamp(replica_day["timestamp"].iloc[-1])
        if (
            _clock_seconds(first)
            > _parse_clock(
                contract["tick_export"]["first_tick_no_later_than_server_time"]
            )
            or _clock_seconds(last)
            < _parse_clock(
                contract["tick_export"]["last_tick_no_earlier_than_server_time"]
            )
        ):
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
    ticks, file_records, failures = _load_tick_items(
        input_manifest["tick_exports"], contract
    )
    ticks["server_date"] = ticks["timestamp"].dt.strftime("%Y-%m-%d")
    required = list(block["sessions"])
    observed = set(ticks["server_date"].unique())
    unexpected = sorted(observed - set(required))
    if unexpected:
        failures.append("wrong_symbol_or_server_date")
    records_by_alias = {record["alias"]: record for record in file_records}
    for item in input_manifest["tick_exports"]:
        actual_dates = set(
            ticks.loc[ticks["source_alias"].eq(item["alias"]), "server_date"]
        )
        declared_dates = set(item["server_dates"])
        date_status = actual_dates == declared_dates
        records_by_alias[item["alias"]]["declared_server_dates_status"] = (
            "PASS" if date_status else "FAIL"
        )
        if not date_status:
            failures.append("wrong_symbol_or_server_date")

    replica_records = []
    for item in input_manifest.get("replica_exports", []):
        record = _safe_file_record(item, "tick_replica")
        provenance_ok, provenance_error = _tick_provenance_status(item, contract)
        record["provenance_status"] = "PASS" if provenance_ok else "FAIL"
        if provenance_error:
            record["provenance_error_type"] = provenance_error
            failures.append("wrong_symbol_or_server_date")
        replica_records.append(record)

    duplicate_columns = [
        "timestamp",
        "time_msc",
        "bid",
        "ask",
        "last",
        "volume",
        "flags",
    ]
    cross_source_duplicates = (
        ticks.groupby(duplicate_columns, dropna=False)["source_alias"]
        .transform("nunique")
        .gt(1)
        if not ticks.empty
        else pd.Series(dtype=bool)
    )
    if cross_source_duplicates.any():
        failures.append("duplicate_source_tick_data")

    gap_policy = contract["gap_policy"]
    gaps = (
        classify_recurring_gaps(
            detect_coverage_gaps(
                ticks[["timestamp"]],
                threshold_seconds=gap_policy["threshold_seconds"],
            ),
            minimum_sessions=gap_policy[
                "scheduled_classification_min_recurring_sessions"
            ],
            tolerance_seconds=gap_policy["same_server_clock_tolerance_seconds"],
        )
        if not ticks.empty
        else pd.DataFrame()
    )
    accepted_gap_rows = []
    for _, gap in gaps.iterrows():
        classification = str(gap["gap_classification"])
        evidence = None
        duration_seconds = float(gap["duration_seconds"])
        if duration_seconds > gap_policy["maximum_accepted_gap_seconds"]:
            classification = "excessive_coverage_gap"
            failures.append("unknown_or_nonreplicated_material_quote_gap")
        elif classification == "unknown_coverage_gap":
            evidence = _replica_evidence(gap, ticks, input_manifest, contract)
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
                "duration_seconds": round(duration_seconds, 6),
                "classification": classification,
                "accepted": classification in {
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
        "replica_files": replica_records,
        "sessions": sessions,
        "unexpected_server_dates": unexpected,
        "cross_source_duplicate_rows": int(cross_source_duplicates.sum()),
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
        record.update(
            {
                "parser_status": "FAIL",
                "parser_error_type": type(error).__name__,
            }
        )
        output = {
            "status": "FAIL",
            "file": record,
            "required_sections_status": "FAIL",
            "declared_context": {
                "start": item.get("declared_context_start"),
                "end": item.get("declared_context_end"),
                "status": "FAIL",
            },
            "report_tick_overlap_status": "FAIL",
            "financial_reconciliation_status": "FAIL",
            "inventory_reconciliation_status": "FAIL",
            "lifecycle_completeness": {
                "status": "FAIL",
                "records_accounted": 0,
                "carry_over_records": 0,
                "critical_exception_count": 0,
            },
        }
        return {}, output, ["missing_or_unparseable_registered_session"]
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
    if ticks.empty:
        tick_start = None
        tick_end = None
        inventory = {"status": "FAIL"}
    else:
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
        tick_start is not None
        and tick_end is not None
        and not timestamps.empty
        and timestamps.max() >= tick_start
        and timestamps.min() <= tick_end
    )
    context_start = pd.Timestamp(block["report_context_start"])
    context_end = pd.Timestamp(block["report_context_end"])
    context_coverage = (
        not timestamps.empty
        and timestamps.min().normalize() <= context_start
        and timestamps.max().normalize() >= context_end
    )
    if not overlap or not context_coverage:
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
        "report_context_timestamp_coverage_status": (
            "PASS" if context_coverage else "FAIL"
        ),
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


def build_primary_intake_registration(
    input_manifest: dict,
    intake: dict,
    structural_record: dict,
    infrastructure_sha256: str,
) -> dict:
    """Bind the original primary snapshot to any later fallback decision."""
    if input_manifest.get("block_id") != "primary":
        raise ValueError("Only the registered primary block can be recorded")
    if intake.get("input_set_sha256") != input_set_sha256(input_manifest):
        raise ValueError("Primary intake input hash differs from its snapshot")
    if structural_record.get("input_set_sha256") != intake.get("input_set_sha256"):
        raise ValueError("Primary structural record input hash differs from intake")
    if (
        structural_record.get("infrastructure_manifest_sha256")
        != infrastructure_sha256
    ):
        raise ValueError("Primary structural record infrastructure hash differs")
    payload = {
        "schema_version": PRIMARY_INTAKE_REGISTRATION_SCHEMA_VERSION,
        "block_id": "primary",
        "input_set_sha256": intake["input_set_sha256"],
        "infrastructure_manifest_sha256": infrastructure_sha256,
        "input_manifest": input_manifest,
        "blind_intake": intake,
        "structural_record": structural_record,
    }
    payload["registration_id"] = canonical_json_sha256(payload)
    return payload


def verify_primary_intake_registration(
    contract: dict,
    registration: dict,
    infrastructure_sha256: str,
) -> tuple[dict, dict, dict]:
    """Rebuild the fixed primary registration before authorizing fallback."""
    source = dict(registration)
    stored_registration_id = source.pop("registration_id", None)
    if (
        not stored_registration_id
        or canonical_json_sha256(source) != stored_registration_id
    ):
        raise AssertionError("Primary intake registration hash changed")
    if (
        registration.get("schema_version")
        != PRIMARY_INTAKE_REGISTRATION_SCHEMA_VERSION
        or registration.get("block_id") != "primary"
        or registration.get("infrastructure_manifest_sha256")
        != infrastructure_sha256
    ):
        raise AssertionError("Primary intake registration identity changed")
    input_manifest = validate_input_aliases(
        registration.get("input_manifest", {}), contract
    )
    intake = registration.get("blind_intake")
    structural_record = registration.get("structural_record")
    if not isinstance(intake, dict) or not isinstance(structural_record, dict):
        raise AssertionError("Primary intake registration is incomplete")
    if registration.get("input_set_sha256") != input_set_sha256(input_manifest):
        raise AssertionError("Primary intake registration input hash changed")
    verify_primary_structural_failure(
        contract,
        input_manifest,
        intake,
        structural_record,
        infrastructure_sha256,
    )
    return input_manifest, intake, structural_record


def verify_fallback_prerequisites(
    root: str | Path,
    contract: dict,
    authorization: dict,
    infrastructure_sha256: str,
) -> None:
    """Authorize fallback before its raw files can be copied or parsed."""
    forbidden_primary_path_keys = {
        "primary_input_manifest_path",
        "primary_intake_path",
        "primary_failure_record_path",
    }
    if forbidden_primary_path_keys & set(authorization):
        raise ValueError("Fallback authorization cannot select primary artifacts")
    registration_path = primary_intake_registration_path(root)
    if not registration_path.is_file():
        raise ValueError("Fallback requires the registered primary intake")
    registration = json.loads(registration_path.read_text(encoding="utf-8"))
    _, _, primary_failure = verify_primary_intake_registration(
        contract, registration, infrastructure_sha256
    )
    validate_fallback_authorization(
        authorization,
        primary_failure,
        infrastructure_sha256,
        registration["registration_id"],
    )


def validate_fallback_authorization(
    authorization: dict,
    primary_failure: dict,
    infrastructure_sha256: str,
    primary_registration_id: str,
) -> None:
    primary_source = dict(primary_failure)
    stored_record_id = primary_source.pop("record_id", None)
    if (
        not stored_record_id
        or canonical_json_sha256(primary_source) != stored_record_id
    ):
        raise ValueError("Primary structural failure record hash changed")
    if primary_failure.get("block_id") != "primary":
        raise ValueError("Fallback requires a primary structural record")
    if primary_failure.get("accepted") is not False:
        raise ValueError("Fallback cannot follow an accepted primary block")
    if primary_failure.get("infrastructure_manifest_sha256") != infrastructure_sha256:
        raise ValueError("Primary structural failure infrastructure hash changed")
    if authorization.get("reviewed") is not True:
        raise ValueError("Fallback requires explicit reviewed authorization")
    if authorization.get("primary_failure_record_id") != primary_failure.get(
        "record_id"
    ):
        raise ValueError("Fallback authorization references another failure")
    if authorization.get("primary_registration_id") != primary_registration_id:
        raise ValueError("Fallback authorization references another primary intake")
    if authorization.get("infrastructure_manifest_sha256") != infrastructure_sha256:
        raise ValueError("Fallback authorization infrastructure hash changed")
    if authorization.get("reason_codes") != primary_failure.get("failure_codes"):
        raise ValueError("Fallback authorization reason codes changed")


def verify_primary_structural_failure(
    contract: dict,
    input_manifest: dict,
    intake: dict,
    failure: dict,
    infrastructure_sha256: str,
) -> None:
    """Rebuild the primary failure before it can unlock the fallback block."""
    if input_manifest.get("block_id") != "primary":
        raise AssertionError("Fallback requires the registered primary inputs")
    intake_source = dict(intake)
    stored_intake_hash = intake_source.pop("deterministic_intake_sha256", None)
    if not stored_intake_hash or canonical_json_sha256(intake_source) != stored_intake_hash:
        raise AssertionError("Primary blind intake deterministic hash changed")
    rebuilt_intake, _ = build_blind_intake(contract, input_manifest)
    assert_blind_firewall(rebuilt_intake, contract)
    if rebuilt_intake != intake:
        raise AssertionError("Primary blind intake does not reproduce from inputs")
    rebuilt_failure = build_structural_record(
        rebuilt_intake, infrastructure_sha256
    )
    if rebuilt_failure != failure:
        raise AssertionError("Primary structural failure does not reproduce from intake")
    if failure.get("accepted") is not False:
        raise AssertionError("Fallback requires a rejected primary structural record")
