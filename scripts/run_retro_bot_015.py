"""Source-free RB-015 robustness/stress replay CLI.

The replay stage accepts one typed, synthetic JSON fixture on stdin.  It does
not accept paths, raw exports, or precomputed observation rows.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_009 import (
    M5_FIREWALL,
    RB008_CONFIG_SHA256,
    REPORT_MANIFEST_SHA256,
    TICK_MANIFEST_SHA256,
)
from xau_trigger.retro_bot_011 import (
    FIXTURE_ID,
    PROJECTION_DIGEST,
    PROJECTION_VERSION,
    locked_stress_cases,
    stress_replay_fixture,
    validate_stress_aggregate,
)


def _config_payload() -> dict[str, object]:
    return {
        "stage": "validate-config",
        "projection_version": PROJECTION_VERSION,
        "fixture_id": FIXTURE_ID,
        "projection_digest": PROJECTION_DIGEST,
        "case_count": len(locked_stress_cases()),
        "cases": [
            {
                "case_id": case.case_id,
                "family": case.family,
                "clock_id": case.clock_id,
                "timestamp_mode": case.timestamp_mode,
                "quote_mode": case.quote_mode,
                "cost_scenario_id": case.cost_scenario_id,
                "coverage_mode": case.coverage_mode,
                "slice_id": case.slice_id,
                "ablation_id": case.ablation_id,
            }
            for case in locked_stress_cases()
        ],
        "rb008_config_sha256": RB008_CONFIG_SHA256,
        "source_manifest_digests": {
            "report_manifest_sha256": REPORT_MANIFEST_SHA256,
            "tick_manifest_sha256": TICK_MANIFEST_SHA256,
        },
        "m5_firewall": M5_FIREWALL,
    }


def _read_json() -> object:
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError as error:
        raise RetroBotInputError("RB-015 input JSON is invalid") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("validate-config", "stress-replay", "verify-aggregate"))
    args = parser.parse_args(argv)

    try:
        if args.stage == "validate-config":
            print(json.dumps(_config_payload(), ensure_ascii=True, separators=(",", ":")))
            return 0

        document = _read_json()
        if not isinstance(document, dict):
            raise RetroBotInputError("RB-015 expects one typed JSON object")
        if args.stage == "stress-replay":
            output = stress_replay_fixture(document)
            print(json.dumps(output, ensure_ascii=True, separators=(",", ":")))
            return 0

        validate_stress_aggregate(document)
        print(
            json.dumps(
                {
                    "stage": args.stage,
                    "verified": True,
                    "projection_digest": PROJECTION_DIGEST,
                    "m5_firewall": M5_FIREWALL,
                },
                ensure_ascii=True,
                separators=(",", ":"),
            )
        )
        return 0
    except (RetroBotInputError, TypeError, ValueError, KeyError) as error:
        # Keep malformed-input errors short and free of local/private paths.
        print(str(error) or "RB-015 input rejected", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
