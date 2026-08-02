"""Run RETRO-BOT-002 paper accounting from verified RB-001 sources."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from xau_trigger.parsers.mt5_report import parse_report
from xau_trigger.retro_bot import filter_xauusd_tables, eligible_intervals, load_config, verify_registered_source_manifest
from xau_trigger.state_reconstruction import merge_lifecycles, reconstruct_states
from xau_trigger.retro_bot_002 import aggregate_paper_outcomes, paper_backtest_intervals

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "data" / "raw" / "passview_quarantine" / "retro-bot-002" / "paper_runs"


def _under(root: Path, path: Path) -> None:
    try:
        path.relative_to(root)
    except ValueError as error:
        raise ValueError("path escapes permitted root") from error


def _ignored(path: Path) -> None:
    relative = path.resolve().relative_to(ROOT.resolve())
    if subprocess.run(["git", "check-ignore", "--no-index", "-q", str(relative)], cwd=ROOT, check=False).returncode != 0:
        raise ValueError("paper output is not ignored")


def run(args: argparse.Namespace) -> dict:
    config = load_config()
    quarantine = args.quarantine_root.resolve()
    report_dir = args.report_run_dir.resolve()
    tick_dir = args.tick_run_dir.resolve()
    output = args.output_run_dir.resolve()
    _under(quarantine, report_dir); _under(quarantine, tick_dir); _under(quarantine, output)
    if output.parent != OUTPUT_ROOT.resolve() or output.exists():
        raise ValueError("paper output must be a fresh direct child of the registered ignored root")
    _ignored(output)
    if output == report_dir or output == tick_dir or output in report_dir.parents or output in tick_dir.parents:
        raise ValueError("paper output overlaps a source run")
    reports = verify_registered_source_manifest(report_dir, quarantine, config, "reports")
    ticks = verify_registered_source_manifest(tick_dir, quarantine, config, "ticks")
    candidates = []
    for alias in config.source_receipt["report_aliases"]:
        tables = filter_xauusd_tables(parse_report(reports[alias], report_id=alias))
        lifecycle, lifecycle_exceptions, _ = merge_lifecycles(tables["positions"], tables["open_positions"])
        events, intervals, state_exceptions = reconstruct_states(lifecycle)
        candidates.extend(eligible_intervals(alias, lifecycle, events, intervals, lifecycle_exceptions, state_exceptions, config))
    outcomes = paper_backtest_intervals(candidates, config, [ticks[alias] for alias in config.source_receipt["tick_aliases"]])
    aggregate = aggregate_paper_outcomes(outcomes, config, report_manifest_sha256=config.source_receipt["report_manifest_sha256"], tick_manifest_sha256=config.source_receipt["tick_manifest_sha256"])
    output.mkdir(parents=True)
    (output / "aggregate.json").write_text(json.dumps(aggregate, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    return {"case_id": aggregate["case_id"], "status": "aggregate_written", "aggregate_sha256": aggregate["aggregate_sha256"]}


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
    except Exception:
        print(json.dumps({"status": "failed", "reason": "internal_failure"}, ensure_ascii=True, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
