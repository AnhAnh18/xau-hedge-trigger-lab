"""Owner-authorized, aggregate-only E-002 historical capture.

This adapter verifies the receipt-pinned archive, parses lifecycle reports in
memory, and emits redacted cycle aggregates. It never writes source rows or
exposes a trading/execution surface.
"""
from __future__ import annotations

import json
import hashlib
import math
import re
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import numpy as np

from .retro_bot import RetroBotInputError
from .retro_hist_002 import (
    END_SERVER,
    REPORT_ALIASES,
    REPORT_MANIFEST_SHA256,
    REPORT_RUN_ID,
    START_SERVER,
    TICK_ALIASES,
    TICK_MANIFEST_SHA256,
    TICK_RUN_ID,
    Position,
    deduplicate_positions,
    sha256_file,
    state_for,
    QUARANTINE_ROOT,
)
from .retro_live_evidence_001 import FROZEN_GATE_DIGEST, assert_firewall_clean, digest, load_gate_registry
from .retro_live_evidence_002_receipt import validate_source_receipt
from .parsers.mt5_report import parse_report

CASE_ID = "RETRO-LIVE-EVIDENCE-002"
AUTHORIZED_RECEIPT_SHA256 = "ce95e862518a16b896670fd98ac87a1d4cada8f21fb3eeaf4eb93c686d8b9fd2"
SERVER_START = pd.Timestamp("2026-05-01 00:00:00")
SERVER_END = pd.Timestamp("2026-07-31 00:00:00")
M5_FIREWALL = "RETRO_ONLY_NO_M5_CONTAMINATION"
REPORT_FIELDS = ("position_id", "symbol", "side", "volume", "open_time", "close_time")
TICK_FIELDS = ("time_utc", "bid", "ask")
SPREAD_BUCKET = Decimal("0.00000001")


@dataclass
class _Cycle:
    ordinal: int
    categories: set[str] = field(default_factory=set)
    action_count: int = 0
    buy_actions: int = 0
    sell_actions: int = 0
    quantities: set[str] = field(default_factory=set)
    had_hedge: bool = False
    censored: bool = False

    def redacted(self) -> dict[str, Any]:
        categories = set(self.categories)
        if not self.had_hedge:
            categories.add("one_leg_recovery")
        if len(self.quantities) > 1:
            categories.add("variable_lot")
        return {
            "cycle_id": f"e002-c{self.ordinal:06d}",
            "categories": sorted(categories),
            "action_count": self.action_count,
            "buy_actions": self.buy_actions,
            "sell_actions": self.sell_actions,
            "observed_lot_bands": sorted(self.quantities),
            "censored": self.censored,
        }


def _load_report_positions(report_paths: Mapping[str, Path]) -> list[Position]:
    rows: list[dict[str, object]] = []
    for alias in REPORT_ALIASES:
        tables = parse_report(report_paths[alias], report_id=alias)
        for section in ("positions", "open_positions"):
            frame = tables[section]
            if not frame.empty:
                rows.extend(frame[list(REPORT_FIELDS)].to_dict("records"))
    positions, _ = deduplicate_positions(rows)
    return positions


def _events(positions: list[Position]) -> tuple[dict[pd.Timestamp, list[tuple[str, Position]]], bool]:
    events: dict[pd.Timestamp, list[tuple[str, Position]]] = defaultdict(list)
    active_at_start = [
        item for item in positions
        if item.open_time < SERVER_START and (item.close_time is None or item.close_time > SERVER_START)
    ]
    for item in positions:
        if item.censored:
            if SERVER_START <= item.open_time < SERVER_END:
                events[item.open_time].append(("CENSOR_START", item))
            if item.close_time is not None and SERVER_START < item.close_time < SERVER_END:
                events[item.close_time].append(("CENSOR_END", item))
            continue
        if SERVER_START <= item.open_time < SERVER_END:
            events[item.open_time].append(("OPEN", item))
        if item.close_time is not None and SERVER_START < item.close_time < SERVER_END:
            events[item.close_time].append(("CLOSE", item))
    return events, bool(active_at_start)


def _scan_ticks(
    tick_paths: Mapping[str, Path],
    *,
    event_times: set[pd.Timestamp] | None = None,
) -> tuple[set[pd.Timestamp], set[pd.Timestamp], dict[str, int]]:
    """Derive gap/spread markers without retaining raw tick rows."""
    start_utc = pd.Timestamp("2026-04-30T21:00:00Z")
    end_utc = pd.Timestamp("2026-07-30T21:00:00Z")
    broad_start = start_utc - pd.Timedelta(days=2)
    broad_end = end_utc + pd.Timedelta(hours=1)
    spread_hist: defaultdict[int, int] = defaultdict(int)
    monday_gap_times: set[pd.Timestamp] = set()
    daily_max: dict[str, int] = {}
    # Pandas may expose parsed UTC columns at microsecond precision; keep
    # event markers in the same integer unit as ``ts.astype("int64")``.
    event_ns = np.array(sorted(pd.Timestamp(item).value // 1_000 for item in (event_times or set())), dtype=np.int64)
    event_max_spread = np.full(event_ns.shape, -1, dtype=np.int64)
    match_window_ns = int(pd.Timedelta(seconds=5).total_seconds() * 1_000_000)
    previous_match_ns = np.empty(0, dtype=np.int64)
    previous_match_spread = np.empty(0, dtype=np.int64)
    previous_ns: int | None = None
    previous_mid: float | None = None
    valid_rows = 0
    for alias in sorted(tick_paths):
        for chunk in pd.read_csv(tick_paths[alias], usecols=list(TICK_FIELDS), chunksize=250_000):
            timestamps = pd.to_datetime(chunk["time_utc"], utc=True, errors="coerce")
            bids = pd.to_numeric(chunk["bid"], errors="coerce")
            asks = pd.to_numeric(chunk["ask"], errors="coerce")
            valid = timestamps.notna() & bids.notna() & asks.notna()
            valid &= np.isfinite(bids.to_numpy(dtype=float)) & np.isfinite(asks.to_numpy(dtype=float))
            valid &= (bids > 0) & (asks > 0) & (asks >= bids)
            valid &= (timestamps >= broad_start) & (timestamps < broad_end)
            if not bool(valid.any()):
                continue
            ts = timestamps[valid]
            bid_values = bids[valid].to_numpy(dtype=float)
            ask_values = asks[valid].to_numpy(dtype=float)
            ns = ts.astype("int64").to_numpy()
            mids = (bid_values + ask_values) / 2.0
            prior_ns, prior_mid = previous_ns, previous_mid
            if prior_ns is not None and int(ns[0]) < prior_ns:
                raise RetroBotInputError("E-002 tick timestamp order decreased")
            deltas = np.diff(ns)
            if np.any(deltas < 0):
                raise RetroBotInputError("E-002 tick timestamp order decreased")
            gap_delta = np.diff(ns, prepend=ns[0])
            gap_mid_delta = np.abs(mids - np.roll(mids, 1))
            if len(mids) and prior_ns is not None and prior_mid is not None:
                gap_delta[0] = ns[0] - prior_ns
                gap_mid_delta[0] = abs(mids[0] - prior_mid)
            previous_ns = int(ns[-1])
            previous_mid = float(mids[-1])
            server_ts = pd.Series(ts) + pd.Timedelta(hours=3)
            monday = server_ts.dt.weekday.to_numpy() == 0
            monday_mask = monday & (gap_delta >= int(pd.Timedelta(hours=24).total_seconds() * 1_000_000)) & (gap_mid_delta >= 0.50)
            for tick_time in ts[monday_mask]:
                monday_gap_times.add(pd.Timestamp(tick_time))
            in_window = (ts >= start_utc) & (ts < end_utc)
            if not bool(in_window.any()):
                continue
            valid_rows += int(in_window.sum())
            window_ns = ns[in_window.to_numpy()]
            spread_buckets = ((ask_values[in_window.to_numpy()] - bid_values[in_window.to_numpy()]) / float(SPREAD_BUCKET)).astype(np.int64)
            unique, counts = np.unique(spread_buckets, return_counts=True)
            for bucket, count in zip(unique.tolist(), counts.tolist()):
                spread_hist[int(bucket)] += int(count)
            if event_ns.size:
                match_ns = np.concatenate((previous_match_ns, window_ns))
                match_spread = np.concatenate((previous_match_spread, spread_buckets))
                first_event = int(np.searchsorted(event_ns, match_ns[0] - match_window_ns, side="left"))
                last_event = int(np.searchsorted(event_ns, match_ns[-1] + match_window_ns, side="right"))
                for index in range(first_event, last_event):
                    left = int(np.searchsorted(match_ns, event_ns[index] - match_window_ns, side="left"))
                    right = int(np.searchsorted(match_ns, event_ns[index] + match_window_ns, side="right"))
                    if right > left:
                        event_max_spread[index] = max(event_max_spread[index], int(match_spread[left:right].max()))
                tail = window_ns >= window_ns[-1] - match_window_ns
                previous_match_ns = window_ns[tail]
                previous_match_spread = spread_buckets[tail]
            day_values = (pd.Series(ts[in_window]).dt.tz_convert("UTC") + pd.Timedelta(hours=3)).dt.date.astype(str).to_numpy()
            for day in np.unique(day_values):
                day_mask = day_values == day
                day_max = int(spread_buckets[day_mask].max())
                if day_max > daily_max.get(str(day), -1):
                    daily_max[str(day)] = day_max
    if not spread_hist:
        return monday_gap_times, set(), {"valid_rows": 0, "monday_gap_days": len(monday_gap_times), "wide_spread_days": 0}
    target = max(1, math.ceil(sum(spread_hist.values()) * 0.95))
    cumulative = 0
    threshold = max(spread_hist)
    for bucket in sorted(spread_hist):
        cumulative += spread_hist[bucket]
        if cumulative >= target:
            threshold = bucket
            break
    wide_spread_times = {
        pd.Timestamp(int(event_ns[index]), unit="us", tz="UTC")
        for index, maximum in enumerate(event_max_spread.tolist())
        if maximum > threshold
    }
    wide_spread_days = {
        day for day, maximum in daily_max.items() if maximum > threshold
    }
    return monday_gap_times, wide_spread_times, {"valid_rows": valid_rows, "monday_gap_days": len(monday_gap_times), "wide_spread_days": len(wide_spread_days), "wide_spread_threshold_bucket": threshold}


def _capture_cycles(positions: list[Position], *, monday_gap_dates: set[pd.Timestamp] | None = None, wide_spread_dates: set[pd.Timestamp] | None = None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    monday_gap_dates = monday_gap_dates or set()
    wide_spread_dates = wide_spread_dates or set()
    events, carry_in = _events(positions)
    active = {
        item.position_id: item
        for item in positions
        if item.open_time < SERVER_START and (item.close_time is None or item.close_time > SERVER_START)
    }
    known_flat = not active
    current: _Cycle | None = None
    completed: list[_Cycle] = []
    ordinal = 0
    kind_rank = {"CENSOR_END": 0, "CLOSE": 1, "CENSOR_START": 2, "OPEN": 3}
    def near_tick(timestamp: pd.Timestamp, candidates: set[pd.Timestamp]) -> bool:
        event_utc = (timestamp - pd.Timedelta(hours=3)).tz_localize("UTC")
        return any(abs((event_utc - tick_time).total_seconds()) <= 5 for tick_time in candidates)
    for timestamp in sorted(events):
        labels = sorted(events[timestamp], key=lambda item: (kind_rank[item[0]], item[1].side, item[1].position_id))
        ambiguous_group = len(labels) > 1
        for kind, item in labels:
            before = state_for(active)
            if current is None and known_flat and before == "FLAT" and kind in {"OPEN", "CENSOR_START"}:
                ordinal += 1
                current = _Cycle(ordinal, censored=kind == "CENSOR_START" or ambiguous_group)
            if current is not None:
                if ambiguous_group:
                    current.censored = True
                current.action_count += 1
                current.observed_actions = current.action_count
                if item.side == "buy":
                    current.buy_actions += 1
                else:
                    current.sell_actions += 1
                current.quantities.add(format(item.quantity, "f"))
                if before in {"HEDGED_1X1", "UNBALANCED_HEDGE", "MULTI_POSITION"}:
                    current.had_hedge = True
                if not current.censored and near_tick(timestamp, monday_gap_dates):
                    current.categories.add("monday_gap")
                    current.categories.discard("normal_hedge")
                if not current.censored and near_tick(timestamp, wide_spread_dates):
                    current.categories.add("wide_spread")
                if not current.censored and before == "HEDGED_1X1" and kind == "CLOSE" and "monday_gap" not in current.categories:
                    current.categories.add("normal_hedge")
                if kind.startswith("CENSOR"):
                    current.censored = True
            if kind in {"OPEN", "CENSOR_START"}:
                active[item.position_id] = item
            else:
                active.pop(item.position_id, None)
            after = state_for(active)
            if current is not None and not current.censored and after == "HEDGED_1X1" and "monday_gap" not in current.categories:
                current.had_hedge = True
                current.categories.add("normal_hedge")
            if current is not None and not current.censored and current.had_hedge and after in {"ONE_BUY", "ONE_SELL"}:
                current.categories.add("one_leg_recovery")
            if current is not None and after == "FLAT":
                completed.append(current)
                current = None
                known_flat = True
            elif current is None and after == "FLAT":
                known_flat = True
    if current is not None:
        current.censored = True
        completed.append(current)
    rows = [cycle.redacted() for cycle in completed if cycle.action_count > 0]
    return rows, {"carry_in": int(carry_in), "completed_or_censored_cycles": len(rows), "censored_cycles": sum(row["censored"] for row in rows)}


def _verify_manifest_subset(run_id: str, expected_digest: str, expected_aliases: set[str], selected_aliases: set[str], *, sort_keys: bool) -> dict[str, Path]:
    run_dir = (QUARANTINE_ROOT / run_id).resolve()
    run_dir.relative_to(QUARANTINE_ROOT.resolve())
    manifest_path = run_dir / "manifests" / "archive-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = manifest["payload"]
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=sort_keys)
    if manifest.get("manifest_sha256") != expected_digest or hashlib.sha256(encoded.encode("utf-8")).hexdigest() != expected_digest:
        raise RetroBotInputError("E-002 parent manifest digest mismatch")
    if payload.get("transfer_status") != "accepted":
        raise RetroBotInputError("E-002 parent manifest transfer status invalid")
    objects = {item.get("alias"): item for item in payload.get("objects", [])}
    if set(objects) != expected_aliases or not selected_aliases <= expected_aliases:
        raise RetroBotInputError("E-002 parent manifest aliases invalid")
    paths: dict[str, Path] = {}
    for alias in selected_aliases:
        item = objects[alias]
        relative = item.get("relative_path")
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise RetroBotInputError("E-002 parent manifest path invalid")
        path = (run_dir / relative).resolve()
        path.relative_to(run_dir.resolve())
        if path.parent != (run_dir / "incoming").resolve() or path.name != alias:
            raise RetroBotInputError("E-002 parent manifest path not pinned")
        actual_hash = sha256_file(path)
        if path.stat().st_size != item.get("bytes") or actual_hash != item.get("source_sha256") or actual_hash != item.get("destination_sha256"):
            raise RetroBotInputError("E-002 selected source object digest mismatch")
        paths[alias] = path
    return paths


def _verify_receipt_sources(receipt: Mapping[str, Any]) -> tuple[dict[str, Path], dict[str, Path]]:
    report_aliases = [alias for alias, kind in zip(receipt["source_aliases"], receipt["object_types"]) if kind == "report"]
    tick_aliases = [alias for alias, kind in zip(receipt["source_aliases"], receipt["object_types"]) if kind == "tick"]
    if not report_aliases or not tick_aliases:
        raise RetroBotInputError("E-002 source receipt must bind reports and ticks")
    report_paths = _verify_manifest_subset(REPORT_RUN_ID, REPORT_MANIFEST_SHA256, set(REPORT_ALIASES), set(report_aliases), sort_keys=True)
    tick_paths = _verify_manifest_subset(TICK_RUN_ID, TICK_MANIFEST_SHA256, set(TICK_ALIASES), set(tick_aliases), sort_keys=False)
    if any(kind not in {"report", "tick"} for kind in receipt["object_types"]):
        raise RetroBotInputError("E-002 receipt contains unsupported source object type")
    fields = receipt["allowed_fields_by_alias"]
    if any(tuple(fields[alias]) != tuple(REPORT_FIELDS) for alias in report_aliases):
        raise RetroBotInputError("E-002 report allowlist is not bound to the adapter")
    if any(tuple(fields[alias]) != tuple(TICK_FIELDS) for alias in tick_aliases):
        raise RetroBotInputError("E-002 tick allowlist is not bound to the adapter")
    for alias, path in {**report_paths, **tick_paths}.items():
        if path.stat().st_size != receipt["byte_count_by_alias"][alias]:
            raise RetroBotInputError("E-002 source byte count mismatch")
    expected_hashes = receipt["sha256_by_alias"]
    manifest_paths = {**report_paths, **tick_paths}
    for alias in report_aliases + tick_aliases:
        # verify_manifest already checked the object hash; compare the same
        # accepted bytes to the independent E-002 receipt metadata.
        if sha256_file(manifest_paths[alias]) != expected_hashes[alias]:
            raise RetroBotInputError("E-002 source hash mismatch")
    return report_paths, tick_paths


def capture_authorized(receipt: Mapping[str, Any]) -> dict[str, Any]:
    validate_source_receipt(receipt)
    if receipt["source_receipt_sha256"] != AUTHORIZED_RECEIPT_SHA256:
        raise RetroBotInputError("E-002 receipt is not the frozen authorized summer scope")
    if receipt["population_utc_half_open"] != ["2026-04-30T21:00:00.000000Z", "2026-07-30T21:00:00.000000Z"]:
        raise RetroBotInputError("E-002 population scope changed")
    report_paths, tick_paths = _verify_receipt_sources(receipt)
    positions = _load_report_positions(report_paths)
    event_times, _ = _events(positions)
    event_utc_times = {
        (timestamp - pd.Timedelta(hours=3)).tz_localize("UTC")
        for timestamp in event_times
    }
    monday_gap_dates, wide_spread_dates, tick_stats = _scan_ticks(tick_paths, event_times=event_utc_times)
    cycles, cycle_stats = _capture_cycles(positions, monday_gap_dates=monday_gap_dates, wide_spread_dates=wide_spread_dates)
    eligible = [row for row in cycles if not row["censored"]]
    categories = {name: sum(name in row["categories"] for row in eligible) for name in ("normal_hedge", "one_leg_recovery", "monday_gap", "variable_lot", "wide_spread")}
    buy_actions = sum(row["buy_actions"] for row in eligible)
    sell_actions = sum(row["sell_actions"] for row in eligible)
    actionful_sufficient = len(eligible) >= 30 and categories["normal_hedge"] >= 8 and categories["one_leg_recovery"] >= 6 and categories["monday_gap"] >= 4 and categories["variable_lot"] >= 6 and categories["wide_spread"] >= 4 and buy_actions >= 10 and sell_actions >= 10
    input_digest = digest(cycles)
    component_digest = digest({"cycle_count": len(cycles), "eligible_cycle_count": len(eligible), "category_counts": categories, "buy_actions": buy_actions, "sell_actions": sell_actions, "tick_stats": tick_stats})
    metrics = {
        "state_parity": None, "direction_parity": None, "ordering_parity": None,
        "timing_within_band": None, "lot_parity": None, "duplicate_action_rate": None,
        # E-002 capture does not yet have E-003 checkpoint comparisons or a
        # replay safety audit; these frozen estimands remain not-evaluable.
        "coverage": None,
        "censor_rate": None,
        "state_safety": None, "robustness_pass_fraction": None, "determinism": False,
    }
    gate_pass = {name: False if metrics[name] is None else metrics[name] >= gate["threshold"] if gate["direction"] == "ge" else metrics[name] <= gate["threshold"] if gate["direction"] == "le" else metrics[name] == gate["threshold"] for name, gate in load_gate_registry()["gates"].items()}
    result: dict[str, Any] = {
        "schema_version": 1,
        "case_id": CASE_ID,
        "source_receipt_sha256": receipt["source_receipt_sha256"],
        "source_receipt_present": True,
        "synthetic_only": False,
        "parent_gate_digest": FROZEN_GATE_DIGEST,
        "report_manifest_sha256": REPORT_MANIFEST_SHA256,
        "tick_manifest_sha256": TICK_MANIFEST_SHA256,
        "population_utc_half_open": receipt["population_utc_half_open"],
        "source_timezone_code": receipt["source_timezone_code"],
        "report_alias_count": len(report_paths),
        "tick_alias_count": len(tick_paths),
        "tick_stats": tick_stats,
        "cycle_count": len(cycles),
        "eligible_cycle_count": len(eligible),
        "category_counts": categories,
        "buy_actions": buy_actions,
        "sell_actions": sell_actions,
        "cycle_stats": cycle_stats,
        "cycles": cycles,
        "input_digest": input_digest,
        "component_digest": component_digest,
        "metrics": metrics,
        "gate_pass": gate_pass,
        "source_rows_emitted": False,
        "detailed_rows_retained": False,
        "m5_firewall": M5_FIREWALL,
        "execution_surface": False,
        "status": "no-supported-candidate" if actionful_sufficient else "insufficient-actionful-coverage",
    }
    result["aggregate_sha256"] = digest(result)
    assert_firewall_clean([result["source_receipt_sha256"], result["parent_gate_digest"], result["population_utc_half_open"], result["source_timezone_code"], result["cycles"], result["category_counts"]])
    return result


def build_capture_receipt(value: Mapping[str, Any]) -> dict[str, Any]:
    payload = {
        "case_id": CASE_ID,
        "source_receipt_sha256": value["source_receipt_sha256"],
        "parent_gate_digest": value["parent_gate_digest"],
        "input_digest": value["input_digest"],
        "component_digest": value["component_digest"],
        "aggregate_sha256": value["aggregate_sha256"],
        "status": value["status"],
    }
    return {**payload, "receipt_sha256": digest(payload)}


def verify_capture_receipt(value: Mapping[str, Any]) -> bool:
    required = {"case_id", "source_receipt_sha256", "parent_gate_digest", "input_digest", "component_digest", "aggregate_sha256", "status", "receipt_sha256"}
    if not isinstance(value, Mapping) or set(value) != required or value["case_id"] != CASE_ID or value["source_receipt_sha256"] != AUTHORIZED_RECEIPT_SHA256 or value["parent_gate_digest"] != FROZEN_GATE_DIGEST or value["status"] not in {"insufficient-actionful-coverage", "no-supported-candidate"}:
        raise RetroBotInputError("E-002 capture receipt identity invalid")
    for field_name in ("source_receipt_sha256", "parent_gate_digest", "input_digest", "component_digest", "aggregate_sha256", "receipt_sha256"):
        if not isinstance(value[field_name], str) or not re.fullmatch(r"[0-9a-f]{64}", value[field_name]):
            raise RetroBotInputError("E-002 capture receipt digest invalid")
    if value["receipt_sha256"] != digest({key: value[key] for key in value if key != "receipt_sha256"}):
        raise RetroBotInputError("E-002 capture receipt self-digest invalid")
    return True


def verify_authorized_capture(
    value: Mapping[str, Any],
    receipt: Mapping[str, Any],
    *,
    expected_input_digest: str,
    expected_component_digest: str,
    expected_aggregate_sha256: str,
    expected_status: str,
) -> bool:
    required = {
        "schema_version", "case_id", "source_receipt_sha256", "source_receipt_present", "synthetic_only",
        "parent_gate_digest", "report_manifest_sha256", "tick_manifest_sha256", "population_utc_half_open",
        "source_timezone_code", "report_alias_count", "tick_alias_count", "tick_stats", "cycle_count",
        "eligible_cycle_count", "category_counts", "buy_actions", "sell_actions", "cycle_stats", "cycles",
        "input_digest", "component_digest", "metrics", "gate_pass", "source_rows_emitted",
        "detailed_rows_retained", "m5_firewall", "execution_surface", "status", "aggregate_sha256",
    }
    if not isinstance(value, Mapping) or set(value) != required:
        raise RetroBotInputError("E-002 capture aggregate schema invalid")
    validate_source_receipt(receipt)
    if receipt["source_receipt_sha256"] != AUTHORIZED_RECEIPT_SHA256:
        raise RetroBotInputError("E-002 trusted source receipt digest invalid")
    if value["schema_version"] != 1 or value["case_id"] != CASE_ID or value["source_receipt_sha256"] != AUTHORIZED_RECEIPT_SHA256 or value["parent_gate_digest"] != FROZEN_GATE_DIGEST or value["source_receipt_present"] is not True or value["synthetic_only"] is not False or value["m5_firewall"] != M5_FIREWALL or value["execution_surface"] is not False or value["source_rows_emitted"] is not False or value["detailed_rows_retained"] is not False:
        raise RetroBotInputError("E-002 capture provenance/firewall invalid")
    report_count = sum(kind == "report" for kind in receipt["object_types"])
    tick_count = sum(kind == "tick" for kind in receipt["object_types"])
    if value["report_manifest_sha256"] != REPORT_MANIFEST_SHA256 or value["tick_manifest_sha256"] != TICK_MANIFEST_SHA256 or value["population_utc_half_open"] != receipt["population_utc_half_open"] or value["source_timezone_code"] != receipt["source_timezone_code"] or value["report_alias_count"] != report_count or value["tick_alias_count"] != tick_count:
        raise RetroBotInputError("E-002 capture source provenance changed")
    if value["aggregate_sha256"] != digest({key: value[key] for key in value if key != "aggregate_sha256"}):
        raise RetroBotInputError("E-002 capture aggregate digest invalid")
    if (
        not isinstance(expected_input_digest, str)
        or not isinstance(expected_component_digest, str)
        or not isinstance(expected_aggregate_sha256, str)
        or not isinstance(expected_status, str)
        or value["input_digest"] != expected_input_digest
        or value["component_digest"] != expected_component_digest
        or value["aggregate_sha256"] != expected_aggregate_sha256
        or value["status"] != expected_status
    ):
        raise RetroBotInputError("E-002 trusted capture digests are required")
    if value["input_digest"] != digest(value["cycles"]):
        raise RetroBotInputError("E-002 capture input digest invalid")
    expected_component = digest({"cycle_count": value["cycle_count"], "eligible_cycle_count": value["eligible_cycle_count"], "category_counts": value["category_counts"], "buy_actions": value["buy_actions"], "sell_actions": value["sell_actions"], "tick_stats": value["tick_stats"]})
    if value["component_digest"] != expected_component:
        raise RetroBotInputError("E-002 capture component digest invalid")
    if value["cycle_count"] != len(value["cycles"]) or value["eligible_cycle_count"] > value["cycle_count"]:
        raise RetroBotInputError("E-002 capture cycle counts invalid")
    if set(value["category_counts"]) != {"normal_hedge", "one_leg_recovery", "monday_gap", "variable_lot", "wide_spread"} or any(type(item) is not int or item < 0 for item in value["category_counts"].values()):
        raise RetroBotInputError("E-002 capture category schema invalid")
    if set(value["cycle_stats"]) != {"carry_in", "completed_or_censored_cycles", "censored_cycles"} or any(type(item) is not int or item < 0 for item in value["cycle_stats"].values()):
        raise RetroBotInputError("E-002 capture cycle stats invalid")
    if value["cycle_stats"]["completed_or_censored_cycles"] != value["cycle_count"] or value["cycle_stats"]["censored_cycles"] != value["cycle_count"] - value["eligible_cycle_count"]:
        raise RetroBotInputError("E-002 capture cycle stats inconsistent")
    allowed_categories = {"normal_hedge", "one_leg_recovery", "monday_gap", "variable_lot", "wide_spread"}
    cycle_ids: set[str] = set()
    for row in value["cycles"]:
        if not isinstance(row, Mapping) or set(row) != {"cycle_id", "categories", "action_count", "buy_actions", "sell_actions", "observed_lot_bands", "censored"} or not isinstance(row["cycle_id"], str) or not re.fullmatch(r"e002-c[0-9]{6}", row["cycle_id"]) or row["cycle_id"] in cycle_ids:
            raise RetroBotInputError("E-002 capture cycle row invalid")
        cycle_ids.add(row["cycle_id"])
        if not isinstance(row["categories"], list) or len(set(row["categories"])) != len(row["categories"]) or any(category not in allowed_categories for category in row["categories"]):
            raise RetroBotInputError("E-002 capture cycle categories invalid")
        if any(type(row[field]) is not int or row[field] < 0 for field in ("action_count", "buy_actions", "sell_actions")) or row["action_count"] < 1 or row["buy_actions"] + row["sell_actions"] > row["action_count"] or type(row["censored"]) is not bool:
            raise RetroBotInputError("E-002 capture cycle counts invalid")
        if not isinstance(row["observed_lot_bands"], list) or any(not isinstance(lot, str) or not re.fullmatch(r"[0-9]+\.[0-9]{8}", lot) or Decimal(lot) <= 0 for lot in row["observed_lot_bands"]):
            raise RetroBotInputError("E-002 capture lot bands invalid")
    eligible_rows = [row for row in value["cycles"] if not row["censored"]]
    recomputed_categories = {name: sum(name in row["categories"] for row in eligible_rows) for name in sorted(allowed_categories)}
    if dict(value["category_counts"]) != recomputed_categories or value["eligible_cycle_count"] != len(eligible_rows) or value["buy_actions"] != sum(row["buy_actions"] for row in eligible_rows) or value["sell_actions"] != sum(row["sell_actions"] for row in eligible_rows):
        raise RetroBotInputError("E-002 capture category/action totals inconsistent")
    if set(value["tick_stats"]) not in ({"valid_rows", "monday_gap_days", "wide_spread_days"}, {"valid_rows", "monday_gap_days", "wide_spread_days", "wide_spread_threshold_bucket"}) or any(type(item) is not int or item < 0 for item in value["tick_stats"].values()):
        raise RetroBotInputError("E-002 capture tick stats invalid")
    if value["status"] not in {"insufficient-actionful-coverage", "no-supported-candidate"}:
        raise RetroBotInputError("E-002 capture status invalid")
    gates = load_gate_registry()["gates"]
    if set(value["metrics"]) != set(gates) or set(value["gate_pass"]) != set(gates) or any(type(flag) is not bool for flag in value["gate_pass"].values()):
        raise RetroBotInputError("E-002 capture gate schema invalid")
    if value["metrics"]["determinism"] is not False:
        raise RetroBotInputError("E-002 capture determinism must remain unclaimed")
    for name, metric in value["metrics"].items():
        if name == "determinism":
            continue
        if name == "state_safety":
            if metric is not None and (type(metric) is not int or metric < 0):
                raise RetroBotInputError("E-002 capture safety metric invalid")
        elif metric is not None and (type(metric) not in (int, float) or isinstance(metric, bool) or not math.isfinite(metric) or metric < 0 or metric > 1):
            raise RetroBotInputError("E-002 capture ratio metric invalid")
    expected_pass = {name: False if value["metrics"][name] is None else value["metrics"][name] >= gate["threshold"] if gate["direction"] == "ge" else value["metrics"][name] <= gate["threshold"] if gate["direction"] == "le" else value["metrics"][name] == gate["threshold"] for name, gate in gates.items()}
    if dict(value["gate_pass"]) != expected_pass:
        raise RetroBotInputError("E-002 capture gate results invalid")
    population = load_gate_registry()["actionful_population"]
    sufficient = value["eligible_cycle_count"] >= population["minimum_total"] and all(value["category_counts"][key] >= threshold for key, threshold in population["minimum_categories"].items()) and value["buy_actions"] >= population["minimum_buy_actions"] and value["sell_actions"] >= population["minimum_sell_actions"]
    expected_status = "no-supported-candidate" if sufficient else "insufficient-actionful-coverage"
    if value["status"] != expected_status:
        raise RetroBotInputError("E-002 capture sufficiency status invalid")
    assert_firewall_clean([value["cycles"], value["category_counts"], value["metrics"], value["gate_pass"]])
    return True
