"""Source-free RB-019 variable-lot replay CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_015 import parse_input, replay, verify_aggregate


def _dump(value: object) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("replay", "verify-aggregate"))
    args = parser.parse_args(argv)
    try:
        document = parse_input(sys.stdin)
        if not isinstance(document, dict):
            raise RetroBotInputError("RB-019 input must be an object")
        if args.stage == "replay":
            _dump(replay(document))
        else:
            verify_aggregate(document)
            _dump({"stage": "verify-aggregate", "verified": True})
        return 0
    except (
        RetroBotInputError,
        TypeError,
        ValueError,
        KeyError,
        AttributeError,
        IndexError,
        OverflowError,
        UnicodeError,
        RecursionError,
    ):
        sys.stderr.write("RB-019 input rejected\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
