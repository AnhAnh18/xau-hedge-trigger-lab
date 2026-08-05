"""Source-free RB-018 synthetic/shadow terminal seal CLI."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_014 import parse_input, seal, verify_seal


def _dump(value: object) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=True, separators=(",", ":")) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("seal", "verify-seal"))
    args = parser.parse_args(argv)
    try:
        document = parse_input(sys.stdin)
        if not isinstance(document, dict):
            raise RetroBotInputError("RB-018 input must be an object")
        if args.stage == "seal":
            _dump(seal(document))
        else:
            verify_seal(document)
            _dump({"stage": "verify-seal", "verified": True})
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
        sys.stderr.write("RB-018 input rejected\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
