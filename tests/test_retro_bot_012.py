from __future__ import annotations

import copy
import json
import subprocess
import sys

import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_011 import PROJECTION_DIGEST, PROJECTION_VERSION, FIXTURE_ID
from xau_trigger.retro_bot_012 import (
    PACKAGE_ID,
    RB014_PROVENANCE_SHA256,
    build_manifest,
    fixture_sha256,
    load_json_no_duplicates,
    package_replay_fixture,
    validate_manifest,
    validate_package,
    validate_state_snapshot,
)

from test_retro_bot_011 import _fixture


def test_manifest_locks_inherited_provenance_and_cost_fingerprints() -> None:
    manifest = build_manifest()
    validate_manifest(manifest)
    assert manifest["package_id"] == PACKAGE_ID
    assert manifest["projection_version"] == PROJECTION_VERSION
    assert manifest["projection_digest"] == PROJECTION_DIGEST
    assert manifest["fixture_id"] == FIXTURE_ID
    assert manifest["rb014_provenance_sha256"] == RB014_PROVENANCE_SHA256
    assert [item["scenario_id"] for item in manifest["cost_scenarios"]] == ["zero", "spread_slippage", "latency_margin"]


def test_package_replay_is_redacted_and_self_verifying() -> None:
    package = package_replay_fixture(_fixture())
    validate_package(package)
    assert package["case_id"] == "RB-016"
    assert package["receipt"]["terminal_status"] == "descriptive-only-no-selection"
    encoded = json.dumps(package, ensure_ascii=True, separators=(",", ":"))
    assert "net_return" not in encoded
    assert "raw_path" not in encoded
    assert "report-001.html" not in encoded


def test_fixture_digest_ignores_transport_whitespace_but_detects_content() -> None:
    fixture = _fixture()
    assert fixture_sha256(fixture) == fixture_sha256(json.loads(json.dumps(fixture, indent=2)))
    reordered = copy.deepcopy(fixture)
    values = reordered["cycles"][0]["cycle"]["causal_window"]["close_snapshots"][0]["values"]
    reordered["cycles"][0]["cycle"]["causal_window"]["close_snapshots"][0]["values"] = dict(reversed(list(values.items())))
    assert fixture_sha256(fixture) == fixture_sha256(reordered)
    changed = copy.deepcopy(fixture)
    changed["cycles"][0]["cycle"]["unit_id"] = "changed"
    with pytest.raises(RetroBotInputError):
        fixture_sha256(changed)


def test_state_and_nested_digest_tampering_rejected() -> None:
    package = package_replay_fixture(_fixture())
    bad = copy.deepcopy(package)
    bad["state_snapshot"]["epoch"] = 1
    with pytest.raises(RetroBotInputError):
        validate_package(bad)
    bad = copy.deepcopy(package)
    bad["receipt"]["fixture_sha256"] = "0" * 64
    with pytest.raises(RetroBotInputError):
        validate_package(bad)


def test_recursive_privacy_m5_and_live_firewall() -> None:
    fixture = _fixture()
    bad = copy.deepcopy(fixture)
    bad["cycles"][0]["cycle"]["causal_window"]["private_path"] = "C:/secret"
    with pytest.raises(RetroBotInputError):
        package_replay_fixture(bad)
    package = package_replay_fixture(fixture)
    bad_package = copy.deepcopy(package)
    bad_package["receipt"]["m5_reference"] = "M5 model"
    with pytest.raises(RetroBotInputError):
        validate_package(bad_package)
    bad_package = copy.deepcopy(package)
    bad_package["receipt"]["live_execution"] = True
    with pytest.raises(RetroBotInputError):
        validate_package(bad_package)


def test_duplicate_json_keys_rejected_at_any_depth() -> None:
    with pytest.raises(RetroBotInputError):
        load_json_no_duplicates('{"a":1,"a":2}')
    with pytest.raises(RetroBotInputError):
        load_json_no_duplicates('{"a":{"b":1,"b":2}}')


def test_cli_is_stdin_only_and_deterministic() -> None:
    fixture = json.dumps(_fixture(), ensure_ascii=True, separators=(",", ":"))
    command = [sys.executable, "scripts/run_retro_bot_016.py", "package-replay"]
    first = subprocess.run(command, input=fixture, text=True, capture_output=True, check=False)
    second = subprocess.run(command, input=fixture, text=True, capture_output=True, check=False)
    assert first.returncode == 0, first.stderr
    assert first.stdout == second.stdout
    package = json.loads(first.stdout)
    verify = subprocess.run([sys.executable, "scripts/run_retro_bot_016.py", "verify-receipt"], input=first.stdout, text=True, capture_output=True, check=False)
    assert verify.returncode == 0, verify.stderr
    assert json.loads(verify.stdout)["verified"] is True
    bad = subprocess.run(command, input=json.dumps({"raw_path": "C:/secret"}), text=True, capture_output=True, check=False)
    assert bad.returncode == 2
    assert "C:/secret" not in bad.stderr
    config = subprocess.run([sys.executable, "scripts/run_retro_bot_016.py", "validate-config"], text=True, capture_output=True, check=False)
    assert config.returncode == 0
    assert json.loads(config.stdout)["package_id"] == PACKAGE_ID
