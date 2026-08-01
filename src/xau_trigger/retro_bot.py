"""Safe, deterministic inputs for the RETRO-BOT historical replay lane.

This module validates provenance and exposes timestamps only. It never writes
tick rows or sends orders to MetaTrader.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Iterable, Sequence

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "docs" / "retro_bot" / "RETRO-BOT-001-config.json"
LOCKED_CONFIG_SHA256 = "b420d9d014c2cac67461eda9603a200b2a48d0ad1fa0299baaf1c8cdeded5c52"
TICK_ALIAS_RANGE_RE = re.compile(r"XAUUSD_ticks_(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})\.csv$")


class RetroBotInputError(ValueError):
    """Raised when a RETRO-BOT source or configuration fails closed."""


def _canonical_digest(document: dict, digest_field: str) -> str:
    payload = dict(document)
    payload.pop(digest_field, None)
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class Policy:
    id: str
    delay_seconds: int


@dataclass(frozen=True)
class ClockSegment:
    utc_start_inclusive: pd.Timestamp | None
    utc_end_exclusive: pd.Timestamp | None
    offset_hours: int

    def contains(self, timestamp_utc: pd.Timestamp) -> bool:
        if self.utc_start_inclusive is not None and timestamp_utc < self.utc_start_inclusive:
            return False
        if self.utc_end_exclusive is not None and timestamp_utc >= self.utc_end_exclusive:
            return False
        return True


@dataclass(frozen=True)
class ClockMapping:
    status: str
    timestamp_utc: pd.Timestamp | None


@dataclass(frozen=True)
class ClockScenario:
    id: str
    kind: str
    offset_hours: int | None = None
    segments: tuple[ClockSegment, ...] = ()

    @staticmethod
    def _utc(value: pd.Timestamp | str) -> pd.Timestamp:
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        else:
            timestamp = timestamp.tz_convert("UTC")
        return timestamp

    @staticmethod
    def _server_naive(value: pd.Timestamp | str) -> pd.Timestamp:
        timestamp = pd.Timestamp(value)
        if timestamp.tzinfo is not None:
            timestamp = timestamp.tz_convert("UTC").tz_localize(None)
        return timestamp

    def server_from_utc(self, timestamp: pd.Timestamp | str) -> pd.Timestamp:
        timestamp_utc = self._utc(timestamp)
        if self.kind == "fixed":
            if self.offset_hours is None:
                raise RetroBotInputError(f"Clock {self.id} has no fixed offset")
            return (timestamp_utc + pd.Timedelta(hours=self.offset_hours)).tz_localize(None)
        for segment in self.segments:
            if segment.contains(timestamp_utc):
                return (timestamp_utc + pd.Timedelta(hours=segment.offset_hours)).tz_localize(None)
        raise RetroBotInputError(f"UTC timestamp is outside clock segments: {timestamp_utc}")

    def utc_candidates(self, server_timestamp: pd.Timestamp | str) -> tuple[pd.Timestamp, ...]:
        server_naive = self._server_naive(server_timestamp)
        if self.kind == "fixed":
            if self.offset_hours is None:
                raise RetroBotInputError(f"Clock {self.id} has no fixed offset")
            return ((server_naive - pd.Timedelta(hours=self.offset_hours)).tz_localize("UTC"),)
        candidates: list[pd.Timestamp] = []
        for segment in self.segments:
            candidate = (server_naive - pd.Timedelta(hours=segment.offset_hours)).tz_localize("UTC")
            if segment.contains(candidate):
                candidates.append(candidate)
        unique = sorted({candidate.value: candidate for candidate in candidates}.values())
        return tuple(unique)

    def map_server_to_utc(self, server_timestamp: pd.Timestamp | str) -> ClockMapping:
        candidates = self.utc_candidates(server_timestamp)
        if len(candidates) == 1:
            return ClockMapping("unique", candidates[0])
        if not candidates:
            return ClockMapping("nonexistent", None)
        return ClockMapping("ambiguous", None)


@dataclass(frozen=True)
class PopulationWindow:
    start_server: pd.Timestamp
    end_server_exclusive: pd.Timestamp


@dataclass(frozen=True)
class RetroBotConfig:
    case_id: str
    population: PopulationWindow
    policies: tuple[Policy, ...]
    clocks: tuple[ClockScenario, ...]
    source_receipt: dict
    eligibility: dict
    censoring: dict
    lead_time_bands: tuple[dict, ...]
    config_sha256: str


def _parse_clock(raw: dict) -> ClockScenario:
    if raw["kind"] == "fixed":
        return ClockScenario(raw["id"], raw["kind"], offset_hours=int(raw["offset_hours"]))
    segments = []
    for segment in raw["segments"]:
        start = segment["utc_start_inclusive"]
        end = segment["utc_end_exclusive"]
        segments.append(
            ClockSegment(
                None if start is None else ClockScenario._utc(start),
                None if end is None else ClockScenario._utc(end),
                int(segment["offset_hours"]),
            )
        )
    return ClockScenario(raw["id"], raw["kind"], segments=tuple(segments))


def load_config(path: Path = DEFAULT_CONFIG_PATH) -> RetroBotConfig:
    if path.resolve() != DEFAULT_CONFIG_PATH.resolve():
        raise RetroBotInputError("RETRO-BOT config path is not the locked artifact")
    document = json.loads(path.read_text(encoding="utf-8"))
    expected = document.get("config_sha256")
    if expected != LOCKED_CONFIG_SHA256 or _canonical_digest(document, "config_sha256") != expected:
        raise RetroBotInputError("RETRO-BOT config self-digest mismatch")
    population = document["population"]
    policies = tuple(Policy(item["id"], int(item["delay_seconds"])) for item in document["policies"])
    if len({policy.id for policy in policies}) != len(policies):
        raise RetroBotInputError("RETRO-BOT policy ids are not unique")
    clocks = tuple(_parse_clock(item) for item in document["clock_scenarios"])
    if len({clock.id for clock in clocks}) != len(clocks):
        raise RetroBotInputError("RETRO-BOT clock ids are not unique")
    return RetroBotConfig(
        case_id=document["case_id"],
        population=PopulationWindow(
            pd.Timestamp(population["start_server"]),
            pd.Timestamp(population["end_server_exclusive"]),
        ),
        policies=policies,
        clocks=clocks,
        source_receipt=document["source_receipt"],
        eligibility=document["eligibility"],
        censoring=document["censoring"],
        lead_time_bands=tuple(document["lead_time_bands_seconds"]),
        config_sha256=expected,
    )


def _require_under(root: Path, path: Path, label: str) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise RetroBotInputError(f"{label} escapes its permitted root") from error


def _manifest_payload_digest(payload: dict, sort_keys: bool) -> str:
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=sort_keys)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _verify_source_manifest(
    run_dir: Path,
    quarantine_root: Path,
    expected_manifest_sha256: str,
    expected_aliases: Sequence[str],
    *,
    sort_keys: bool,
) -> dict[str, Path]:
    """Verify one accepted quarantine run and return only verified paths."""
    run_dir = run_dir.resolve()
    quarantine_root = quarantine_root.resolve()
    _require_under(quarantine_root, run_dir, "source run")
    manifest_path = run_dir / "manifests" / "archive-manifest.json"
    _require_under(run_dir, manifest_path, "source manifest")
    if not manifest_path.is_file():
        raise RetroBotInputError("source manifest is missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = manifest.get("payload")
    if not isinstance(payload, dict) or payload.get("transfer_status") != "accepted":
        raise RetroBotInputError("source manifest is not accepted")
    if manifest.get("manifest_sha256") != expected_manifest_sha256 or _manifest_payload_digest(payload, sort_keys) != expected_manifest_sha256:
        raise RetroBotInputError("source manifest self-digest mismatch")
    objects = payload.get("objects")
    if not isinstance(objects, list):
        raise RetroBotInputError("source manifest object list is missing")
    expected = set(expected_aliases)
    actual = {item.get("alias") for item in objects}
    if actual != expected or len(objects) != len(expected):
        raise RetroBotInputError("source manifest aliases do not match the registered set")
    verified: dict[str, Path] = {}
    for item in objects:
        alias = item["alias"]
        relative = item.get("relative_path")
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise RetroBotInputError(f"source path is not relative: {alias}")
        path = (run_dir / relative).resolve()
        _require_under(run_dir, path, f"source path {alias}")
        _require_under(quarantine_root, path, f"source path {alias}")
        if path.parent != (run_dir / "incoming").resolve() or path.name != alias:
            raise RetroBotInputError(f"source path is not pinned: {alias}")
        if path.suffix.lower() != Path(alias).suffix.lower() or not path.is_file():
            raise RetroBotInputError(f"source suffix/file is not pinned: {alias}")
        actual_hash = sha256_file(path)
        if actual_hash != item.get("source_sha256") or actual_hash != item.get("destination_sha256"):
            raise RetroBotInputError(f"source hash mismatch: {alias}")
        verified[alias] = path
    return verified


def verify_registered_source_manifest(
    run_dir: Path,
    quarantine_root: Path,
    config: RetroBotConfig,
    role: str,
) -> dict[str, Path]:
    """Verify the exact registered report or tick manifest for a locked run."""
    if config.case_id != "RETRO-BOT-001" or config.config_sha256 != LOCKED_CONFIG_SHA256:
        raise RetroBotInputError("RETRO-BOT config object is not locked")
    # Reload the pinned artifact so a caller cannot substitute mutable nested
    # receipt dictionaries on an otherwise valid-looking config object.
    receipt = load_config().source_receipt
    if role == "reports":
        expected_digest = receipt["report_manifest_sha256"]
        aliases = receipt["report_aliases"]
    elif role == "ticks":
        expected_digest = receipt["tick_manifest_sha256"]
        aliases = receipt["tick_aliases"]
    else:
        raise RetroBotInputError(f"unknown RETRO-BOT source role: {role}")
    sort_keys = bool(receipt["manifest_canonical_sort_keys"][role])
    return _verify_source_manifest(
        run_dir,
        quarantine_root,
        expected_digest,
        aliases,
        sort_keys=sort_keys,
    )


@dataclass(frozen=True)
class TickLookup:
    status: str
    timestamp_utc: pd.Timestamp | None
    valid_tick_count: int


def first_valid_tick(
    paths: Iterable[Path],
    start_utc: pd.Timestamp,
    end_utc_exclusive: pd.Timestamp,
    *,
    chunksize: int = 250_000,
) -> TickLookup:
    """Return the earliest valid tick timestamp in a half-open UTC window."""
    return first_valid_ticks(paths, [start_utc], end_utc_exclusive, chunksize=chunksize)[ClockScenario._utc(start_utc)]


def _path_overlaps_utc_window(path: Path, start_utc: pd.Timestamp, end_utc: pd.Timestamp) -> bool:
    """Skip irrelevant weekly exports from their generated, non-private alias."""
    match = TICK_ALIAS_RANGE_RE.fullmatch(path.name)
    if match is None:
        return True
    source_start = pd.Timestamp(match.group(1), tz="UTC")
    source_end = pd.Timestamp(match.group(2), tz="UTC")
    return source_start < end_utc and start_utc < source_end


def first_valid_ticks(
    paths: Iterable[Path],
    start_times_utc: Iterable[pd.Timestamp],
    end_utc_exclusive: pd.Timestamp,
    *,
    chunksize: int = 250_000,
) -> dict[pd.Timestamp, TickLookup]:
    """Stream each source once and find one first valid tick for each target."""
    starts = tuple(sorted({ClockScenario._utc(value) for value in start_times_utc}))
    end = ClockScenario._utc(end_utc_exclusive)
    if not starts:
        return {}
    earliest: dict[pd.Timestamp, pd.Timestamp | None] = {start: None for start in starts}
    valid_counts = {start: 0 for start in starts}
    active_starts = tuple(start for start in starts if start < end)
    if active_starts:
        earliest_start = active_starts[0]
        for path in paths:
            if not _path_overlaps_utc_window(path, earliest_start, end):
                continue
            for chunk in pd.read_csv(path, usecols=["time_utc", "bid", "ask"], chunksize=chunksize):
                timestamps = pd.to_datetime(chunk["time_utc"], utc=True, errors="coerce")
                bid = pd.to_numeric(chunk["bid"], errors="coerce")
                ask = pd.to_numeric(chunk["ask"], errors="coerce")
                valid = timestamps.notna() & bid.notna() & ask.notna()
                valid &= (bid > 0) & (ask > 0) & (ask >= bid)
                valid &= (timestamps >= earliest_start) & (timestamps < end)
                if not bool(valid.any()):
                    continue
                valid_timestamps = timestamps[valid]
                for start in active_starts:
                    candidates = valid_timestamps[valid_timestamps >= start]
                    if candidates.empty:
                        continue
                    valid_counts[start] += int(len(candidates))
                    candidate = candidates.min()
                    if earliest[start] is None or candidate < earliest[start]:
                        earliest[start] = candidate
    results: dict[pd.Timestamp, TickLookup] = {}
    for start in starts:
        if start >= end:
            results[start] = TickLookup("right_censored_delay_not_reached", None, 0)
        elif earliest[start] is None:
            results[start] = TickLookup("right_censored_no_valid_tick", None, valid_counts[start])
        else:
            results[start] = TickLookup("emitted", earliest[start], valid_counts[start])
    return results


def _legacy_first_valid_tick(
    paths: Iterable[Path],
    start_utc: pd.Timestamp,
    end_utc_exclusive: pd.Timestamp,
    *,
    chunksize: int = 250_000,
) -> TickLookup:
    """Compatibility implementation retained for an auditable one-target path."""
    start = ClockScenario._utc(start_utc)
    end = ClockScenario._utc(end_utc_exclusive)
    if start >= end:
        return TickLookup("right_censored_delay_not_reached", None, 0)
    earliest: pd.Timestamp | None = None
    valid_count = 0
    for path in paths:
        for chunk in pd.read_csv(path, usecols=["time_utc", "bid", "ask"], chunksize=chunksize):
            timestamps = pd.to_datetime(chunk["time_utc"], utc=True, errors="coerce")
            bid = pd.to_numeric(chunk["bid"], errors="coerce")
            ask = pd.to_numeric(chunk["ask"], errors="coerce")
            valid = timestamps.notna() & bid.notna() & ask.notna()
            valid &= (bid > 0) & (ask > 0) & (ask >= bid)
            valid &= (timestamps >= start) & (timestamps < end)
            if not bool(valid.any()):
                continue
            candidates = timestamps[valid]
            valid_count += int(len(candidates))
            candidate = candidates.min()
            if earliest is None or candidate < earliest:
                earliest = candidate
    if earliest is None:
        return TickLookup("right_censored_no_valid_tick", None, valid_count)
    return TickLookup("emitted", earliest, valid_count)


@dataclass(frozen=True)
class EligibleInterval:
    """Minimal, non-financial input for one observed one-sided interval."""

    report_alias: str
    interval_id: int
    state: str
    unlock_time_server: pd.Timestamp
    observed_rehedge_time_server: pd.Timestamp
    duration_seconds: int

    @property
    def action_side(self) -> str:
        return "sell" if self.state == "ONE_BUY" else "buy"


@dataclass(frozen=True)
class ReplayOutcome:
    report_alias: str
    interval_id: int
    policy_id: str
    clock_id: str
    status: str
    action_side: str | None
    lead_seconds: float | None
    valid_tick_count: int


def filter_xauusd_tables(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Return only XAUUSD position snapshots before lifecycle reconstruction."""
    filtered = dict(tables)
    for name in ("positions", "open_positions"):
        table = tables[name]
        if "symbol" not in table.columns:
            raise RetroBotInputError(f"{name} is missing the symbol column")
        filtered[name] = table[table["symbol"].astype(str).str.upper() == "XAUUSD"].copy()
    return filtered


def eligible_intervals(
    report_alias: str,
    lifecycle: pd.DataFrame,
    events: pd.DataFrame,
    intervals: pd.DataFrame,
    lifecycle_exceptions: pd.DataFrame,
    state_exceptions: pd.DataFrame,
    config: RetroBotConfig,
) -> tuple[EligibleInterval, ...]:
    """Apply the predeclared report-level and interval-level eligibility rule."""
    if lifecycle.empty:
        return ()
    if "symbol" not in lifecycle.columns:
        raise RetroBotInputError("eligible interval input is missing the XAUUSD lifecycle")
    symbols = lifecycle["symbol"].astype(str).str.upper()
    if not symbols.eq("XAUUSD").all():
        raise RetroBotInputError("eligible interval input contains a non-XAUUSD lifecycle")
    if not lifecycle_exceptions.empty or intervals.empty:
        return ()
    eligibility = config.eligibility
    required = {"start_time", "end_time", "duration_seconds", "state", "preceding_event_type", "following_event_type", "interval_id"}
    if required - set(intervals.columns):
        raise RetroBotInputError("state intervals do not expose the registered eligibility fields")
    if {"event_time", "ordering_quality", "behavior_type"} - set(events.columns):
        raise RetroBotInputError("state events do not expose deterministic boundary fields")
    exception_times: tuple[pd.Timestamp, ...] = ()
    if not state_exceptions.empty:
        if "event_time" not in state_exceptions.columns:
            raise RetroBotInputError("state exceptions cannot be placed on the timeline")
        exception_times = tuple(pd.Timestamp(value) for value in state_exceptions["event_time"].dropna())
    outputs: list[EligibleInterval] = []
    for _, row in intervals.iterrows():
        start = pd.Timestamp(row["start_time"])
        end = pd.Timestamp(row["end_time"])
        state = str(row["state"])
        if pd.isna(start) or pd.isna(end) or not (config.population.start_server <= start < end <= config.population.end_server_exclusive):
            continue
        actual_duration = float((end - start).total_seconds())
        reported_duration = float(row["duration_seconds"])
        if abs(actual_duration - reported_duration) > 1e-6:
            continue
        if state not in eligibility["states"] or actual_duration < int(eligibility["minimum_duration_seconds"]):
            continue
        expected_before = eligibility["preceding_event_by_state"][state]
        expected_after = eligibility["following_event_by_state"][state]
        if row["preceding_event_type"] != expected_before:
            continue
        if row["following_event_type"] != expected_after:
            continue
        boundary = events[events["event_time"].isin([start, end])]
        if len(boundary) != 2 or (boundary["ordering_quality"] != "deterministic").any():
            continue
        start_events = boundary[boundary["event_time"] == start]
        end_events = boundary[boundary["event_time"] == end]
        if len(start_events) != 1 or len(end_events) != 1:
            continue
        if start_events.iloc[0]["behavior_type"] != expected_before or end_events.iloc[0]["behavior_type"] != expected_after:
            continue
        if any(start <= exception_time <= end for exception_time in exception_times):
            continue
        outputs.append(
            EligibleInterval(
                report_alias=report_alias,
                interval_id=int(row["interval_id"]),
                state=state,
                unlock_time_server=start,
                observed_rehedge_time_server=end,
                duration_seconds=int(actual_duration),
            )
        )
    return tuple(outputs)


def replay_rehedge_policy(
    interval: EligibleInterval,
    policy: Policy,
    clock: ClockScenario,
    config: RetroBotConfig,
    tick_paths: Iterable[Path],
) -> ReplayOutcome:
    """Replay one fixed-delay policy without allowing an action after re-hedge."""
    return replay_rehedge_policies(interval, (policy,), clock, config, tick_paths)[0]


def replay_rehedge_policies(
    interval: EligibleInterval,
    policies: Sequence[Policy],
    clock: ClockScenario,
    config: RetroBotConfig,
    tick_paths: Iterable[Path],
) -> tuple[ReplayOutcome, ...]:
    """Replay all registered policies for one interval with one tick pass."""
    locked_config = load_config()
    registered_policies = {item.id: item for item in locked_config.policies}
    registered_clocks = {item.id: item for item in locked_config.clocks}
    for policy in policies:
        if config.config_sha256 != LOCKED_CONFIG_SHA256 or policy.id not in registered_policies or policy != registered_policies[policy.id]:
            raise RetroBotInputError("replay policy is not one of the locked RETRO-BOT policies")
    if clock.id not in registered_clocks or clock != registered_clocks[clock.id]:
        raise RetroBotInputError("replay clock is not one of the locked RETRO-BOT scenarios")
    end_mapping = clock.map_server_to_utc(interval.observed_rehedge_time_server)
    unlock_mapping = clock.map_server_to_utc(interval.unlock_time_server)
    base = {"report_alias": interval.report_alias, "interval_id": interval.interval_id, "clock_id": clock.id}
    if end_mapping.status != "unique" or unlock_mapping.status != "unique":
        return tuple(
            ReplayOutcome(**base, policy_id=policy.id, status="excluded_clock_unresolved", action_side=None, lead_seconds=None, valid_tick_count=0)
            for policy in policies
        )
    rehedge_utc = end_mapping.timestamp_utc
    outcomes: list[ReplayOutcome | None] = []
    pending: list[tuple[Policy, pd.Timestamp]] = []
    for policy in policies:
        target_server = interval.unlock_time_server + pd.Timedelta(seconds=policy.delay_seconds)
        if target_server >= interval.observed_rehedge_time_server:
            outcomes.append(ReplayOutcome(**base, policy_id=policy.id, status="right_censored_delay_not_reached", action_side=None, lead_seconds=None, valid_tick_count=0))
            continue
        target_mapping = clock.map_server_to_utc(target_server)
        if target_mapping.status != "unique" or target_mapping.timestamp_utc is None or rehedge_utc is None or target_mapping.timestamp_utc >= rehedge_utc:
            outcomes.append(ReplayOutcome(**base, policy_id=policy.id, status="excluded_clock_unresolved", action_side=None, lead_seconds=None, valid_tick_count=0))
            continue
        outcomes.append(None)
        pending.append((policy, target_mapping.timestamp_utc))
    lookups = first_valid_ticks(tick_paths, [target for _, target in pending], rehedge_utc) if pending and rehedge_utc is not None else {}
    pending_index = 0
    for index, outcome in enumerate(outcomes):
        if outcome is not None:
            continue
        policy, target_utc = pending[pending_index]
        pending_index += 1
        lookup = lookups[target_utc]
        if lookup.status != "emitted" or lookup.timestamp_utc is None:
            outcomes[index] = ReplayOutcome(**base, policy_id=policy.id, status=lookup.status, action_side=None, lead_seconds=None, valid_tick_count=lookup.valid_tick_count)
            continue
        lead_seconds = float((rehedge_utc - lookup.timestamp_utc).total_seconds())
        if lead_seconds <= 0:
            raise RetroBotInputError("half-open tick accessor emitted an action at or after re-hedge")
        outcomes[index] = ReplayOutcome(**base, policy_id=policy.id, status="emitted", action_side=interval.action_side, lead_seconds=lead_seconds, valid_tick_count=lookup.valid_tick_count)
    return tuple(outcome for outcome in outcomes if outcome is not None)


def lead_time_band(lead_seconds: float, config: RetroBotConfig) -> str:
    if lead_seconds < 0:
        raise RetroBotInputError("lead time cannot be negative")
    for band in config.lead_time_bands:
        maximum = band["maximum_exclusive"]
        if lead_seconds >= float(band["minimum_inclusive"]) and (maximum is None or lead_seconds < float(maximum)):
            return str(band["id"])
    raise RetroBotInputError("lead time does not fit the registered bands")


AGGREGATE_SCHEMA_VERSION = 1
_FORBIDDEN_AGGREGATE_KEY_PARTS = ("price", "ticket", "account", "comment", "path", "timestamp", "interval_id", "report_alias")


def _assert_aggregate_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            lowered = str(key).casefold()
            if any(part in lowered for part in _FORBIDDEN_AGGREGATE_KEY_PARTS):
                raise RetroBotInputError(f"aggregate contains a prohibited key: {key}")
            _assert_aggregate_keys(nested)
    elif isinstance(value, list):
        for nested in value:
            _assert_aggregate_keys(nested)


def aggregate_outcomes(
    outcomes: Iterable[ReplayOutcome],
    config: RetroBotConfig,
    *,
    report_manifest_sha256: str,
    tick_manifest_sha256: str,
) -> dict:
    """Reduce interval-level replay outcomes to a redacted canonical payload."""
    if config.config_sha256 != LOCKED_CONFIG_SHA256:
        raise RetroBotInputError("aggregate config is not locked")
    config = load_config()
    rows = []
    materialized = tuple(outcomes)
    expected_statuses = {
        "emitted",
        "right_censored_delay_not_reached",
        "right_censored_no_valid_tick",
        "excluded_clock_unresolved",
    }
    policy_order = {policy.id: index for index, policy in enumerate(config.policies)}
    clock_order = {clock.id: index for index, clock in enumerate(config.clocks)}
    expected_pairs = {(clock.id, policy.id) for clock in config.clocks for policy in config.policies}
    pair_keys: dict[tuple[str, str], set[tuple[str, int]]] = {pair: set() for pair in expected_pairs}
    for item in materialized:
        pair = (item.clock_id, item.policy_id)
        if pair not in expected_pairs:
            raise RetroBotInputError("aggregate contains an unregistered policy/clock pair")
        key = (item.report_alias, item.interval_id)
        if key in pair_keys[pair]:
            raise RetroBotInputError("aggregate contains a duplicate interval outcome")
        pair_keys[pair].add(key)
    if materialized:
        if any(not pair_keys[pair] for pair in expected_pairs):
            raise RetroBotInputError("aggregate is missing a policy/clock coverage set")
        coverage_sets = {frozenset(keys) for keys in pair_keys.values()}
        if len(coverage_sets) != 1:
            raise RetroBotInputError("aggregate policy/clock coverage sets do not match")
    for clock in config.clocks:
        for policy in config.policies:
            selected = tuple(item for item in materialized if item.clock_id == clock.id and item.policy_id == policy.id)
            if any(item.status not in expected_statuses for item in selected):
                raise RetroBotInputError("aggregate contains an unknown replay status")
            counts = {status: sum(item.status == status for item in selected) for status in expected_statuses}
            bands = {band["id"]: 0 for band in config.lead_time_bands}
            for item in selected:
                if item.status == "emitted":
                    if item.lead_seconds is None or item.action_side not in {"buy", "sell"}:
                        raise RetroBotInputError("emitted aggregate row is incomplete")
                    bands[lead_time_band(item.lead_seconds, config)] += 1
            rows.append(
                {
                    "clock_id": clock.id,
                    "policy_id": policy.id,
                    "eligible_interval_count": len(selected),
                    "emitted_count": counts["emitted"],
                    "right_censored_delay_not_reached_count": counts["right_censored_delay_not_reached"],
                    "right_censored_no_valid_tick_count": counts["right_censored_no_valid_tick"],
                    "excluded_clock_unresolved_count": counts["excluded_clock_unresolved"],
                    "direction_match_count": counts["emitted"],
                    "lead_time_bands": bands,
                }
            )
    rows.sort(key=lambda row: (clock_order[row["clock_id"]], policy_order[row["policy_id"]]))
    payload = {
        "schema_version": AGGREGATE_SCHEMA_VERSION,
        "case_id": config.case_id,
        "config_sha256": config.config_sha256,
        "source_manifest_digests": {
            "report_manifest_sha256": report_manifest_sha256,
            "tick_manifest_sha256": tick_manifest_sha256,
        },
        "policy_clock_rows": rows,
        "aggregate_sha256": "TO_BE_FILLED",
    }
    payload["aggregate_sha256"] = _canonical_digest(payload, "aggregate_sha256")
    validate_aggregate_payload(payload, config)
    return payload


def validate_aggregate_payload(payload: dict, config: RetroBotConfig) -> None:
    """Fail closed if an aggregate is tampered with or contains raw-like fields."""
    if not isinstance(payload, dict):
        raise RetroBotInputError("aggregate payload is not an object")
    if config.config_sha256 != LOCKED_CONFIG_SHA256:
        raise RetroBotInputError("aggregate config object is not locked")
    config = load_config()
    expected_digest = payload.get("aggregate_sha256")
    if not isinstance(expected_digest, str) or _canonical_digest(payload, "aggregate_sha256") != expected_digest:
        raise RetroBotInputError("aggregate self-digest mismatch")
    if type(payload.get("schema_version")) is not int or payload.get("schema_version") != AGGREGATE_SCHEMA_VERSION or payload.get("case_id") != config.case_id:
        raise RetroBotInputError("aggregate schema/case is not pinned")
    root_keys = {
        "schema_version",
        "case_id",
        "config_sha256",
        "source_manifest_digests",
        "policy_clock_rows",
        "aggregate_sha256",
    }
    if set(payload) != root_keys:
        raise RetroBotInputError("aggregate root schema contains unknown fields")
    if payload.get("config_sha256") != LOCKED_CONFIG_SHA256:
        raise RetroBotInputError("aggregate config digest is not locked")
    digests = payload.get("source_manifest_digests")
    receipt = config.source_receipt
    if not isinstance(digests, dict) or set(digests) != {"report_manifest_sha256", "tick_manifest_sha256"} or digests != {
        "report_manifest_sha256": receipt["report_manifest_sha256"],
        "tick_manifest_sha256": receipt["tick_manifest_sha256"],
    }:
        raise RetroBotInputError("aggregate source digests are not registered")
    rows = payload.get("policy_clock_rows")
    if not isinstance(rows, list):
        raise RetroBotInputError("aggregate policy/clock rows are not a list")
    expected_pairs = {(clock.id, policy.id) for clock in config.clocks for policy in config.policies}
    if any(not isinstance(row, dict) for row in rows):
        raise RetroBotInputError("aggregate policy/clock row is not an object")
    actual_pairs = {(row.get("clock_id"), row.get("policy_id")) for row in rows}
    if actual_pairs != expected_pairs or len(rows or []) != len(expected_pairs):
        raise RetroBotInputError("aggregate policy/clock row set is not pinned")
    band_ids = {band["id"] for band in config.lead_time_bands}
    for row in rows:
        row_keys = {
            "clock_id",
            "policy_id",
            "eligible_interval_count",
            "emitted_count",
            "right_censored_delay_not_reached_count",
            "right_censored_no_valid_tick_count",
            "excluded_clock_unresolved_count",
            "direction_match_count",
            "lead_time_bands",
        }
        if set(row) != row_keys or not isinstance(row["clock_id"], str) or not isinstance(row["policy_id"], str):
            raise RetroBotInputError("aggregate row schema contains unknown or invalid fields")
        count_fields = (
            "eligible_interval_count",
            "emitted_count",
            "right_censored_delay_not_reached_count",
            "right_censored_no_valid_tick_count",
            "excluded_clock_unresolved_count",
            "direction_match_count",
        )
        if any(type(row.get(field)) is not int or row[field] < 0 for field in count_fields):
            raise RetroBotInputError("aggregate count is invalid")
        if sum(row[field] for field in count_fields[1:5]) != row["eligible_interval_count"]:
            raise RetroBotInputError("aggregate status counts do not reconcile")
        if row["direction_match_count"] != row["emitted_count"]:
            raise RetroBotInputError("aggregate direction invariant failed")
        bands = row.get("lead_time_bands")
        if not isinstance(bands, dict) or set(bands) != band_ids or any(type(value) is not int or value < 0 for value in bands.values()) or sum(bands.values()) != row["emitted_count"]:
            raise RetroBotInputError("aggregate lead-time bands do not reconcile")
    _assert_aggregate_keys(payload)


def render_aggregate_markdown(payload: dict, config: RetroBotConfig) -> str:
    """Render only redacted aggregate facts; never include interval details."""
    validate_aggregate_payload(payload, config)
    lines = [
        "# RETRO-BOT-001 Aggregate Replay Result",
        "",
        "Status: descriptive RETRO evidence; no M5 input or verdict.",
        "",
        f"Aggregate digest: `{payload['aggregate_sha256']}`.",
        "",
        "All registered policies and clock scenarios are reported side by side; "
        "no policy or clock is selected as a winner.",
        "",
        "| Clock | Policy | Eligible | Emitted | Delay-censored | No-tick-censored | Clock-unresolved |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in payload["policy_clock_rows"]:
        lines.append(
            f"| `{row['clock_id']}` | `{row['policy_id']}` | {row['eligible_interval_count']} | "
            f"{row['emitted_count']} | {row['right_censored_delay_not_reached_count']} | "
            f"{row['right_censored_no_valid_tick_count']} | {row['excluded_clock_unresolved_count']} |"
        )
    lines.extend(
        [
            "",
            "Observed outputs are compatible with the registered surrogate policies only; "
            "they do not identify the original trigger, manual intervention, profitability, "
            "broker ownership, or a tradeable edge.",
        ]
    )
    return "\n".join(lines) + "\n"
