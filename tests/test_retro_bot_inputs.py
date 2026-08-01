from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

from xau_trigger.retro_bot import (
    RetroBotInputError,
    _verify_source_manifest,
    first_valid_tick,
    load_config,
    sha256_file,
    verify_registered_source_manifest,
)


def _payload_digest(payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _write_manifest(run_dir: Path, alias: str, source_bytes: bytes, relative_path: str = "incoming/tick-001.csv") -> str:
    path = run_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(source_bytes)
    source_hash = sha256_file(path)
    payload = {
        "transfer_status": "accepted",
        "objects": [
            {
                "alias": alias,
                "relative_path": relative_path,
                "source_sha256": source_hash,
                "destination_sha256": source_hash,
            }
        ],
    }
    digest = _payload_digest(payload)
    manifest_path = run_dir / "manifests" / "archive-manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps({"manifest_sha256": digest, "payload": payload}), encoding="utf-8")
    return digest


def test_config_clock_scenarios_handle_dst_inverse_fail_closed() -> None:
    config = load_config()
    clocks = {clock.id: clock for clock in config.clocks}

    assert clocks["utc_plus_2"].server_from_utc("2026-01-01T00:00:00Z") == pd.Timestamp("2026-01-01 02:00:00")
    eu_dst = clocks["eu_dst_2025_2026"]
    assert eu_dst.server_from_utc("2026-03-29T00:59:59Z") == pd.Timestamp("2026-03-29 02:59:59")
    assert eu_dst.server_from_utc("2026-03-29T01:00:00Z") == pd.Timestamp("2026-03-29 04:00:00")
    assert eu_dst.map_server_to_utc("2026-03-29 03:30:00").status == "nonexistent"
    assert eu_dst.map_server_to_utc("2026-10-25 03:30:00").status == "ambiguous"
    mapped = eu_dst.map_server_to_utc("2026-03-29 04:30:00")
    assert mapped.status == "unique"
    assert mapped.timestamp_utc == pd.Timestamp("2026-03-29T01:30:00Z")


def test_config_path_and_public_manifest_roles_are_locked(tmp_path: Path) -> None:
    copied = tmp_path / "config.json"
    copied.write_text("{}", encoding="utf-8")
    with pytest.raises(RetroBotInputError, match="path is not the locked artifact"):
        load_config(copied)
    with pytest.raises(RetroBotInputError, match="unknown RETRO-BOT source role"):
        verify_registered_source_manifest(tmp_path / "run", tmp_path, load_config(), "other")


def test_public_manifest_verifier_ignores_mutated_nested_receipt(tmp_path: Path) -> None:
    quarantine_root = tmp_path / "quarantine"
    run_dir = quarantine_root / "retro-bot-001" / "run-001"
    synthetic_digest = _write_manifest(run_dir, "tick-001.csv", b"synthetic")
    config = load_config()
    # The frozen dataclass intentionally exposes a dict for inspection; public
    # verification must still use the fresh locked artifact, not these values.
    config.source_receipt["report_manifest_sha256"] = synthetic_digest
    config.source_receipt["report_aliases"] = ["tick-001.csv"]
    with pytest.raises(RetroBotInputError, match="self-digest mismatch"):
        verify_registered_source_manifest(run_dir, quarantine_root, config, "reports")


def test_verify_source_manifest_pins_hash_alias_and_quarantine_path(tmp_path: Path) -> None:
    quarantine_root = tmp_path / "quarantine"
    run_dir = quarantine_root / "retro-bot-001" / "run-001"
    digest = _write_manifest(run_dir, "tick-001.csv", b"time_utc,bid,ask\n")

    verified = _verify_source_manifest(
        run_dir,
        quarantine_root,
        digest,
        ["tick-001.csv"],
        sort_keys=True,
    )

    assert list(verified) == ["tick-001.csv"]
    assert verified["tick-001.csv"].parent.name == "incoming"


def test_verify_source_manifest_rejects_path_escape(tmp_path: Path) -> None:
    quarantine_root = tmp_path / "quarantine"
    run_dir = quarantine_root / "retro-bot-001" / "run-001"
    digest = _write_manifest(run_dir, "tick-001.csv", b"x", "../outside.csv")

    with pytest.raises(RetroBotInputError, match="escapes"):
        _verify_source_manifest(run_dir, quarantine_root, digest, ["tick-001.csv"], sort_keys=True)


def test_verify_source_manifest_rejects_hash_tamper_and_partial_alias(tmp_path: Path) -> None:
    quarantine_root = tmp_path / "quarantine"
    run_dir = quarantine_root / "retro-bot-001" / "run-001"
    digest = _write_manifest(run_dir, "tick-001.csv", b"original")
    (run_dir / "incoming" / "tick-001.csv").write_bytes(b"tampered")
    with pytest.raises(RetroBotInputError, match="hash mismatch"):
        _verify_source_manifest(run_dir, quarantine_root, digest, ["tick-001.csv"], sort_keys=True)

    partial_dir = quarantine_root / "retro-bot-001" / "run-002"
    partial_digest = _write_manifest(partial_dir, "tick-001.csv.partial", b"partial", "incoming/tick-001.csv.partial")
    with pytest.raises(RetroBotInputError, match="aliases"):
        _verify_source_manifest(partial_dir, quarantine_root, partial_digest, ["tick-001.csv"], sort_keys=True)


def test_first_valid_tick_streams_half_open_window_without_invalid_quotes(tmp_path: Path) -> None:
    ticks = tmp_path / "ticks.csv"
    ticks.write_text(
        "time_utc,bid,ask\n"
        "2026-01-01T00:00:00Z,0,1\n"
        "2026-01-01T00:00:01Z,1,0.5\n"
        "2026-01-01T00:00:02Z,1,2\n"
        "2026-01-01T00:00:03Z,2,3\n",
        encoding="utf-8",
    )

    emitted = first_valid_tick(
        [ticks],
        pd.Timestamp("2026-01-01T00:00:01Z"),
        pd.Timestamp("2026-01-01T00:00:03Z"),
        chunksize=1,
    )
    assert emitted.status == "emitted"
    assert emitted.timestamp_utc == pd.Timestamp("2026-01-01T00:00:02Z")
    assert emitted.valid_tick_count == 1

    no_tick = first_valid_tick(
        [ticks],
        pd.Timestamp("2026-01-01T00:00:04Z"),
        pd.Timestamp("2026-01-01T00:00:05Z"),
    )
    assert no_tick.status == "right_censored_no_valid_tick"
    assert no_tick.timestamp_utc is None

    delay_censored = first_valid_tick(
        [ticks],
        pd.Timestamp("2026-01-01T00:00:03Z"),
        pd.Timestamp("2026-01-01T00:00:03Z"),
    )
    assert delay_censored.status == "right_censored_delay_not_reached"
