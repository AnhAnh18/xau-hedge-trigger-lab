"""RETRO-BOT-002 stream-only paper accounting for the RB-001 replay."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .retro_bot import (
    ClockScenario,
    EligibleInterval,
    LOCKED_CONFIG_SHA256,
    Policy,
    RetroBotConfig,
    RetroBotInputError,
    _canonical_digest,
    load_config,
)


PAPER_CASE_ID = "RETRO-BOT-002"
PAPER_SCHEMA_VERSION = 1
PAPER_QUANTITY = 1.0
PAPER_MARK_ANCHOR = "observed_rehedge"
PAPER_STATUSES = (
    "emitted_marked",
    "emitted_mark_censored",
    "right_censored_delay_not_reached",
    "right_censored_no_valid_tick",
    "excluded_clock_unresolved",
)
RETURN_BANDS = ("loss", "flat", "gain")
_FORBIDDEN = ("price", "timestamp", "path", "ticket", "account_id", "account_number", "comment", "interval_id", "report_alias")


@dataclass(frozen=True)
class PaperOutcome:
    policy_id: str
    clock_id: str
    status: str
    action_side: str | None
    net_return: float | None


def _return_band(value: float) -> str:
    if value < 0:
        return "loss"
    if value > 0:
        return "gain"
    return "flat"


def paper_backtest_interval(
    interval: EligibleInterval,
    policy: Policy,
    clock: ClockScenario,
    config: RetroBotConfig,
    tick_paths: Iterable[Path],
) -> PaperOutcome:
    """Run one interval through the same one-pass streaming implementation."""
    locked = load_config()
    if config != locked or policy not in locked.policies or clock not in locked.clocks:
        raise RetroBotInputError("paper policy/clock/config is not locked")
    outcomes = paper_backtest_intervals((interval,), locked, tick_paths)
    return next(item for item in outcomes if item.policy_id == policy.id and item.clock_id == clock.id)


def paper_backtest_intervals(intervals: Iterable[EligibleInterval], config: RetroBotConfig, tick_paths: Iterable[Path]) -> tuple[PaperOutcome, ...]:
    locked = load_config()
    if config != locked or config.config_sha256 != LOCKED_CONFIG_SHA256:
        raise RetroBotInputError("paper config is not locked")
    config = locked
    intervals = tuple(intervals)
    outcomes: dict[tuple[int, str, str], PaperOutcome] = {}
    windows: dict[tuple[int, str, str], tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp, str]] = {}
    for index, interval in enumerate(intervals):
        for clock in config.clocks:
            unlock = clock.map_server_to_utc(interval.unlock_time_server)
            anchor = clock.map_server_to_utc(interval.observed_rehedge_time_server)
            mark_end = clock.map_server_to_utc(config.population.end_server_exclusive)
            for policy in config.policies:
                key = (index, clock.id, policy.id)
                target_server = interval.unlock_time_server + pd.Timedelta(seconds=policy.delay_seconds)
                target = clock.map_server_to_utc(target_server)
                if unlock.status != "unique" or anchor.status != "unique" or target.status != "unique" or mark_end.status != "unique":
                    outcomes[key] = PaperOutcome(policy.id, clock.id, "excluded_clock_unresolved", None, None)
                elif target.timestamp_utc is None or anchor.timestamp_utc is None or mark_end.timestamp_utc is None or target_server >= interval.observed_rehedge_time_server or target.timestamp_utc >= anchor.timestamp_utc:
                    outcomes[key] = PaperOutcome(policy.id, clock.id, "right_censored_delay_not_reached", None, None)
                else:
                    windows[key] = (target.timestamp_utc, anchor.timestamp_utc, anchor.timestamp_utc, mark_end.timestamp_utc, interval.action_side)
    first_action: dict[tuple[int, str, str], tuple[pd.Timestamp, float, float] | None] = {key: None for key in windows}
    first_mark: dict[tuple[int, str, str], tuple[pd.Timestamp, float, float] | None] = {key: None for key in windows}
    window_keys = tuple(windows)
    action_starts = pd.DatetimeIndex([windows[key][0] for key in window_keys])
    action_ends = pd.DatetimeIndex([windows[key][1] for key in window_keys])
    mark_starts = pd.DatetimeIndex([windows[key][2] for key in window_keys])
    mark_ends = pd.DatetimeIndex([windows[key][3] for key in window_keys])
    for path in tick_paths:
        for chunk in pd.read_csv(path, usecols=["time_utc", "bid", "ask"], chunksize=100_000):
            timestamps = pd.to_datetime(chunk["time_utc"], utc=True, errors="coerce")
            bids = pd.to_numeric(chunk["bid"], errors="coerce")
            asks = pd.to_numeric(chunk["ask"], errors="coerce")
            valid = timestamps.notna() & bids.notna() & asks.notna() & (bids > 0) & (asks > 0) & (asks >= bids)
            valid_rows = pd.DataFrame({"timestamp": timestamps[valid], "bid": bids[valid], "ask": asks[valid]})
            if valid_rows.empty:
                continue
            valid_rows = valid_rows.sort_values("timestamp", kind="stable").reset_index(drop=True)
            tick_times = pd.DatetimeIndex(valid_rows["timestamp"])
            action_indexes = tick_times.searchsorted(action_starts, side="left")
            action_valid = action_indexes < len(valid_rows)
            action_valid &= tick_times.take(np.minimum(action_indexes, len(valid_rows) - 1)) < action_ends
            action_valid &= np.fromiter((first_action[key] is None for key in window_keys), dtype=bool)
            for index in np.flatnonzero(action_valid):
                row_index = int(action_indexes[index])
                quote_row = valid_rows.iloc[row_index]
                first_action[window_keys[index]] = (
                    tick_times[row_index],
                    float(quote_row["bid"]),
                    float(quote_row["ask"]),
                )
            mark_indexes = tick_times.searchsorted(mark_starts, side="left")
            mark_valid = mark_indexes < len(valid_rows)
            mark_valid &= tick_times.take(np.minimum(mark_indexes, len(valid_rows) - 1)) < mark_ends
            mark_valid &= np.fromiter((first_mark[key] is None for key in window_keys), dtype=bool)
            for index in np.flatnonzero(mark_valid):
                row_index = int(mark_indexes[index])
                quote_row = valid_rows.iloc[row_index]
                first_mark[window_keys[index]] = (
                    tick_times[row_index],
                    float(quote_row["bid"]),
                    float(quote_row["ask"]),
                )
    for key in windows:
        _, clock_id, policy_id = key
        action = first_action[key]
        mark = first_mark[key]
        interval_index = key[0]
        if action is None:
            outcomes[key] = PaperOutcome(policy_id, clock_id, "right_censored_no_valid_tick", None, None)
        elif mark is None:
            outcomes[key] = PaperOutcome(policy_id, clock_id, "emitted_mark_censored", intervals[interval_index].action_side, None)
        else:
            side = intervals[interval_index].action_side
            entry = action[2] if side == "buy" else action[1]
            liquidation = mark[1] if side == "buy" else mark[2]
            net = (liquidation - entry) if side == "buy" else (entry - liquidation)
            outcomes[key] = PaperOutcome(policy_id, clock_id, "emitted_marked", side, float(net))
    return tuple(outcomes[(index, clock.id, policy.id)] for index in range(len(intervals)) for clock in config.clocks for policy in config.policies)


def _assert_safe(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if any(token in str(key).casefold() for token in _FORBIDDEN):
                raise RetroBotInputError(f"paper aggregate contains prohibited key: {key}")
            _assert_safe(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_safe(nested)


def aggregate_paper_outcomes(outcomes: Iterable[PaperOutcome], config: RetroBotConfig, *, report_manifest_sha256: str, tick_manifest_sha256: str) -> dict:
    locked = load_config()
    if config != locked or config.config_sha256 != LOCKED_CONFIG_SHA256:
        raise RetroBotInputError("paper config is not locked")
    config = locked
    if report_manifest_sha256 != config.source_receipt["report_manifest_sha256"] or tick_manifest_sha256 != config.source_receipt["tick_manifest_sha256"]:
        raise RetroBotInputError("paper source manifests are not registered")
    expected = {(clock.id, policy.id) for clock in config.clocks for policy in config.policies}
    materialized = tuple(outcomes)
    grouped: dict[tuple[str, str], list[PaperOutcome]] = {key: [] for key in expected}
    for item in materialized:
        key = (item.clock_id, item.policy_id)
        if key not in grouped:
            raise RetroBotInputError("paper aggregate contains unregistered pair")
        grouped[key].append(item)
    rows = []
    for clock in config.clocks:
        for policy in config.policies:
            selected = grouped[(clock.id, policy.id)]
            counts = {status: sum(item.status == status for item in selected) for status in PAPER_STATUSES}
            bands = {band: 0 for band in RETURN_BANDS}
            for item in selected:
                if item.status == "emitted_marked":
                    if item.net_return is None or item.action_side not in {"buy", "sell"}:
                        raise RetroBotInputError("marked paper outcome is incomplete")
                    bands[_return_band(item.net_return)] += 1
            rows.append({
                "clock_id": clock.id,
                "policy_id": policy.id,
                "synthetic_quantity": PAPER_QUANTITY,
                "eligible_interval_count": len(selected),
                **{f"{status}_count": counts[status] for status in PAPER_STATUSES},
                "return_bands": bands,
            })
    coverage = {row["eligible_interval_count"] for row in rows}
    if len(coverage) > 1:
        raise RetroBotInputError("paper policy/clock coverage is inconsistent")
    payload = {
        "schema_version": PAPER_SCHEMA_VERSION,
        "case_id": PAPER_CASE_ID,
        "base_config_sha256": config.config_sha256,
        "source_manifest_digests": {"report_manifest_sha256": report_manifest_sha256, "tick_manifest_sha256": tick_manifest_sha256},
        "accounting": {"quantity": PAPER_QUANTITY, "entry": "buy_at_ask_sell_at_bid", "mark": "buy_at_bid_sell_at_ask", "mark_anchor": PAPER_MARK_ANCHOR, "costs": "none"},
        "policy_clock_rows": rows,
        "aggregate_sha256": "TO_BE_FILLED",
    }
    payload["aggregate_sha256"] = _canonical_digest(payload, "aggregate_sha256")
    validate_paper_aggregate(payload, config)
    return payload


def validate_paper_aggregate(payload: dict, config: RetroBotConfig) -> None:
    locked = load_config()
    if config != locked or config.config_sha256 != LOCKED_CONFIG_SHA256:
        raise RetroBotInputError("paper config is not locked")
    config = locked
    if not isinstance(payload, dict) or payload.get("aggregate_sha256") != _canonical_digest(payload, "aggregate_sha256"):
        raise RetroBotInputError("paper aggregate digest mismatch")
    if type(payload.get("schema_version")) is not int or payload.get("schema_version") != PAPER_SCHEMA_VERSION or payload.get("case_id") != PAPER_CASE_ID or payload.get("base_config_sha256") != config.config_sha256:
        raise RetroBotInputError("paper aggregate schema/case mismatch")
    expected_digests = {
        "report_manifest_sha256": config.source_receipt["report_manifest_sha256"],
        "tick_manifest_sha256": config.source_receipt["tick_manifest_sha256"],
    }
    if payload.get("source_manifest_digests") != expected_digests:
        raise RetroBotInputError("paper source digests are not registered")
    if payload.get("accounting") != {"quantity": PAPER_QUANTITY, "entry": "buy_at_ask_sell_at_bid", "mark": "buy_at_bid_sell_at_ask", "mark_anchor": PAPER_MARK_ANCHOR, "costs": "none"}:
        raise RetroBotInputError("paper accounting assumptions are not pinned")
    required_root = {"schema_version", "case_id", "base_config_sha256", "source_manifest_digests", "accounting", "policy_clock_rows", "aggregate_sha256"}
    if set(payload) != required_root:
        raise RetroBotInputError("paper aggregate root schema mismatch")
    rows = payload.get("policy_clock_rows")
    if not isinstance(rows, list) or len(rows) != len(config.clocks) * len(config.policies):
        raise RetroBotInputError("paper policy/clock rows are incomplete")
    pairs = set()
    expected_pairs = {(clock.id, policy.id) for clock in config.clocks for policy in config.policies}
    for row in rows:
        if set(row) != {"clock_id", "policy_id", "synthetic_quantity", "eligible_interval_count", *[f"{s}_count" for s in PAPER_STATUSES], "return_bands"}:
            raise RetroBotInputError("paper row schema mismatch")
        pair = (row["clock_id"], row["policy_id"])
        if pair in pairs or pair not in expected_pairs:
            raise RetroBotInputError("paper policy/clock pairs are duplicated or unregistered")
        pairs.add(pair)
        if row["synthetic_quantity"] != PAPER_QUANTITY or type(row["synthetic_quantity"]) is bool:
            raise RetroBotInputError("paper synthetic quantity is not registered")
        statuses = [row[f"{s}_count"] for s in PAPER_STATUSES]
        if any(type(value) is not int or isinstance(value, bool) or value < 0 for value in statuses + [row["eligible_interval_count"]]):
            raise RetroBotInputError("paper count invalid")
        if sum(statuses) != row["eligible_interval_count"]:
            raise RetroBotInputError("paper status counts do not reconcile")
        bands = row["return_bands"]
        if set(bands) != set(RETURN_BANDS) or any(type(value) is not int or isinstance(value, bool) or value < 0 for value in bands.values()) or sum(bands.values()) != row["emitted_marked_count"]:
            raise RetroBotInputError("paper return bands do not reconcile")
    if pairs != expected_pairs:
        raise RetroBotInputError("paper policy/clock pair set is incomplete")
    _assert_safe(payload)


def render_paper_markdown(payload: dict, config: RetroBotConfig) -> str:
    validate_paper_aggregate(payload, config)
    lines = ["# RETRO-BOT-002 Paper Backtest Result", "", "Status: descriptive RETRO evidence; synthetic accounting only; no M5 input or verdict.", "", f"Aggregate digest: `{payload['aggregate_sha256']}`.", "", "| Clock | Policy | Eligible | Marked | Mark-censored | Delay-censored | No-tick-censored | Clock-unresolved | Loss | Flat | Gain |", "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for row in payload["policy_clock_rows"]:
        bands = row["return_bands"]
        lines.append(f"| `{row['clock_id']}` | `{row['policy_id']}` | {row['eligible_interval_count']} | {row['emitted_marked_count']} | {row['emitted_mark_censored_count']} | {row['right_censored_delay_not_reached_count']} | {row['right_censored_no_valid_tick_count']} | {row['excluded_clock_unresolved_count']} | {bands['loss']} | {bands['flat']} | {bands['gain']} |")
    lines.extend(["", "Accounting is fixed at quantity 1.0: buys execute at ask and mark at bid; sells execute at bid and mark at ask at the observed re-hedge anchor. No policy or clock is selected, and no profitability or live-execution claim is made."])
    return "\n".join(lines) + "\n"
