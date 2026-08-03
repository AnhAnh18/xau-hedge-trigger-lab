"""Source-free RB-014 paper aggregate CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.retro_bot_009 import BOOTSTRAPS, CANDIDATES, CLOCKS, FOLDS
from xau_trigger.retro_bot_010 import (
    M5_FIREWALL,
    RB008_CONFIG_SHA256,
    REPORT_MANIFEST_SHA256,
    TICK_MANIFEST_SHA256,
    paper_replay_fixture,
    validate_paper_aggregate,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("validate-config", "paper-replay", "verify-aggregate"))
    args = parser.parse_args(argv)
    if args.stage == "validate-config":
        print(json.dumps({"stage": args.stage, "folds": FOLDS, "clocks": CLOCKS, "bootstraps": BOOTSTRAPS, "candidates": CANDIDATES, "config_sha256": RB008_CONFIG_SHA256, "firewall": M5_FIREWALL}, separators=(",", ":")))
        return 0
    document = json.load(sys.stdin)
    if not isinstance(document, dict):
        raise SystemExit("RB-014 expects one redacted JSON object")
    if args.stage == "paper-replay":
        aggregate = paper_replay_fixture(document)
    else:
        validate_paper_aggregate(document)
        aggregate = document
    if args.stage == "paper-replay":
        print(json.dumps(aggregate, ensure_ascii=True, separators=(",", ":")))
    else:
        print(json.dumps({"stage": args.stage, "verified": True, "report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
