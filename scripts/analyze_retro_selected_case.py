"""Analyze one pinned RETRO-004..006 case with aggregate-only output."""

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
QUARANTINE_ROOT = ROOT / "data" / "raw" / "passview_quarantine"
REPORT_RUN = QUARANTINE_ROOT / "retro-003-history-screening-20260801" / "run-20260801T160000"
TICK_RUN = QUARANTINE_ROOT / "mt5-ticks-20260801" / "run-20260801T061208"
REPORT_MANIFEST_SHA256 = "88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30"
TICK_MANIFEST_SHA256 = "a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c"

CASE_CONFIGS = {
    "RETRO-004": {
        "report_alias": "report-001.html",
        "report_hash": "7463483d5ed31e2a8b0d619a340dd49b61d4eb84b26f5ba42c48e6b1fbee524d",
        "tick_alias": "XAUUSD_ticks_2025-11-08_to_2025-11-15.csv",
        "tick_hash": "979486ff36d9de63046ecacb6515822d5fa388ddecc0073df6c5025ebd5ed033",
        "start": "2025-11-12 22:24:01",
        "end": "2025-11-12 22:29:30",
        "window_start": "2025-11-12 22:22:01",
        "window_end": "2025-11-12 22:31:30",
        "side": "sell",
    },
    "RETRO-005": {
        "report_alias": "report-005.html",
        "report_hash": "215359dceaf3c00ede520e7612fd8678a4c566b63fb76b78c75ba0310fcde407",
        "tick_alias": "XAUUSD_ticks_2026-02-28_to_2026-03-07.csv",
        "tick_hash": "c81bbeeea8482fc0f2aff03ea0470d597126f9913f34af27ed9699a5a8d5581a",
        "start": "2026-03-03 23:57:47",
        "end": "2026-03-04 01:01:00",
        "window_start": "2026-03-03 23:55:47",
        "window_end": "2026-03-04 01:03:00",
        "side": "buy",
    },
    "RETRO-006": {
        "report_alias": "report-009.html",
        "report_hash": "0640f4b54a9fe7d40a03ae467eff600a2c675bfbb427fc4fe64373cb51f912f9",
        "tick_alias": "XAUUSD_ticks_2026-06-27_to_2026-07-04.csv",
        "tick_hash": "383800055701a106ec759c834238955805e93fac229f7e3fa9b6b9ca96def346",
        "start": "2026-07-01 01:29:55",
        "end": "2026-07-01 01:39:15",
        "window_start": "2026-07-01 01:27:55",
        "window_end": "2026-07-01 01:41:15",
        "side": "buy",
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_ignored(path: Path) -> None:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", str(path.relative_to(ROOT))],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("RETRO selected-case aggregate output is not ignored")


def verify_manifest(run_dir: Path, expected: str, sort_keys: bool) -> dict:
    try:
        run_dir.resolve().relative_to(QUARANTINE_ROOT.resolve())
    except ValueError as error:
        raise ValueError("RETRO selected-case source run escapes quarantine") from error
    manifest = json.loads((run_dir / "manifests" / "archive-manifest.json").read_text(encoding="utf-8"))
    payload = manifest["payload"]
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=sort_keys)
    if manifest.get("manifest_sha256") != expected or hashlib.sha256(canonical.encode("utf-8")).hexdigest() != expected:
        raise ValueError("RETRO selected-case manifest is not pinned")
    if payload.get("transfer_status") != "accepted":
        raise ValueError("RETRO selected-case manifest is not accepted")
    return manifest


def verified_path(run_dir: Path, manifest: dict, alias: str, expected_hash: str) -> Path:
    item_map = {item["alias"]: item for item in manifest["payload"]["objects"]}
    if alias not in item_map or item_map[alias]["source_sha256"] != expected_hash:
        raise ValueError(f"RETRO selected-case source is not pinned: {alias}")
    item = item_map[alias]
    relative = item.get("relative_path")
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError(f"RETRO selected-case source path is not relative: {alias}")
    path = (run_dir / relative).resolve()
    try:
        path.relative_to(run_dir.resolve())
    except ValueError as error:
        raise ValueError(f"RETRO selected-case source path escapes run: {alias}") from error
    if path.parent != (run_dir / "incoming").resolve() or path.name != alias or path.suffix.lower() != Path(alias).suffix.lower():
        raise ValueError(f"RETRO selected-case source path or suffix is not pinned: {alias}")
    actual = sha256_file(path)
    if actual != expected_hash or actual != item["destination_sha256"]:
        raise ValueError(f"RETRO selected-case source hash mismatch: {alias}")
    return path


def band(value: float) -> str:
    if value < 0:
        return "no_adverse_excursion_observed"
    if value < 15:
        return "under_15"
    if value < 20:
        return "15_to_20"
    return "at_least_20"


def tick_metrics(path: Path, config: dict, offset_hours: int, entry_price: float) -> dict:
    window_start = pd.Timestamp(config["window_start"])
    window_end = pd.Timestamp(config["window_end"])
    chunks = []
    invalid = 0
    for chunk in pd.read_csv(path, usecols=["time_utc", "bid", "ask"], chunksize=250_000):
        recorded = pd.to_datetime(chunk["time_utc"], utc=True, errors="raise").dt.tz_localize(None)
        chunk["server_timestamp"] = recorded + pd.Timedelta(hours=offset_hours)
        chunk = chunk[(chunk["server_timestamp"] >= window_start) & (chunk["server_timestamp"] <= window_end)]
        if chunk.empty:
            continue
        chunk["bid"] = pd.to_numeric(chunk["bid"], errors="coerce")
        chunk["ask"] = pd.to_numeric(chunk["ask"], errors="coerce")
        invalid += int(
            chunk[["bid", "ask"]].isna().any(axis=1).sum()
            + ((chunk["bid"] <= 0) | (chunk["ask"] <= 0) | (chunk["ask"] < chunk["bid"])).sum()
        )
        valid = chunk.dropna(subset=["bid", "ask"])
        valid = valid[(valid["bid"] > 0) & (valid["ask"] >= valid["bid"])]
        if not valid.empty:
            chunks.append(valid[["server_timestamp", "bid", "ask"]])
    if not chunks:
        return {"coverage": "absent", "boundary_alignment": False, "invalid_quote_count": invalid, "valid_tick_count": 0, "duplicate_timestamp_count": 0, "largest_internal_gap_seconds": None, "drawdown_band": "unresolved_no_coverage"}
    ticks = pd.concat(chunks, ignore_index=True).sort_values("server_timestamp", kind="stable")
    timestamps = ticks["server_timestamp"]
    gaps = timestamps.diff().dt.total_seconds().dropna()
    duplicate_count = int(timestamps.duplicated(keep=False).sum())
    report_times = [pd.Timestamp(config["start"]), pd.Timestamp(config["end"])]
    aligned = []
    for server_time in report_times:
        delta = (timestamps - server_time).abs().dt.total_seconds()
        aligned.append(bool(not delta.empty and float(delta.min()) <= 2.0))
    if config["side"] == "buy":
        adverse = entry_price - float(ticks["bid"].min())
    else:
        adverse = float(ticks["ask"].max()) - entry_price
    return {
        "coverage": "present",
        "boundary_alignment": bool(all(aligned)),
        "aligned_boundary_count": int(sum(aligned)),
        "invalid_quote_count": invalid,
        "valid_tick_count": int(len(ticks)),
        "duplicate_timestamp_count": duplicate_count,
        "largest_internal_gap_seconds": round(float(gaps.max()), 3) if not gaps.empty else 0.0,
        "drawdown_band": band(adverse),
    }


def build_aggregate(case_id: str) -> dict:
    config = CASE_CONFIGS[case_id]
    report_manifest = verify_manifest(REPORT_RUN, REPORT_MANIFEST_SHA256, True)
    tick_manifest = verify_manifest(TICK_RUN, TICK_MANIFEST_SHA256, False)
    report_path = verified_path(REPORT_RUN, report_manifest, config["report_alias"], config["report_hash"])
    tick_path = verified_path(TICK_RUN, tick_manifest, config["tick_alias"], config["tick_hash"])
    tables = parse_report(report_path, report_id=case_id)
    # Keep only lifecycle rows that can affect the bounded case window before
    # reconstructing state; the parser needs the complete report schema.
    window_start = pd.Timestamp(config["window_start"])
    window_end = pd.Timestamp(config["window_end"])
    positions = tables["positions"]
    tables["positions"] = positions[
        (positions["open_time"] <= window_end)
        & (positions["close_time"].isna() | (positions["close_time"] >= window_start))
    ].copy()
    open_positions = tables["open_positions"]
    tables["open_positions"] = open_positions[open_positions["open_time"] <= window_end].copy()
    tables["orders"] = tables["orders"][(tables["orders"]["open_time"] >= window_start) & (tables["orders"]["open_time"] <= window_end)].copy()
    tables["deals"] = tables["deals"][(tables["deals"]["time"] >= window_start) & (tables["deals"]["time"] <= window_end)].copy()
    lifecycle, lifecycle_exceptions, _ = merge_lifecycles(tables["positions"], tables["open_positions"])
    events, intervals, state_exceptions = reconstruct_states(lifecycle)
    start = pd.Timestamp(config["start"])
    end = pd.Timestamp(config["end"])
    targets = intervals[
        (intervals["start_time"] == start)
        & (intervals["end_time"] == end)
        & (intervals["state"] == ("ONE_BUY" if config["side"] == "buy" else "ONE_SELL"))
    ]
    if len(targets) != 1:
        raise ValueError(f"{case_id} target interval is not uniquely reconstructable")
    target = targets.iloc[0]
    expected_before = "UNLOCK_TO_BUY" if config["side"] == "buy" else "UNLOCK_TO_SELL"
    expected_after = "REHEDGE_SELL" if config["side"] == "buy" else "REHEDGE_BUY"
    if target["preceding_event_type"] != expected_before or target["following_event_type"] != expected_after:
        raise ValueError(f"{case_id} target transition does not match its registered side")
    boundary = events[events["event_time"].isin([start, end])]
    if len(boundary) != 2 or (boundary["ordering_quality"] != "deterministic").any():
        raise ValueError(f"{case_id} target boundary ordering is ambiguous")
    if not lifecycle_exceptions.empty:
        raise ValueError(f"{case_id} has lifecycle exceptions")
    relevant_state_exceptions = state_exceptions[
        (state_exceptions["event_time"] >= start) & (state_exceptions["event_time"] <= end)
    ] if not state_exceptions.empty and "event_time" in state_exceptions.columns else state_exceptions
    if not relevant_state_exceptions.empty:
        raise ValueError(f"{case_id} has relevant state exceptions")
    active = lifecycle[
        (lifecycle["symbol"] == "XAUUSD")
        & (lifecycle["side"] == config["side"])
        & (lifecycle["open_time"] <= start)
        & (lifecycle["close_time"].isna() | (lifecycle["close_time"] >= end))
    ]
    if len(active) != 1:
        raise ValueError(f"{case_id} active one-leg position is not unique")
    entry_price = float(active.iloc[0]["open_price"])
    diagnostics = {f"utc_plus_{offset}": tick_metrics(tick_path, config, offset, entry_price) for offset in (2, 3)}
    supported = [name for name, metrics in diagnostics.items() if metrics["coverage"] == "present" and metrics["boundary_alignment"]]
    if len(supported) == 1:
        clock_status = "unique_supported"
        selected_clock = supported[0]
        drawdown_band = diagnostics[selected_clock]["drawdown_band"]
    elif len(supported) == 0:
        clock_status = "no_supported_mapping"
        selected_clock = None
        drawdown_band = "unresolved_clock_basis"
    else:
        clock_status = "ambiguous_multiple_supported_mappings"
        selected_clock = None
        drawdown_band = "unresolved_clock_basis"
    window_orders = tables["orders"][(tables["orders"]["open_time"] >= window_start) & (tables["orders"]["open_time"] <= window_end)]
    comments = window_orders["comment"].fillna("").astype(str).str.strip()
    continuation = int(
        (
            (events["behavior_type"] == expected_after)
            & (events["event_time"] > start)
            & (events["event_time"] < end)
        ).sum()
    )
    return {
        "schema_version": 1,
        "case_id": case_id,
        "source_validation": "accepted_hash_verified_report_and_tick_objects",
        "report_manifest_sha256": REPORT_MANIFEST_SHA256,
        "tick_manifest_sha256": TICK_MANIFEST_SHA256,
        "registered_window": "inclusive server window with 120-second padding",
        "target": {
            "server_date": start.strftime("%Y-%m-%d"),
            "side": config["side"],
            "duration_seconds": int(target["duration_seconds"]),
            "transition_reconstructed": True,
            "continuation_opposite_rehedge_inside_interval": continuation,
        },
        "clock": {
            "status": clock_status,
            "selected_mapping": selected_clock,
            "diagnostics": diagnostics,
            "price_metric_status": "resolved" if selected_clock else "unresolved_clock_basis",
            "drawdown_band": drawdown_band,
        },
        "order_comment_indicator": {
            "window_order_count": int(len(window_orders)),
            "window_all_blank": bool(comments.eq("").all()),
            "journal_inspected": False,
        },
        "limitations": [
            "Report event times have second-level resolution.",
            "Historical server clock is tested only at UTC+2 and UTC+3; ambiguity remains unresolved when both support the boundaries.",
            "No journal or terminal support source was authorized for this case.",
            "Descriptive only; no trigger, profitability, ownership, or tradeable-edge claim.",
        ],
        "m5_firewall": "not_an_M5_input; no fitting, evaluation, threshold change, or gate decision",
        "raw_rows_printed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-id", choices=sorted(CASE_CONFIGS), required=True)
    args = parser.parse_args()
    output = ROOT / "reports" / "private" / args.case_id.lower()
    aggregate_path = output / f"{args.case_id.lower()}-aggregate.json"
    require_ignored(aggregate_path)
    aggregate = build_aggregate(args.case_id)
    canonical = json.dumps(aggregate, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    aggregate["aggregate_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    output.mkdir(parents=True, exist_ok=True)
    aggregate_path.write_text(json.dumps(aggregate, ensure_ascii=True, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    print(json.dumps({"case_id": args.case_id, "aggregate_sha256": aggregate["aggregate_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
