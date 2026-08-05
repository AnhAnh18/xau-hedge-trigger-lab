"""Aggregate-only RETRO-007 concurrent-position and gap screening."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import numpy as np

from xau_trigger.parsers.mt5_report import parse_report

ROOT = Path(__file__).resolve().parents[1]
QUARANTINE_ROOT = ROOT / "data" / "raw" / "passview_quarantine"
REPORT_RUN = QUARANTINE_ROOT / "retro-003-history-screening-20260801" / "run-20260801T160000"
TICK_RUN = QUARANTINE_ROOT / "mt5-ticks-20260801" / "run-20260801T061208"
REPORT_MANIFEST_SHA256 = "88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30"
TICK_MANIFEST_SHA256 = "a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c"
REPORT_ALIASES = tuple(f"report-{index:03d}.html" for index in range(1, 10))
START_SERVER = pd.Timestamp("2025-11-01 00:00:00")
END_SERVER = pd.Timestamp("2026-07-31 00:00:00")
GAP_THRESHOLD_SECONDS = 60.0
POST_GAP_SECONDS = 120.0
CLOCK_OFFSETS = {"utc_plus_2": pd.Timedelta(hours=2), "utc_plus_3": pd.Timedelta(hours=3)}
M5_FIREWALL = "M5_FIREWALL_ATTESTATION_V1"
OUTPUT = ROOT / "reports" / "private" / "retro-007" / "retro-007-aggregate.json"


@dataclass(frozen=True)
class PositionInterval:
    side: str
    open_time: pd.Timestamp
    close_time: pd.Timestamp
    censored: bool


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True, allow_nan=False)


def _verify_run(run_dir: Path, expected_manifest: str, aliases: set[str], *, sort_keys: bool) -> dict[str, Path]:
    if run_dir.resolve().relative_to(QUARANTINE_ROOT.resolve()) is None:
        raise ValueError("source run escaped quarantine")
    manifest_path = run_dir / "manifests" / "archive-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = manifest["payload"]
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=sort_keys)
    if manifest.get("manifest_sha256") != expected_manifest or hashlib.sha256(encoded.encode()).hexdigest() != expected_manifest:
        raise ValueError("source manifest digest mismatch")
    objects = {item["alias"]: item for item in payload["objects"]}
    if payload.get("transfer_status") != "accepted" or set(objects) != aliases:
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
        actual = _sha256_file(path)
        if actual != item["source_sha256"] or actual != item["destination_sha256"]:
            raise ValueError("source object hash mismatch")
        paths[alias] = path
    return paths


def _position_row_signature(row: pd.Series) -> tuple[object, ...]:
    open_time = pd.Timestamp(row["open_time"]) if pd.notna(row["open_time"]) else pd.NaT
    volume = float(row["volume"])
    if not math.isfinite(volume) or volume <= 0 or pd.isna(open_time):
        raise ValueError("invalid position row")
    return (str(row["side"]).casefold(), volume, int(open_time.value))


def _load_positions(report_paths: dict[str, Path]) -> tuple[list[PositionInterval], dict[str, int]]:
    grouped: dict[str, list[tuple[tuple[object, ...], pd.Timestamp, str]]] = defaultdict(list)
    report_count = 0
    invalid_rows = 0
    for alias in REPORT_ALIASES:
        tables = parse_report(report_paths[alias], report_id=alias)
        report_count += 1
        frames = []
        for source_kind in ("positions", "open_positions"):
            frame = tables[source_kind]
            if not frame.empty:
                frames.append(frame.assign(_source_kind=source_kind))
        if not frames:
            continue
        positions = pd.concat(frames, ignore_index=True)
        positions = positions[positions["symbol"].astype(str).str.casefold().eq("xauusd")]
        for _, row in positions.iterrows():
            position_id = str(row["position_id"]).strip()
            if not position_id or position_id.casefold() in {"nan", "none"}:
                continue
            try:
                signature = _position_row_signature(row)
            except (TypeError, ValueError, OverflowError):
                invalid_rows += 1
                continue
            close_time = pd.Timestamp(row["close_time"]) if pd.notna(row["close_time"]) else pd.NaT
            grouped[position_id].append((signature, close_time, alias))

    duplicate_rows = 0
    conflict_ids = 0
    censored_count = 0
    intervals: list[PositionInterval] = []
    for rows in grouped.values():
        duplicate_rows += max(0, len(rows) - 1)
        signatures = {row[0] for row in rows}
        if len(signatures) != 1:
            conflict_ids += 1
            continue
        signature = next(iter(signatures))
        side = str(signature[0])
        open_time = pd.Timestamp(signature[2])
        closes = [row[1] for row in rows if pd.notna(row[1])]
        if len({int(value.value) for value in closes}) > 1:
            conflict_ids += 1
            continue
        if pd.isna(open_time) or side not in {"buy", "sell"}:
            continue
        if not closes:
            censored_count += 1
            continue
        close_time = max(closes)
        start = max(open_time, START_SERVER)
        end = min(close_time, END_SERVER)
        if start < end:
            intervals.append(PositionInterval(side, start, end, False))
    return intervals, {
        "reports_parsed": report_count,
        "position_ids_seen": len(grouped),
        "duplicate_position_rows": duplicate_rows,
        "conflicting_position_ids": conflict_ids,
        "right_censored_positions": censored_count,
        "invalid_position_rows": invalid_rows,
    }


def _scan_ticks(tick_paths: dict[str, Path]) -> tuple[list[tuple[pd.Timestamp, pd.Timestamp, float]], dict[str, int]]:
    gaps: list[tuple[pd.Timestamp, pd.Timestamp, float]] = []
    previous_ns: int | None = None
    valid_count = duplicate_count = 0
    broad_start = (START_SERVER - max(CLOCK_OFFSETS.values()) - pd.Timedelta(seconds=GAP_THRESHOLD_SECONDS)).tz_localize("UTC")
    broad_end = (END_SERVER - min(CLOCK_OFFSETS.values()) + pd.Timedelta(seconds=GAP_THRESHOLD_SECONDS)).tz_localize("UTC")
    broad_start_ns = int(broad_start.value)
    broad_end_ns = int(broad_end.value)
    threshold_ns = int(GAP_THRESHOLD_SECONDS * 1_000_000_000)
    for alias in sorted(tick_paths):
        for chunk in pd.read_csv(tick_paths[alias], usecols=["time_utc", "bid", "ask"], chunksize=250_000):
            timestamps = pd.to_datetime(chunk["time_utc"], utc=True, errors="coerce")
            bids = pd.to_numeric(chunk["bid"], errors="coerce")
            asks = pd.to_numeric(chunk["ask"], errors="coerce")
            valid = timestamps.notna() & bids.notna() & asks.notna() & (bids > 0) & (asks > 0) & (asks >= bids)
            valid &= (timestamps >= broad_start) & (timestamps <= broad_end)
            values = timestamps[valid].to_numpy(dtype="datetime64[ns]").astype("int64")
            if len(values) == 0:
                continue
            combined = np.concatenate(([previous_ns], values)) if previous_ns is not None else values
            deltas = np.diff(combined)
            if np.any(deltas < 0):
                raise ValueError("tick timestamps decrease")
            duplicate_count += int(np.count_nonzero(deltas == 0))
            for index in np.flatnonzero(deltas > threshold_ns):
                start_ns = int(combined[index])
                end_ns = int(combined[index + 1])
                if end_ns >= broad_start_ns and start_ns <= broad_end_ns:
                    gaps.append((pd.Timestamp(start_ns, unit="ns", tz="UTC"), pd.Timestamp(end_ns, unit="ns", tz="UTC"), (end_ns - start_ns) / 1_000_000_000))
            previous_ns = int(values[-1])
            valid_count += len(values)
    return gaps, {"valid_tick_rows": valid_count, "duplicate_tick_timestamps": duplicate_count, "coverage_gap_count": len(gaps)}


def _gap_class(gap_start: pd.Timestamp, gap_end: pd.Timestamp, offset: pd.Timedelta) -> str:
    local_start = gap_start.tz_convert(None) + offset
    local_end = gap_end.tz_convert(None) + offset
    if gap_start.weekday() == 4 and gap_end.weekday() in {5, 6} and local_end.weekday() == 0:
        return "weekend_opening_gap"
    return "temporal_coverage_gap"


def _bucket_for_time(timestamp: pd.Timestamp) -> str:
    return "monday" if timestamp.weekday() == 0 else "non_monday"


def _concurrency(intervals: list[PositionInterval]) -> dict[str, object]:
    events: dict[pd.Timestamp, list[tuple[str, int]]] = defaultdict(list)
    for interval in intervals:
        events[interval.open_time].append((interval.side, 1))
        events[interval.close_time].append((interval.side, -1))
    active = {"buy": 0, "sell": 0}
    max_total = max_buy = max_sell = 0
    definite_gt2 = definite_four = 0
    definite_gt2_episodes = definite_four_episodes = 0
    in_gt2 = in_four = False
    monday = {"intervals_gt2": 0, "four_pattern_intervals": 0}
    non_monday = {"intervals_gt2": 0, "four_pattern_intervals": 0}
    by_month: dict[str, int] = defaultdict(int)
    possible_gt2 = possible_four = 0
    ordered = sorted(events)
    for index, timestamp in enumerate(ordered):
        before = dict(active)
        for side, delta in sorted(events[timestamp], key=lambda item: item[1]):
            active[side] += delta
        after = dict(active)
        upper = {"buy": before["buy"] + sum(delta for side, delta in events[timestamp] if side == "buy" and delta > 0), "sell": before["sell"] + sum(delta for side, delta in events[timestamp] if side == "sell" and delta > 0)}
        has_open = any(delta > 0 for _, delta in events[timestamp])
        has_close = any(delta < 0 for _, delta in events[timestamp])
        if has_open and has_close and sum(upper.values()) > 2 and sum(after.values()) <= 2:
            possible_gt2 += 1
        if has_open and has_close and upper["buy"] >= 2 and upper["sell"] >= 2 and not (after["buy"] >= 2 and after["sell"] >= 2):
            possible_four += 1
        if index + 1 >= len(ordered):
            continue
        next_time = ordered[index + 1]
        if next_time <= timestamp:
            continue
        total = active["buy"] + active["sell"]
        max_total = max(max_total, total)
        max_buy = max(max_buy, active["buy"])
        max_sell = max(max_sell, active["sell"])
        cursor = timestamp
        while cursor < next_time:
            segment_end = min(next_time, cursor.normalize() + pd.Timedelta(days=1))
            if total > 2:
                if not in_gt2:
                    definite_gt2_episodes += 1
                definite_gt2 += 1
                in_gt2 = True
                bucket = _bucket_for_time(cursor)
                (monday if bucket == "monday" else non_monday)["intervals_gt2"] += 1
                by_month[cursor.strftime("%Y-%m")] += 1
            if active["buy"] >= 2 and active["sell"] >= 2:
                if not in_four:
                    definite_four_episodes += 1
                definite_four += 1
                in_four = True
                bucket = _bucket_for_time(cursor)
                (monday if bucket == "monday" else non_monday)["four_pattern_intervals"] += 1
            cursor = segment_end
        if total <= 2:
            in_gt2 = False
        if not (active["buy"] >= 2 and active["sell"] >= 2):
            in_four = False
    return {
        "max_total_active": max_total,
        "max_buy_active": max_buy,
        "max_sell_active": max_sell,
        "definite_segments_total_gt2": definite_gt2,
        "definite_segments_2buy_2sell": definite_four,
        "definite_episodes_total_gt2": definite_gt2_episodes,
        "definite_episodes_2buy_2sell": definite_four_episodes,
        "possible_same_second_total_gt2": possible_gt2,
        "possible_same_second_2buy_2sell": possible_four,
        "monday": monday,
        "non_monday": non_monday,
        "definite_gt2_by_month": dict(sorted(by_month.items())),
    }


def _gap_associations(intervals: list[PositionInterval], gaps: list[tuple[pd.Timestamp, pd.Timestamp, float]]) -> dict[str, object]:
    output: dict[str, object] = {}
    for clock, offset in CLOCK_OFFSETS.items():
        classes: dict[str, int] = defaultdict(int)
        multi_near = 0
        for gap_start, gap_end, _ in gaps:
            gap_class = _gap_class(gap_start, gap_end, offset)
            classes[gap_class] += 1
            local_start = gap_start.tz_convert(None) + offset
            local_end = gap_end.tz_convert(None) + offset
            near_start = local_start
            near_end = local_end + pd.Timedelta(seconds=POST_GAP_SECONDS)
            active = [
                PositionInterval(item.side, max(item.open_time, near_start), min(item.close_time, near_end), False)
                for item in intervals
                if item.open_time < near_end and item.close_time > near_start
            ]
            if active and int(_concurrency(active)["max_total_active"]) > 2:
                multi_near += 1
        output[clock] = {"gap_counts": dict(sorted(classes.items())), "multi_position_gap_windows": multi_near}
    return output


def _require_ignored(path: Path) -> None:
    result = subprocess.run(["git", "check-ignore", "--no-index", "-q", str(path.relative_to(ROOT))], cwd=ROOT, check=False)
    if result.returncode != 0:
        raise ValueError("RETRO-007 output path is not ignored")


def run(report_run: Path = REPORT_RUN, tick_run: Path = TICK_RUN) -> dict[str, object]:
    if report_run.resolve() != REPORT_RUN.resolve() or tick_run.resolve() != TICK_RUN.resolve():
        raise ValueError("source runs are not the pinned RETRO-003 runs")
    report_paths = _verify_run(report_run, REPORT_MANIFEST_SHA256, set(REPORT_ALIASES), sort_keys=True)
    tick_manifest_path = tick_run / "manifests" / "archive-manifest.json"
    tick_manifest = json.loads(tick_manifest_path.read_text(encoding="utf-8"))
    tick_aliases = {item["alias"] for item in tick_manifest["payload"]["objects"]}
    tick_paths = _verify_run(tick_run, TICK_MANIFEST_SHA256, tick_aliases, sort_keys=False)
    intervals, position_stats = _load_positions(report_paths)
    gaps, tick_stats = _scan_ticks(tick_paths)
    result: dict[str, object] = {
        "schema_version": 1,
        "case_id": "RETRO-007",
        "source_validation": "accepted_hash_verified_RETRO-003_manifests",
        "report_manifest_sha256": REPORT_MANIFEST_SHA256,
        "tick_manifest_sha256": TICK_MANIFEST_SHA256,
        "population": {"start_server": "2025-11-01 00:00:00", "end_server_exclusive": "2026-07-31 00:00:00", "report_alias_count": len(report_paths), "tick_alias_count": len(tick_paths)},
        "position_coverage": position_stats,
        "tick_coverage": tick_stats,
        "concurrency": _concurrency(intervals),
        "gap_associations": _gap_associations(intervals, gaps),
        "claims": {"definite": "positive_duration_intervals_only", "possible": "same_second_open_close_upper_bound", "unresolved": "clock_mapping_and_right_censored_snapshots", "raw_rows_printed": False},
        "m5_firewall": M5_FIREWALL,
    }
    result["aggregate_sha256"] = hashlib.sha256(_canonical(result).encode()).hexdigest()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-run", type=Path, default=REPORT_RUN)
    parser.add_argument("--tick-run", type=Path, default=TICK_RUN)
    args = parser.parse_args()
    try:
        result = run(args.report_run.resolve(), args.tick_run.resolve())
        _require_ignored(OUTPUT)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(_canonical(result), encoding="utf-8")
        print(json.dumps({"case_id": result["case_id"], "aggregate_sha256": result["aggregate_sha256"], "max_total_active": result["concurrency"]["max_total_active"], "max_buy_active": result["concurrency"]["max_buy_active"], "max_sell_active": result["concurrency"]["max_sell_active"], "definite_episodes_total_gt2": result["concurrency"]["definite_episodes_total_gt2"], "definite_episodes_2buy_2sell": result["concurrency"]["definite_episodes_2buy_2sell"], "possible_same_second_total_gt2": result["concurrency"]["possible_same_second_total_gt2"]}, ensure_ascii=True, separators=(",", ":")))
        return 0
    except Exception:
        print("RETRO-007 analysis rejected", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
