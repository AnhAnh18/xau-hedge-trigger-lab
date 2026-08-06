"""stdin-only synthetic E-006 readiness safety verifier."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_live_evidence_001 import parse_unique_json
from xau_trigger.retro_live_evidence_006 import evaluate_readiness, verify_readiness

def main() -> int:
    try:
        document = parse_unique_json(sys.stdin.read())
        required = {"evidence_digests", "evidence_flags", "adapter_safety"}
        if not isinstance(document, dict) or set(document) != required:
            raise RetroBotInputError("E-006 CLI requires readiness inputs only")
        output = evaluate_readiness(**document)
        verify_readiness(output, expected_evidence_digest=output["evidence_digest"], expected_component_digests=output["evidence_digests"])
        sys.stdout.write(json.dumps(output, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n")
        return 0
    except (RetroBotInputError, TypeError, ValueError, KeyError, OverflowError):
        sys.stderr.write("E-006 input rejected\n")
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
