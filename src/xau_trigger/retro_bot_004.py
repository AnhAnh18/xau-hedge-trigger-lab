"""RETRO-BOT-004 population, fold, bootstrap, and censoring boundary.

This module freezes the data boundary for later autonomous replay. It retains
only aggregate counts and never writes raw rows or private source paths.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd

from .retro_bot import (
    ClockMapping,
    LOCKED_CONFIG_SHA256 as LOCKED_BASE_CONFIG_SHA256,
    RetroBotInputError,
    load_config,
    verify_registered_source_manifest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "docs" / "retro_bot" / "RETRO-BOT-004-config.json"
CASE_ID = "RETRO-BOT-004"
SCHEMA_VERSION = 1
LOCKED_CONFIG_SHA256 = "26fec4baa2b8e2680cc17afaad299bbbb00afba32810865ac60bf28eb2e49ebf"
REPORT_ALIASES = tuple(f"report-{index:03d}.html" for index in range(1, 10))
BOOTSTRAP_IDS = ("left_censored", "fixed_warmup_seed")
CENSOR_CLASSES = (
    "clock_unresolved",
    "invalid_transition",
    "cross_fold_continuation",
    "left_censored_unknown_bootstrap",
    "coverage_censored_no_valid_tick",
    "right_censored_no_terminal",
)
_FORBIDDEN_OUTPUT_PARTS = (
    "timestamp", "price", "ticket", "path", "report_alias", "interval",
    "unit_id", "account", "credential", "comment", "raw",
)


def _canonical_digest(payload: Mapping[str, object], digest_field: str) -> str:
    document = dict(payload)
    document.pop(digest_field, None)
    canonical = json.dumps(document, ensure_ascii=True, separators=(",", ":"), sort_keys=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReportRange:
    alias: str
    start: pd.Timestamp
    end: pd.Timestamp


@dataclass(frozen=True)
class Fold:
    id: str
    role: str
    report_aliases: tuple[str, ...]


@dataclass(frozen=True)
class BootstrapScenario:
    id: str
    seed_state: str | None
    warmup_seconds: int | None
    assumption_dependent: bool


@dataclass(frozen=True)
class PopulationConfig:
    config_sha256: str
    base_config_sha256: str
    report_ranges: tuple[ReportRange, ...]
    folds: tuple[Fold, ...]
    bootstrap_scenarios: tuple[BootstrapScenario, ...]
    censor_precedence: tuple[str, ...]
    min_units_per_fold: int
    min_intervals_per_side: int
    source_manifest_digests: tuple[str, str]


@dataclass(frozen=True)
class WindowRecord:
    """In-memory-only lifecycle summary used to test boundary accounting."""

    report_alias: str
    start_server: pd.Timestamp
    end_server: pd.Timestamp
    side: str
    independent_unit: str
    clock_status: str = "unique"
    invalid_transition: bool = False
    has_terminal: bool = True
    has_valid_tick: bool = True


def _utc_naive(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp


def load_population_config(path: Path = DEFAULT_CONFIG_PATH) -> PopulationConfig:
    if path.resolve() != DEFAULT_CONFIG_PATH.resolve():
        raise RetroBotInputError("RB-008 config path is not the locked artifact")
    document = json.loads(path.read_text(encoding="utf-8"))
    expected = document.get("config_sha256")
    if not isinstance(expected, str) or expected != LOCKED_CONFIG_SHA256 or expected != _canonical_digest(document, "config_sha256"):
        raise RetroBotInputError("RB-008 config self-digest mismatch")
    base = load_config()
    if document.get("base_config_sha256") != LOCKED_BASE_CONFIG_SHA256:
        raise RetroBotInputError("RB-008 base config digest is not locked")
    source = document.get("source_receipt")
    if not isinstance(source, dict):
        raise RetroBotInputError("RB-008 source receipt is missing")
    if source.get("path") != "docs/observational_cases/RETRO-003-2025-11_to_2026-07-history-screening-receipt.md" or source.get("base_config_path") != "docs/retro_bot/RETRO-BOT-001-config.json":
        raise RetroBotInputError("RB-008 source receipt paths are not locked")
    expected_source = (
        base.source_receipt["report_manifest_sha256"],
        base.source_receipt["tick_manifest_sha256"],
    )
    if (
        source.get("report_manifest_sha256"),
        source.get("tick_manifest_sha256"),
    ) != expected_source:
        raise RetroBotInputError("RB-008 source manifests are not registered")
    ranges: list[ReportRange] = []
    for raw in document.get("report_ranges", []):
        if not isinstance(raw, dict) or set(raw) != {"alias", "start", "end"}:
            raise RetroBotInputError("RB-008 report range schema mismatch")
        ranges.append(ReportRange(raw["alias"], _utc_naive(raw["start"]), _utc_naive(raw["end"])))
    if tuple(item.alias for item in ranges) != REPORT_ALIASES:
        raise RetroBotInputError("RB-008 report aliases are not the locked chronological set")
    if any(item.start >= item.end for item in ranges) or any(
        left.end != right.start for left, right in zip(ranges, ranges[1:])
    ):
        raise RetroBotInputError("RB-008 report ranges are not contiguous")
    folds: list[Fold] = []
    seen_aliases: set[str] = set()
    seen_fold_ids: set[str] = set()
    seen_roles: set[str] = set()
    for raw in document.get("folds", []):
        aliases = tuple(raw.get("report_aliases", ()))
        if not raw.get("id") or raw.get("role") not in {"development", "validation", "holdout"}:
            raise RetroBotInputError("RB-008 fold schema mismatch")
        if raw["id"] in seen_fold_ids or raw["role"] in seen_roles:
            raise RetroBotInputError("RB-008 fold ids/roles are not unique")
        if not aliases or len(set(aliases)) != len(aliases) or any(alias not in REPORT_ALIASES for alias in aliases):
            raise RetroBotInputError("RB-008 fold contains an unknown report alias")
        if seen_aliases.intersection(aliases):
            raise RetroBotInputError("RB-008 folds overlap")
        seen_aliases.update(aliases)
        seen_fold_ids.add(raw["id"])
        seen_roles.add(raw["role"])
        folds.append(Fold(raw["id"], raw["role"], aliases))
    if seen_aliases != set(REPORT_ALIASES) or len(folds) != 3:
        raise RetroBotInputError("RB-008 fold coverage is incomplete")
    scenarios: list[BootstrapScenario] = []
    for raw in document.get("bootstrap_scenarios", []):
        scenario = BootstrapScenario(
            raw["id"], raw.get("seed_state"), raw.get("warmup_seconds"), bool(raw["assumption_dependent"])
        )
        if scenario.id not in BOOTSTRAP_IDS or scenario.warmup_seconds is not None and scenario.warmup_seconds < 0:
            raise RetroBotInputError("RB-008 bootstrap scenario is invalid")
        scenarios.append(scenario)
    if tuple(item.id for item in scenarios) != BOOTSTRAP_IDS:
        raise RetroBotInputError("RB-008 bootstrap scenarios are incomplete or reordered")
    if scenarios[0].seed_state is not None or not scenarios[1].assumption_dependent or scenarios[1].seed_state != "HEDGED":
        raise RetroBotInputError("RB-008 bootstrap semantics are not locked")
    support = document.get("minimum_support", {})
    if support.get("independent_units_per_fold") != 2 or support.get("eligible_intervals_per_side") != 2:
        raise RetroBotInputError("RB-008 minimum support is not locked")
    precedence = tuple(document.get("censor_precedence", ()))
    if precedence != CENSOR_CLASSES:
        raise RetroBotInputError("RB-008 censor precedence is not locked")
    return PopulationConfig(
        expected,
        document["base_config_sha256"],
        tuple(ranges),
        tuple(folds),
        tuple(scenarios),
        precedence,
        2,
        2,
        expected_source,
    )


def fold_for_report(report_alias: str, config: PopulationConfig) -> Fold:
    matches = [fold for fold in config.folds if report_alias in fold.report_aliases]
    if len(matches) != 1:
        raise RetroBotInputError("RB-008 report has no unique fold")
    return matches[0]


def verify_rb008_sources(
    reports_run_dir: Path,
    ticks_run_dir: Path,
    quarantine_root: Path,
    config: PopulationConfig,
) -> dict[str, dict[str, Path]]:
    """Verify both registered source manifests before any source is opened."""
    base = load_config()
    return {
        "reports": verify_registered_source_manifest(reports_run_dir, quarantine_root, base, "reports"),
        "ticks": verify_registered_source_manifest(ticks_run_dir, quarantine_root, base, "ticks"),
    }


def map_clock_boundary(clock_id: str, server_timestamp: object) -> ClockMapping:
    """Map one report-second boundary using a locked clock scenario."""
    base = load_config()
    clocks = {clock.id: clock for clock in base.clocks}
    if clock_id not in clocks:
        raise RetroBotInputError("RB-008 clock id is not registered")
    return clocks[clock_id].map_server_to_utc(server_timestamp)


def _fold_bounds(fold: Fold, config: PopulationConfig) -> tuple[pd.Timestamp, pd.Timestamp]:
    ranges = {item.alias: item for item in config.report_ranges}
    return ranges[fold.report_aliases[0]].start, ranges[fold.report_aliases[-1]].end


def classify_window(record: WindowRecord, bootstrap_id: str, config: PopulationConfig) -> tuple[str, str]:
    if bootstrap_id not in BOOTSTRAP_IDS:
        raise RetroBotInputError("RB-008 bootstrap id is not registered")
    fold = fold_for_report(record.report_alias, config)
    report_range = next(item for item in config.report_ranges if item.alias == record.report_alias)
    start, end = _fold_bounds(fold, config)
    if record.end_server <= record.start_server:
        return fold.id, "invalid_transition"
    if record.start_server < report_range.start or record.end_server > report_range.end:
        if report_range.start <= record.start_server < report_range.end and record.end_server > report_range.end:
            return fold.id, "cross_fold_continuation"
        return fold.id, "invalid_transition"
    checks = (
        (record.clock_status != "unique", "clock_unresolved"),
        (record.invalid_transition, "invalid_transition"),
        (record.start_server < start or record.end_server > end, "cross_fold_continuation"),
        (record.side not in {"ONE_BUY", "ONE_SELL"}, "invalid_transition"),
        (bootstrap_id == "left_censored", "left_censored_unknown_bootstrap"),
        (not record.has_valid_tick, "coverage_censored_no_valid_tick"),
        (not record.has_terminal, "right_censored_no_terminal"),
    )
    for condition, status in checks:
        if condition:
            return fold.id, status
    return fold.id, "valid"


def _overlapping_record_indexes(records: tuple[WindowRecord, ...], config: PopulationConfig) -> set[int]:
    """Mark later duplicate/overlapping windows without sorting caller input."""
    rejected: set[int] = set()
    prior_by_fold: dict[str, list[tuple[int, WindowRecord]]] = {}
    seen_keys: set[tuple[str, int, int, str, str]] = set()
    for index, record in enumerate(records):
        fold_id = fold_for_report(record.report_alias, config).id
        key = (
            record.report_alias,
            record.start_server.value,
            record.end_server.value,
            record.side,
            record.independent_unit,
        )
        if key in seen_keys:
            rejected.add(index)
        seen_keys.add(key)
        for _, previous in prior_by_fold.setdefault(fold_id, []):
            if record.start_server < previous.end_server and previous.start_server < record.end_server:
                rejected.add(index)
        prior_by_fold[fold_id].append((index, record))
    return rejected


def build_population_aggregate(
    records: Iterable[WindowRecord],
    config: PopulationConfig,
    *,
    clock_ids: Iterable[str] = ("utc_plus_2", "utc_plus_3", "eu_dst_2025_2026"),
) -> dict:
    materialized = tuple(records)
    clocks = tuple(clock_ids)
    if len(set(clocks)) != len(clocks) or not set(clocks).issubset({"utc_plus_2", "utc_plus_3", "eu_dst_2025_2026"}):
        raise RetroBotInputError("RB-008 clock ids are not registered")
    rejected = _overlapping_record_indexes(materialized, config)
    normalized = tuple(
        replace(record, invalid_transition=True) if index in rejected else record
        for index, record in enumerate(materialized)
    )
    rows: list[dict] = []
    for bootstrap in config.bootstrap_scenarios:
        for clock in clocks:
            for fold in config.folds:
                selected = [record for record in normalized if record.report_alias in fold.report_aliases]
                statuses = [classify_window(record, bootstrap.id, config)[1] for record in selected]
                counts = {status: statuses.count(status) for status in (*CENSOR_CLASSES, "valid")}
                side_counts = {
                    side: sum(status == "valid" and record.side == side for record, status in zip(selected, statuses))
                    for side in ("ONE_BUY", "ONE_SELL")
                }
                units = len({record.independent_unit for record, status in zip(selected, statuses) if status == "valid"})
                sufficient = units >= config.min_units_per_fold and all(
                    side_counts[side] >= config.min_intervals_per_side for side in side_counts
                )
                rows.append({
                    "fold": fold.id,
                    "bootstrap": bootstrap.id,
                    "clock": clock,
                    "total_windows": len(selected),
                    "valid_windows": counts["valid"],
                    "censor_counts": {status: counts[status] for status in CENSOR_CLASSES},
                    "independent_units": units,
                    "valid_by_side": side_counts,
                    "support_status": "sufficient" if sufficient else "insufficient_population",
                })
    payload = {
        "schema_version": SCHEMA_VERSION,
        "case_id": CASE_ID,
        "source_manifest_digests": {
            "report_manifest_sha256": config.source_manifest_digests[0],
            "tick_manifest_sha256": config.source_manifest_digests[1],
        },
        "policy_clock_rows": rows,
        "m5_firewall": "not_an_M5_input; descriptive RETRO only",
        "aggregate_sha256": "TO_BE_FILLED",
    }
    payload["aggregate_sha256"] = _canonical_digest(payload, "aggregate_sha256")
    validate_aggregate(payload, config)
    return payload


def _assert_safe(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).casefold()
            if any(part in lowered for part in _FORBIDDEN_OUTPUT_PARTS):
                raise RetroBotInputError(f"RB-008 aggregate contains prohibited key: {key}")
            _assert_safe(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_safe(nested)
    elif isinstance(value, str):
        lowered = value.casefold()
        if any(token in lowered for token in ("\\", "/", ".csv", ".html", ".xlsx", ".png", ".ex5", "password", "credential", "ticket")):
            raise RetroBotInputError("RB-008 aggregate contains prohibited string content")


def validate_aggregate(payload: dict, config: PopulationConfig) -> None:
    if payload.get("aggregate_sha256") != _canonical_digest(payload, "aggregate_sha256"):
        raise RetroBotInputError("RB-008 aggregate digest mismatch")
    expected_root = {"schema_version", "case_id", "source_manifest_digests", "policy_clock_rows", "m5_firewall", "aggregate_sha256"}
    if set(payload) != expected_root or payload.get("schema_version") != SCHEMA_VERSION or payload.get("case_id") != CASE_ID:
        raise RetroBotInputError("RB-008 aggregate root/schema mismatch")
    expected_digests = {
        "report_manifest_sha256": config.source_manifest_digests[0],
        "tick_manifest_sha256": config.source_manifest_digests[1],
    }
    if payload.get("source_manifest_digests") != expected_digests or payload.get("m5_firewall") != "not_an_M5_input; descriptive RETRO only":
        raise RetroBotInputError("RB-008 aggregate provenance/firewall mismatch")
    rows = payload.get("policy_clock_rows")
    expected_count = len(config.folds) * len(config.bootstrap_scenarios) * 3
    if not isinstance(rows, list) or len(rows) != expected_count:
        raise RetroBotInputError("RB-008 aggregate row coverage is incomplete")
    expected_pairs = {
        (fold.id, bootstrap.id, clock)
        for fold in config.folds
        for bootstrap in config.bootstrap_scenarios
        for clock in ("utc_plus_2", "utc_plus_3", "eu_dst_2025_2026")
    }
    seen_pairs: set[tuple[str, str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise RetroBotInputError("RB-008 aggregate row must be an object")
        required = {"fold", "bootstrap", "clock", "total_windows", "valid_windows", "censor_counts", "independent_units", "valid_by_side", "support_status"}
        pair = (row.get("fold"), row.get("bootstrap"), row.get("clock"))
        if (
            set(row) != required
            or any(not isinstance(value, str) for value in pair)
            or pair not in expected_pairs
            or pair in seen_pairs
        ):
            raise RetroBotInputError("RB-008 aggregate row schema mismatch")
        seen_pairs.add(pair)
        counts = row["censor_counts"]
        side_counts = row["valid_by_side"]
        if not isinstance(counts, dict) or not isinstance(side_counts, dict):
            raise RetroBotInputError("RB-008 aggregate count maps must be objects")
        numeric = [row["total_windows"], row["valid_windows"], row["independent_units"], *side_counts.values(), *counts.values()]
        if any(type(value) is not int or value < 0 for value in numeric):
            raise RetroBotInputError("RB-008 aggregate counts must be nonnegative integers")
        if set(counts) != set(CENSOR_CLASSES) or sum(counts.values()) + row["valid_windows"] != row["total_windows"]:
            raise RetroBotInputError("RB-008 censor conservation failed")
        if (
            set(side_counts) != {"ONE_BUY", "ONE_SELL"}
            or sum(side_counts.values()) != row["valid_windows"]
            or row["support_status"] not in {"sufficient", "insufficient_population"}
        ):
            raise RetroBotInputError("RB-008 support schema mismatch")
    if seen_pairs != expected_pairs:
        raise RetroBotInputError("RB-008 aggregate clock/fold/bootstrap coverage is incomplete")
    _assert_safe(payload)
