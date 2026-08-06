from __future__ import annotations

import json
from pathlib import Path
import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_live_evidence_001 import (
    assert_firewall_clean, assert_oracle_isolated, digest, load_gate_registry, parse_unique_json, seal_holdout_receipt, validate_gate_registry, verify_holdout_receipt,
    FROZEN_GATE_DIGEST,
    validate_synthetic_receipt,
)


def _receipt() -> dict:
    value = {"authorization_id":"E001-SYNTHETIC-ONLY","source_aliases":[],"object_types":[],"sha256_by_alias":{},"population_utc_half_open":["2026-01-01T00:00:00.000000Z","2026-01-02T00:00:00.000000Z"],"allowed_fields":{},"canonicalization_version":"synthetic-v1","parser_version":"synthetic-v1","retention":"redacted-aggregates-and-digests-only"}
    value["receipt_sha256"] = digest(value)
    return value


def test_frozen_registry_and_synthetic_receipt_validate() -> None:
    assert validate_gate_registry(load_gate_registry())
    assert validate_synthetic_receipt(_receipt())


def test_receipt_tamper_and_gate_tamper_rejected() -> None:
    receipt = _receipt(); receipt["parser_version"] = "changed"
    with pytest.raises(RetroBotInputError): validate_synthetic_receipt(receipt)
    gates = load_gate_registry(); gates["gates"]["coverage"]["threshold"] = 0
    with pytest.raises(RetroBotInputError): validate_gate_registry(gates)


def test_firewall_rejects_forbidden_nested_fields() -> None:
    assert assert_firewall_clean({"synthetic": {"count": 1}})
    with pytest.raises(RetroBotInputError): assert_firewall_clean({"nested": {"password": "x"}})
    with pytest.raises(RetroBotInputError): assert_firewall_clean({"raw_rows": [1]})
    with pytest.raises(RetroBotInputError): assert_firewall_clean({"source_path": "C:\\private\\x"})
    with pytest.raises(RetroBotInputError): assert_firewall_clean({"unc": "\\\\server\\share"})
    with pytest.raises(RetroBotInputError): assert_firewall_clean({"mt5_api": "x"})


def test_holdout_receipt_is_tamper_and_reuse_safe() -> None:
    receipt = seal_holdout_receipt(gate_digest=FROZEN_GATE_DIGEST, source_digest="b" * 64, holdout_digest="c" * 64, nonce="nonce-1234")
    used = set()
    assert verify_holdout_receipt(receipt, used_nonces=used)
    used.add(receipt["nonce"])
    with pytest.raises(RetroBotInputError): verify_holdout_receipt(receipt, used_nonces=used)
    receipt["holdout_digest"] = "d" * 64
    with pytest.raises(RetroBotInputError): verify_holdout_receipt(receipt, used_nonces=set())
    with pytest.raises(RetroBotInputError): verify_holdout_receipt(receipt, used_nonces=None)


def test_duplicate_json_oracle_isolation_and_deterministic_digest() -> None:
    with pytest.raises(RetroBotInputError): parse_unique_json('{"a":1,"a":2}')
    assert assert_oracle_isolated({"ticks": []}, {"observed_events": []})
    with pytest.raises(RetroBotInputError): assert_oracle_isolated({"oracle_labels": []}, {})
    with pytest.raises(RetroBotInputError): assert_oracle_isolated({"nested": {"ORACLE_Labels": []}}, {})
    assert digest({"x": 1}) == digest({"x": 1})


def test_registry_file_is_canonical_and_no_source_aliases() -> None:
    path = Path("docs/retro_live_evidence/RETRO-LIVE-EVIDENCE-001-gates.json")
    raw = path.read_text(encoding="utf-8")
    value = json.loads(raw)
    assert json.loads(json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))) == value
    assert value["actionful_population"]["minimum_total"] == 30
