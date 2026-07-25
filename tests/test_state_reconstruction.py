import pandas as pd
from src.xau_trigger.state_reconstruction import merge_lifecycles, reconstruct_states

def _closed(position_id, side, opened, closed, volume=0.3):
    return {"report_id": "r1", "position_id": position_id, "symbol": "XAUUSD", "side": side, "volume": volume, "open_time": pd.Timestamp(opened), "open_price": 1.0, "close_time": pd.Timestamp(closed), "close_price": 1.0, "profit": 0.0, "swap": 0.0, "commission": 0.0}

def test_merge_carry_over_position():
    positions = pd.DataFrame([_closed("1", "buy", "2026-01-01 00:00", "2026-01-01 00:02")])
    snapshots = pd.DataFrame([_closed("2", "sell", "2026-01-01 00:01", "2026-01-01 00:01"), _closed("2", "sell", "2026-01-01 00:01", "2026-01-01 00:01")]).drop(columns=["close_time", "close_price", "commission"])
    lifecycle, _, summary = merge_lifecycles(positions, snapshots)
    assert len(lifecycle) == 2 and summary["snapshot_rows_merged"] == 1

def test_unlock_and_rehedge_classification():
    positions = pd.DataFrame([_closed("b1", "buy", "2026-01-01 00:00", "2026-01-01 00:03"), _closed("s1", "sell", "2026-01-01 00:01", "2026-01-01 00:02"), _closed("s2", "sell", "2026-01-01 00:04", "2026-01-01 00:05")])
    lifecycle, _, _ = merge_lifecycles(positions, pd.DataFrame(columns=positions.columns))
    events, intervals, _ = reconstruct_states(lifecycle)
    assert "UNLOCK_TO_BUY" in set(events.behavior_type)
    assert "REHEDGE_SELL" in set(events.behavior_type)
    assert intervals.duration_seconds.sum() == (events.event_time.max() - events.event_time.min()).total_seconds()

def test_unlock_to_sell_and_rehedge_buy_classification():
    positions = pd.DataFrame([_closed("s1", "sell", "2026-01-01 00:00", "2026-01-01 00:03"), _closed("b1", "buy", "2026-01-01 00:01", "2026-01-01 00:02"), _closed("b2", "buy", "2026-01-01 00:04", "2026-01-01 00:05")])
    lifecycle, _, _ = merge_lifecycles(positions, pd.DataFrame(columns=positions.columns))
    events, _, _ = reconstruct_states(lifecycle)
    assert "UNLOCK_TO_SELL" in set(events.behavior_type)
    assert "REHEDGE_BUY" in set(events.behavior_type)

def test_same_second_ordering_is_marked_ambiguous():
    positions = pd.DataFrame([_closed("b1", "buy", "2026-01-01 00:00", "2026-01-01 00:02"), _closed("s1", "sell", "2026-01-01 00:00", "2026-01-01 00:03")])
    lifecycle, _, _ = merge_lifecycles(positions, pd.DataFrame(columns=positions.columns))
    events, _, exceptions = reconstruct_states(lifecycle)
    assert (events.ordering_quality == "ambiguous").any()
    assert "ambiguous_ordering" in set(exceptions.exception_type)

def test_multi_position_state_is_preserved():
    positions = pd.DataFrame([_closed("b1", "buy", "2026-01-01 00:00", "2026-01-01 00:05"), _closed("s1", "sell", "2026-01-01 00:01", "2026-01-01 00:05"), _closed("b2", "buy", "2026-01-01 00:02", "2026-01-01 00:04")])
    lifecycle, _, _ = merge_lifecycles(positions, pd.DataFrame(columns=positions.columns))
    events, _, _ = reconstruct_states(lifecycle)
    assert "MULTI_POSITION" in set(events.state_after)
