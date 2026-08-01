"""Reconcile RETRO-002 original and archived ticks with aggregate-only output."""

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
CASE_ROOT = ROOT / "data" / "raw" / "passview_quarantine" / "retro-002-20260731"
EXPECTED_RUN_ID = "run-20260801T120000"
EXPECTED_MANIFEST_SHA256 = "877fb44fcc60fbdf523c801ec4dbc8cd49368e805b402d5536fa05bba87c8e31"
EXPECTED_OBJECT_HASHES = {
    "report-002.html": "0ff0519ea9a4b72a4805aa227b39c65e942ba9bcbdd881952319372a848a54a0",
    "ticks-original-002.csv": "7ff026ec217fa809b41ca61b55e22a51395d809491ccaea899a0700d879839d9",
    "ticks-archive-002.csv": "ac319c2c17b5b23d395d0e00dd80631b76cf61a9def4473cb06517c09f2bd180",
}
CASE_START = pd.Timestamp("2026-07-31 16:00:00.000")
CASE_END = pd.Timestamp("2026-07-31 17:21:00.000")
SERVER_UTC_OFFSET = pd.Timedelta(hours=3)
PRIVATE_OUTPUT = ROOT / "reports" / "private" / "retro-002" / "retro-002-aggregate.json"


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
        raise ValueError("RETRO-002 aggregate output is not in an ignored path")


def load_verified_sources(run_dir: Path) -> tuple[dict[str, Path], str]:
    expected = CASE_ROOT / EXPECTED_RUN_ID
    if run_dir.resolve() != expected.resolve():
        raise ValueError("RETRO-002 source run is not the pinned accepted run")
    manifest = json.loads((run_dir / "manifests" / "archive-manifest.json").read_text(encoding="utf-8"))
    if manifest["manifest_sha256"] != EXPECTED_MANIFEST_SHA256:
        raise ValueError("RETRO-002 source manifest is not the pinned manifest")
    payload = manifest["payload"]
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != manifest["manifest_sha256"]:
        raise ValueError("RETRO-002 source manifest self-digest does not match")
    objects = {item["alias"]: item for item in payload["objects"]}
    if set(objects) != set(EXPECTED_OBJECT_HASHES) or payload["transfer_status"] != "accepted":
        raise ValueError("RETRO-002 manifest does not contain the accepted source set")
    paths: dict[str, Path] = {}
    for alias, item in objects.items():
        relative_path = item.get("relative_path")
        if not isinstance(relative_path, str) or Path(relative_path).is_absolute():
            raise ValueError(f"RETRO-002 source path is not a relative quarantine path: {alias}")
        path = (expected / relative_path).resolve()
        try:
            path.relative_to(expected.resolve())
        except ValueError as error:
            raise ValueError(f"RETRO-002 source path escapes the pinned run: {alias}") from error
        expected_incoming = (expected / "incoming").resolve()
        if path.parent != expected_incoming or path.name != alias or path.suffix.lower() != Path(alias).suffix.lower():
            raise ValueError(f"RETRO-002 source path or suffix is not pinned for alias: {alias}")
        actual = sha256_file(path)
        if actual != EXPECTED_OBJECT_HASHES[alias] or actual != item["source_sha256"] or actual != item["destination_sha256"]:
            raise ValueError(f"RETRO-002 source hash mismatch: {alias}")
        paths[alias] = path
    return paths, manifest["manifest_sha256"]


def select_target(report_path: Path) -> tuple[pd.Timestamp, pd.Timestamp, float]:
    tables = parse_report(report_path, report_id="retro-002")
    lifecycle, lifecycle_exceptions, _ = merge_lifecycles(tables["positions"], tables["open_positions"])
    events, intervals, state_exceptions = reconstruct_states(lifecycle)
    candidates = intervals[
        (intervals["state"] == "ONE_BUY")
        & (intervals["preceding_event_type"] == "UNLOCK_TO_BUY")
        & (intervals["following_event_type"] == "REHEDGE_SELL")
        & (intervals["start_time"] >= CASE_START)
        & (intervals["end_time"] <= CASE_END)
        & (intervals["duration_seconds"] >= 300)
    ]
    if len(candidates) != 1:
        raise ValueError("RETRO-002 target interval is not uniquely reconstructable")
    target = candidates.iloc[0]
    boundary_events = events[events["event_time"].isin([target["start_time"], target["end_time"]])]
    if boundary_events.empty or (boundary_events["ordering_quality"] != "deterministic").any():
        raise ValueError("RETRO-002 target boundary has ambiguous report-second ordering")
    if not lifecycle_exceptions.empty or not state_exceptions.empty:
        case_exceptions = state_exceptions[
            (state_exceptions.get("event_time", pd.Series(dtype="datetime64[ns]")) >= CASE_START)
            & (state_exceptions.get("event_time", pd.Series(dtype="datetime64[ns]")) <= CASE_END)
        ]
        if not lifecycle_exceptions.empty or not case_exceptions.empty:
            raise ValueError("RETRO-002 report reconstruction has relevant exceptions")
    active_buys = tables["positions"][
        (tables["positions"]["symbol"] == "XAUUSD")
        & (tables["positions"]["side"] == "buy")
        & (tables["positions"]["open_time"] <= target["start_time"])
        & (tables["positions"]["close_time"] >= target["end_time"])
    ]
    if len(active_buys) != 1:
        raise ValueError("RETRO-002 active Buy is not uniquely reconstructable")
    return target["start_time"], target["end_time"], float(active_buys.iloc[0]["open_price"])


def normalize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    frame.columns = [str(column).strip().strip("<>").lower() for column in frame.columns]
    return frame


def tick_chunks(path: Path, source_kind: str):
    if source_kind == "original":
        for chunk in pd.read_csv(path, sep="\t", chunksize=250_000, encoding="utf-8-sig"):
            chunk = normalize_columns(chunk)
            required = {"date", "time", "bid", "ask"}
            if required - set(chunk.columns):
                raise ValueError("Original RETRO-002 tick schema is not recognized")
            chunk["recorded_timestamp"] = pd.to_datetime(
                chunk["date"].astype(str) + " " + chunk["time"].astype(str),
                format="%Y.%m.%d %H:%M:%S.%f",
                errors="raise",
            )
            yield chunk[["recorded_timestamp", "bid", "ask"]]
        return
    for chunk in pd.read_csv(path, chunksize=250_000, encoding="utf-8"):
        chunk = normalize_columns(chunk)
        required = {"time_utc", "bid", "ask"}
        if required - set(chunk.columns):
            raise ValueError("Archived RETRO-002 tick schema is not recognized")
        chunk["recorded_timestamp"] = pd.to_datetime(chunk["time_utc"], utc=True, errors="raise").dt.tz_localize(None)
        yield chunk[["recorded_timestamp", "bid", "ask"]]


def to_server_time(recorded: pd.Series, mapping: str) -> pd.Series:
    if mapping == "registered_utc_plus_3":
        return recorded + SERVER_UTC_OFFSET
    if mapping == "source_clock":
        return recorded
    raise ValueError(f"Unknown RETRO-002 clock mapping: {mapping}")


def band(drawdown: float) -> str:
    if drawdown < 0:
        return "no_below_entry_tick_observed"
    if drawdown < 15:
        return "under_15"
    if drawdown < 20:
        return "15_to_20"
    return "at_least_20"


def summarize_ticks(path: Path, source_kind: str, mapping: str, entry_price: float) -> dict:
    count = duplicate_count = invalid_quote_count = 0
    min_bid: float | None = None
    previous: pd.Timestamp | None = None
    largest_gap = 0.0
    for chunk in tick_chunks(path, source_kind):
        chunk["server_timestamp"] = to_server_time(chunk["recorded_timestamp"], mapping)
        chunk = chunk[(chunk["server_timestamp"] >= CASE_START) & (chunk["server_timestamp"] <= CASE_END)]
        if chunk.empty:
            continue
        chunk["bid"] = pd.to_numeric(chunk["bid"], errors="coerce")
        chunk["ask"] = pd.to_numeric(chunk["ask"], errors="coerce")
        invalid_quote_count += int(
            chunk[["bid", "ask"]].isna().any(axis=1).sum()
            + ((chunk["bid"] <= 0) | (chunk["ask"] <= 0) | (chunk["ask"] < chunk["bid"])).sum()
        )
        valid = chunk.dropna(subset=["bid", "ask"])
        valid = valid[(valid["bid"] > 0) & (valid["ask"] >= valid["bid"])]
        if valid.empty:
            continue
        timestamps = valid["server_timestamp"].tolist()
        if previous is not None:
            gap = (timestamps[0] - previous).total_seconds()
            if gap == 0:
                duplicate_count += 1
            largest_gap = max(largest_gap, gap)
        gaps = valid["server_timestamp"].diff().dt.total_seconds().dropna()
        duplicate_count += int((gaps == 0).sum())
        if not gaps.empty:
            largest_gap = max(largest_gap, float(gaps.max()))
        previous = timestamps[-1]
        count += int(len(valid))
        current_min = float(valid["bid"].min())
        min_bid = current_min if min_bid is None else min(min_bid, current_min)
    if count == 0 or min_bid is None:
        return {
            "coverage": "absent",
            "valid_tick_count": 0,
            "duplicate_timestamp_count": 0,
            "invalid_quote_count": invalid_quote_count,
            "largest_internal_gap_seconds": None,
            "drawdown_band": "unresolved_no_coverage",
        }
    return {
        "coverage": "present",
        "valid_tick_count": count,
        "duplicate_timestamp_count": duplicate_count,
        "invalid_quote_count": invalid_quote_count,
        "largest_internal_gap_seconds": round(largest_gap, 3),
        "drawdown_band": band(entry_price - min_bid),
    }


def build_aggregate(run_dir: Path) -> dict:
    sources, manifest_sha256 = load_verified_sources(run_dir)
    target_start, target_end, entry_price = select_target(sources["report-002.html"])
    metrics = {}
    for alias, source_kind in (("ticks-original-002.csv", "original"), ("ticks-archive-002.csv", "archive")):
        mappings = ("registered_utc_plus_3", "source_clock") if source_kind == "original" else ("registered_utc_plus_3",)
        metrics[alias] = {
            mapping: summarize_ticks(sources[alias], source_kind, mapping, entry_price)
            for mapping in mappings
        }
    registered_original = metrics["ticks-original-002.csv"]["registered_utc_plus_3"]
    registered_archive = metrics["ticks-archive-002.csv"]["registered_utc_plus_3"]
    source_clock_original = metrics["ticks-original-002.csv"]["source_clock"]
    agreement = {
        "registered_mapping_coverage_agreement": (
            registered_original["coverage"] == "present"
            and registered_archive["coverage"] == "present"
        ),
        "registered_mapping_drawdown_band_agreement": (
            registered_original["drawdown_band"] == registered_archive["drawdown_band"]
        ),
        "original_source_clock_diagnostic_present": source_clock_original["coverage"] == "present",
    }
    agreement["verdict"] = (
        "agree"
        if agreement["registered_mapping_coverage_agreement"]
        and agreement["registered_mapping_drawdown_band_agreement"]
        else "conflict"
    )
    aggregate = {
        "schema_version": 1,
        "case_id": "RETRO-002",
        "source_manifest_sha256": manifest_sha256,
        "source_validation": "accepted_hash_verified_triplet",
        "window": "inclusive 2026-07-31 16:00:00.000 through 17:21:00.000 server time",
        "target": {"duration_seconds": int((target_end - target_start).total_seconds())},
        "source_metrics": metrics,
        "source_agreement": agreement,
        "limitations": [
            "Report event times have second-level resolution.",
            "Price summaries are coarse bands, not a trigger reconstruction.",
            "No journal or additional tick source was authorized for RETRO-002.",
        ],
        "m5_firewall": "not_an_M5_input; no fitting, evaluation, threshold change, or gate decision",
    }
    canonical = json.dumps(aggregate, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    aggregate["aggregate_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return aggregate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run", type=Path, required=True)
    args = parser.parse_args()
    require_ignored(PRIVATE_OUTPUT)
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
