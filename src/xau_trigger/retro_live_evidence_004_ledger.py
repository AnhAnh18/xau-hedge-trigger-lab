"""Redacted, one-shot E-004 holdout ledger.

This module is deliberately pure and source-free. Durable callers must pin
the current head externally and perform compare-and-swap before persisting a
returned envelope. The context root binds the frozen gate plus source/fold
digests; holdout inputs are pinned per entry.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping, Sequence

from .retro_bot import RetroBotInputError
from .retro_live_evidence_001 import FROZEN_GATE_DIGEST, assert_firewall_clean, digest
from .retro_live_evidence_003 import verify_holdout_block, verify_holdout_result

CASE_ID = "RETRO-LIVE-EVIDENCE-004"
SCHEMA_VERSION = 1
GENESIS_PAYLOAD = {"case_id": CASE_ID, "schema_version": SCHEMA_VERSION, "tag": "E004-LEDGER-GENESIS-V1"}
GENESIS_DIGEST = "95e50b19d2e41ae107bdcb8fa7d2bf1d7e5c61e100d4d21229f3b8a2c51a3d04"
MAX_ENTRIES = 1024
MAX_CANONICAL_BYTES = 1_000_000
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
NONCE = re.compile(r"[A-Za-z0-9._-]{8,80}\Z")

LEDGER_FIELDS = frozenset({"schema_version", "case_id", "context_digest", "genesis_digest", "entries", "head_digest"})
ENTRY_FIELDS = frozenset({"sequence", "previous_digest", "receipt", "evaluation_proof", "entry_digest"})
CONTEXT_FIELDS = frozenset({"source_digest", "fold_order_digest", "fold_bounds_digest"})
RESULT_FIELDS = frozenset({
    "schema_version", "case_id", "synthetic_only", "holdout_consumed",
    "development_digest", "validation_digest", "holdout_digest",
    "robustness_pass_fraction", "robustness_count", "fold_order_digest",
    "fold_bounds_digest", "source_receipt_digest", "status", "receipt_sha256",
    "aggregate_sha256",
})


def genesis_digest() -> str:
    """Return the pinned empty-ledger anchor."""
    if digest(GENESIS_PAYLOAD) != GENESIS_DIGEST:
        raise RetroBotInputError("E-004 genesis vector mismatch")
    return GENESIS_DIGEST


def _hex(value: object, label: str) -> str:
    if not isinstance(value, str) or HEX64.fullmatch(value) is None:
        raise RetroBotInputError(f"E-004 {label} digest invalid")
    return value


def _trusted_inputs(value: object) -> frozenset[str]:
    if not isinstance(value, (list, tuple, set, frozenset)) or len(value) > MAX_ENTRIES:
        raise RetroBotInputError("E-004 trusted input set invalid")
    values = frozenset(_hex(item, "trusted input") for item in value)
    if len(values) != len(value):
        raise RetroBotInputError("E-004 trusted input set has duplicates")
    return values


def context_digest(*, source_digest: str, fold_order_digest: str, fold_bounds_digest: str) -> str:
    """Derive the fixed source/fold context root for one ledger."""
    payload = {
        "gate_digest": FROZEN_GATE_DIGEST,
        "fold_bounds_digest": _hex(fold_bounds_digest, "fold bounds"),
        "fold_order_digest": _hex(fold_order_digest, "fold order"),
        "source_digest": _hex(source_digest, "source"),
        "tag": "E004-LEDGER-CONTEXT-V1",
    }
    return digest(payload)


def _context_from_args(*, source_digest: str, fold_order_digest: str, fold_bounds_digest: str) -> dict[str, str]:
    return {
        "source_digest": _hex(source_digest, "source"),
        "fold_order_digest": _hex(fold_order_digest, "fold order"),
        "fold_bounds_digest": _hex(fold_bounds_digest, "fold bounds"),
    }


def _validate_receipt(receipt: Mapping[str, Any], context: Mapping[str, str], expected_input_digest: str | None = None) -> None:
    if not isinstance(receipt, Mapping):
        raise RetroBotInputError("E-004 holdout receipt must be an object")
    if not isinstance(receipt.get("nonce"), str) or NONCE.fullmatch(receipt["nonce"]) is None:
        raise RetroBotInputError("E-004 nonce bounds invalid")
    used: set[str] = set()
    verify_holdout_block(receipt, used_nonces=used)
    if receipt["gate_digest"] != FROZEN_GATE_DIGEST:
        raise RetroBotInputError("E-004 gate binding mismatch")
    _hex(receipt["input_digest"], "input")
    if expected_input_digest is not None and receipt["input_digest"] != _hex(expected_input_digest, "input"):
        raise RetroBotInputError("E-004 input binding mismatch")
    for key in ("source_digest", "fold_order_digest", "fold_bounds_digest"):
        if receipt[key] != context[key]:
            raise RetroBotInputError(f"E-004 {key} binding mismatch")
    assert_firewall_clean([receipt[key] for key in ("source_digest", "input_digest", "fold_order_digest", "fold_bounds_digest", "receipt_sha256", "nonce")])


def _validate_proof(proof: Mapping[str, Any], receipt: Mapping[str, Any], context: Mapping[str, str]) -> None:
    if not isinstance(proof, Mapping) or set(proof) != RESULT_FIELDS:
        raise RetroBotInputError("E-004 evaluation proof schema invalid")
    if type(proof["schema_version"]) is not int or type(proof["synthetic_only"]) is not bool or type(proof["holdout_consumed"]) is not bool:
        raise RetroBotInputError("E-004 evaluation proof types invalid")
    verify_holdout_result(proof)
    if proof["case_id"] != CASE_ID or proof["receipt_sha256"] != receipt["receipt_sha256"]:
        raise RetroBotInputError("E-004 evaluation proof receipt binding mismatch")
    if proof["holdout_digest"] != receipt["input_digest"] or proof["source_receipt_digest"] != context["source_digest"]:
        raise RetroBotInputError("E-004 evaluation proof context mismatch")
    if proof["fold_order_digest"] != context["fold_order_digest"] or proof["fold_bounds_digest"] != context["fold_bounds_digest"]:
        raise RetroBotInputError("E-004 evaluation proof fold binding mismatch")


def _entry_digest(*, sequence: int, previous_digest: str, receipt: Mapping[str, Any], evaluation_proof: Mapping[str, Any]) -> str:
    return digest({"evaluation_proof": evaluation_proof, "previous_digest": previous_digest, "receipt": receipt, "sequence": sequence})


def seal_ledger_entry(*, sequence: int, previous_digest: str, receipt: Mapping[str, Any], evaluation_proof: Mapping[str, Any], source_digest: str, input_digest: str, fold_order_digest: str, fold_bounds_digest: str) -> dict[str, Any]:
    context = _context_from_args(source_digest=source_digest, fold_order_digest=fold_order_digest, fold_bounds_digest=fold_bounds_digest)
    if type(sequence) is not int or sequence < 1 or sequence > MAX_ENTRIES:
        raise RetroBotInputError("E-004 entry sequence invalid")
    previous = _hex(previous_digest, "previous")
    _validate_receipt(receipt, context, expected_input_digest=input_digest)
    _validate_proof(evaluation_proof, receipt, context)
    entry = {"sequence": sequence, "previous_digest": previous, "receipt": deepcopy(dict(receipt)), "evaluation_proof": deepcopy(dict(evaluation_proof))}
    return {**entry, "entry_digest": _entry_digest(**entry)}


def _validate_envelope_shape(ledger: Mapping[str, Any]) -> None:
    if not isinstance(ledger, Mapping) or set(ledger) != LEDGER_FIELDS:
        raise RetroBotInputError("E-004 ledger schema invalid")
    if type(ledger["schema_version"]) is not int or ledger["schema_version"] != SCHEMA_VERSION or ledger["case_id"] != CASE_ID or ledger["genesis_digest"] != GENESIS_DIGEST:
        raise RetroBotInputError("E-004 ledger identity invalid")
    if not isinstance(ledger["entries"], list) or len(ledger["entries"]) > MAX_ENTRIES:
        raise RetroBotInputError("E-004 ledger entry bound invalid")
    _hex(ledger["context_digest"], "context")
    _hex(ledger["head_digest"], "head")
    encoded = str(digest(ledger))
    if len(encoded) != 64 or len(__import__("json").dumps(ledger, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")) > MAX_CANONICAL_BYTES:
        raise RetroBotInputError("E-004 ledger size invalid")


def _binding_key(receipt: Mapping[str, Any]) -> tuple[str, ...]:
    # Nonce and receipt hash are intentionally excluded: a new nonce must not
    # bypass one-shot consumption for the same trusted holdout context.
    return tuple(receipt[key] for key in ("gate_digest", "source_digest", "input_digest", "fold_order_digest", "fold_bounds_digest"))


def verify_ledger(*, ledger: Mapping[str, Any], expected_head_digest: str, trusted_input_digests: Sequence[str], source_digest: str, fold_order_digest: str, fold_bounds_digest: str) -> bool:
    _validate_envelope_shape(ledger)
    context = _context_from_args(source_digest=source_digest, fold_order_digest=fold_order_digest, fold_bounds_digest=fold_bounds_digest)
    trusted_inputs = _trusted_inputs(trusted_input_digests)
    expected_context = context_digest(**context)
    if ledger["context_digest"] != expected_context or _hex(expected_head_digest, "expected head") != ledger["head_digest"]:
        raise RetroBotInputError("E-004 external ledger anchor/context mismatch")
    previous = GENESIS_DIGEST
    bindings: set[tuple[str, ...]] = set()
    nonces: set[str] = set()
    for index, entry in enumerate(ledger["entries"], start=1):
        if not isinstance(entry, Mapping) or set(entry) != ENTRY_FIELDS or type(entry["sequence"]) is not int or entry["sequence"] != index or entry["previous_digest"] != previous:
            raise RetroBotInputError("E-004 ledger chain ordering invalid")
        receipt, proof = entry["receipt"], entry["evaluation_proof"]
        _validate_receipt(receipt, context)
        if receipt["input_digest"] not in trusted_inputs:
            raise RetroBotInputError("E-004 trusted input binding mismatch")
        _validate_proof(proof, receipt, context)
        nonce = receipt["nonce"]
        if nonce in nonces or _binding_key(receipt) in bindings:
            raise RetroBotInputError("E-004 duplicate nonce/holdout binding")
        expected_entry = _entry_digest(sequence=entry["sequence"], previous_digest=previous, receipt=receipt, evaluation_proof=proof)
        if entry["entry_digest"] != expected_entry:
            raise RetroBotInputError("E-004 entry digest mismatch")
        nonces.add(nonce); bindings.add(_binding_key(receipt)); previous = expected_entry
    if ledger["head_digest"] != previous:
        raise RetroBotInputError("E-004 ledger head mismatch")
    assert_firewall_clean([ledger["context_digest"], ledger["genesis_digest"], ledger["head_digest"], [entry["entry_digest"] for entry in ledger["entries"]]])
    return True


def append_ledger_entry(*, ledger: Mapping[str, Any], expected_head_digest: str, receipt: Mapping[str, Any], evaluation_proof: Mapping[str, Any], evaluation_succeeded: bool, input_digest: str, trusted_input_digests: Sequence[str], source_digest: str, fold_order_digest: str, fold_bounds_digest: str) -> dict[str, Any]:
    if evaluation_succeeded is not True:
        raise RetroBotInputError("E-004 evaluation did not complete successfully")
    context = _context_from_args(source_digest=source_digest, fold_order_digest=fold_order_digest, fold_bounds_digest=fold_bounds_digest)
    trusted_inputs = _trusted_inputs(trusted_input_digests)
    if _hex(input_digest, "input") not in trusted_inputs:
        raise RetroBotInputError("E-004 candidate input is not trusted")
    verify_ledger(ledger=ledger, expected_head_digest=expected_head_digest, trusted_input_digests=trusted_inputs, **context)
    _validate_receipt(receipt, context, expected_input_digest=input_digest)
    _validate_proof(evaluation_proof, receipt, context)
    existing = ledger["entries"]
    candidate_binding = _binding_key(receipt)
    for item in existing:
        if candidate_binding is not None and _binding_key(item["receipt"]) == candidate_binding:
            candidate = seal_ledger_entry(sequence=item["sequence"], previous_digest=item["previous_digest"], receipt=receipt, evaluation_proof=evaluation_proof, input_digest=input_digest, **context)
            if candidate == item:
                return deepcopy(dict(ledger))
            raise RetroBotInputError("E-004 holdout already consumed with different entry")
    if len(existing) >= MAX_ENTRIES:
        raise RetroBotInputError("E-004 ledger is full")
    candidate = seal_ledger_entry(sequence=len(existing) + 1, previous_digest=ledger["head_digest"], receipt=receipt, evaluation_proof=evaluation_proof, input_digest=input_digest, **context)
    result = {"schema_version": SCHEMA_VERSION, "case_id": CASE_ID, "context_digest": context_digest(**context), "genesis_digest": GENESIS_DIGEST, "entries": [deepcopy(item) for item in existing] + [candidate], "head_digest": candidate["entry_digest"]}
    verify_ledger(ledger=result, expected_head_digest=result["head_digest"], trusted_input_digests=trusted_inputs, **context)
    return result
