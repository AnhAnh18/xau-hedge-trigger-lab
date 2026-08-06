"""stdin-only E-002 metadata receipt validator."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_live_evidence_001 import parse_unique_json
from xau_trigger.retro_live_evidence_002_receipt import validate_source_receipt

def main() -> int:
    try:
        value = parse_unique_json(sys.stdin.read())
        validate_source_receipt(value)
        sys.stdout.write(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n")
        return 0
    except (RetroBotInputError, TypeError, ValueError, KeyError, OverflowError):
        sys.stderr.write("E-002 source receipt rejected\n")
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
