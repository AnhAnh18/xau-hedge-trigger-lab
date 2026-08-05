"""Aggregate-only RH-001 historical lot-distribution audit."""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from pathlib import Path
from typing import Iterable

import pandas as pd

from xau_trigger.parsers.mt5_report import parse_report

ROOT = Path(__file__).resolve().parents[1]
QUARANTINE_ROOT = ROOT / "data" / "raw" / "passview_quarantine"
REPORT_RUN_ID = "retro-003-history-screening-20260801/run-20260801T160000"
TICK_RUN_ID = "mt5-ticks-20260801/run-20260801T061208"
REPORT_MANIFEST_SHA256 = "88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30"
TICK_MANIFEST_SHA256 = "a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c"
REPORT_ALIASES = tuple(f"report-{index:03d}.html" for index in range(1, 10))
TICK_ALIASES = tuple(
    f"XAUUSD_ticks_{start:%Y-%m-%d}_to_{end:%Y-%m-%d}.csv"
    for start in (date(2025, 11, 1) + pd.Timedelta(days=7 * index) for index in range(39))
    for end in (start + pd.Timedelta(days=7),)
)
START_SERVER = pd.Timestamp("2025-11-01 00:00:00")
END_SERVER = pd.Timestamp("2026-07-31 00:00:00")
FIXED8 = Decimal("0.00000001")
MAX_QUANTITY = Decimal("1000.00000000")
M5_FIREWALL = "M5_FIREWALL_ATTESTATION_V1"
OUTPUT = ROOT / "reports" / "private" / "retro-hist-001" / "lot-audit-aggregate.json"


@dataclass(frozen=True)
class PositionRecord:
    position_id: str
    side: str
    quantity: Decimal
    open_time: pd.Timestamp
    close_time: pd.Timestamp | None


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_dir(run_id: str) -> Path:
    candidate = (QUARANTINE_ROOT / run_id).resolve()
    candidate.relative_to(QUARANTINE_ROOT.resolve())
    return candidate


def _verify_manifest(
    run_id: str,
    expected_digest: str,
    expected_aliases: set[str],
    *,
    sort_keys: bool,
    check_files: bool,
) -> dict[str, Path]:
    run_dir = _run_dir(run_id)
    manifest_path = run_dir / "manifests" / "archive-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = manifest["payload"]
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=sort_keys)
    if manifest.get("manifest_sha256") != expected_digest or hashlib.sha256(encoded.encode()).hexdigest() != expected_digest:
        raise ValueError("source manifest digest mismatch")
    if payload.get("transfer_status") != "accepted":
        raise ValueError("source transfer is not accepted")
    objects = {item["alias"]: item for item in payload["objects"]}
    if set(objects) != expected_aliases:
        raise ValueError("source aliases are not pinned")
    paths: dict[str, Path] = {}
    for alias, item in objects.items():
        relative = item.get("relative_path")
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise ValueError("source relative path is invalid")
        path = (run_dir / relative).resolve()
        path.relative_to(run_dir.resolve())
        if path.parent != (run_dir / "incoming").resolve() or path.name != alias:
            raise ValueError("source path is not pinned")
        if check_files:
            actual = _sha256_file(path)
            if actual != item["source_sha256"] or actual != item["destination_sha256"]:
                raise ValueError("source object hash mismatch")
        paths[alias] = path
    return paths


def _parse_fixed8(value: object) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise ValueError("quantity is not numeric")
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError("quantity is malformed") from None
    if not quantity.is_finite() or quantity <= 0 or quantity > MAX_QUANTITY:
        raise ValueError("quantity is outside bounds")
    try:
        fixed = quantity.quantize(FIXED8, rounding=ROUND_DOWN)
    except InvalidOperation:
        raise ValueError("quantity cannot be fixed8 encoded") from None
    if fixed != quantity:
        raise ValueError("quantity has more than eight decimal places")
    return fixed


def _timestamp(value: object, *, allow_missing: bool) -> pd.Timestamp | None:
    if value is None or pd.isna(value):
        if allow_missing:
            return None
        raise ValueError("timestamp is missing")
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        if allow_missing:
            return None
        raise ValueError("timestamp is missing")
    if timestamp.tzinfo is not None:
        raise ValueError("timestamp must be naive server time")
    return timestamp


def _normalize_row(row: dict[str, object]) -> tuple[str, tuple[object, ...], pd.Timestamp | None]:
    position_id = str(row.get("position_id", "")).strip()
    if not position_id or position_id.casefold() in {"nan", "none"}:
        raise ValueError("position id is missing")
    symbol = str(row.get("symbol", "")).strip().casefold()
    side = str(row.get("side", "")).strip().casefold()
    if symbol != "xauusd" or side not in {"buy", "sell"}:
        raise ValueError("symbol or side is unsupported")
    quantity = _parse_fixed8(row.get("volume"))
    open_time = _timestamp(row.get("open_time"), allow_missing=False)
    close_time = _timestamp(row.get("close_time"), allow_missing=True)
    signature = (side, format(quantity, "f"), int(open_time.value))
    return position_id, signature, close_time


def _summarize_records(records: Iterable[dict[str, object]], *, reports_parsed: int) -> tuple[dict[str, object], dict[str, object]]:
    grouped: dict[str, list[tuple[tuple[object, ...], pd.Timestamp | None]]] = defaultdict(list)
    invalid_rows = 0
    for row in records:
        try:
            position_id, signature, close_time = _normalize_row(row)
        except (TypeError, ValueError, OverflowError):
            invalid_rows += 1
            continue
        grouped[position_id].append((signature, close_time))

    duplicate_rows = 0
    conflict_ids = 0
    right_censored = 0
    outside_population = 0
    accepted: list[PositionRecord] = []
    for position_id, rows in grouped.items():
        duplicate_rows += max(0, len(rows) - 1)
        signatures = {row[0] for row in rows}
        if len(signatures) != 1:
            conflict_ids += 1
            continue
        signature = next(iter(signatures))
        closes = {int(row[1].value) for row in rows if row[1] is not None}
        if len(closes) > 1:
            conflict_ids += 1
            continue
        side = str(signature[0])
        quantity = Decimal(str(signature[1]))
        open_time = pd.Timestamp(int(signature[2]), unit="ns")
        close_time = pd.Timestamp(next(iter(closes)), unit="ns") if closes else None
        if open_time >= END_SERVER or (close_time is not None and close_time <= START_SERVER):
            outside_population += 1
            continue
        if close_time is not None and max(open_time, START_SERVER) >= min(close_time, END_SERVER):
            outside_population += 1
            continue
        censored = close_time is None
        if censored:
            right_censored += 1
        accepted.append(PositionRecord(position_id, side, quantity, open_time, close_time))

    bands: dict[str, dict[str, dict[str, int]]] = {
        "buy": {"closed": {}, "right_censored": {}},
        "sell": {"closed": {}, "right_censored": {}},
    }
    for item in accepted:
        status = "right_censored" if item.close_time is None else "closed"
        quantity = format(item.quantity, "f")
        bucket = bands[item.side][status]
        bucket[quantity] = bucket.get(quantity, 0) + 1
    bands = {
        side: {status: dict(sorted(values.items())) for status, values in statuses.items()}
        for side, statuses in bands.items()
    }
    coverage = {
        "reports_parsed": reports_parsed,
        "position_ids_seen": len(grouped),
        "accepted_position_ids": len(accepted),
        "duplicate_position_rows": duplicate_rows,
        "conflicting_position_ids": conflict_ids,
        "invalid_position_rows": invalid_rows,
        "right_censored_positions": right_censored,
        "outside_population_position_ids": outside_population,
    }
    claims = {
        "lot_schedule": "distribution_baseline_only_ordered_schedule_deferred",
        "quantity_source": "positions_and_open_positions.volume",
        "raw_rows_printed": False,
        "observed_future_action_size_used": False,
    }
    return coverage, {"lot_bands": bands, "claims": claims}


def _load_report_records(report_paths: dict[str, Path]) -> tuple[list[dict[str, object]], int]:
    records: list[dict[str, object]] = []
    for alias in REPORT_ALIASES:
        tables = parse_report(report_paths[alias], report_id=alias)
        for source_kind in ("positions", "open_positions"):
            frame = tables[source_kind]
            if frame.empty:
                continue
            records.extend(frame[["position_id", "symbol", "side", "volume", "open_time", "close_time"]].to_dict("records"))
    return records, len(REPORT_ALIASES)


def _require_ignored(path: Path) -> None:
    result = subprocess.run(["git", "check-ignore", "--no-index", "-q", str(path.relative_to(ROOT))], cwd=ROOT, check=False)
    if result.returncode != 0:
        raise ValueError("RH-001 output path is not ignored")


def run() -> dict[str, object]:
    report_paths = _verify_manifest(REPORT_RUN_ID, REPORT_MANIFEST_SHA256, set(REPORT_ALIASES), sort_keys=True, check_files=True)
    _verify_manifest(TICK_RUN_ID, TICK_MANIFEST_SHA256, set(TICK_ALIASES), sort_keys=False, check_files=False)
    records, report_count = _load_report_records(report_paths)
    coverage, details = _summarize_records(records, reports_parsed=report_count)
    result: dict[str, object] = {
        "schema_version": 1,
        "case_id": "RETRO-HIST-001",
        "source_validation": "accepted_hash_verified_RETRO003_manifest_runs",
        "report_manifest_sha256": REPORT_MANIFEST_SHA256,
        "tick_manifest_sha256": TICK_MANIFEST_SHA256,
        "population": {
            "start_server": "2025-11-01 00:00:00",
            "end_server_exclusive": "2026-07-31 00:00:00",
            "report_alias_count": len(REPORT_ALIASES),
            "tick_alias_count": len(TICK_ALIASES),
        },
        "position_coverage": coverage,
        "lot_bands": details["lot_bands"],
        "m5_firewall": M5_FIREWALL,
        "claims": details["claims"],
    }
    result["aggregate_sha256"] = hashlib.sha256(_canonical(result).encode()).hexdigest()
    return result


def main() -> int:
    try:
        result = run()
        _require_ignored(OUTPUT)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(_canonical(result), encoding="utf-8")
        print(json.dumps({
            "case_id": result["case_id"],
            "aggregate_sha256": result["aggregate_sha256"],
            "accepted_position_ids": result["position_coverage"]["accepted_position_ids"],
            "invalid_position_rows": result["position_coverage"]["invalid_position_rows"],
        }, ensure_ascii=True, separators=(",", ":")))
        return 0
    except Exception:
        print("RETRO-HIST-001 analysis rejected", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
