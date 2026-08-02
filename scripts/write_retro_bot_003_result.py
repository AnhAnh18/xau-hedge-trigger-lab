"""Render a tracked RETRO-BOT-003 result from a validated aggregate."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

from xau_trigger.retro_bot import RetroBotInputError, load_config
from xau_trigger.retro_bot_003 import render_sequential_markdown, validate_sequential_aggregate


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "retro_bot" / "RETRO-BOT-003-result.md"
MULTI_CYCLE_ROOT = ROOT / "data" / "raw" / "passview_quarantine" / "retro-bot-003" / "multi_cycle_runs"


def _require_aggregate(path: Path) -> None:
    path = Path(os.path.abspath(path))
    root = Path(os.path.abspath(MULTI_CYCLE_ROOT))
    if path.name != "aggregate.json" or path.parent.parent != root or not path.is_file():
        raise RetroBotInputError("aggregate input is not a registered multi-cycle aggregate")
    _reject_symlink_components(path, root)
    try:
        Path(os.path.realpath(path)).relative_to(Path(os.path.realpath(root)))
    except ValueError as error:
        raise RetroBotInputError("aggregate input resolves outside the registered root") from error
    relative = path.relative_to(Path(os.path.abspath(ROOT)))
    if subprocess.run(["git", "check-ignore", "--no-index", "-q", str(relative)], cwd=ROOT, check=False).returncode != 0:
        raise RetroBotInputError("aggregate input is not ignored")


def _reject_symlink_components(path: Path, root: Path) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise RetroBotInputError("path is outside the registered root") from error
    current = root
    for component in relative.parts:
        current /= component
        if current.is_symlink():
            raise RetroBotInputError("symlink path component is not allowed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        requested_output = Path(os.path.abspath(args.output))
        default_output = Path(os.path.abspath(DEFAULT_OUTPUT))
        workspace_root = Path(os.path.abspath(ROOT))
        if requested_output != default_output:
            raise RetroBotInputError("result output path is not registered")
        _reject_symlink_components(requested_output, workspace_root)
        try:
            Path(os.path.realpath(requested_output)).relative_to(Path(os.path.realpath(workspace_root)))
        except ValueError as error:
            raise RetroBotInputError("result output resolves outside the workspace") from error
        _require_aggregate(args.aggregate)
        payload = json.loads(args.aggregate.read_text(encoding="utf-8"))
        config = load_config()
        validate_sequential_aggregate(payload, config)
        args.output.write_text(render_sequential_markdown(payload, config), encoding="utf-8")
        print(json.dumps({"case_id": payload["case_id"], "status": "result_written", "aggregate_sha256": payload["aggregate_sha256"]}, sort_keys=True))
        return 0
    except RetroBotInputError as error:
        print(json.dumps({"status": "failed", "reason": str(error)}, sort_keys=True))
        return 2
    except Exception:
        print(json.dumps({"status": "failed", "reason": "internal_failure"}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
