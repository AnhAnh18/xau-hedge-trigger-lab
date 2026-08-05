"""Aggregate-only RH-002 observed lifecycle and tick-adapter run."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from xau_trigger.retro_hist_002 import (
    END_SERVER,
    M5_FIREWALL,
    REPORT_ALIASES,
    REPORT_MANIFEST_SHA256,
    REPORT_RUN_ID,
    START_SERVER,
    STATE_LABELS,
    TICK_ALIASES,
    TICK_MANIFEST_SHA256,
    TICK_RUN_ID,
    deduplicate_positions,
    iter_ticks,
    load_positions,
    reconstruct_observed,
    verify_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "private" / "retro-hist-002" / "lifecycle-aggregate.json"


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def _empty_matrix() -> dict[str, dict[str, int]]:
    return {source: {target: 0 for target in STATE_LABELS} for source in STATE_LABELS}


def _scan_ticks(tick_paths: dict[str, Path]) -> dict[str, int]:
    broad_start = (START_SERVER - pd.Timedelta(hours=3, seconds=60)).tz_localize("UTC")
    broad_end = (END_SERVER - pd.Timedelta(hours=2) + pd.Timedelta(seconds=60)).tz_localize("UTC")
    aggregate = {
        "valid_rows": 0,
        "invalid_rows": 0,
        "duplicate_timestamps": 0,
        "out_of_order": 0,
        "crossed_quotes": 0,
        "envelope_excluded_rows": 0,
        "files_hash_verified": len(tick_paths),
    }
    previous_ns: int | None = None
    for alias in sorted(tick_paths):
        ticks, stats = iter_ticks(tick_paths[alias], broad_start=broad_start, broad_end=broad_end, previous_ns=previous_ns)
        for _ in ticks:
            pass
        for key in ("valid_rows", "invalid_rows", "duplicate_timestamps", "out_of_order", "crossed_quotes", "envelope_excluded_rows"):
            aggregate[key] += stats[key]
        previous_ns = stats["last_time_ns"]
    return aggregate


def _require_ignored(path: Path) -> None:
    result = subprocess.run(["git", "check-ignore", "--no-index", "-q", str(path.relative_to(ROOT))], cwd=ROOT, check=False)
    if result.returncode != 0:
        raise ValueError("RH-002 output path is not ignored")


def run() -> dict[str, object]:
    report_paths = verify_manifest(REPORT_RUN_ID, REPORT_MANIFEST_SHA256, set(REPORT_ALIASES), sort_keys=True, check_objects=True)
    tick_paths = verify_manifest(TICK_RUN_ID, TICK_MANIFEST_SHA256, set(TICK_ALIASES), sort_keys=False, check_objects=True)
    positions, position_stats = load_positions(report_paths)
    observed = reconstruct_observed(positions)
    tick_stats = _scan_ticks(tick_paths)
    policy_states = {label: 0 for label in STATE_LABELS}
    policy_states["FLAT"] = 1
    policy_matrix = _empty_matrix()
    event_coverage = {
        "reports_parsed": position_stats["reports_parsed"],
        "accepted_position_ids": position_stats["accepted_position_ids"],
        "open_events": observed["event_coverage"]["open_events"],
        "close_events": observed["event_coverage"]["close_events"],
        "duplicate_labels": observed["event_coverage"]["duplicate_labels"],
        "collision_timestamps": observed["event_coverage"]["collision_timestamps"],
        "conflicting_position_ids": position_stats["conflicting_position_ids"],
        "invalid_rows": position_stats["invalid_position_rows"],
        "censored_position_ids": position_stats["censored_position_ids"],
    }
    result: dict[str, object] = {
        "schema_version": 1,
        "case_id": "RETRO-HIST-002",
        "source_validation": "accepted_hash_verified_RETRO003_manifest_runs_all_objects",
        "report_manifest_sha256": REPORT_MANIFEST_SHA256,
        "tick_manifest_sha256": TICK_MANIFEST_SHA256,
        "population": {
            "start_server": "2025-11-01 00:00:00",
            "end_server_exclusive": "2026-07-31 00:00:00",
            "report_alias_count": len(REPORT_ALIASES),
            "tick_alias_count": len(TICK_ALIASES),
            "tick_clock_scenarios": ["utc_plus_2", "utc_plus_3"],
        },
        "event_coverage": event_coverage,
        "state_counts": {"oracle": observed["state_counts"], "policy": policy_states},
        "transition_counts": {"oracle": observed["transition_counts"], "policy": policy_matrix},
        "tick_coverage": tick_stats,
        "m5_firewall": M5_FIREWALL,
        "claims": {
            "oracle_labels_used_for_policy": False,
            "policy_actions_emitted": 0,
            "raw_rows_printed": False,
            "pnl_or_model_selection": False,
        },
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
            "accepted_position_ids": result["event_coverage"]["accepted_position_ids"],
            "oracle_open_events": result["event_coverage"]["open_events"],
            "oracle_close_events": result["event_coverage"]["close_events"],
            "valid_tick_rows": result["tick_coverage"]["valid_rows"],
        }, ensure_ascii=True, separators=(",", ":")))
        return 0
    except Exception:
        print("RETRO-HIST-002 analysis rejected", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
