"""Safe, deterministic inputs for the RETRO-BOT historical replay lane.

This module validates provenance and exposes timestamps only. It never writes
tick rows or sends orders to MetaTrader.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "docs" / "retro_bot" / "RETRO-BOT-001-config.json"
LOCKED_CONFIG_SHA256 = "a1fcf30d7d1a8a57ad96bad2b69d92d157c683a179da70bcebb438deb4770c0c"


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
