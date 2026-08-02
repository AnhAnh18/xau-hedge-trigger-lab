"""Render a tracked RETRO-BOT-002 result from a validated aggregate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from xau_trigger.retro_bot import load_config
from xau_trigger.retro_bot_002 import render_paper_markdown, validate_paper_aggregate

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "retro_bot" / "RETRO-BOT-002-result.md"
PAPER_RUN_ROOT = ROOT / "data" / "raw" / "passview_quarantine" / "retro-bot-002" / "paper_runs"


def _ignored(path: Path) -> None:
    try:
        relative = path.resolve().relative_to(ROOT.resolve())
    except ValueError as error:
        raise ValueError("aggregate input is outside the workspace") from error
    if subprocess.run(["git", "check-ignore", "--no-index", "-q", str(relative)], cwd=ROOT, check=False).returncode != 0:
        raise ValueError("aggregate input is not ignored")


def _require_aggregate(path: Path) -> None:
    path = path.resolve()
    try:
        path.relative_to(PAPER_RUN_ROOT.resolve())
    except ValueError as error:
        raise ValueError("aggregate input is outside the registered paper-run root") from error
    if path.name != "aggregate.json" or path.parent.parent != PAPER_RUN_ROOT.resolve() or not path.is_file():
        raise ValueError("aggregate input is not a registered paper-run aggregate")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        if args.output.resolve() != DEFAULT_OUTPUT.resolve():
            raise ValueError("result output path is not registered")
        _require_aggregate(args.aggregate)
        _ignored(args.aggregate)
        payload = json.loads(args.aggregate.read_text(encoding="utf-8"))
        config = load_config()
        validate_paper_aggregate(payload, config)
        args.output.write_text(render_paper_markdown(payload, config), encoding="utf-8")
        print(json.dumps({"case_id": payload["case_id"], "status": "result_written", "aggregate_sha256": payload["aggregate_sha256"]}, sort_keys=True))
        return 0
    except Exception:
        print(json.dumps({"status": "failed", "reason": "invalid_or_unapproved_aggregate"}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
