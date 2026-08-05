from __future__ import annotations

import copy
import json
import subprocess
import sys

import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_010 import canonical_cycle_id
from xau_trigger.retro_bot_012 import package_replay_fixture
from xau_trigger.retro_bot_013 import (
    REPORT_FIELDS,
    SHOWN,
    TERMINAL_STATUS,
    UNRESOLVED,
    closeout,
    load_json_no_duplicates,
    validate_holdout_fixture,
    verify_closeout,
)

from test_retro_bot_011 import _fixture


def _holdout_fixture() -> dict[str, object]:
    fixture = copy.deepcopy(_fixture())
    for wrapper in fixture["cycles"]:
        cycle = wrapper["cycle"]
        cycle["fold"] = "holdout"
        cycle["cycle_id"] = canonical_cycle_id(
            "holdout",
            cycle["clock_id"],
            cycle["bootstrap_id"],
            cycle["candidate_id"],
            cycle["unit_id"],
        )
        causal = cycle["causal_window"]
        causal["report_alias"] = "report-008.html"
        for record in causal["decision_records"]:
            record["fold"] = "holdout"
            record["future_read"] = False
            record["oracle_used"] = False
            record["report_alias"] = "report-008.html"
    return fixture


def _input() -> dict[str, object]:
    fixture = _holdout_fixture()
    return {"package": package_replay_fixture(_fixture()), "holdout_fixture": fixture}


def test_closeout_has_exact_redacted_schema_and_inconclusive_status() -> None:
    report = closeout(_input())
    assert tuple(report) == REPORT_FIELDS
    assert report["case_id"] == "RB-017"
    assert report["terminal_status"] == TERMINAL_STATUS
    assert report["selection_performed"] is False
    assert report["holdout_supported"] is False
    assert report["shown"] == list(SHOWN)
    assert report["unresolved"] == list(UNRESOLVED)
    encoded = json.dumps(report, ensure_ascii=True, separators=(",", ":"))
    assert "net_return" not in encoded
    assert "report-009.html" not in encoded


def test_holdout_fold_alias_and_decision_tampering_rejected() -> None:
    fixture = _holdout_fixture()
    validate_holdout_fixture(fixture)
    bad = copy.deepcopy(fixture)
    bad["cycles"][0]["cycle"]["fold"] = "development"
    with pytest.raises(RetroBotInputError):
        closeout({"package": package_replay_fixture(_fixture()), "holdout_fixture": bad})
    bad = copy.deepcopy(fixture)
    bad["cycles"][0]["cycle"]["causal_window"]["report_alias"] = "report-009.html"
    with pytest.raises(RetroBotInputError):
        validate_holdout_fixture(bad)
    bad = copy.deepcopy(fixture)
    bad["cycles"][0]["cycle"]["causal_window"]["decision_records"][0]["oracle_used"] = True
    with pytest.raises(RetroBotInputError):
        validate_holdout_fixture(bad)


def test_package_and_aggregate_tampering_rejected() -> None:
    document = _input()
    bad = copy.deepcopy(document)
    bad["package"]["package_sha256"] = "0" * 64
    with pytest.raises(RetroBotInputError):
        closeout(bad)
    bad = copy.deepcopy(document)
    bad["holdout_fixture"]["projection"]["projection_digest"] = "0" * 64
    with pytest.raises(RetroBotInputError):
        closeout(bad)


def test_verify_recomputes_and_accepts_optional_report_only_when_identical() -> None:
    document = _input()
    report = closeout(document)
    assert verify_closeout({**document, "report": report}) is True
    assert verify_closeout(document) is True
    bad = copy.deepcopy(document)
    bad["report"] = copy.deepcopy(report)
    bad["report"]["holdout_supported"] = True
    with pytest.raises(RetroBotInputError):
        verify_closeout(bad)


def test_duplicate_keys_and_extra_input_keys_rejected() -> None:
    with pytest.raises(RetroBotInputError):
        load_json_no_duplicates('{"package":{},"package":{}}')
    document = _input()
    with pytest.raises(RetroBotInputError):
        closeout({**document, "extra": False})


def test_private_m5_live_values_rejected() -> None:
    document = _input()
    bad = copy.deepcopy(document)
    bad["holdout_fixture"]["private_path"] = "C:/secret"
    with pytest.raises(RetroBotInputError):
        closeout(bad)
    bad = copy.deepcopy(document)
    bad["holdout_fixture"]["m5_reference"] = "M5 model"
    with pytest.raises(RetroBotInputError):
        closeout(bad)


def test_cli_closeout_verify_and_determinism() -> None:
    encoded = json.dumps(_input(), ensure_ascii=True, separators=(",", ":"))
    command = [sys.executable, "scripts/run_retro_bot_017.py", "closeout"]
    first = subprocess.run(command, input=encoded, text=True, capture_output=True, check=False)
    second = subprocess.run(command, input=encoded, text=True, capture_output=True, check=False)
    assert first.returncode == 0, first.stderr
    assert first.stdout == second.stdout
    report = json.loads(first.stdout)
    verify_input = json.dumps({**_input(), "report": report}, ensure_ascii=True, separators=(",", ":"))
    verified = subprocess.run([sys.executable, "scripts/run_retro_bot_017.py", "verify-closeout"], input=verify_input, text=True, capture_output=True, check=False)
    assert verified.returncode == 0, verified.stderr
    assert json.loads(verified.stdout) == {"stage": "verify-closeout", "verified": True}
    bad = subprocess.run(command, input=json.dumps({"raw_path": "C:/secret"}), text=True, capture_output=True, check=False)
    assert bad.returncode == 2
    assert "C:/secret" not in bad.stderr
