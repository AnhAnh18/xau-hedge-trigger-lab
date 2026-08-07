"""Verify a redacted E-002 capture against a separately retained receipt."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_live_evidence_001 import parse_unique_json
from xau_trigger.retro_live_evidence_002_capture import verify_authorized_capture, verify_capture_receipt
from xau_trigger.retro_live_evidence_002_receipt import validate_source_receipt


def main() -> int:
    try:
        document = parse_unique_json(sys.stdin.read())
        if not isinstance(document, dict) or set(document) != {"capture", "source_receipt", "capture_receipt"}:
            raise RetroBotInputError("E-002 capture verification envelope invalid")
        validate_source_receipt(document["source_receipt"])
        verify_capture_receipt(document["capture_receipt"])
        verify_authorized_capture(
            document["capture"],
            document["source_receipt"],
            expected_input_digest=document["capture_receipt"]["input_digest"],
            expected_component_digest=document["capture_receipt"]["component_digest"],
            expected_aggregate_sha256=document["capture_receipt"]["aggregate_sha256"],
            expected_status=document["capture_receipt"]["status"],
        )
        sys.stdout.write(json.dumps({"case_id": document["capture"]["case_id"], "status": document["capture"]["status"], "verified": True, "aggregate_sha256": document["capture"]["aggregate_sha256"]}, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n")
        return 0
    except (RetroBotInputError, TypeError, ValueError, KeyError):
        sys.stderr.write("E-002 capture verification rejected\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
