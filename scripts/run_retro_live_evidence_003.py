"""stdin-only synthetic E-003 fidelity/holdout stage."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_live_evidence_001 import parse_unique_json
from xau_trigger.retro_live_evidence_003 import evaluate_fidelity, verify_fidelity_aggregate

def main() -> int:
    try:
        document = parse_unique_json(sys.stdin.read())
        if not isinstance(document, dict) or set(document) != {"comparisons"}:
            raise RetroBotInputError("E-003 CLI requires comparisons only")
        output = evaluate_fidelity(document["comparisons"])
        verify_fidelity_aggregate(output)
        sys.stdout.write(json.dumps(output, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n")
        return 0
    except (RetroBotInputError, TypeError, ValueError, KeyError):
        sys.stderr.write("E-003 input rejected\n")
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
