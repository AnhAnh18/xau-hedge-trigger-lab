"""Run the owner-authorized, aggregate-only RETRO-001 case analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import pandas as pd

from xau_trigger.parsers.mt5_report import parse_report
from xau_trigger.state_reconstruction import merge_lifecycles, reconstruct_states


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_OUTPUT = ROOT / "reports" / "private" / "retro-001" / "retro-001-aggregate.json"
CASE_ROOT = ROOT / "data" / "raw" / "passview_quarantine" / "retro-001-20260731"
EXPECTED_RUN_ID = "run-20260801T090000"
EXPECTED_MANIFEST_SHA256 = "dd913d7b2a0ebfda5444b9a14d97c3959fa3db1fe4c8a8afe4cd937e37b58c74"
EXPECTED_OBJECT_HASHES = {
    "report-001.html": "0640f4b54a9fe7d40a03ae467eff600a2c675bfbb427fc4fe64373cb51f912f9",
    "ticks-001.csv": "ac319c2c17b5b23d395d0e00dd80631b76cf61a9def4473cb06517c09f2bd180",
}
CASE_START = pd.Timestamp("2026-07-31 16:00:00")
CASE_END = pd.Timestamp("2026-07-31 17:21:00")
SERVER_UTC_OFFSET = pd.Timedelta(hours=3)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_verified_sources(run_dir: Path) -> tuple[Path, Path, str]:
    expected_run_dir = CASE_ROOT / EXPECTED_RUN_ID
    if run_dir.resolve() != expected_run_dir.resolve():
        raise ValueError("RETRO source run is not the pinned RETRO-001 run")
    manifest_path = run_dir / "manifests" / "archive-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload = manifest["payload"]
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    if manifest["manifest_sha256"] != EXPECTED_MANIFEST_SHA256:
        raise ValueError("RETRO source manifest is not the pinned RETRO-001 manifest")
    if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != manifest["manifest_sha256"]:
        raise ValueError("RETRO source manifest self-digest does not match")

    expected = {"report-001.html", "ticks-001.csv"}
    objects = {item["alias"]: item for item in payload["objects"]}
    if set(objects) != expected or payload["transfer_status"] != "accepted":
        raise ValueError("RETRO source manifest does not contain the accepted case pair")
    paths: dict[str, Path] = {}
    for alias, item in objects.items():
        if item["source_sha256"] != EXPECTED_OBJECT_HASHES[alias]:
            raise ValueError(f"RETRO source object hash is not pinned: {alias}")
        path = run_dir / item["relative_path"]
        actual = sha256_file(path)
        if actual != item["source_sha256"] or actual != item["destination_sha256"]:
            raise ValueError(f"RETRO source hash mismatch: {alias}")
        paths[alias] = path
    return paths["report-001.html"], paths["ticks-001.csv"], manifest["manifest_sha256"]


def _require_ignored(path: Path) -> None:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", str(path.relative_to(ROOT))],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("RETRO aggregate output is not in an ignored path")


def _target_interval(intervals: pd.DataFrame) -> pd.Series:
    candidates = intervals[
        (intervals["state"] == "ONE_BUY")
        & (intervals["preceding_event_type"] == "UNLOCK_TO_BUY")
        & (intervals["following_event_type"] == "REHEDGE_SELL")
        & (intervals["start_time"] >= CASE_START)
        & (intervals["end_time"] <= CASE_END)
        & (intervals["duration_seconds"] >= 300)
    ]
    if len(candidates) != 1:
        raise ValueError("RETRO-001 case interval is not uniquely reconstructable")
    return candidates.iloc[0]


def _read_ticks_utc(path: Path, start_utc: pd.Timestamp, end_utc: pd.Timestamp) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for chunk in pd.read_csv(path, usecols=["time_utc", "bid", "ask"], chunksize=250_000):
        chunk["timestamp"] = pd.to_datetime(chunk["time_utc"], utc=True, errors="raise")
        chunk = chunk[(chunk["timestamp"] >= start_utc) & (chunk["timestamp"] <= end_utc)]
        if not chunk.empty:
            parts.append(chunk[["timestamp", "bid", "ask"]])
    if not parts:
        raise ValueError("No tick coverage inside the registered RETRO-001 interval")
    ticks = pd.concat(parts, ignore_index=True)
    ticks["bid"] = pd.to_numeric(ticks["bid"], errors="raise")
    ticks["ask"] = pd.to_numeric(ticks["ask"], errors="raise")
    if (ticks["ask"] < ticks["bid"]).any() or (ticks[["bid", "ask"]] <= 0).any().any():
        raise ValueError("Invalid tick quote in RETRO-001 interval")
    return ticks


def _read_case_ticks(path: Path, start_server: pd.Timestamp, end_server: pd.Timestamp) -> pd.DataFrame:
    start_utc = (start_server - SERVER_UTC_OFFSET).tz_localize("UTC")
    end_utc = (end_server - SERVER_UTC_OFFSET).tz_localize("UTC")
    return _read_ticks_utc(path, start_utc, end_utc)


def _check_tick_time_alignment(path: Path, positions: pd.DataFrame) -> dict:
    events = positions[
        (positions["symbol"] == "XAUUSD")
        & (positions["open_time"] >= CASE_START)
        & (positions["open_time"] <= CASE_END)
    ][["open_time", "side"]].copy()
    if events.empty:
        raise ValueError("No in-window XAUUSD report entries for tick-time check")

    registered_ticks = _read_case_ticks(path, CASE_START, CASE_END)
    probe = events.copy()
    probe["event_utc"] = (probe["open_time"] - SERVER_UTC_OFFSET).dt.tz_localize("UTC")
    matched = pd.merge_asof(
        probe.sort_values("event_utc"),
        registered_ticks.sort_values("timestamp"),
        left_on="event_utc",
        right_on="timestamp",
        direction="nearest",
        tolerance=pd.Timedelta(seconds=2),
    )
    matched_event_count = int(matched["timestamp"].notna().sum())
    return {
        "utc_plus_3_supported": matched_event_count == len(events),
        "matched_report_entry_count": matched_event_count,
    }


def _same_day_comparator(intervals: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, interval in intervals.iterrows():
        if interval["state"] not in {"ONE_BUY", "ONE_SELL"}:
            continue
        if interval["start_time"].date() != CASE_START.date() or interval["end_time"].date() != CASE_START.date():
            continue
        if interval["state"] == "ONE_BUY":
            expected_before, expected_after = "UNLOCK_TO_BUY", "REHEDGE_SELL"
        else:
            expected_before, expected_after = "UNLOCK_TO_SELL", "REHEDGE_BUY"
        if interval["preceding_event_type"] != expected_before or interval["following_event_type"] != expected_after:
            continue
        next_events = events[events["event_time"] > interval["end_time"]]
        if next_events.empty:
            continue
        next_rotation = next_events.iloc[0]
        if (
            next_rotation["behavior_type"] not in {"UNLOCK_TO_BUY", "UNLOCK_TO_SELL"}
            or next_rotation["event_time"].date() != CASE_START.date()
        ):
            continue
        rows.append(interval)
    return pd.DataFrame(rows, columns=intervals.columns)


def _duration_rank(comparator: pd.DataFrame, target: pd.Series) -> tuple[int, int]:
    buy_only = comparator[comparator["state"] == "ONE_BUY"]
    target_duration = float(target["duration_seconds"])
    rank = 1 + int((buy_only["duration_seconds"] > target_duration).sum())
    return rank, len(buy_only)


def build_aggregate(run_dir: Path) -> dict:
    report_path, tick_path, manifest_sha256 = _load_verified_sources(run_dir)
    tables = parse_report(report_path, report_id="retro-001")
    lifecycle, lifecycle_exceptions, _ = merge_lifecycles(tables["positions"], tables["open_positions"])
    events, intervals, state_exceptions = reconstruct_states(lifecycle)
    target = _target_interval(intervals)
    time_alignment = _check_tick_time_alignment(tick_path, tables["positions"])
    ticks = _read_case_ticks(tick_path, target["start_time"], target["end_time"])
    boundary_events = events[events["event_time"].isin([target["start_time"], target["end_time"]])]
    if boundary_events.empty or (boundary_events["ordering_quality"] != "deterministic").any():
        raise ValueError("RETRO-001 target boundary has ambiguous report-second ordering")
    comparator = _same_day_comparator(intervals, events)

    active_buys = tables["positions"][
        (tables["positions"]["symbol"] == "XAUUSD")
        & (tables["positions"]["side"] == "buy")
        & (tables["positions"]["open_time"] <= target["start_time"])
        & (tables["positions"]["close_time"] >= target["end_time"])
    ]
    if len(active_buys) != 1:
        raise ValueError("RETRO-001 active Buy is not uniquely reconstructable")
    entry_price = float(active_buys.iloc[0]["open_price"])
    drawdown = entry_price - float(ticks["bid"].min())
    duration_rank, duration_count = _duration_rank(comparator, target)

    day_events = events[events["event_time"].dt.date == CASE_START.date()]
    primary_events = day_events[
        (day_events["event_time"] >= CASE_START) & (day_events["event_time"] <= CASE_END)
    ]
    post_target = primary_events[primary_events["event_time"] >= target["end_time"]]
    post_target_unlock = post_target[post_target["behavior_type"] == "UNLOCK_TO_SELL"]
    post_target_rotation = post_target[
        (post_target["behavior_type"] == "REHEDGE_BUY")
        & (post_target["event_time"] > post_target_unlock["event_time"].min())
    ]
    one_leg_day = comparator
    comments = tables["orders"][tables["orders"]["open_time"].dt.date == CASE_START.date()]["comment"]

    case_state_exception_count = len(state_exceptions)
    if not state_exceptions.empty and "event_time" in state_exceptions.columns:
        case_state_exception_count = int(
            (
                (state_exceptions["event_time"] >= CASE_START)
                & (state_exceptions["event_time"] <= CASE_END)
            ).sum()
        )
    if not time_alignment["utc_plus_3_supported"]:
        drawdown_band = "unresolved_time_alignment"
    elif drawdown < 15:
        drawdown_band = "under_15"
    elif drawdown < 20:
        drawdown_band = "15_to_20"
    else:
        drawdown_band = "at_least_20"

    tick_coverage = {"available": False, "status": "unresolved_time_alignment"}
    if time_alignment["utc_plus_3_supported"]:
        gap_seconds = ticks["timestamp"].diff().dt.total_seconds().dropna()
        tick_coverage = {
            "available": True,
            "status": "accepted",
            "tick_count": int(len(ticks)),
            "largest_internal_gap_seconds": round(float(gap_seconds.max()), 3),
        }

    aggregate = {
        "schema_version": 1,
        "case_id": "RETRO-001",
        "source_manifest_sha256": manifest_sha256,
        "source_validation": "accepted_hash_verified_pair",
        "analysis_scope": "2026-07-31 one-leg hedge case; descriptive only",
        "case": {
            "one_buy_interval_reconstructed": True,
            "post_target_rotation_observed": bool(
                not post_target_unlock.empty and not post_target_rotation.empty
            ),
            "one_buy_duration_seconds": int(target["duration_seconds"]),
            "one_buy_duration_rank_among_same_day_buy_only_comparator_intervals": duration_rank,
            "same_day_buy_only_comparator_interval_count": duration_count,
            "rehedge_sell_events_before_interval_end": int(
                ((events["behavior_type"] == "REHEDGE_SELL")
                 & (events["event_time"] > target["start_time"])
                 & (events["event_time"] < target["end_time"])).sum()
            ),
            "drawdown_band": drawdown_band,
            "tick_coverage": tick_coverage,
            "tick_time_alignment": time_alignment,
        },
        "same_day_context": {
            "one_leg_comparator_interval_count": int(len(one_leg_day)),
            "buy_only_comparator_interval_count": int((one_leg_day["state"] == "ONE_BUY").sum()),
            "sell_only_comparator_interval_count": int((one_leg_day["state"] == "ONE_SELL").sum()),
        },
        "manual_intervention": {
            "journal_inspected": False,
            "all_same_day_order_comments_blank": bool(comments.fillna("").str.strip().eq("").all()),
            "verdict": "unresolved",
        },
        "limitations": [
            "MT5 report event times have second-level resolution.",
            "Server timezone is a window-scoped UTC+3 inference.",
            "No journal was authorized or inspected for this pass.",
            "This is a single descriptive case and cannot establish a bot rule or manual intervention.",
        ],
        "m5_firewall": "not_an_M5_input; no fitting, evaluation, or gate decision",
        "reconstruction_exception_counts": {
            "lifecycle": int(len(lifecycle_exceptions)),
            "state": case_state_exception_count,
        },
    }
    canonical = json.dumps(aggregate, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    aggregate["aggregate_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return aggregate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run", type=Path, required=True)
    args = parser.parse_args()

    _require_ignored(PRIVATE_OUTPUT)
    aggregate = build_aggregate(args.source_run)
    PRIVATE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PRIVATE_OUTPUT.write_text(
        json.dumps(aggregate, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps({"case_id": aggregate["case_id"], "aggregate_sha256": aggregate["aggregate_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
