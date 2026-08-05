"""RB-018 synthetic/shadow terminal seal.

This module consumes only redacted RB-017 reports and in-memory receipts.
It has no source-data, filesystem, network, MT5, or live-order surface.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import IO, Mapping

from .retro_bot import RetroBotInputError
from .retro_bot_012 import load_json_no_duplicates
from .retro_bot_013 import REPORT_FIELDS as RB017_REPORT_FIELDS
from .retro_bot_013 import _validate_report as validate_rb017_report

RB018_ID = "RB-018"
SCHEMA_VERSION = 1
M5_FIREWALL = "M5_FIREWALL_ATTESTATION_V1"
REGISTRATION_SHA256 = "a66b085509e14729b5acdf1e39a0c823a74770b7406251a141d454de3f02b6b9"
RB017_PREREQUISITE_SHA256 = "3a51a2de0898652c4c58d599508a89894d0a7ecb9cb0d178e9d0d5efa69a5c4b"
RB017_VALIDATOR_SHA256 = "0329ddfd59e70be9e76c73a99f60c64726747a3453b5f30f40219f8c9757d7d4"
TERMINAL_STATUS = "offline-lane-closed-synthetic-shadow-only"
HISTORICAL_CONCLUSION = "behaviorally-compatible-accounting-inconclusive"
SHOWN = (
    "rb017_report_integrity",
    "rb017_two_run_determinism_receipts",
    "rb017_independent_review_pass",
    "offline_boundary_intact",
    "terminal_receipt_self_digest",
)
UNRESOLVED = (
    "synthetic_shadow_only",
    "no_new_historical_evidence",
    "no_candidate_selection",
    "no_profitability",
    "original_trigger_unidentified",
    "no_live_execution",
    "model_scope_unchanged",
)
PROCESS_FIELDS = ("schema_version", "runner_id", "execution_nonce")
RUN_FIELDS = ("run_id", "report", "stdout_sha256", "process_receipt", "run_receipt_sha256")
GATE_FIELDS = (
    "schema_version",
    "owner_authorization",
    "registration_sha256",
    "rb017_prerequisite_sha256",
    "rb017_validator_sha256",
    "rb017_review_verdict",
    "rb017_rereview_verdict",
    "focused_tests_passed",
    "full_tests_passed",
    "privacy_passed",
    "compile_passed",
    "diff_check_passed",
    "m5_firewall_passed",
    "source_expansion",
    "m5_modified",
    "live_execution",
    "attestation_sha256",
)
INPUT_FIELDS = ("schema_version", "case_id", "runs", "gate_attestation")
VERIFY_FIELDS = INPUT_FIELDS + ("receipt",)
RECEIPT_FIELDS = (
    "schema_version",
    "case_id",
    "rb017_report_sha256",
    "rb017_package_sha256",
    "rb017_holdout_fixture_sha256",
    "rb017_holdout_aggregate_sha256",
    "run_receipt_sha256s",
    "gate_attestation_sha256",
    "run_count",
    "byte_identical",
    "review_verdict",
    "terminal_status",
    "historical_conclusion",
    "selection_performed",
    "new_sources_used",
    "m5_inputs_used",
    "live_execution",
    "shown",
    "unresolved",
    "m5_firewall",
    "receipt_sha256",
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_STRINGS = {
    RB018_ID,
    "run_a",
    "run_b",
    "RB017_CLOSEOUT_PROCESS_V1",
    "PASS",
    "raw_historical_scope",
    "no_live_execution",
    "live_execution",
    M5_FIREWALL,
}
FORBIDDEN_KEY_TOKENS = (
    "password",
    "credential",
    "secret",
    "journal",
    "ticket",
    ".ex5",
    "raw_path",
    "private_path",
    "account",
    "login",
    "subprocess",
    "network",
    "mt5",
    "order",
    "position",
)
FORBIDDEN_VALUE_TOKENS = (
    "password",
    "credential",
    "secret",
    "journal",
    "ticket",
    ".ex5",
    "raw_rows",
    "private_path",
    "subprocess",
    "network",
    "mt5",
    "file://",
)


def canonical_json(value: object) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError) as error:
        raise RetroBotInputError("RB-018 canonical JSON is invalid") from error


def _sha(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _hex(value: object) -> bool:
    return isinstance(value, str) and bool(HEX64.fullmatch(value))


def _fields(value: object, expected: tuple[str, ...], message: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or tuple(value.keys()) != expected:
        raise RetroBotInputError(message)
    return value


def _firewall(value: object, *, key: str = "") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise RetroBotInputError("RB-018 input rejected")
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise RetroBotInputError("RB-018 input rejected")
            folded_key = raw_key.casefold()
            if any(token in folded_key for token in FORBIDDEN_KEY_TOKENS):
                raise RetroBotInputError("RB-018 privacy/firewall violation")
            if folded_key == "m5_firewall" or folded_key in {
                "m5_firewall_passed",
                "m5_modified",
                "m5_inputs_used",
            }:
                _firewall(item, key=folded_key)
            else:
                _firewall(item, key=folded_key)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _firewall(item, key=key)
        return
    if isinstance(value, str):
        folded = value.casefold()
        if value in ALLOWED_STRINGS:
            return
        if any(token in folded for token in FORBIDDEN_VALUE_TOKENS):
            raise RetroBotInputError("RB-018 privacy/firewall violation")
        if "m5" in folded or "live" in folded:
            raise RetroBotInputError("RB-018 privacy/firewall violation")
        if "\\" in value or "/" in value or ":" in value:
            raise RetroBotInputError("RB-018 path-like value")


def _validate_process(value: object) -> Mapping[str, object]:
    process = _fields(value, PROCESS_FIELDS, "RB-018 process receipt is invalid")
    if type(process["schema_version"]) is not int or process["schema_version"] != 1 or process["runner_id"] != "RB017_CLOSEOUT_PROCESS_V1":
        raise RetroBotInputError("RB-018 process receipt is invalid")
    if not _hex(process["execution_nonce"]):
        raise RetroBotInputError("RB-018 process nonce is invalid")
    return process


def _validate_report(report: object) -> Mapping[str, object]:
    if not isinstance(report, Mapping):
        raise RetroBotInputError("RB-018 RB-017 report is invalid")
    try:
        validate_rb017_report(report)
    except Exception as error:
        if isinstance(error, RetroBotInputError):
            raise
        raise RetroBotInputError("RB-018 RB-017 report is invalid") from error
    if tuple(report.keys()) != RB017_REPORT_FIELDS:
        raise RetroBotInputError("RB-018 RB-017 report schema is invalid")
    return report


def _stdout_digest(report: Mapping[str, object]) -> str:
    return hashlib.sha256((canonical_json(report) + "\n").encode("utf-8")).hexdigest()


def _validate_run(value: object) -> Mapping[str, object]:
    run = _fields(value, RUN_FIELDS, "RB-018 run schema is invalid")
    if run["run_id"] not in {"run_a", "run_b"}:
        raise RetroBotInputError("RB-018 run id is invalid")
    report = _validate_report(run["report"])
    if not _hex(run["stdout_sha256"]) or run["stdout_sha256"] != _stdout_digest(report):
        raise RetroBotInputError("RB-018 stdout digest is invalid")
    _validate_process(run["process_receipt"])
    expected = _sha({key: run[key] for key in RUN_FIELDS if key != "run_receipt_sha256"})
    if not _hex(run["run_receipt_sha256"]) or run["run_receipt_sha256"] != expected:
        raise RetroBotInputError("RB-018 run receipt digest is invalid")
    return run


def _validate_gate(value: object) -> Mapping[str, object]:
    gate = _fields(value, GATE_FIELDS, "RB-018 gate schema is invalid")
    if (
        type(gate["schema_version"]) is not int
        or gate["schema_version"] != 1
        or gate["owner_authorization"] != "RB018_SYNTHETIC_SHADOW_AUTHORIZED"
        or gate["registration_sha256"] != REGISTRATION_SHA256
        or gate["rb017_prerequisite_sha256"] != RB017_PREREQUISITE_SHA256
        or gate["rb017_validator_sha256"] != RB017_VALIDATOR_SHA256
        or gate["rb017_review_verdict"] != "PASS"
        or gate["rb017_rereview_verdict"] != "PASS"
        or any(type(gate[field]) is not bool or gate[field] is not True for field in (
            "focused_tests_passed",
            "full_tests_passed",
            "privacy_passed",
            "compile_passed",
            "diff_check_passed",
            "m5_firewall_passed",
        ))
        or gate["source_expansion"] is not False
        or gate["m5_modified"] is not False
        or gate["live_execution"] is not False
    ):
        raise RetroBotInputError("RB-018 gate attestation is invalid")
    expected = _sha({key: gate[key] for key in GATE_FIELDS if key != "attestation_sha256"})
    if gate["attestation_sha256"] != expected:
        raise RetroBotInputError("RB-018 attestation digest is invalid")
    return gate


def _build_receipt(runs: list[Mapping[str, object]], gate: Mapping[str, object]) -> dict[str, object]:
    first = runs[0]["report"]
    receipt: dict[str, object] = {
        "schema_version": 1,
        "case_id": RB018_ID,
        "rb017_report_sha256": first["report_sha256"],
        "rb017_package_sha256": first["package_sha256"],
        "rb017_holdout_fixture_sha256": first["holdout_fixture_sha256"],
        "rb017_holdout_aggregate_sha256": first["holdout_aggregate_sha256"],
        "run_receipt_sha256s": [runs[0]["run_receipt_sha256"], runs[1]["run_receipt_sha256"]],
        "gate_attestation_sha256": gate["attestation_sha256"],
        "run_count": 2,
        "byte_identical": True,
        "review_verdict": "PASS",
        "terminal_status": TERMINAL_STATUS,
        "historical_conclusion": HISTORICAL_CONCLUSION,
        "selection_performed": False,
        "new_sources_used": False,
        "m5_inputs_used": False,
        "live_execution": False,
        "shown": list(SHOWN),
        "unresolved": list(UNRESOLVED),
        "m5_firewall": M5_FIREWALL,
        "receipt_sha256": "TO_BE_FILLED",
    }
    receipt["receipt_sha256"] = _sha({key: receipt[key] for key in RECEIPT_FIELDS if key != "receipt_sha256"})
    if tuple(receipt.keys()) != RECEIPT_FIELDS:
        raise RetroBotInputError("RB-018 receipt schema is invalid")
    return receipt


def _validate_receipt(receipt: object) -> Mapping[str, object]:
    value = _fields(receipt, RECEIPT_FIELDS, "RB-018 receipt schema is invalid")
    if (
        type(value["schema_version"]) is not int
        or value["schema_version"] != 1
        or value["case_id"] != RB018_ID
        or type(value["run_count"]) is not int
        or value["run_count"] != 2
        or value["byte_identical"] is not True
        or value["review_verdict"] != "PASS"
        or value["terminal_status"] != TERMINAL_STATUS
        or value["historical_conclusion"] != HISTORICAL_CONCLUSION
        or value["selection_performed"] is not False
        or value["new_sources_used"] is not False
        or value["m5_inputs_used"] is not False
        or value["live_execution"] is not False
        or value["shown"] != list(SHOWN)
        or value["unresolved"] != list(UNRESOLVED)
        or value["m5_firewall"] != M5_FIREWALL
    ):
        raise RetroBotInputError("RB-018 receipt literal is invalid")
    for key in (
        "rb017_report_sha256",
        "rb017_package_sha256",
        "rb017_holdout_fixture_sha256",
        "rb017_holdout_aggregate_sha256",
        "gate_attestation_sha256",
        "receipt_sha256",
    ):
        if not _hex(value[key]):
            raise RetroBotInputError("RB-018 receipt digest is invalid")
    if (
        not isinstance(value["run_receipt_sha256s"], list)
        or len(value["run_receipt_sha256s"]) != 2
        or any(not _hex(item) for item in value["run_receipt_sha256s"])
    ):
        raise RetroBotInputError("RB-018 receipt run digests are invalid")
    expected = _sha({key: value[key] for key in RECEIPT_FIELDS if key != "receipt_sha256"})
    if value["receipt_sha256"] != expected:
        raise RetroBotInputError("RB-018 receipt self-digest is invalid")
    return value


def seal(document: Mapping[str, object]) -> dict[str, object]:
    _firewall(document)
    root = _fields(document, INPUT_FIELDS, "RB-018 input schema is invalid")
    if type(root["schema_version"]) is not int or root["schema_version"] != 1 or root["case_id"] != RB018_ID:
        raise RetroBotInputError("RB-018 input literal is invalid")
    runs_value = root["runs"]
    if not isinstance(runs_value, list) or len(runs_value) != 2:
        raise RetroBotInputError("RB-018 runs are invalid")
    runs = [_validate_run(item) for item in runs_value]
    if [run["run_id"] for run in runs] != ["run_a", "run_b"]:
        raise RetroBotInputError("RB-018 run order is invalid")
    nonces = [run["process_receipt"]["execution_nonce"] for run in runs]
    if nonces[0] == nonces[1]:
        raise RetroBotInputError("RB-018 process receipts are not distinct")
    if canonical_json(runs[0]["report"]) != canonical_json(runs[1]["report"]):
        raise RetroBotInputError("RB-018 reports are not byte-identical")
    gate = _validate_gate(root["gate_attestation"])
    return _build_receipt(runs, gate)


def verify_seal(document: Mapping[str, object]) -> bool:
    _firewall(document)
    if not isinstance(document, Mapping) or tuple(document.keys()) not in (INPUT_FIELDS, VERIFY_FIELDS):
        raise RetroBotInputError("RB-018 verify schema is invalid")
    root = document
    expected = seal({key: root[key] for key in INPUT_FIELDS})
    if "receipt" in root:
        supplied = _validate_receipt(root["receipt"])
        if canonical_json(supplied) != canonical_json(expected):
            raise RetroBotInputError("RB-018 receipt mismatch")
    return True


def parse_input(stream: IO[str] | str) -> object:
    try:
        value = load_json_no_duplicates(stream)
        _firewall(value)
        return value
    except Exception as error:
        if isinstance(error, RetroBotInputError):
            raise
        raise RetroBotInputError("RB-018 input rejected") from error


__all__ = [
    "RB018_ID",
    "RECEIPT_FIELDS",
    "REGISTRATION_SHA256",
    "RB017_PREREQUISITE_SHA256",
    "RB017_VALIDATOR_SHA256",
    "seal",
    "verify_seal",
    "parse_input",
    "canonical_json",
]
