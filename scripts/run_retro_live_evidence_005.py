"""stdin-only synthetic E-005 shadow-observer verifier."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_live_evidence_001 import parse_unique_json
from xau_trigger.retro_live_evidence_005 import evaluate_shadow, verify_shadow_aggregate

def main() -> int:
    try:
        document = parse_unique_json(sys.stdin.read())
        if not isinstance(document, dict) or set(document) != {"observations"}:
            raise RetroBotInputError("E-005 CLI requires observations only")
        output = evaluate_shadow(document["observations"])
        verify_shadow_aggregate(output, expected_input_digest=output["input_digest"])
        sys.stdout.write(json.dumps(output, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n")
        return 0
    except (RetroBotInputError, TypeError, ValueError, KeyError):
        sys.stderr.write("E-005 input rejected\n")
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
