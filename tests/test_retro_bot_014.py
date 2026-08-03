from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys

import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_013 import closeout
from xau_trigger.retro_bot_014 import (
    GATE_FIELDS,
    INPUT_FIELDS,
    RECEIPT_FIELDS,
    RB017_PREREQUISITE_SHA256,
    RB017_VALIDATOR_SHA256,
    REGISTRATION_SHA256,
    canonical_json,
    parse_input,
    seal,
    verify_seal,
)

from test_retro_bot_013 import _input as rb017_input


def _report() -> dict[str, object]:
    return closeout(rb017_input())


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _run(report: dict[str, object], run_id: str, nonce: str) -> dict[str, object]:
    run: dict[str, object] = {
        "run_id": run_id,
        "report": copy.deepcopy(report),
        "stdout_sha256": hashlib.sha256((canonical_json(report) + "\n").encode("utf-8")).hexdigest(),
        "process_receipt": {
            "schema_version": 1,
            "runner_id": "RB017_CLOSEOUT_PROCESS_V1",
            "execution_nonce": nonce,
        },
        "run_receipt_sha256": "TO_BE_FILLED",
    }
    run["run_receipt_sha256"] = _digest({key: run[key] for key in run if key != "run_receipt_sha256"})
    return run


def _gate() -> dict[str, object]:
    gate: dict[str, object] = {
        "schema_version": 1,
        "owner_authorization": "RB018_SYNTHETIC_SHADOW_AUTHORIZED",
        "registration_sha256": REGISTRATION_SHA256,
        "rb017_prerequisite_sha256": RB017_PREREQUISITE_SHA256,
        "rb017_validator_sha256": RB017_VALIDATOR_SHA256,
        "rb017_review_verdict": "PASS",
        "rb017_rereview_verdict": "PASS",
        "focused_tests_passed": True,
        "full_tests_passed": True,
        "privacy_passed": True,
        "compile_passed": True,
        "diff_check_passed": True,
        "m5_firewall_passed": True,
        "source_expansion": False,
        "m5_modified": False,
        "live_execution": False,
        "attestation_sha256": "TO_BE_FILLED",
    }
    gate["attestation_sha256"] = _digest(
        {key: gate[key] for key in GATE_FIELDS if key != "attestation_sha256"}
    )
    return gate


def _document() -> dict[str, object]:
    report = _report()
    return {
        "schema_version": 1,
        "case_id": "RB-018",
        "runs": [
            _run(report, "run_a", "0" * 63 + "1"),
            _run(report, "run_b", "0" * 63 + "2"),
        ],
        "gate_attestation": _gate(),
    }


def test_seal_has_exact_terminal_schema_and_literals() -> None:
    receipt = seal(_document())
    assert tuple(receipt) == RECEIPT_FIELDS
    assert receipt["case_id"] == "RB-018"
    assert receipt["run_count"] == 2
    assert receipt["byte_identical"] is True
    assert receipt["terminal_status"] == "offline-lane-closed-synthetic-shadow-only"
    assert receipt["historical_conclusion"] == "behaviorally-compatible-accounting-inconclusive"
    assert receipt["selection_performed"] is False
    assert receipt["new_sources_used"] is False
    assert receipt["m5_inputs_used"] is False
    assert receipt["live_execution"] is False


def test_verify_accepts_recomputed_and_supplied_receipt() -> None:
    document = _document()
    receipt = seal(document)
    assert verify_seal(document) is True
    assert verify_seal({**document, "receipt": receipt}) is True


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["runs"][1]["process_receipt"].__setitem__(
            "execution_nonce", d["runs"][0]["process_receipt"]["execution_nonce"]
        ),
        lambda d: d["runs"][0].__setitem__("stdout_sha256", "f" * 64),
        lambda d: d["gate_attestation"].__setitem__("m5_modified", True),
        lambda d: d["runs"][0]["report"].__setitem__("case_id", "RB-018"),
    ],
)
def test_tampering_and_non_distinct_process_receipts_rejected(mutate) -> None:
    document = _document()
    mutate(document)
    with pytest.raises(RetroBotInputError):
        seal(document)


def test_boolean_and_float_integer_fields_are_rejected() -> None:
    for location in (
        ("root", "schema_version"),
        ("process", "schema_version"),
        ("gate", "schema_version"),
    ):
        document = _document()
        if location[0] == "root":
            document[location[1]] = True
        elif location[0] == "process":
            document["runs"][0]["process_receipt"][location[1]] = 1.0
            document["runs"][0]["run_receipt_sha256"] = _digest(
                {key: document["runs"][0][key] for key in document["runs"][0] if key != "run_receipt_sha256"}
            )
        else:
            document["gate_attestation"][location[1]] = True
            document["gate_attestation"]["attestation_sha256"] = _digest(
                {key: document["gate_attestation"][key] for key in GATE_FIELDS if key != "attestation_sha256"}
            )
        with pytest.raises(RetroBotInputError):
            seal(document)


def test_firewall_and_schema_reject_private_unknown_values() -> None:
    document = _document()
    document["unexpected"] = {"private_path": "C:/secret"}
    with pytest.raises(RetroBotInputError):
        seal(document)


def test_duplicate_nonfinite_and_trailing_json_rejected() -> None:
    for raw in (
        '{"schema_version":1,"schema_version":1}',
        '{"schema_version":1} trailing',
        '{"value":1e309}',
    ):
        with pytest.raises(RetroBotInputError):
            parse_input(raw)


def test_contract_hashes_and_canonical_golden_vector() -> None:
    assert REGISTRATION_SHA256 == "a66b085509e14729b5acdf1e39a0c823a74770b7406251a141d454de3f02b6b9"
    assert RB017_PREREQUISITE_SHA256 == "3a51a2de0898652c4c58d599508a89894d0a7ecb9cb0d178e9d0d5efa69a5c4b"
    assert RB017_VALIDATOR_SHA256 == "0329ddfd59e70be9e76c73a99f60c64726747a3453b5f30f40219f8c9757d7d4"
    assert canonical_json({"a": 1, "b": "x"}) == '{"a":1,"b":"x"}'


def test_cli_is_deterministic_and_rejects_with_exact_error() -> None:
    document = json.dumps(_document(), ensure_ascii=True, separators=(",", ":"))
    command = [sys.executable, "scripts/run_retro_bot_018.py", "seal"]
    first = subprocess.run(command, input=document, text=True, capture_output=True, check=False)
    second = subprocess.run(command, input=document, text=True, capture_output=True, check=False)
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    bad = subprocess.run(command, input='{"schema_version":1}', text=True, capture_output=True, check=False)
    assert bad.returncode == 2
    assert bad.stdout == ""
    assert bad.stderr == "RB-018 input rejected\n"


def test_verify_cli_success_shape() -> None:
    document = _document()
    receipt = seal(document)
    verify_input = json.dumps({**document, "receipt": receipt}, separators=(",", ":"))
    result = subprocess.run(
        [sys.executable, "scripts/run_retro_bot_018.py", "verify-seal"],
        input=verify_input,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"stage": "verify-seal", "verified": True}
