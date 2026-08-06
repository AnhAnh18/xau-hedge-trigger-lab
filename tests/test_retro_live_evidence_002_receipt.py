from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_live_evidence_001 import digest
from xau_trigger.retro_live_evidence_002_receipt import validate_source_receipt


def _receipt() -> dict[str, object]:
    payload: dict[str, object] = {"authorization_id": "E002-AUTH-20260806", "owner_approval_utc": "2026-08-06T12:00:00.000000Z", "scope": "bounded-actionful-capture-only", "new_sources_authorized": True, "execution_surface_authorized": False, "m5_inputs_models_thresholds_gates_untouched": True, "retention_deadline_utc": "2026-08-09T12:00:00.000000Z", "source_aliases": ["ticks-a", "report-a"], "object_types": ["tick", "report"], "sha256_by_alias": {"ticks-a": "a" * 64, "report-a": "b" * 64}, "byte_count_by_alias": {"ticks-a": 10, "report-a": 20}, "population_utc_half_open": ["2026-08-03T00:00:00.000000Z", "2026-08-08T00:00:00.000000Z"], "source_timezone_code": "UTC+3-summer", "allowed_fields_by_alias": {"ticks-a": ["time_utc", "bid", "ask"], "report-a": ["time_utc", "side", "action", "state", "lot"]}, "canonicalization_version": "e002-c14n-1", "parser_version": "e002-parser-1", "retention": "redacted-aggregates-and-digests-only"}
    return {**payload, "source_receipt_sha256": digest(payload)}


def test_receipt_validator_accepts_metadata_only_envelope():
    assert validate_source_receipt(_receipt())


def test_receipt_validator_rejects_paths_and_tampering():
    bad = _receipt(); bad["source_aliases"] = ["C:\\secret.csv", "report-a"]
    with pytest.raises(RetroBotInputError): validate_source_receipt(bad)
    bad = _receipt(); bad["byte_count_by_alias"] = {"ticks-a": 0, "report-a": 20}
    with pytest.raises(RetroBotInputError): validate_source_receipt(bad)
    bad = _receipt(); bad["source_receipt_sha256"] = "0" * 64
    with pytest.raises(RetroBotInputError): validate_source_receipt(bad)
    bad = _receipt(); bad["population_utc_half_open"] = ["2026-02-30T00:00:00.000000Z", "2026-08-08T00:00:00.000000Z"]; bad["source_receipt_sha256"] = digest({key: bad[key] for key in bad if key != "source_receipt_sha256"})
    with pytest.raises(RetroBotInputError): validate_source_receipt(bad)
    bad = _receipt(); bad["retention"] = "retain-source-files-until-2099"; bad["source_receipt_sha256"] = digest({key: bad[key] for key in bad if key != "source_receipt_sha256"})
    with pytest.raises(RetroBotInputError): validate_source_receipt(bad)
    bad = _receipt(); del bad["retention_deadline_utc"]
    with pytest.raises(RetroBotInputError): validate_source_receipt(bad)
    bad = _receipt(); bad["owner_approval_utc"] = "٢٠٢٦-08-06T12:00:00.000000Z"; bad["source_receipt_sha256"] = digest({key: bad[key] for key in bad if key != "source_receipt_sha256"})
    with pytest.raises(RetroBotInputError): validate_source_receipt(bad)


def test_receipt_cli_is_stdin_only():
    script = Path(__file__).parents[1] / "scripts" / "validate_retro_live_evidence_002_receipt.py"
    run = subprocess.run([sys.executable, str(script)], input=json.dumps(_receipt()), text=True, capture_output=True, check=True)
    assert json.loads(run.stdout)["authorization_id"] == "E002-AUTH-20260806"
