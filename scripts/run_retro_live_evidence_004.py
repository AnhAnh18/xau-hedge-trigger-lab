"""Strict stdin-only E-004 ledger verifier/appender."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_live_evidence_001 import canonical_json, parse_unique_json
from xau_trigger.retro_live_evidence_004_ledger import append_ledger_entry, verify_ledger

MAX_INPUT_BYTES = 2_000_000
CONTEXT_FIELDS = {"source_digest", "fold_order_digest", "fold_bounds_digest"}
VERIFY_FIELDS = {"operation", "ledger", "expected_head_digest", "trusted_context", "trusted_input_digests"}
APPEND_FIELDS = VERIFY_FIELDS | {"receipt", "evaluation_proof", "evaluation_succeeded", "trusted_input_digest"}


def main() -> int:
    try:
        data = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(data) > MAX_INPUT_BYTES:
            raise RetroBotInputError("E-004 CLI input too large")
        document = parse_unique_json(data.decode("utf-8"))
        if not isinstance(document, dict) or document.get("operation") not in {"verify", "append"}:
            raise RetroBotInputError("E-004 CLI operation invalid")
        required = VERIFY_FIELDS if document["operation"] == "verify" else APPEND_FIELDS
        if set(document) != required or not isinstance(document["trusted_context"], dict) or set(document["trusted_context"]) != CONTEXT_FIELDS:
            raise RetroBotInputError("E-004 CLI envelope invalid")
        context = document["trusted_context"]
        if document["operation"] == "verify":
            verify_ledger(ledger=document["ledger"], expected_head_digest=document["expected_head_digest"], trusted_input_digests=document["trusted_input_digests"], **context)
            output = document["ledger"]
        else:
            output = append_ledger_entry(ledger=document["ledger"], expected_head_digest=document["expected_head_digest"], receipt=document["receipt"], evaluation_proof=document["evaluation_proof"], evaluation_succeeded=document["evaluation_succeeded"], input_digest=document["trusted_input_digest"], trusted_input_digests=document["trusted_input_digests"], **context)
        sys.stdout.write(canonical_json(output) + "\n")
        return 0
    except (UnicodeDecodeError, RetroBotInputError, TypeError, ValueError, KeyError):
        sys.stderr.write("E-004 input rejected\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
