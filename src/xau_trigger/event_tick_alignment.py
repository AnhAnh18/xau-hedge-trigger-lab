"""Deterministic, provenance-preserving alignment of MT5 lifecycle events to ticks."""
from __future__ import annotations

import pandas as pd

def quote_column(event_type: str, side: str) -> str:
    if (event_type == "POSITION_OPEN" and side == "buy") or (event_type == "POSITION_CLOSE" and side == "sell"): return "ask"
    return "bid"

def _tier(reported: pd.Timestamp, candidate: pd.Timestamp) -> str:
    delta = (candidate - reported).total_seconds()
    if 0 <= delta < 1: return "A"
    if -1 <= delta < 2: return "B"
    return "C"

def align_events(events: pd.DataFrame, ticks: pd.DataFrame, max_price_error: float = 0.50) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ticks = ticks.sort_values("timestamp", kind="stable").reset_index(drop=True)
    coverage_start, coverage_end = ticks.timestamp.min(), ticks.timestamp.max()
    overlap = events[events.event_time.between(coverage_start, coverage_end)].copy()
    candidate_rows, aligned_rows = [], []
    for _, event in overlap.iterrows():
        start, end = event.event_time - pd.Timedelta(seconds=2), event.event_time + pd.Timedelta(seconds=3)
        candidates = ticks[(ticks.timestamp >= start) & (ticks.timestamp < end)].copy()
        quote = quote_column(event.event_type, event.side)
        candidates["matched_quote"] = candidates[quote]
        candidates["price_error"] = (candidates.matched_quote - event.execution_price).abs()
        candidates["time_error_ms"] = ((candidates.timestamp - event.event_time).dt.total_seconds() * 1000).round().astype("int64")
        candidates["match_tier"] = candidates.timestamp.map(lambda value: _tier(event.event_time, value))
        candidates["event_id"] = event.event_id
        candidates["quote_side"] = quote
        ordered = candidates.assign(_tier_rank=candidates.match_tier.map({"A": 0, "B": 1, "C": 2})).sort_values(["_tier_rank", "price_error", "time_error_ms", "time_msc"], key=lambda series: series.abs() if series.name == "time_error_ms" else series, kind="stable")
        candidates["candidate_rank"] = 0
        candidates.loc[ordered.index, "candidate_rank"] = range(1, len(ordered) + 1)
        candidate_rows.append(candidates[["event_id", "timestamp", "time_msc", "bid", "ask", "matched_quote", "quote_side", "price_error", "time_error_ms", "match_tier", "candidate_rank"]])
        if candidates.empty:
            aligned_rows.append(_unmatched(event, "no_ticks_in_search_window")); continue
        ranked = candidates.sort_values(["match_tier", "price_error", "time_error_ms", "time_msc"], key=lambda series: series.map({"A": 0, "B": 1, "C": 2}) if series.name == "match_tier" else series.abs() if series.name == "time_error_ms" else series, kind="stable")
        best = ranked.iloc[0]; near_equal = ranked[(ranked.match_tier == best.match_tier) & (ranked.price_error == best.price_error) & (ranked.time_error_ms.abs() == abs(best.time_error_ms))]
        quality = "HIGH" if best.match_tier == "A" and best.price_error <= 0.01 and len(near_equal) == 1 else "MEDIUM" if best.match_tier in {"A", "B"} and best.price_error <= 0.05 and len(near_equal) == 1 else "LOW" if best.price_error <= max_price_error and len(near_equal) == 1 else "AMBIGUOUS" if best.price_error <= max_price_error else "UNMATCHED"
        if quality == "UNMATCHED": aligned_rows.append(_unmatched(event, "price_error_above_threshold", len(candidates))); continue
        state_ok = event.state_before in {"HEDGED_1X1", "ONE_BUY", "ONE_SELL"} or event.state_after in {"HEDGED_1X1", "ONE_BUY", "ONE_SELL"}
        primary = bool(event.volume == 0.3 and event.accounting_category == "classified_standard" and state_ok and quality in {"HIGH", "MEDIUM"})
        aligned_rows.append({**event.to_dict(), "reported_time": event.event_time, "matched_time_msc": int(best.time_msc), "matched_timestamp": best.timestamp, "matched_bid": best.bid, "matched_ask": best.ask, "matched_quote": best.matched_quote, "time_error_ms": int(best.time_error_ms), "price_error": float(best.price_error), "candidate_count": len(candidates), "match_tier": best.match_tier, "match_quality": quality, "match_method": "quote_price_then_time", "m2_ordering_quality": event.ordering_quality, "m3_ordering_quality": "resolved" if event.ordering_quality == "ambiguous" and quality in {"HIGH", "MEDIUM"} else "still_ambiguous" if event.ordering_quality == "ambiguous" else "not_applicable", "sequence_resolution_method": "tick_quote_alignment" if event.ordering_quality == "ambiguous" and quality in {"HIGH", "MEDIUM"} else None, "is_primary_trigger_sample": primary, "unmatched_reason": None})
    aligned = pd.DataFrame(aligned_rows)
    candidates = pd.concat(candidate_rows, ignore_index=True) if candidate_rows else pd.DataFrame()
    # Same-second resolution is only accepted when all aligned events have distinct high/medium tick timestamps.
    for _, group in aligned[aligned.m2_ordering_quality == "ambiguous"].groupby("reported_time"):
        resolvable = len(group) > 1 and group.match_quality.isin(["HIGH", "MEDIUM"]).all() and group.matched_time_msc.nunique() == len(group)
        aligned.loc[group.index, "m3_ordering_quality"] = "resolved" if resolvable else "still_ambiguous"
        aligned.loc[group.index, "sequence_resolution_method"] = "tick_quote_alignment" if resolvable else None
        if resolvable:
            ordered_index = group.sort_values("matched_time_msc").index
            aligned.loc[ordered_index, "m3_resolved_sequence"] = range(1, len(ordered_index) + 1)
    unmatched = aligned[aligned.match_quality == "UNMATCHED"].copy()
    return aligned, candidates, unmatched

def _unmatched(event: pd.Series, reason: str, candidate_count: int = 0) -> dict:
    return {**event.to_dict(), "reported_time": event.event_time, "matched_time_msc": None, "matched_timestamp": pd.NaT, "matched_bid": None, "matched_ask": None, "matched_quote": None, "time_error_ms": None, "price_error": None, "candidate_count": candidate_count, "match_tier": None, "match_quality": "UNMATCHED", "match_method": None, "m2_ordering_quality": event.ordering_quality, "m3_ordering_quality": "still_ambiguous" if event.ordering_quality == "ambiguous" else "not_applicable", "m3_resolved_sequence": None, "sequence_resolution_method": None, "is_primary_trigger_sample": False, "unmatched_reason": reason}
