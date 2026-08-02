"""RETRO-BOT-003 sequential multi-cycle wrapper over locked paper outcomes."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import pandas as pd

from .retro_bot import (
    EligibleInterval,
    LOCKED_CONFIG_SHA256,
    RetroBotConfig,
    RetroBotInputError,
    _canonical_digest,
    load_config,
)
from .retro_bot_002 import (
    PAPER_STATUSES,
    RETURN_BANDS,
    PaperOutcome,
    paper_backtest_intervals,
)


SEQUENTIAL_CASE_ID = "RETRO-BOT-003"
SEQUENTIAL_SCHEMA_VERSION = 1
SEQUENTIAL_STATUSES = PAPER_STATUSES + ("excluded_overlap", "excluded_invalid_order")
_FORBIDDEN = (
    "price", "timestamp", "path", "ticket", "account_id", "account_number",
    "comment", "interval_id", "report_alias", "cycle_id",
)


@dataclass(frozen=True)
class SequentialOutcome:
    """One policy/clock result retaining only in-memory sequence metadata."""

    cycle_index: int
    policy_id: str
    clock_id: str
    status: str
    action_side: str | None
    net_return: float | None


def _valid_interval_order(intervals: tuple[EligibleInterval, ...]) -> tuple[set[int], set[int]]:
    """Return cycle indexes rejected for overlap and invalid chronology."""
    overlap: set[int] = set()
    invalid: set[int] = set()
    previous: tuple[pd.Timestamp, pd.Timestamp] | None = None
    for index, interval in enumerate(intervals):
        try:
            start = pd.Timestamp(interval.unlock_time_server)
            end = pd.Timestamp(interval.observed_rehedge_time_server)
            if pd.isna(start) or pd.isna(end) or end <= start:
                raise ValueError("invalid interval boundary")
        except (TypeError, ValueError, pd.errors.OutOfBoundsDatetime):
            invalid.add(index)
            previous = None
            continue
        if previous is not None:
            previous_start, previous_end = previous
            if start <= previous_start:
                invalid.add(index)
            if start < previous_end:
                overlap.add(index)
        previous = (start, end)
    return overlap, invalid


def sequential_paper_outcomes(
    intervals: Iterable[EligibleInterval],
    config: RetroBotConfig,
    tick_paths: Iterable,
) -> tuple[SequentialOutcome, ...]:
    """Apply RB-006 independently to chronological cycles, fail-closed on order."""
    locked = load_config()
    if config != locked or config.config_sha256 != LOCKED_CONFIG_SHA256:
        raise RetroBotInputError("sequential config is not locked")
    config = locked
    materialized = tuple(intervals)
    overlap, invalid = _valid_interval_order(materialized)
    base = paper_backtest_intervals(materialized, config, tick_paths)
    return wrap_paper_outcomes(base, materialized, config)


def wrap_paper_outcomes(
    outcomes: Iterable[PaperOutcome],
    intervals: Iterable[EligibleInterval],
    config: RetroBotConfig,
) -> tuple[SequentialOutcome, ...]:
    """Wrap already-computed RB-006 outcomes without re-reading any source."""
    locked = load_config()
    if config != locked or config.config_sha256 != LOCKED_CONFIG_SHA256:
        raise RetroBotInputError("sequential config is not locked")
    config = locked
    materialized = tuple(intervals)
    base = tuple(outcomes)
    expected = len(materialized) * len(config.clocks) * len(config.policies)
    if len(base) != expected:
        raise RetroBotInputError("RB-006 outcome coverage is incomplete")
    overlap, invalid = _valid_interval_order(materialized)
    # RB-006 emits interval-major, clock/policy-minor rows.
    result: list[SequentialOutcome] = []
    cursor = 0
    for index in range(len(materialized)):
        for clock in config.clocks:
            for policy in config.policies:
                item = base[cursor]
                cursor += 1
                if item.policy_id != policy.id or item.clock_id != clock.id or item.status not in PAPER_STATUSES:
                    raise RetroBotInputError("RB-006 outcome identity/status does not match locked coverage")
                if item.status == "emitted_marked" and (
                    item.action_side not in {"buy", "sell"}
                    or item.net_return is None
                    or isinstance(item.net_return, bool)
                    or not isinstance(item.net_return, (int, float))
                    or not math.isfinite(float(item.net_return))
                ):
                    raise RetroBotInputError("RB-006 marked outcome is incomplete")
                if item.status == "emitted_mark_censored" and (item.action_side not in {"buy", "sell"} or item.net_return is not None):
                    raise RetroBotInputError("RB-006 mark-censored outcome is incomplete")
                if item.status not in {"emitted_marked", "emitted_mark_censored"} and (item.action_side is not None or item.net_return is not None):
                    raise RetroBotInputError("RB-006 censored outcome carries action data")
                status = item.status
                side = item.action_side
                net = item.net_return
                if index in invalid:
                    status, side, net = "excluded_invalid_order", None, None
                elif index in overlap:
                    status, side, net = "excluded_overlap", None, None
                result.append(SequentialOutcome(index, policy.id, clock.id, status, side, net))
    return tuple(result)


def _return_band(value: float) -> str:
    return "loss" if value < 0 else "gain" if value > 0 else "flat"


def aggregate_sequential_outcomes(
    outcomes: Iterable[SequentialOutcome],
    config: RetroBotConfig,
    *,
    report_manifest_sha256: str,
    tick_manifest_sha256: str,
) -> dict:
    locked = load_config()
    if config != locked or config.config_sha256 != LOCKED_CONFIG_SHA256:
        raise RetroBotInputError("sequential config is not locked")
    config = locked
    receipt = config.source_receipt
    if (report_manifest_sha256, tick_manifest_sha256) != (
        receipt["report_manifest_sha256"], receipt["tick_manifest_sha256"]
    ):
        raise RetroBotInputError("sequential source manifests are not registered")
    materialized = tuple(outcomes)
    expected_pairs = {(clock.id, policy.id) for clock in config.clocks for policy in config.policies}
    grouped: dict[tuple[str, str], list[SequentialOutcome]] = {pair: [] for pair in expected_pairs}
    for item in materialized:
        pair = (item.clock_id, item.policy_id)
        if pair not in grouped or type(item.cycle_index) is not int or item.cycle_index < 0:
            raise RetroBotInputError("sequential outcome contains an invalid pair or cycle index")
        grouped[pair].append(item)
    if materialized:
        sets = {frozenset(item.cycle_index for item in values) for values in grouped.values()}
        if any(
            len(values) != len({item.cycle_index for item in values})
            or [item.cycle_index for item in values] != sorted(item.cycle_index for item in values)
            or {item.cycle_index for item in values} != set(range(len(values)))
            for values in grouped.values()
        ) or len(sets) != 1:
            raise RetroBotInputError("sequential cycle coverage/order is inconsistent")
    rows = []
    for clock in config.clocks:
        for policy in config.policies:
            selected = grouped[(clock.id, policy.id)]
            if any(item.status not in SEQUENTIAL_STATUSES for item in selected):
                raise RetroBotInputError("sequential outcome contains an unknown status")
            counts = {status: sum(item.status == status for item in selected) for status in SEQUENTIAL_STATUSES}
            bands = {band: 0 for band in RETURN_BANDS}
            for item in selected:
                if item.status == "emitted_marked":
                    if (
                        item.net_return is None
                        or item.action_side not in {"buy", "sell"}
                        or isinstance(item.net_return, bool)
                        or not isinstance(item.net_return, (int, float))
                        or not math.isfinite(float(item.net_return))
                    ):
                        raise RetroBotInputError("marked sequential outcome is incomplete")
                    bands[_return_band(item.net_return)] += 1
                elif item.status == "emitted_mark_censored":
                    if item.net_return is not None or item.action_side not in {"buy", "sell"}:
                        raise RetroBotInputError("mark-censored sequential outcome is incomplete")
                elif item.action_side is not None or item.net_return is not None:
                    raise RetroBotInputError("censored/excluded sequential outcome carries action data")
            rows.append({
                "clock_id": clock.id,
                "policy_id": policy.id,
                "total_cycle_count": len(selected),
                "eligible_cycle_count": sum(counts[s] for s in PAPER_STATUSES),
                "action_count": counts["emitted_marked"] + counts["emitted_mark_censored"],
                "marked_count": counts["emitted_marked"],
                "censored_count": sum(counts[s] for s in PAPER_STATUSES if s != "emitted_marked"),
                "overlap_count": counts["excluded_overlap"],
                "invalid_order_count": counts["excluded_invalid_order"],
                "return_bands": bands,
            })
    payload = {
        "schema_version": SEQUENTIAL_SCHEMA_VERSION,
        "case_id": SEQUENTIAL_CASE_ID,
        "base_config_sha256": config.config_sha256,
        "source_manifest_digests": {
            "report_manifest_sha256": report_manifest_sha256,
            "tick_manifest_sha256": tick_manifest_sha256,
        },
        "policy_clock_rows": rows,
        "aggregate_sha256": "TO_BE_FILLED",
    }
    payload["aggregate_sha256"] = _canonical_digest(payload, "aggregate_sha256")
    validate_sequential_aggregate(payload, config)
    return payload


def _assert_safe(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if any(token in str(key).casefold() for token in _FORBIDDEN):
                raise RetroBotInputError(f"sequential aggregate contains prohibited key: {key}")
            _assert_safe(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_safe(nested)


def validate_sequential_aggregate(payload: dict, config: RetroBotConfig) -> None:
    locked = load_config()
    if config != locked or config.config_sha256 != LOCKED_CONFIG_SHA256:
        raise RetroBotInputError("sequential config is not locked")
    config = locked
    if not isinstance(payload, dict) or payload.get("aggregate_sha256") != _canonical_digest(payload, "aggregate_sha256"):
        raise RetroBotInputError("sequential aggregate digest mismatch")
    if type(payload.get("schema_version")) is not int or payload.get("schema_version") != SEQUENTIAL_SCHEMA_VERSION or payload.get("case_id") != SEQUENTIAL_CASE_ID:
        raise RetroBotInputError("sequential aggregate schema/case mismatch")
    root = {"schema_version", "case_id", "base_config_sha256", "source_manifest_digests", "policy_clock_rows", "aggregate_sha256"}
    if set(payload) != root or payload.get("base_config_sha256") != config.config_sha256:
        raise RetroBotInputError("sequential aggregate root/config mismatch")
    expected_digests = {"report_manifest_sha256": config.source_receipt["report_manifest_sha256"], "tick_manifest_sha256": config.source_receipt["tick_manifest_sha256"]}
    if payload.get("source_manifest_digests") != expected_digests:
        raise RetroBotInputError("sequential source digests are not registered")
    rows = payload.get("policy_clock_rows")
    expected_pairs = {(clock.id, policy.id) for clock in config.clocks for policy in config.policies}
    if not isinstance(rows, list) or len(rows) != len(expected_pairs):
        raise RetroBotInputError("sequential policy/clock rows are incomplete")
    seen = set()
    keys = {"clock_id", "policy_id", "total_cycle_count", "eligible_cycle_count", "action_count", "marked_count", "censored_count", "overlap_count", "invalid_order_count", "return_bands"}
    for row in rows:
        if set(row) != keys:
            raise RetroBotInputError("sequential row schema mismatch")
        pair = (row["clock_id"], row["policy_id"])
        if pair in seen or pair not in expected_pairs:
            raise RetroBotInputError("sequential policy/clock pairs are duplicated or unregistered")
        seen.add(pair)
        counts = [row[key] for key in keys if key.endswith("_count")]
        if any(type(value) is not int or isinstance(value, bool) or value < 0 for value in counts):
            raise RetroBotInputError("sequential count is invalid")
        if row["eligible_cycle_count"] + row["overlap_count"] + row["invalid_order_count"] != row["total_cycle_count"]:
            raise RetroBotInputError("sequential total accounting does not reconcile")
        if row["marked_count"] > row["action_count"] or row["action_count"] > row["eligible_cycle_count"]:
            raise RetroBotInputError("sequential action accounting does not reconcile")
        bands = row["return_bands"]
        if set(bands) != set(RETURN_BANDS) or any(type(value) is not int or isinstance(value, bool) or value < 0 for value in bands.values()) or sum(bands.values()) != row["marked_count"]:
            raise RetroBotInputError("sequential return bands do not reconcile")
    if seen != expected_pairs:
        raise RetroBotInputError("sequential policy/clock pair set is incomplete")
    _assert_safe(payload)


def render_sequential_markdown(payload: dict, config: RetroBotConfig) -> str:
    validate_sequential_aggregate(payload, config)
    lines = [
        "# RETRO-BOT-003 Sequential Multi-Cycle Result", "",
        "Status: descriptive RETRO evidence; synthetic sequential accounting only; no M5 input or verdict.", "",
        f"Aggregate digest: `{payload['aggregate_sha256']}`.", "",
        "| Clock | Policy | Total | Eligible | Action | Marked | Censored | Overlap | Invalid | Loss | Flat | Gain |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["policy_clock_rows"]:
        bands = row["return_bands"]
        lines.append(f"| `{row['clock_id']}` | `{row['policy_id']}` | {row['total_cycle_count']} | {row['eligible_cycle_count']} | {row['action_count']} | {row['marked_count']} | {row['censored_count']} | {row['overlap_count']} | {row['invalid_order_count']} | {bands['loss']} | {bands['flat']} | {bands['gain']} |")
    lines.extend(["", "All locked policies and clocks are reported side by side. Overlapping or invalidly ordered cycles are excluded from action/mark accounting; no policy, clock, profitability, ownership, or live-execution claim is made."])
    return "\n".join(lines) + "\n"


# Descriptive aliases keep the public API discoverable without coupling callers
# to the RETRO-BOT numbering used by the artifact names.
multi_cycle_backtest_intervals = sequential_paper_outcomes
wrap_locked_paper_outcomes = wrap_paper_outcomes
aggregate_multi_cycle_outcomes = aggregate_sequential_outcomes
validate_multi_cycle_aggregate = validate_sequential_aggregate
