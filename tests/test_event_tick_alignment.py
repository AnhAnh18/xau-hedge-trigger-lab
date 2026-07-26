import pandas as pd
from xau_trigger.event_tick_alignment import align_events, quote_column

def _event(event_id, event_type, side, price, when="2026-07-23 12:00:00"):
    return {"event_id": event_id, "event_time": pd.Timestamp(when), "event_type": event_type, "side": side, "execution_price": price, "volume": 0.3, "ordering_quality": "deterministic", "accounting_category": "classified_standard", "state_before": "ONE_BUY", "state_after": "HEDGED_1X1"}

def _ticks():
    return pd.DataFrame({"timestamp": pd.to_datetime(["2026-07-23 11:59:59.900", "2026-07-23 12:00:00.100", "2026-07-23 12:00:01.100", "2026-07-23 12:00:03.100"]), "time_msc": [1, 2, 3, 4], "bid": [100.0, 100.1, 100.2, 100.2], "ask": [100.2, 100.3, 100.4, 100.4]})

def test_quote_side_mapping():
    assert quote_column("POSITION_OPEN", "buy") == "ask"
    assert quote_column("POSITION_OPEN", "sell") == "bid"
    assert quote_column("POSITION_CLOSE", "buy") == "bid"
    assert quote_column("POSITION_CLOSE", "sell") == "ask"

def test_buy_open_matches_ask_in_exact_second():
    aligned, _, _ = align_events(pd.DataFrame([_event(1, "POSITION_OPEN", "buy", 100.3)]), _ticks())
    assert aligned.iloc[0].matched_quote == 100.3 and aligned.iloc[0].match_tier == "A"

def test_fallback_and_large_price_error():
    events = pd.DataFrame([_event(1, "POSITION_OPEN", "sell", 100.2, "2026-07-23 12:00:02"), _event(2, "POSITION_CLOSE", "buy", 999.0)])
    aligned, _, unmatched = align_events(events, _ticks())
    assert aligned.iloc[0].match_tier == "B"
    assert aligned.iloc[1].match_quality == "UNMATCHED" and len(unmatched) == 1

def test_alignment_is_deterministic():
    events = pd.DataFrame([_event(1, "POSITION_OPEN", "buy", 100.3)])
    first, _, _ = align_events(events, _ticks()); second, _, _ = align_events(events, _ticks())
    assert first[["matched_time_msc", "match_quality"]].equals(second[["matched_time_msc", "match_quality"]])
