from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_hist_002 import Position
from xau_trigger.retro_live_evidence_002_capture import (
    _capture_cycles,
    _scan_ticks,
    build_capture_receipt,
    capture_authorized,
    verify_authorized_capture,
)
from xau_trigger.retro_live_evidence_002_receipt import validate_source_receipt
from xau_trigger.retro_live_evidence_001 import digest


def _position(position_id: str, side: str, quantity: str, opened: str, closed: str | None) -> Position:
    return Position(position_id, side, Decimal(quantity), pd.Timestamp(opened), pd.Timestamp(closed) if closed else None)


def test_capture_cycles_is_redacted_and_censors_carry_in() -> None:
    positions = [
        _position("buy-1", "buy", "0.30000000", "2026-05-02 00:00:00", "2026-05-02 00:20:00"),
        _position("sell-1", "sell", "0.30000000", "2026-05-02 00:05:00", "2026-05-02 00:10:00"),
        _position("carry", "buy", "0.10000000", "2026-04-30 23:00:00", "2026-05-01 00:05:00"),
    ]
    rows, stats = _capture_cycles(positions)
    assert stats["carry_in"] == 1
    assert len(rows) == 1
    assert rows[0]["categories"] == ["normal_hedge", "one_leg_recovery"]
    assert rows[0]["action_count"] == 4
    assert rows[0]["buy_actions"] == 2
    assert rows[0]["sell_actions"] == 2
    assert "time" not in rows[0] and "position_id" not in rows[0]


def test_capture_cycles_is_byte_deterministic() -> None:
    positions = [
        _position("b", "buy", "0.30000000", "2026-06-01 00:00:00", "2026-06-01 00:05:00"),
        _position("s", "sell", "0.30000000", "2026-06-01 00:01:00", "2026-06-01 00:04:00"),
    ]
    first, _ = _capture_cycles(positions)
    second, _ = _capture_cycles(positions)
    assert digest(first) == digest(second)


def test_same_timestamp_group_is_censored() -> None:
    positions = [
        _position("b", "buy", "0.30000000", "2026-06-01 00:00:00", "2026-06-01 00:05:00"),
        _position("s", "sell", "0.30000000", "2026-06-01 00:00:00", "2026-06-01 00:04:00"),
    ]
    rows, _ = _capture_cycles(positions)
    assert rows and rows[0]["censored"] is True


def test_one_leg_category_requires_one_leg_after_hedge() -> None:
    positions = [
        _position("b1", "buy", "0.30000000", "2026-06-01 00:00:00", "2026-06-01 00:03:00"),
        _position("s1", "sell", "0.30000000", "2026-06-01 00:00:00", "2026-06-01 00:04:00"),
        _position("b2", "buy", "0.10000000", "2026-06-01 00:01:00", "2026-06-01 00:05:00"),
    ]
    rows, _ = _capture_cycles(positions)
    assert "one_leg_recovery" not in rows[0]["categories"]


def test_censor_start_is_retained_as_censored_cycle() -> None:
    positions = [_position("c", "buy", "0.10000000", "2026-05-01 00:00:00", "2026-05-01 00:05:00")]
    positions[0] = Position(positions[0].position_id, positions[0].side, positions[0].quantity, positions[0].open_time, positions[0].close_time, True)
    rows, _ = _capture_cycles(positions)
    assert rows and rows[0]["censored"] is True


def test_tick_scan_derives_gap_and_spread_day_markers(tmp_path: Path) -> None:
    path = tmp_path / "ticks.csv"
    path.write_text(
        "time_utc,bid,ask\n"
        "2026-05-01T20:00:00.000000Z,100.00,100.01\n"
        "2026-05-04T00:00:00.000000Z,101.00,101.20\n"
        "2026-05-04T00:00:01.000000Z,101.00,101.20\n",
        encoding="utf-8",
    )
    gaps, wide, stats = _scan_ticks({"synthetic.csv": path})
    assert {item.date().isoformat() for item in gaps} == {"2026-05-04"}
    assert wide == set()
    assert stats["valid_rows"] == 3
    assert stats["monday_gap_days"] == 1


def test_wide_spread_matching_keeps_nonmaximum_qualifying_ticks(tmp_path: Path) -> None:
    path = tmp_path / "ticks.csv"
    rows = ["time_utc,bid,ask"]
    rows.extend(
        f"{(pd.Timestamp('2026-05-05T00:00:00Z') + pd.Timedelta(seconds=index)).isoformat()},100.00,100.01"
        for index in range(100)
    )
    rows.extend(
        [
            "2026-05-05T00:02:00+00:00,100.00,100.20",
            "2026-05-05T00:10:00+00:00,100.00,100.30",
        ]
    )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    marker = pd.Timestamp("2026-05-05T00:02:00Z")
    _, wide, stats = _scan_ticks({"synthetic.csv": path}, event_times={marker})
    assert stats["wide_spread_days"] == 1
    assert pd.Timestamp("2026-05-05T00:02:00Z") in wide
    positions = [_position("b", "buy", "0.30000000", "2026-05-05 03:02:00", "2026-05-05 03:03:00")]
    captured, _ = _capture_cycles(positions, wide_spread_dates=wide)
    assert "wide_spread" in captured[0]["categories"]


def test_wide_spread_matching_crosses_tick_chunk_boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "ticks.csv"
    rows = ["time_utc,bid,ask", "2026-05-05T00:00:00+00:00,100.00,100.01", "2026-05-05T00:00:01+00:00,100.00,100.20"]
    rows.extend(
        f"{(pd.Timestamp('2026-05-05T00:00:02Z') + pd.Timedelta(seconds=index)).isoformat()},100.00,100.01"
        for index in range(101)
    )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    import xau_trigger.retro_live_evidence_002_capture as module

    original_read_csv = module.pd.read_csv

    def tiny_chunks(*args: object, **kwargs: object):
        kwargs["chunksize"] = 2
        return original_read_csv(*args, **kwargs)

    monkeypatch.setattr(module.pd, "read_csv", tiny_chunks)
    marker = pd.Timestamp("2026-05-05T00:00:02Z")
    _, wide, _ = _scan_ticks({"synthetic.csv": path}, event_times={marker})
    assert marker in wide


def test_event_markers_match_server_events_in_utc() -> None:
    positions = [_position("b", "buy", "0.30000000", "2026-05-04 03:00:00", "2026-05-04 03:05:00")]
    marker = pd.Timestamp("2026-05-04T00:00:00Z")
    rows, _ = _capture_cycles(positions, monday_gap_dates={marker}, wide_spread_dates={marker})
    assert rows[0]["categories"] == ["monday_gap", "one_leg_recovery", "wide_spread"]


def test_monday_gap_cycle_is_not_counted_as_normal_hedge() -> None:
    positions = [
        _position("b", "buy", "0.30000000", "2026-05-04 03:00:00", "2026-05-04 03:05:00"),
        _position("s", "sell", "0.30000000", "2026-05-04 03:01:00", "2026-05-04 03:04:00"),
    ]
    marker = pd.Timestamp("2026-05-04T00:00:00Z")
    rows, _ = _capture_cycles(positions, monday_gap_dates={marker})
    assert "monday_gap" in rows[0]["categories"]
    assert "normal_hedge" not in rows[0]["categories"]


def test_authorized_capture_rejects_tampered_receipt_before_source_access() -> None:
    root = Path(__file__).parents[1]
    receipt = __import__("json").loads((root / "docs/retro_live_evidence/RETRO-LIVE-EVIDENCE-002-source-receipt.json").read_text(encoding="utf-8"))
    bad = deepcopy(receipt)
    bad["source_receipt_sha256"] = "0" * 64
    with pytest.raises(RetroBotInputError):
        capture_authorized(bad)


def test_trusted_capture_digests_reject_receipt_tampering(monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).parents[1]
    receipt = __import__("json").loads((root / "docs/retro_live_evidence/RETRO-LIVE-EVIDENCE-002-source-receipt.json").read_text(encoding="utf-8"))
    import xau_trigger.retro_live_evidence_002_capture as module

    monkeypatch.setattr(module, "_verify_receipt_sources", lambda value, scope: ({}, {}))
    monkeypatch.setattr(module, "_load_report_positions", lambda paths: [])
    monkeypatch.setattr(module, "_scan_ticks", lambda paths, **kwargs: (set(), set(), {"valid_rows": 0, "monday_gap_days": 0, "wide_spread_days": 0}))
    monkeypatch.setattr(module, "_capture_cycles", lambda positions, **kwargs: ([], {"carry_in": 0, "completed_or_censored_cycles": 0, "censored_cycles": 0}))
    result = capture_authorized(receipt)
    capture_receipt = build_capture_receipt(result)
    bad = deepcopy(capture_receipt)
    bad["input_digest"] = "0" * 64
    bad["receipt_sha256"] = digest({key: bad[key] for key in bad if key != "receipt_sha256"})
    with pytest.raises(RetroBotInputError):
        verify_authorized_capture(
            result,
            receipt,
            expected_input_digest=bad["input_digest"],
            expected_component_digest=bad["component_digest"],
            expected_aggregate_sha256=bad["aggregate_sha256"],
            expected_status=bad["status"],
        )
    bad = deepcopy(capture_receipt)
    bad["aggregate_sha256"] = "0" * 64
    bad["receipt_sha256"] = digest({key: bad[key] for key in bad if key != "receipt_sha256"})
    with pytest.raises(RetroBotInputError):
        verify_authorized_capture(
            result,
            receipt,
            expected_input_digest=bad["input_digest"],
            expected_component_digest=bad["component_digest"],
            expected_aggregate_sha256=bad["aggregate_sha256"],
            expected_status=bad["status"],
        )

    bad = deepcopy(receipt)
    bad["allowed_fields_by_alias"]["report-001.html"] = ["time_utc", "side", "action", "state", "lot"]
    bad["source_receipt_sha256"] = digest({key: bad[key] for key in bad if key != "source_receipt_sha256"})
    with pytest.raises(RetroBotInputError):
        capture_authorized(bad)


def test_capture_verifier_binds_aggregate_to_the_supplied_receipt(monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).parents[1]
    receipt = __import__("json").loads((root / "docs/retro_live_evidence/RETRO-LIVE-EVIDENCE-002-source-receipt.json").read_text(encoding="utf-8"))
    expansion = __import__("json").loads((root / "docs/retro_live_evidence/RETRO-LIVE-EVIDENCE-002-expansion-winter-source-receipt.json").read_text(encoding="utf-8"))
    import xau_trigger.retro_live_evidence_002_capture as module

    monkeypatch.setattr(module, "_verify_receipt_sources", lambda value, scope: ({}, {}))
    monkeypatch.setattr(module, "_load_report_positions", lambda paths: [])
    monkeypatch.setattr(module, "_scan_ticks", lambda paths, **kwargs: (set(), set(), {"valid_rows": 0, "monday_gap_days": 0, "wide_spread_days": 0}))
    monkeypatch.setattr(module, "_capture_cycles", lambda positions, **kwargs: ([], {"carry_in": 0, "completed_or_censored_cycles": 0, "censored_cycles": 0}))
    result = capture_authorized(receipt)
    rebound = deepcopy(result)
    rebound["source_receipt_sha256"] = expansion["source_receipt_sha256"]
    rebound["population_utc_half_open"] = expansion["population_utc_half_open"]
    rebound["source_timezone_code"] = expansion["source_timezone_code"]
    rebound["tick_alias_count"] = 22
    rebound["aggregate_sha256"] = digest({key: rebound[key] for key in rebound if key != "aggregate_sha256"})
    with pytest.raises(RetroBotInputError):
        verify_authorized_capture(
            rebound,
            expansion,
            expected_input_digest=rebound["input_digest"],
            expected_component_digest=rebound["component_digest"],
            expected_aggregate_sha256=rebound["aggregate_sha256"],
            expected_status=rebound["status"],
        )


def test_receipt_file_is_valid_metadata_only() -> None:
    root = Path(__file__).parents[1]
    receipt = __import__("json").loads((root / "docs/retro_live_evidence/RETRO-LIVE-EVIDENCE-002-source-receipt.json").read_text(encoding="utf-8"))
    assert validate_source_receipt(receipt)
    assert receipt["execution_surface_authorized"] is False
    assert receipt["m5_inputs_models_thresholds_gates_untouched"] is True
