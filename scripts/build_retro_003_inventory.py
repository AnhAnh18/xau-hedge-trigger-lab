"""Build the aggregate-only RETRO-003 candidate inventory."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import pandas as pd

from xau_trigger.parsers.mt5_report import parse_report
from xau_trigger.state_reconstruction import merge_lifecycles, reconstruct_states


ROOT = Path(__file__).resolve().parents[1]
QUARANTINE_ROOT = ROOT / "data" / "raw" / "passview_quarantine"
REPORT_RUN = QUARANTINE_ROOT / "retro-003-history-screening-20260801" / "run-20260801T160000"
TICK_RUN = QUARANTINE_ROOT / "mt5-ticks-20260801" / "run-20260801T061208"
EXPECTED_REPORT_MANIFEST = "88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30"
EXPECTED_TICK_MANIFEST = "a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c"
OUTPUT = ROOT / "reports" / "private" / "retro-003" / "retro-003-aggregate.json"
START_DATE = date(2025, 11, 1)
END_DATE = date(2026, 7, 30)
DATE_RE = re.compile(r"XAUUSD_ticks_(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})\.csv\Z")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_ignored(path: Path) -> None:
    import subprocess

    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", str(path.relative_to(ROOT))],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("RETRO-003 aggregate output is not in an ignored path")


def verify_run(run_dir: Path, expected_manifest: str, aliases: set[str], sort_keys: bool) -> tuple[dict, dict[str, Path]]:
    try:
        run_dir.resolve().relative_to(QUARANTINE_ROOT.resolve())
    except ValueError as error:
        raise ValueError("RETRO-003 source run escapes quarantine") from error
    manifest_path = run_dir / "manifests" / "archive-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("manifest_sha256") != expected_manifest:
        raise ValueError("RETRO-003 manifest digest is not pinned")
    payload = manifest["payload"]
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=sort_keys)
    if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != expected_manifest:
        raise ValueError("RETRO-003 manifest self-digest mismatch")
    objects = {item["alias"]: item for item in payload["objects"]}
    if set(objects) != aliases or payload.get("transfer_status") != "accepted":
        raise ValueError("RETRO-003 manifest object set is not pinned")
    paths: dict[str, Path] = {}
    for alias, item in objects.items():
        relative = item.get("relative_path")
        if not isinstance(relative, str) or Path(relative).is_absolute():
            raise ValueError(f"RETRO-003 source path is not relative: {alias}")
        path = (run_dir / relative).resolve()
        try:
            path.relative_to(run_dir.resolve())
        except ValueError as error:
            raise ValueError(f"RETRO-003 source path escapes run: {alias}") from error
        if path.parent != (run_dir / "incoming").resolve() or path.name != alias:
            raise ValueError(f"RETRO-003 source path is not pinned: {alias}")
        if path.suffix.lower() != Path(alias).suffix.lower():
            raise ValueError(f"RETRO-003 source suffix is not pinned: {alias}")
        actual = sha256_file(path)
        if actual != item["source_sha256"] or actual != item["destination_sha256"]:
            raise ValueError(f"RETRO-003 source hash mismatch: {alias}")
        paths[alias] = path
    return manifest, paths


def tick_coverage(manifest: dict) -> dict:
    ranges = []
    for item in manifest["payload"]["objects"]:
        match = DATE_RE.fullmatch(item["alias"])
        if not match:
            raise ValueError("RETRO-003 tick alias date range is not recognized")
        start = date.fromisoformat(match.group(1))
        end = date.fromisoformat(match.group(2))
        ranges.append((start, end))
    ranges.sort()
    contiguous = all(left[1] == right[0] for left, right in zip(ranges, ranges[1:]))
    return {
        "object_count": len(ranges),
        "contiguous": contiguous,
        "start_date": ranges[0][0].isoformat(),
        "end_date_exclusive": ranges[-1][1].isoformat(),
        "covers_population": contiguous and ranges[0][0] <= START_DATE and ranges[-1][1] > END_DATE,
    }


def duration_band(seconds: float) -> str:
    if seconds < 900:
        return "300_to_900_seconds"
    if seconds < 3600:
        return "900_to_3600_seconds"
    if seconds < 14400:
        return "3600_to_14400_seconds"
    return "at_least_14400_seconds"


def stratum(day: date) -> str:
    if day <= date(2026, 1, 31):
        return "2025-11_to_2026-01"
    if day <= date(2026, 4, 30):
        return "2026-02_to_2026-04"
    return "2026-05_to_2026-07"


def report_candidates(alias: str, path: Path) -> tuple[list[dict], dict]:
    tables = parse_report(path, report_id=alias)
    lifecycle, lifecycle_exceptions, _ = merge_lifecycles(tables["positions"], tables["open_positions"])
    events, intervals, state_exceptions = reconstruct_states(lifecycle)
    exception_times: list[pd.Timestamp] = []
    if not state_exceptions.empty and "event_time" in state_exceptions.columns:
        for value in state_exceptions["event_time"].dropna():
            exception_times.append(pd.Timestamp(value))
    candidates = []
    if not intervals.empty:
        for _, interval in intervals.iterrows():
            start = pd.Timestamp(interval["start_time"])
            end = pd.Timestamp(interval["end_time"])
            if pd.isna(start) or pd.isna(end):
                continue
            day = start.date()
            if day < START_DATE or day > END_DATE or end.date() > END_DATE:
                continue
            if not lifecycle_exceptions.empty:
                continue
            if interval["state"] not in {"ONE_BUY", "ONE_SELL"} or float(interval["duration_seconds"]) < 300:
                continue
            expected_before = "UNLOCK_TO_BUY" if interval["state"] == "ONE_BUY" else "UNLOCK_TO_SELL"
            expected_after = "REHEDGE_SELL" if interval["state"] == "ONE_BUY" else "REHEDGE_BUY"
            if interval["preceding_event_type"] != expected_before or interval["following_event_type"] != expected_after:
                continue
            boundary = events[events["event_time"].isin([start, end])]
            if len(boundary) != 2 or (boundary["ordering_quality"] != "deterministic").any():
                continue
            if any(start <= exception_time <= end for exception_time in exception_times):
                continue
            candidates.append(
                {
                    "report_alias": alias,
                    "server_date": day.isoformat(),
                    "side": "buy" if interval["state"] == "ONE_BUY" else "sell",
                    "start_time": start.strftime("%Y-%m-%d %H:%M:%S"),
                    "end_time": end.strftime("%Y-%m-%d %H:%M:%S"),
                    "duration_seconds": int(float(interval["duration_seconds"])),
                }
            )
    summary = {
        "candidate_count": len(candidates),
        "lifecycle_exception_count": int(len(lifecycle_exceptions)),
        "state_exception_count": int(len(state_exceptions)),
        "position_rows": int(len(tables["positions"])),
        "order_rows": int(len(tables["orders"])),
        "deal_rows": int(len(tables["deals"])),
    }
    return candidates, summary


def process_report(item: tuple[str, Path]) -> tuple[str, list[dict], dict]:
    alias, path = item
    candidates, summary = report_candidates(alias, path)
    return alias, candidates, summary


def select_cases(candidates: list[dict]) -> tuple[list[dict], dict]:
    by_date: dict[str, list[dict]] = {}
    for candidate in candidates:
        by_date.setdefault(candidate["server_date"], []).append(candidate)
    eligible_dates = []
    for day_text, rows in by_date.items():
        day = date.fromisoformat(day_text)
        best = sorted(rows, key=lambda row: (-row["duration_seconds"], row["start_time"], row["side"]))[0]
        eligible_dates.append((day, best))
    eligible_dates.sort(key=lambda item: item[0])
    selected = []
    for label in ("2025-11_to_2026-01", "2026-02_to_2026-04", "2026-05_to_2026-07"):
        matches = [item for item in eligible_dates if stratum(item[0]) == label]
        if matches:
            day, row = matches[0]
            selected.append({"stratum": label, **row, "duration_band": duration_band(row["duration_seconds"]), "selection_status": "earliest_eligible_date"})
    if len(selected) < 3:
        used = {item["server_date"] for item in selected}
        for day, row in eligible_dates:
            if len(selected) >= 3:
                break
            if row["server_date"] in used:
                continue
            selected.append({"stratum": stratum(day), **row, "duration_band": duration_band(row["duration_seconds"]), "selection_status": "chronological_fallback"})
            used.add(row["server_date"])
    return selected, {"eligible_date_count": len(eligible_dates), "selected_case_count": len(selected)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-run", type=Path, default=REPORT_RUN)
    parser.add_argument("--tick-run", type=Path, default=TICK_RUN)
    args = parser.parse_args()
    if args.report_run.resolve() != REPORT_RUN.resolve() or args.tick_run.resolve() != TICK_RUN.resolve():
        raise ValueError("RETRO-003 source runs are not the pinned accepted runs")
    require_ignored(OUTPUT)
    report_manifest, report_paths = verify_run(args.report_run, EXPECTED_REPORT_MANIFEST, {f"report-{i:03d}.html" for i in range(1, 10)}, True)
    tick_manifest, _ = verify_run(args.tick_run, EXPECTED_TICK_MANIFEST, {item["alias"] for item in json.loads((args.tick_run / "manifests" / "archive-manifest.json").read_text(encoding="utf-8"))["payload"]["objects"]}, False)
    candidates = []
    report_summaries = {}
    work = [(alias, report_paths[alias]) for alias in sorted(report_paths)]
    with ProcessPoolExecutor(max_workers=min(3, len(work))) as executor:
        for alias, rows, summary in executor.map(process_report, work):
            candidates.extend(rows)
            report_summaries[alias] = summary
    selected, selection_summary = select_cases(candidates)
    aggregate = {
        "schema_version": 1,
        "case_id": "RETRO-003",
        "source_validation": "accepted_hash_verified_report_and_tick_manifests",
        "report_manifest_sha256": report_manifest["manifest_sha256"],
        "tick_manifest_sha256": tick_manifest["manifest_sha256"],
        "population": {"start_date": START_DATE.isoformat(), "end_date_inclusive": END_DATE.isoformat(), "excluded_existing_cases": ["2026-07-31"]},
        "clock_policy": "screen_structurally; resolve UTC+2 or UTC+3 per selected case",
        "tick_coverage": tick_coverage(tick_manifest),
        "report_summaries": report_summaries,
        "eligible_date_count": selection_summary["eligible_date_count"],
        "selected_cases": selected,
        "selection_rule": "three fixed month strata; earliest eligible date; longest qualifying interval within date; chronological fallback only",
        "m5_firewall": "not_an_M5_input; no fitting, evaluation, threshold change, or gate decision",
        "raw_rows_printed": False,
    }
    canonical = json.dumps(aggregate, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    aggregate["aggregate_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(aggregate, ensure_ascii=True, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    print(json.dumps({"case_id": aggregate["case_id"], "aggregate_sha256": aggregate["aggregate_sha256"], "selected_case_count": len(selected), "eligible_date_count": aggregate["eligible_date_count"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
