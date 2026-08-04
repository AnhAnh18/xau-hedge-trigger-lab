"""Causal lifecycle and stream-only adapter primitives for RH-002."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np
import pandas as pd

from xau_trigger.parsers.mt5_report import parse_report

ROOT = Path(__file__).resolve().parents[2]
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
STATE_LABELS = (
    "FLAT",
    "ONE_BUY",
    "ONE_SELL",
    "HEDGED_1X1",
    "UNBALANCED_HEDGE",
    "MULTI_POSITION",
    "CENSORED",
)


class RetroHistInputError(ValueError):
    """Fail-closed input or state transition error."""


@dataclass(frozen=True)
class Position:
    position_id: str
    side: str
    quantity: Decimal
    open_time: pd.Timestamp
    close_time: pd.Timestamp | None
    censored: bool = False


@dataclass(frozen=True)
class LifecycleEvent:
    kind: str
    position_id: str
    side: str
    quantity: Decimal
    time: pd.Timestamp


@dataclass(frozen=True)
class CausalAction:
    action_id: str
    time_ns: int
    kind: str
    side: str
    quantity: Decimal


@dataclass(frozen=True)
class PolicyState:
    state: str = "FLAT"
    buy_quantity: Decimal = Decimal("0.00000000")
    sell_quantity: Decimal = Decimal("0.00000000")
    last_time_ns: int | None = None
    last_action_id: str | None = None
    seen_action_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Tick:
    time_utc: pd.Timestamp
    bid: Decimal
    ask: Decimal


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def parse_fixed8(value: object) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise RetroHistInputError("quantity is not numeric")
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise RetroHistInputError("quantity is malformed") from None
    if not quantity.is_finite() or quantity <= 0 or quantity > MAX_QUANTITY:
        raise RetroHistInputError("quantity is outside bounds")
    fixed = quantity.quantize(FIXED8, rounding=ROUND_DOWN)
    if fixed != quantity:
        raise RetroHistInputError("quantity is not fixed8")
    return fixed


def _timestamp(value: object, *, allow_missing: bool = False) -> pd.Timestamp | None:
    if value is None or pd.isna(value):
        if allow_missing:
            return None
        raise RetroHistInputError("timestamp is missing")
    result = pd.Timestamp(value)
    if pd.isna(result):
        if allow_missing:
            return None
        raise RetroHistInputError("timestamp is missing")
    if result.tzinfo is not None:
        raise RetroHistInputError("report timestamp must be naive")
    return result


def _run_dir(run_id: str) -> Path:
    result = (QUARANTINE_ROOT / run_id).resolve()
    result.relative_to(QUARANTINE_ROOT.resolve())
    return result


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_manifest(
    run_id: str,
    expected_digest: str,
    expected_aliases: set[str],
    *,
    sort_keys: bool,
    check_objects: bool = True,
) -> dict[str, Path]:
    run_dir = _run_dir(run_id)
    manifest_path = run_dir / "manifests" / "archive-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = manifest["payload"]
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=sort_keys)
    if manifest.get("manifest_sha256") != expected_digest or hashlib.sha256(encoded.encode()).hexdigest() != expected_digest:
        raise RetroHistInputError("manifest digest mismatch")
    if payload.get("transfer_status") != "accepted":
        raise RetroHistInputError("source transfer is not accepted")
    object_items = payload["objects"]
    aliases = [item.get("alias") for item in object_items]
    if any(not isinstance(alias, str) for alias in aliases) or len(aliases) != len(set(aliases)):
        raise RetroHistInputError("source aliases contain duplicates or invalid values")
    objects = {item["alias"]: item for item in object_items}
    if set(objects) != expected_aliases:
        raise RetroHistInputError("source aliases are not pinned")
    paths: dict[str, Path] = {}
    for alias, item in objects.items():
        relative = item.get("relative_path")
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise RetroHistInputError("source relative path is invalid")
        path = (run_dir / relative).resolve()
        path.relative_to(run_dir.resolve())
        if path.parent != (run_dir / "incoming").resolve() or path.name != alias:
            raise RetroHistInputError("source path is not pinned")
        if check_objects:
            actual = sha256_file(path)
            if actual != item["source_sha256"] or actual != item["destination_sha256"]:
                raise RetroHistInputError("source object digest mismatch")
        paths[alias] = path
    return paths


def normalize_position(row: dict[str, object]) -> Position:
    position_id = str(row.get("position_id", "")).strip()
    side = str(row.get("side", "")).strip().casefold()
    symbol = str(row.get("symbol", "")).strip().casefold()
    if not position_id or position_id.casefold() in {"nan", "none"}:
        raise RetroHistInputError("position id is missing")
    if symbol != "xauusd" or side not in {"buy", "sell"}:
        raise RetroHistInputError("position symbol or side is invalid")
    open_time = _timestamp(row.get("open_time"))
    close_time = _timestamp(row.get("close_time"), allow_missing=True)
    return Position(position_id, side, parse_fixed8(row.get("volume")), open_time, close_time)


def deduplicate_positions(rows: Iterable[dict[str, object]]) -> tuple[list[Position], dict[str, int]]:
    grouped: dict[str, list[Position]] = defaultdict(list)
    invalid_rows = 0
    for row in rows:
        try:
            position = normalize_position(row)
        except (RetroHistInputError, TypeError, ValueError, OverflowError):
            invalid_rows += 1
            continue
        grouped[position.position_id].append(position)

    duplicate_rows = conflicting_ids = right_censored = outside = 0
    censored_in_population = 0
    accepted: list[Position] = []
    for position_id, values in grouped.items():
        duplicate_rows += max(0, len(values) - 1)
        signatures = {(item.side, item.quantity, int(item.open_time.value)) for item in values}
        closes = {int(item.close_time.value) for item in values if item.close_time is not None}
        if len(signatures) != 1 or len(closes) > 1:
            conflicting_ids += 1
            # A conflicting snapshot cannot yield a definite event. Retain a
            # conservative interval marker so the lifecycle is explicitly
            # censored instead of silently dropping the position ID.
            overlapping = [
                item for item in values
                if item.open_time < END_SERVER
                and (item.close_time is None or item.close_time > START_SERVER)
                and max(item.open_time, START_SERVER)
                < min(item.close_time or END_SERVER, END_SERVER)
            ]
            if overlapping:
                censor_start = min(item.open_time for item in overlapping)
                censor_ends = [item.close_time for item in overlapping if item.close_time is not None]
                censor_end = None if len(censor_ends) != len(overlapping) else max(censor_ends)
                accepted.append(replace(values[0], open_time=censor_start, close_time=censor_end, censored=True))
                censored_in_population += 1
            continue
        first = values[0]
        close_time = pd.Timestamp(next(iter(closes)), unit="ns") if closes else None
        if first.open_time >= END_SERVER or (close_time is not None and close_time <= START_SERVER):
            outside += 1
            continue
        if close_time is not None and max(first.open_time, START_SERVER) >= min(close_time, END_SERVER):
            outside += 1
            continue
        if close_time is None:
            right_censored += 1
        accepted.append(replace(first, close_time=close_time, censored=close_time is None))
    return accepted, {
        "accepted_position_ids": len(accepted),
        "position_ids_seen": len(grouped),
        "duplicate_position_rows": duplicate_rows,
        "conflicting_position_ids": conflicting_ids,
        "invalid_position_rows": invalid_rows,
        "right_censored_positions": right_censored,
        "censored_position_ids": conflicting_ids + right_censored,
        "censored_in_population_position_ids": censored_in_population + right_censored,
        "outside_population_position_ids": outside,
    }


def load_positions(report_paths: dict[str, Path]) -> tuple[list[Position], dict[str, int]]:
    rows: list[dict[str, object]] = []
    for alias in REPORT_ALIASES:
        tables = parse_report(report_paths[alias], report_id=alias)
        for section in ("positions", "open_positions"):
            frame = tables[section]
            if not frame.empty:
                rows.extend(frame[["position_id", "symbol", "side", "volume", "open_time", "close_time"]].to_dict("records"))
    positions, stats = deduplicate_positions(rows)
    stats["reports_parsed"] = len(REPORT_ALIASES)
    return positions, stats


def state_for(active: dict[str, Position]) -> str:
    if any(item.censored for item in active.values()):
        return "CENSORED"
    buys = [item for item in active.values() if item.side == "buy"]
    sells = [item for item in active.values() if item.side == "sell"]
    total = len(active)
    if total == 0:
        return "FLAT"
    if total == 1:
        return "ONE_BUY" if buys else "ONE_SELL"
    if total == 2 and len(buys) == 1 and len(sells) == 1:
        return "HEDGED_1X1" if buys[0].quantity == sells[0].quantity else "UNBALANCED_HEDGE"
    return "MULTI_POSITION"


def _empty_matrix() -> dict[str, dict[str, int]]:
    return {source: {target: 0 for target in STATE_LABELS} for source in STATE_LABELS}


def reconstruct_observed(positions: Iterable[Position]) -> dict[str, object]:
    events: dict[pd.Timestamp, list[LifecycleEvent]] = defaultdict(list)
    active: dict[str, Position] = {}
    for item in positions:
        if item.censored:
            if item.open_time < START_SERVER and (item.close_time is None or item.close_time > START_SERVER):
                active[item.position_id] = item
            if START_SERVER <= item.open_time < END_SERVER:
                events[item.open_time].append(LifecycleEvent("CENSOR_START", item.position_id, item.side, item.quantity, item.open_time))
            if item.close_time is not None and START_SERVER < item.close_time < END_SERVER:
                events[item.close_time].append(LifecycleEvent("CENSOR_END", item.position_id, item.side, item.quantity, item.close_time))
            continue
        if item.open_time < START_SERVER and (item.close_time is None or item.close_time > START_SERVER):
            active[item.position_id] = item
        if START_SERVER <= item.open_time < END_SERVER:
            events[item.open_time].append(LifecycleEvent("OPEN", item.position_id, item.side, item.quantity, item.open_time))
        if item.close_time is not None and START_SERVER < item.close_time < END_SERVER:
            events[item.close_time].append(LifecycleEvent("CLOSE", item.position_id, item.side, item.quantity, item.close_time))

    states = {label: 0 for label in STATE_LABELS}
    transitions = _empty_matrix()
    states[state_for(active)] += 1
    open_events = close_events = duplicate_labels = collisions = 0
    for timestamp in sorted(events):
        kind_rank = {"CENSOR_END": 0, "CLOSE": 1, "CENSOR_START": 2, "OPEN": 3}
        labels = sorted(events[timestamp], key=lambda item: (kind_rank[item.kind], 0 if item.side == "buy" else 1, item.position_id))
        if len(labels) > 1:
            collisions += 1
        seen_keys: set[tuple[str, str]] = set()
        for label in labels:
            key = (label.kind, label.position_id)
            if key in seen_keys:
                duplicate_labels += 1
                continue
            seen_keys.add(key)
            before = state_for(active)
            if label.kind in {"OPEN", "CENSOR_START"}:
                if label.kind == "OPEN":
                    open_events += 1
                    active[label.position_id] = Position(label.position_id, label.side, label.quantity, label.time, None, False)
                else:
                    active[label.position_id] = Position(label.position_id, label.side, label.quantity, label.time, None, True)
            elif label.kind == "CLOSE":
                close_events += 1
                active.pop(label.position_id, None)
            else:
                active.pop(label.position_id, None)
            after = state_for(active)
            states[after] += 1
            transitions[before][after] += 1
    return {
        "event_coverage": {
            "open_events": open_events,
            "close_events": close_events,
            "duplicate_labels": duplicate_labels,
            "collision_timestamps": collisions,
        },
        "state_counts": states,
        "transition_counts": transitions,
    }


def apply_causal_action(state: PolicyState, action: CausalAction) -> PolicyState:
    if not action.action_id or action.action_id in state.seen_action_ids:
        raise RetroHistInputError("action id is duplicate or missing")
    if state.last_time_ns is not None:
        previous_key = (state.last_time_ns, state.last_action_id or "")
        if (action.time_ns, action.action_id) <= previous_key:
            raise RetroHistInputError("action key is not strictly increasing")
    if action.side not in {"buy", "sell"} or action.kind not in {"OPEN", "CLOSE"}:
        raise RetroHistInputError("action kind or side is invalid")
    quantity = parse_fixed8(action.quantity)
    buy = state.buy_quantity
    sell = state.sell_quantity
    if action.kind == "OPEN":
        if action.side == "buy":
            if buy != 0:
                raise RetroHistInputError("buy leg is already active")
            buy = quantity
        else:
            if sell != 0:
                raise RetroHistInputError("sell leg is already active")
            sell = quantity
    elif action.side == "buy":
        if buy != quantity:
            raise RetroHistInputError("buy close quantity mismatch")
        buy = Decimal("0.00000000")
    else:
        if sell != quantity:
            raise RetroHistInputError("sell close quantity mismatch")
        sell = Decimal("0.00000000")
    state_label = "FLAT"
    if buy and sell:
        state_label = "HEDGED_1X1" if buy == sell else "UNBALANCED_HEDGE"
    elif buy:
        state_label = "ONE_BUY"
    elif sell:
        state_label = "ONE_SELL"
    return PolicyState(state_label, buy, sell, action.time_ns, action.action_id, state.seen_action_ids + (action.action_id,))


def apply_oracle_label(state: PolicyState, _label: LifecycleEvent) -> PolicyState:
    """Oracle labels are diagnostics and intentionally cannot mutate policy state."""
    return state


def iter_ticks(path: Path, *, broad_start: pd.Timestamp, broad_end: pd.Timestamp, previous_ns: int | None = None) -> tuple[Iterator[Tick], dict[str, int]]:
    stats = {"valid_rows": 0, "invalid_rows": 0, "duplicate_timestamps": 0, "out_of_order": 0, "crossed_quotes": 0, "envelope_excluded_rows": 0, "last_time_ns": previous_ns}

    def generator() -> Iterator[Tick]:
        nonlocal previous_ns
        for chunk in pd.read_csv(path, usecols=["time_utc", "bid", "ask"], chunksize=250_000):
            timestamps = pd.to_datetime(chunk["time_utc"], utc=True, errors="coerce")
            bids = pd.to_numeric(chunk["bid"], errors="coerce")
            asks = pd.to_numeric(chunk["ask"], errors="coerce")
            for timestamp, bid, ask in zip(timestamps, bids, asks):
                if pd.isna(timestamp):
                    stats["invalid_rows"] += 1
                    continue
                current_ns = int(timestamp.value)
                if previous_ns is not None:
                    if current_ns < previous_ns:
                        stats["out_of_order"] += 1
                        raise RetroHistInputError("tick timestamp order decreased")
                    if current_ns == previous_ns:
                        stats["duplicate_timestamps"] += 1
                previous_ns = current_ns
                stats["last_time_ns"] = current_ns
                if pd.isna(bid) or pd.isna(ask) or not np.isfinite(float(bid)) or not np.isfinite(float(ask)):
                    stats["invalid_rows"] += 1
                    continue
                if float(bid) <= 0 or float(ask) <= 0:
                    stats["invalid_rows"] += 1
                    continue
                if float(ask) < float(bid):
                    stats["crossed_quotes"] += 1
                    continue
                if timestamp < broad_start or timestamp >= broad_end:
                    stats["envelope_excluded_rows"] += 1
                    continue
                stats["valid_rows"] += 1
                yield Tick(timestamp, Decimal(str(bid)), Decimal(str(ask)))

    return generator(), stats
