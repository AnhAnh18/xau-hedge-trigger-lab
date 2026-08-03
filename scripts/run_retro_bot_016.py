"""Source-free RB-016 package freeze CLI.

Stages accept exactly one JSON object on stdin except ``validate-config``.
Malformed input returns exit status 2 with a short non-sensitive message.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_012 import (
    PACKAGE_ID,
    build_manifest,
    load_json_no_duplicates,
    package_replay_fixture,
    validate_package,
)


def _dump(value: object) -> None:
    print(json.dumps(value, ensure_ascii=True, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("validate-config", "package-replay", "verify-receipt"))
    args = parser.parse_args(argv)
    try:
        if args.stage == "validate-config":
            manifest = build_manifest()
            _dump(manifest)
            return 0
        document = load_json_no_duplicates(sys.stdin)
        if not isinstance(document, dict):
            raise RetroBotInputError("RB-016 expects one JSON object")
        if args.stage == "package-replay":
            _dump(package_replay_fixture(document))
            return 0
        validate_package(document)
        _dump({"stage": args.stage, "verified": True})
        return 0
    except (RetroBotInputError, TypeError, ValueError, KeyError):
        print("RB-016 input rejected", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
