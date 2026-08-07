from __future__ import annotations

import json
from pathlib import Path

import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_hist_002 import REPORT_ALIASES, TICK_ALIASES
from xau_trigger.retro_live_evidence_002_capture import AUTHORIZED_SCOPE
from xau_trigger.retro_live_evidence_002_receipt import validate_source_receipt


ROOT = Path(__file__).parents[1]
RECEIPT_DIR = ROOT / "docs" / "retro_live_evidence"
SEASONS = ("winter", "summer")


def _load(season: str) -> dict[str, object]:
    path = RECEIPT_DIR / f"RETRO-LIVE-EVIDENCE-002-expansion-{season}-source-receipt.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_expansion_receipts_are_metadata_only_and_partition_remaining_ticks() -> None:
    receipts = [_load(season) for season in SEASONS]
    for receipt in receipts:
        assert validate_source_receipt(receipt)
        assert receipt["execution_surface_authorized"] is False
        assert receipt["m5_inputs_models_thresholds_gates_untouched"] is True
        assert receipt["retention_deadline_utc"] <= "2026-09-30T23:59:59.999999Z"

    report_sets = [{alias for alias in receipt["source_aliases"] if alias.startswith("report-")} for receipt in receipts]
    assert report_sets == [{f"report-{index:03d}.html" for index in range(1, 10)}] * 2
    tick_sets = [{alias for alias in receipt["source_aliases"] if alias.startswith("XAUUSD_ticks_")} for receipt in receipts]
    assert len(tick_sets[0] | tick_sets[1]) == 25
    assert not (tick_sets[0] & tick_sets[1])

    summer_start = receipts[1]["population_utc_half_open"][0]
    winter_end = receipts[0]["population_utc_half_open"][1]
    assert winter_end < summer_start
    assert "XAUUSD_ticks_2026-03-28_to_2026-04-04.csv" in tick_sets[0]
    assert "XAUUSD_ticks_2026-03-28_to_2026-04-04.csv" not in tick_sets[1]


def test_expansion_receipt_tampering_is_rejected() -> None:
    receipt = _load("winter")
    receipt["sha256_by_alias"]["report-001.html"] = "0" * 64
    with pytest.raises(RetroBotInputError):
        validate_source_receipt(receipt)


def test_authorized_scope_registry_matches_receipts_and_half_open_clock() -> None:
    expected = {
        "winter": ("UTC+2-winter", set(TICK_ALIASES[:22]), 2),
        "summer": ("UTC+3-summer", set(TICK_ALIASES[22:25]), 3),
    }
    for season, (timezone_code, tick_aliases, offset_hours) in expected.items():
        receipt = _load(season)
        scope = AUTHORIZED_SCOPE[receipt["source_receipt_sha256"]]
        assert scope["source_timezone_code"] == timezone_code
        assert scope["report_aliases"] == set(REPORT_ALIASES)
        assert scope["tick_aliases"] == tick_aliases
        assert scope["server_offset_hours"] == offset_hours
        assert receipt["population_utc_half_open"][0] != receipt["population_utc_half_open"][1]
