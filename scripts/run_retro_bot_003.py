"""Run RETRO-BOT-003 sequential accounting from verified RB-001 sources."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from xau_trigger.parsers.mt5_report import parse_report
from xau_trigger.retro_bot import (
    RetroBotInputError,
    eligible_intervals,
    filter_xauusd_tables,
    load_config,
    verify_registered_source_manifest,
)
from xau_trigger.retro_bot_003 import aggregate_sequential_outcomes, sequential_paper_outcomes
from xau_trigger.state_reconstruction import merge_lifecycles, reconstruct_states


ROOT = Path(__file__).resolve().parents[1]
MULTI_CYCLE_RUN_ROOT = ROOT / "data" / "raw" / "passview_quarantine" / "retro-bot-003" / "multi_cycle_runs"


def _under(root: Path, path: Path, label: str) -> None:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as error:
        raise RetroBotInputError(f"{label} escapes quarantine") from error


def _paths_overlap(left: Path, right: Path) -> bool:
    left, right = left.resolve(), right.resolve()
    return left == right or left in right.parents or right in left.parents


def _ignored(path: Path) -> None:
    relative = path.resolve().relative_to(ROOT.resolve())
    if subprocess.run(["git", "check-ignore", "--no-index", "-q", str(relative)], cwd=ROOT, check=False).returncode != 0:
        raise RetroBotInputError("multi-cycle output is not ignored")


def run(args: argparse.Namespace) -> dict:
    config = load_config()
    quarantine = args.quarantine_root.resolve()
    report_run = args.report_run_dir.resolve()
    tick_run = args.tick_run_dir.resolve()
    output_run = args.output_run_dir.resolve()
    _under(quarantine, report_run, "report run")
    _under(quarantine, tick_run, "tick run")
    _under(quarantine, output_run, "multi-cycle output")
    if output_run.parent != MULTI_CYCLE_RUN_ROOT.resolve() or output_run.exists():
        raise RetroBotInputError("multi-cycle output must be a fresh direct child of the registered root")
    _ignored(output_run)
    if _paths_overlap(output_run, report_run) or _paths_overlap(output_run, tick_run):
        raise RetroBotInputError("multi-cycle output overlaps a verified source run")
    reports = verify_registered_source_manifest(report_run, quarantine, config, "reports")
    ticks = verify_registered_source_manifest(tick_run, quarantine, config, "ticks")
    intervals = []
    for alias in config.source_receipt["report_aliases"]:
        tables = filter_xauusd_tables(parse_report(reports[alias], report_id=alias))
        lifecycle, lifecycle_exceptions, _ = merge_lifecycles(tables["positions"], tables["open_positions"])
        events, state_intervals, state_exceptions = reconstruct_states(lifecycle)
        intervals.extend(eligible_intervals(alias, lifecycle, events, state_intervals, lifecycle_exceptions, state_exceptions, config))
    outcomes = sequential_paper_outcomes(intervals, config, [ticks[alias] for alias in config.source_receipt["tick_aliases"]])
    aggregate = aggregate_sequential_outcomes(outcomes, config, report_manifest_sha256=config.source_receipt["report_manifest_sha256"], tick_manifest_sha256=config.source_receipt["tick_manifest_sha256"])
    output_run.mkdir(parents=True)
    (output_run / "aggregate.json").write_text(json.dumps(aggregate, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return {"case_id": aggregate["case_id"], "status": "aggregate_written", "aggregate_sha256": aggregate["aggregate_sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quarantine-root", type=Path, required=True)
    parser.add_argument("--report-run-dir", type=Path, required=True)
    parser.add_argument("--tick-run-dir", type=Path, required=True)
    parser.add_argument("--output-run-dir", type=Path, required=True)
    try:
        print(json.dumps(run(parser.parse_args()), ensure_ascii=True, sort_keys=True))
        return 0
    except RetroBotInputError as error:
        print(json.dumps({"status": "failed", "reason": str(error)}, ensure_ascii=True, sort_keys=True))
        return 2
    except Exception:
        print(json.dumps({"status": "failed", "reason": "internal_failure"}, ensure_ascii=True, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
