from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "retro_bot" / "RETRO-BOT-001-contract.md"
INVENTORY = ROOT / "docs" / "retro_bot" / "RETRO-BOT-001-firewall-inventory.json"
CONFIG = ROOT / "docs" / "retro_bot" / "RETRO-BOT-001-config.json"
EXPECTED_INVENTORY_SHA256 = "34628d77374130ab8aa47aa00d5c1b4dfda8aac53bd9bb19e3b98ad5c9a4ec03"
EXPECTED_CONFIG_SHA256 = "a1fcf30d7d1a8a57ad96bad2b69d92d157c683a179da70bcebb438deb4770c0c"


def _inventory_digest(payload: dict) -> str:
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_retro_bot_firewall_inventory_is_self_hashed() -> None:
    document = json.loads(INVENTORY.read_text(encoding="utf-8"))
    recorded = document.pop("inventory_sha256")
    assert document["schema_version"] == 1
    assert recorded == EXPECTED_INVENTORY_SHA256
    assert recorded == _inventory_digest(document)
    artifacts = document["protected_artifacts"]
    assert len(artifacts) == 58
    assert len(artifacts) == len(set(artifacts))
    for relative_path in artifacts:
        relative = Path(relative_path)
        assert not relative.is_absolute()
        assert ".." not in relative.parts
        assert (ROOT / relative).resolve().is_relative_to(ROOT)
    assert document["forbidden_casefolded_tokens"] == ["retro-bot", "retro_bot", "retrobot"]


def test_retro_bot_firewall_scans_pinned_m5_artifacts() -> None:
    document = json.loads(INVENTORY.read_text(encoding="utf-8"))
    for relative_path in document["protected_artifacts"]:
        path = ROOT / relative_path
        assert path.is_file(), relative_path
        content = path.read_text(encoding="utf-8").casefold()
        for token in document["forbidden_casefolded_tokens"]:
            assert token not in content, f"{token} found in {relative_path}"


def test_retro_bot_machine_config_is_exact_and_self_hashed() -> None:
    document = json.loads(CONFIG.read_text(encoding="utf-8"))
    recorded = document.pop("config_sha256")
    assert recorded == EXPECTED_CONFIG_SHA256
    assert recorded == _inventory_digest(document)
    assert document["case_id"] == "RETRO-BOT-001"
    assert document["population"] == {
        "start_server": "2025-11-01 00:00:00",
        "end_server_exclusive": "2026-07-31 00:00:00",
        "excluded_server_windows": [
            "2026-07-31..2026-08-01",
            "2026-08-03..2026-08-07",
            "2026-08-10..2026-08-14",
        ],
    }
    assert document["policies"] == [
        {"id": "first_available_tick", "delay_seconds": 0},
        {"id": "wait_300_seconds", "delay_seconds": 300},
        {"id": "wait_900_seconds", "delay_seconds": 900},
        {"id": "wait_3600_seconds", "delay_seconds": 3600},
    ]
    eu_dst = document["clock_scenarios"][2]
    assert eu_dst["id"] == "eu_dst_2025_2026"
    assert eu_dst["inverse_report_time_policy"] == "exclude_interval_clock_unresolved_when_zero_or_multiple_utc_candidates"
    ticks = document["source_receipt"]["tick_aliases"]
    assert len(ticks) == document["source_receipt"]["tick_alias_count"] == 39
    assert ticks == sorted(ticks)
    assert len(ticks) == len(set(ticks))


def test_retro_bot_contract_pins_scope_and_frozen_baselines() -> None:
    content = CONTRACT.read_text(encoding="utf-8")
    for required in (
        "2025-11-01 00:00:00",
        "2026-07-31 00:00:00",
        "2026-08-03",
        "2026-08-10",
        "report-manifest digest",
        "tick-manifest digest",
        "first_available_tick",
        "wait_300_seconds",
        "wait_900_seconds",
        "wait_3600_seconds",
        "utc_plus_2",
        "utc_plus_3",
        "eu_dst_2025_2026",
        "right_censored_delay_not_reached",
        "right_censored_no_valid_tick",
        "at_least_3600_seconds",
        "independent reviewer may read a named ignored aggregate payload",
        EXPECTED_CONFIG_SHA256,
        EXPECTED_INVENTORY_SHA256,
    ):
        assert required in content
