"""stdin-only synthetic E-002 aggregate stage."""
from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_live_evidence_001 import parse_unique_json
from xau_trigger.retro_live_evidence_002 import component_digest, ingest_redacted_cycles, verify_evidence_aggregate

def main() -> int:
    try:
        document = parse_unique_json(sys.stdin.read())
        if not isinstance(document, dict) or set(document) != {"cycles"}:
            raise RetroBotInputError("E-002 CLI requires cycles only")
        output = ingest_redacted_cycles(document["cycles"])
        verify_evidence_aggregate(output, expected_input_digest=output["input_digest"], expected_component_digest=component_digest(output))
        sys.stdout.write(json.dumps(output, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n")
        return 0
    except (RetroBotInputError, TypeError, ValueError, KeyError):
        sys.stderr.write("E-002 input rejected\n")
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
