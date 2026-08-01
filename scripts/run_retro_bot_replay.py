"""Run the registered RETRO-BOT replay without exposing raw source rows."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from xau_trigger.parsers.mt5_report import parse_report
from xau_trigger.retro_bot import (
    RetroBotInputError,
    aggregate_outcomes,
    eligible_intervals,
    filter_xauusd_tables,
    load_config,
    replay_rehedge_policies,
    verify_registered_source_manifest,
)
from xau_trigger.state_reconstruction import merge_lifecycles, reconstruct_states


ROOT = Path(__file__).resolve().parents[1]
REPLAY_RUN_ROOT = ROOT / "data" / "raw" / "passview_quarantine" / "retro-bot-001" / "replay_runs"


def _require_ignored(path: Path) -> None:
    try:
        relative = path.resolve().relative_to(ROOT.resolve())
    except ValueError as error:
        raise RetroBotInputError("aggregate output is outside the workspace") from error
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", str(relative)],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise RetroBotInputError("aggregate output directory is not ignored")


def _require_under(root: Path, path: Path) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise RetroBotInputError("aggregate output escapes quarantine") from error


def _paths_overlap(left: Path, right: Path) -> bool:
    """Treat either ancestor relationship as source/output overlap."""
    left = left.resolve()
    right = right.resolve()
    try:
        left.relative_to(right)
        return True
    except ValueError:
        try:
            right.relative_to(left)
            return True
        except ValueError:
            return False


def _require_registered_output_run(output_run: Path, report_run: Path, tick_run: Path) -> None:
    """Pin retained aggregates to fresh direct children of the registered root."""
    output_run = output_run.resolve()
    if output_run.parent != REPLAY_RUN_ROOT.resolve():
        raise RetroBotInputError("aggregate output is not a direct child of the registered replay-run directory")
    if _paths_overlap(output_run, report_run) or _paths_overlap(output_run, tick_run):
        raise RetroBotInputError("aggregate output overlaps a verified source run")


def run(args: argparse.Namespace) -> dict:
    config = load_config()
    quarantine_root = args.quarantine_root.resolve()
    report_run = args.report_run_dir.resolve()
    tick_run = args.tick_run_dir.resolve()
    output_run = args.output_run_dir.resolve()
    _require_under(quarantine_root, output_run)
    _require_registered_output_run(output_run, report_run, tick_run)
    _require_ignored(output_run)
    if output_run.exists():
        raise RetroBotInputError("aggregate output run already exists")
    report_paths = verify_registered_source_manifest(report_run, quarantine_root, config, "reports")
    tick_paths = verify_registered_source_manifest(tick_run, quarantine_root, config, "ticks")
    ordered_ticks = [tick_paths[alias] for alias in config.source_receipt["tick_aliases"]]
    outcomes = []
    for report_alias in config.source_receipt["report_aliases"]:
        tables = filter_xauusd_tables(parse_report(report_paths[report_alias], report_id=report_alias))
        lifecycle, lifecycle_exceptions, _ = merge_lifecycles(tables["positions"], tables["open_positions"])
        events, intervals, state_exceptions = reconstruct_states(lifecycle)
        candidates = eligible_intervals(
            report_alias,
            lifecycle,
            events,
            intervals,
            lifecycle_exceptions,
            state_exceptions,
            config,
        )
        for interval in candidates:
            for clock in config.clocks:
                outcomes.extend(replay_rehedge_policies(interval, config.policies, clock, config, ordered_ticks))
    aggregate = aggregate_outcomes(
        outcomes,
        config,
        report_manifest_sha256=config.source_receipt["report_manifest_sha256"],
        tick_manifest_sha256=config.source_receipt["tick_manifest_sha256"],
    )
    output_run.mkdir(parents=True)
    aggregate_path = output_run / "aggregate.json"
    aggregate_path.write_text(json.dumps(aggregate, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return {"case_id": config.case_id, "status": "aggregate_written", "aggregate_sha256": aggregate["aggregate_sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quarantine-root", type=Path, required=True)
    parser.add_argument("--report-run-dir", type=Path, required=True)
    parser.add_argument("--tick-run-dir", type=Path, required=True)
    parser.add_argument("--output-run-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args), ensure_ascii=True, sort_keys=True))
        return 0
    except RetroBotInputError as error:
        print(json.dumps({"status": "failed", "reason": str(error)}, ensure_ascii=True, sort_keys=True))
        return 2
    except Exception:
        # Avoid exposing parser/source details if a private input is malformed.
        print(json.dumps({"status": "failed", "reason": "internal_failure"}, ensure_ascii=True, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
