"""Render a tracked RETRO-BOT result from a privacy-validated aggregate only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

from xau_trigger.retro_bot import RetroBotInputError, load_config, render_aggregate_markdown, validate_aggregate_payload


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "retro_bot" / "RETRO-BOT-001-result.md"


def _require_ignored(path: Path) -> None:
    try:
        relative = path.resolve().relative_to(ROOT.resolve())
    except ValueError as error:
        raise RetroBotInputError("aggregate input is outside the workspace") from error
    result = subprocess.run(["git", "check-ignore", "--no-index", "-q", str(relative)], cwd=ROOT, check=False)
    if result.returncode != 0:
        raise RetroBotInputError("aggregate input is not ignored")


def run(aggregate_path: Path, output_path: Path) -> dict:
    if output_path.resolve() != DEFAULT_OUTPUT.resolve():
        raise RetroBotInputError("result output path is not registered")
    _require_ignored(aggregate_path)
    config = load_config()
    payload = json.loads(aggregate_path.read_text(encoding="utf-8"))
    validate_aggregate_payload(payload, config)
    output_path.write_text(render_aggregate_markdown(payload, config), encoding="utf-8")
    return {"case_id": config.case_id, "status": "result_written", "aggregate_sha256": payload["aggregate_sha256"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        print(json.dumps(run(args.aggregate, args.output), ensure_ascii=True, sort_keys=True))
        return 0
    except RetroBotInputError as error:
        print(json.dumps({"status": "failed", "reason": str(error)}, ensure_ascii=True, sort_keys=True))
        return 2
    except Exception:
        print(json.dumps({"status": "failed", "reason": "internal_failure"}, ensure_ascii=True, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
