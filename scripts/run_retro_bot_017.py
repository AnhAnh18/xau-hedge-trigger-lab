"""Source-free RB-017 synthetic/shadow closeout CLI.

``closeout`` and ``verify-closeout`` read one JSON object from stdin.  Invalid
input always returns status 2 with the fixed non-sensitive error text.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_013 import (
    closeout,
    load_json_no_duplicates,
    verify_closeout,
)


def _dump(value: object) -> None:
    print(json.dumps(value, ensure_ascii=True, separators=(",", ":")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("closeout", "verify-closeout"))
    args = parser.parse_args(argv)
    try:
        document = load_json_no_duplicates(sys.stdin)
        if not isinstance(document, dict):
            raise RetroBotInputError("RB-017 input must be an object")
        if args.stage == "closeout":
            _dump(closeout(document))
        else:
            verify_closeout(document)
            _dump({"stage": "verify-closeout", "verified": True})
        return 0
    except (RetroBotInputError, TypeError, ValueError, KeyError):
        print("RB-017 input rejected", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
