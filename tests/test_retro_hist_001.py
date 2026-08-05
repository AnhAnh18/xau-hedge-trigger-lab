from decimal import Decimal

import pandas as pd
import pytest

from scripts.analyze_retro_hist_001_lots import _parse_fixed8, _summarize_records


def _row(position_id, side="buy", volume=Decimal("0.30000000"), opened="2026-01-01 00:00:00", closed="2026-01-01 01:00:00"):
    return {
        "position_id": position_id,
        "symbol": "XAUUSD",
        "side": side,
        "volume": volume,
        "open_time": pd.Timestamp(opened),
        "close_time": None if closed is None else pd.Timestamp(closed),
    }


def test_fixed8_rejects_rounding_and_bounds() -> None:
    assert _parse_fixed8("0.30000000") == Decimal("0.30000000")
    with pytest.raises(ValueError):
        _parse_fixed8("0.000000001")
    with pytest.raises(ValueError):
        _parse_fixed8("1000.00000001")


def test_equal_closed_and_open_snapshot_deduplicate_with_closed_precedence() -> None:
    records = [
        _row("1", closed=None),
        _row("1"),
    ]
    coverage, details = _summarize_records(records, reports_parsed=2)
    assert coverage["accepted_position_ids"] == 1
    assert coverage["duplicate_position_rows"] == 1
    assert coverage["right_censored_positions"] == 0
    assert details["lot_bands"]["buy"]["closed"] == {"0.30000000": 1}


def test_conflicting_quantity_and_population_boundaries_fail_closed() -> None:
    records = [
        _row("conflict", volume="0.20000000"),
        _row("conflict", volume="0.30000000"),
        _row("carry", opened="2025-10-31 23:00:00", closed="2025-11-01 01:00:00"),
        _row("after", opened="2026-07-31 00:00:00", closed="2026-07-31 01:00:01"),
        _row("censored", opened="2026-07-30 00:00:00", closed=None),
    ]
    coverage, details = _summarize_records(records, reports_parsed=1)
    assert coverage["conflicting_position_ids"] == 1
    assert coverage["accepted_position_ids"] == 2
    assert coverage["right_censored_positions"] == 1
    assert coverage["outside_population_position_ids"] == 1
    assert details["lot_bands"]["buy"]["closed"] == {"0.30000000": 1}
    assert details["lot_bands"]["buy"]["right_censored"] == {"0.30000000": 1}


def test_invalid_side_symbol_and_quantity_are_not_retained() -> None:
    records = [
        _row("bad-side", side="hold"),
        {**_row("bad-symbol"), "symbol": "EURUSD"},
        {**_row("bad-qty"), "volume": "nan"},
    ]
    coverage, details = _summarize_records(records, reports_parsed=1)
    assert coverage["invalid_position_rows"] == 3
    assert coverage["accepted_position_ids"] == 0
    assert details["lot_bands"] == {"buy": {"closed": {}, "right_censored": {}}, "sell": {"closed": {}, "right_censored": {}}}


def test_nat_like_open_time_is_invalid_not_a_position() -> None:
    records = [{**_row("bad-time"), "open_time": "NaT"}]
    coverage, details = _summarize_records(records, reports_parsed=1)
    assert coverage["invalid_position_rows"] == 1
    assert coverage["accepted_position_ids"] == 0
    assert details["lot_bands"]["buy"]["closed"] == {}
