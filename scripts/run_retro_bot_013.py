"""Source-safe RB-013 stage CLI.

The CLI accepts only redacted aggregate JSON on stdin for verification. Raw
source paths and trading exports are intentionally not accepted.
"""
from __future__ import annotations

import argparse
import json
import sys

from xau_trigger.retro_bot_009 import (
    BOOTSTRAPS,
    CANDIDATES,
    CLOCKS,
    FOLDS,
    M5_FIREWALL,
    RB008_CONFIG_SHA256,
    REPORT_MANIFEST_SHA256,
    TICK_MANIFEST_SHA256,
    WalkForwardRow,
    blind_structural_intake,
    validate_candidate_manifest,
    validate_oracle_diagnostic,
    validate_walk_forward_aggregate,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("validate-config", "blind-structural-intake", "sealed-holdout-replay", "verify-aggregate"))
    args = parser.parse_args(argv)
    if args.stage == "validate-config":
        validate_candidate_manifest(CANDIDATES)
        print(json.dumps({"stage": args.stage, "folds": FOLDS, "clocks": CLOCKS, "bootstraps": BOOTSTRAPS, "candidates": CANDIDATES, "config_sha256": RB008_CONFIG_SHA256, "firewall": M5_FIREWALL}, separators=(",", ":")))
        return 0
    if args.stage == "blind-structural-intake":
        document = json.load(sys.stdin)
        if not isinstance(document, list):
            raise SystemExit("RB-013 structural intake expects a redacted row list")
        rows = tuple(WalkForwardRow(**row) for row in document if isinstance(row, dict))
        result = blind_structural_intake(manifest=CANDIDATES, source_digests={"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256}, rows=rows)
        print(json.dumps(result, separators=(",", ":")))
        return 0
    if args.stage == "sealed-holdout-replay":
        document = json.load(sys.stdin)
        if not isinstance(document, dict):
            raise SystemExit("RB-013 sealed replay expects one redacted aggregate")
        validate_walk_forward_aggregate(document)
        if any(row.get("fold") == "holdout" for row in document.get("rows", [])) is not True:
            raise SystemExit("RB-013 sealed replay aggregate has no holdout rows")
        print(json.dumps({"stage": args.stage, "verified": True}, separators=(",", ":")))
        return 0
    document = json.load(sys.stdin)
    if not isinstance(document, dict):
        raise SystemExit("RB-013 aggregate JSON must be an object")
    if document.get("oracle_only") is True:
        validate_oracle_diagnostic(document)
    else:
        validate_walk_forward_aggregate(document)
    print(json.dumps({"stage": args.stage, "verified": True, "report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
