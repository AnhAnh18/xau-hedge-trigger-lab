"""Aggregate-only RH-004 paper-accounting replay over the accepted archive."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from xau_trigger.retro_hist_002 import (
    END_SERVER,
    REPORT_ALIASES,
    REPORT_MANIFEST_SHA256,
    REPORT_RUN_ID,
    START_SERVER,
    TICK_ALIASES,
    TICK_MANIFEST_SHA256,
    TICK_RUN_ID,
    verify_manifest,
)
from xau_trigger.retro_hist_003 import load_positions_retro
from xau_trigger.retro_hist_004 import (
    CASE_ID,
    SCENARIO_IDS,
    account_cycle,
    empty_aggregate,
    finalize_aggregate,
    scenario_matrix,
    result_digest,
    validate_aggregate,
    verify_governance_artifacts,
)
from scripts.analyze_retro_hist_003_trigger import _run_replay


OUTPUT = ROOT / "reports" / "private" / "retro-hist-004" / "accounting-aggregate.json"


def _require_ignored(path: Path) -> None:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", str(path.relative_to(ROOT))],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("RH-004 output path is not ignored")


def run() -> dict[str, object]:
    # Verify the immutable RH-004 contract/receipt before opening any archive object.
    verify_governance_artifacts()
    report_paths = verify_manifest(REPORT_RUN_ID, REPORT_MANIFEST_SHA256, set(REPORT_ALIASES), sort_keys=True, check_objects=True)
    tick_paths = verify_manifest(TICK_RUN_ID, TICK_MANIFEST_SHA256, set(TICK_ALIASES), sort_keys=False, check_objects=True)
    positions, _ = load_positions_retro(report_paths)
    _, policy_replay = _run_replay(tick_paths, positions)
    population = {
        "start_server": str(START_SERVER),
        "end_server_exclusive": str(END_SERVER),
        "report_alias_count": len(REPORT_ALIASES),
        "tick_alias_count": len(TICK_ALIASES),
        "tick_clock_scenarios": ["utc_plus_2", "utc_plus_3"],
    }
    aggregate = empty_aggregate(
        report_manifest_sha256=REPORT_MANIFEST_SHA256,
        tick_manifest_sha256=TICK_MANIFEST_SHA256,
        population=population,
        policy_action_digests=policy_replay["action_digests"],
    )
    aggregate["state_counts"]["FLAT"] = 2
    for scenario in scenario_matrix():
        result = account_cycle(
            start_state="FLAT",
            initial_buy="0.00000000",
            initial_sell="0.00000000",
            initial_quote=None,
            actions=(),
            quotes=(),
            scenario=scenario,
            mark_time_ns=None,
        )
        aggregate["accounting_counts"][scenario.scenario_id][result.status] = 1
        aggregate["accounting_digests"][scenario.scenario_id] = result_digest(result)
    result = finalize_aggregate(aggregate)
    validate_aggregate(result)
    return result


def main() -> int:
    try:
        result = run()
        _require_ignored(OUTPUT)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(result, ensure_ascii=True, separators=(",", ":")), encoding="utf-8")
        print(json.dumps({"case_id": CASE_ID, "aggregate_sha256": result["aggregate_sha256"]}, separators=(",", ":")))
        return 0
    except Exception:
        print("RETRO-HIST-004 analysis rejected", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
