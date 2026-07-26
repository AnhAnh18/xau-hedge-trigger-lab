from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.acquisition import (
    build_synthetic_acquisition_files,
    discover_files,
    load_acquisition_plan,
    validate_acquisition,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate pre-registered M5 tick/report acquisition inputs."
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=ROOT / "data" / "m5_acquisition_plan.json",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Validate and print the pre-registration without reading raw data.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate anonymized synthetic fixtures instead of private raw data.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output path; stdout is always emitted.",
    )
    return parser.parse_args()


def main() -> None:
    args = _arguments()
    plan = load_acquisition_plan(args.plan)
    if args.plan_only:
        result = {
            "status": "PLAN_VALID",
            "plan_id": plan["plan_id"],
            "registered_on": plan["registered_on"],
            "sessions": plan["sessions"],
            "primary_server_hours": plan["analysis_windows"][
                "primary_server_hours"
            ],
            "secondary_full_session": plan["analysis_windows"][
                "secondary_full_session"
            ],
        }
        exit_code = 0
    else:
        if args.dry_run:
            with TemporaryDirectory(prefix="m5-acquisition-dry-run-") as temp:
                tick_path, report_path = build_synthetic_acquisition_files(
                    plan,
                    temp,
                )
                result = validate_acquisition(
                    plan,
                    [tick_path],
                    [report_path],
                )
        else:
            tick_paths = discover_files(
                ROOT / "data" / "raw" / "ticks",
                plan["tick_export"]["allowed_suffixes"],
            )
            report_paths = discover_files(
                ROOT / "data" / "raw" / "trades",
                plan["trade_report"]["allowed_suffixes"],
            )
            result = validate_acquisition(plan, tick_paths, report_paths)
        exit_code = {"PASS": 0, "INCOMPLETE": 2, "FAIL": 1}[result["status"]]

    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    print(rendered, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
