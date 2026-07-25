"""Deterministic reconstruction of position lifecycles and hedge states."""
from __future__ import annotations

from collections import Counter
import pandas as pd

LIFECYCLE_COLUMNS = ["position_id", "symbol", "side", "volume", "open_time", "open_price", "close_time", "close_price", "profit", "swap", "commission", "source_reports", "is_closed", "is_carry_over"]

def _state(active: dict[str, dict]) -> str:
    buys = [x for x in active.values() if x["side"] == "buy"]
    sells = [x for x in active.values() if x["side"] == "sell"]
    if not active: return "FLAT"
    if len(active) == 1: return "ONE_BUY" if buys else "ONE_SELL"
    if len(active) > 2: return "MULTI_POSITION"
    return "HEDGED_1X1" if len(buys) == len(sells) == 1 and buys[0]["volume"] == sells[0]["volume"] else "UNBALANCED_HEDGE"

def merge_lifecycles(positions: pd.DataFrame, snapshots: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    exceptions: list[dict] = []; rows: list[dict] = []
    closed = positions.copy(); closed["position_id"] = closed.position_id.astype(str)
    open_rows = snapshots.copy(); open_rows["position_id"] = open_rows.position_id.astype(str)
    if not closed.position_id.is_unique: exceptions.append({"exception_type": "duplicate_closed_position", "detail": "Closed Positions contains repeated IDs"})
    for _, item in closed.iterrows():
        rows.append({**item.to_dict(), "source_reports": item.report_id, "is_closed": True, "is_carry_over": False})
    for position_id, group in open_rows.groupby("position_id", sort=False):
        canonical = group.iloc[0]
        fields = ["symbol", "side", "volume", "open_time", "open_price"]
        if any(group[field].nunique(dropna=False) > 1 for field in fields):
            exceptions.append({"position_id": position_id, "exception_type": "open_snapshot_conflict", "detail": "Open Position snapshots disagree"}); continue
        if position_id in set(closed.position_id):
            # A later closed record completes this lifecycle; do not create a second open event.
            continue
        rows.append({**canonical.to_dict(), "close_time": pd.NaT, "close_price": None, "commission": 0.0, "source_reports": ",".join(sorted(group.report_id.astype(str).unique())), "is_closed": False, "is_carry_over": group.report_id.nunique() > 1})
    lifecycle = pd.DataFrame(rows)
    lifecycle = lifecycle[LIFECYCLE_COLUMNS].sort_values(["open_time", "position_id"], kind="stable").reset_index(drop=True)
    summary = {"closed_positions": int(lifecycle.is_closed.sum()), "open_positions": int((~lifecycle.is_closed).sum()), "snapshot_rows_merged": int(len(open_rows) - open_rows.position_id.nunique()), "carry_over_positions": int(lifecycle.is_carry_over.sum())}
    return lifecycle, pd.DataFrame(exceptions), summary

def reconstruct_states(lifecycle: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    events = []
    for row_index, row in lifecycle.reset_index(drop=True).iterrows():
        base = {"position_id": row.position_id, "side": row.side, "volume": row.volume, "source_report": row.source_reports, "row_tiebreak": row_index}
        events.append({**base, "event_time": row.open_time, "event_type": "POSITION_OPEN", "execution_price": row.open_price})
        if pd.notna(row.close_time): events.append({**base, "event_time": row.close_time, "event_type": "POSITION_CLOSE", "execution_price": row.close_price})
    timeline = pd.DataFrame(events).sort_values(["event_time", "row_tiebreak", "event_type"], kind="stable").reset_index(drop=True)
    active: dict[str, dict] = {}; output = []; exceptions = []; sequence = 0
    timestamp_counts = Counter(timeline.event_time)
    for _, event in timeline.iterrows():
        before = _state(active); buys_before = [x for x in active.values() if x["side"] == "buy"]; sells_before = [x for x in active.values() if x["side"] == "sell"]
        if event.event_type == "POSITION_OPEN": active[str(event.position_id)] = {"side": event.side, "volume": event.volume, "entry": event.execution_price}
        elif str(event.position_id) not in active:
            exceptions.append({"event_time": event.event_time, "position_id": event.position_id, "exception_type": "close_unknown_position", "detail": "Close encountered without an active position"})
        else: del active[str(event.position_id)]
        after = _state(active); buys_after = [x for x in active.values() if x["side"] == "buy"]; sells_after = [x for x in active.values() if x["side"] == "sell"]
        behavior = "UNCLASSIFIED"
        if event.event_type == "POSITION_OPEN":
            if before == "FLAT": behavior = "INITIAL_OPEN_BUY" if event.side == "buy" else "INITIAL_OPEN_SELL"
            elif before == "ONE_BUY" and after == "HEDGED_1X1" and event.side == "sell": behavior = "REHEDGE_SELL"
            elif before == "ONE_SELL" and after == "HEDGED_1X1" and event.side == "buy": behavior = "REHEDGE_BUY"
            else: behavior = "OPEN_ADDITIONAL_BUY" if event.side == "buy" else "OPEN_ADDITIONAL_SELL"
        elif before == "HEDGED_1X1" and after == "ONE_BUY" and event.side == "sell": behavior = "UNLOCK_TO_BUY"
        elif before == "HEDGED_1X1" and after == "ONE_SELL" and event.side == "buy": behavior = "UNLOCK_TO_SELL"
        elif after == "FLAT": behavior = "CLOSE_TO_FLAT"
        quality = "ambiguous" if timestamp_counts[event.event_time] > 1 else "deterministic"
        ordering_reason = "same_second_multiple_events" if quality == "ambiguous" else "unique_report_second"
        if quality == "ambiguous": exceptions.append({"event_time": event.event_time, "position_id": event.position_id, "exception_type": "ambiguous_ordering", "detail": "Multiple lifecycle events share this second; stable ID-based ordering used"})
        if quality == "ambiguous": accounting = "ambiguous_ordering"
        elif behavior in {"INITIAL_OPEN_BUY", "INITIAL_OPEN_SELL", "CLOSE_TO_FLAT"}: accounting = "boundary"
        elif "MULTI_POSITION" in {before, after}: accounting = "multi_position"
        elif "UNBALANCED_HEDGE" in {before, after}: accounting = "unbalanced_hedge"
        elif behavior in {"UNLOCK_TO_BUY", "UNLOCK_TO_SELL", "REHEDGE_BUY", "REHEDGE_SELL"}: accounting = "classified_standard"
        else: accounting = "unsupported"
        sequence += 1
        output.append({**event.to_dict(), "event_id": sequence, "event_sequence": sequence, "ordering_quality": quality, "ordering_reason": ordering_reason, "requires_tick_resolution": quality == "ambiguous", "eligible_for_exact_trigger_analysis": quality != "ambiguous", "accounting_category": accounting, "state_before": before, "state_after": after, "behavior_type": behavior, "active_before_count": len(buys_before) + len(sells_before), "active_after_count": len(active), "buy_count_before": len(buys_before), "sell_count_before": len(sells_before), "buy_count_after": len(buys_after), "sell_count_after": len(sells_after), "buy_volume_before": sum(x["volume"] for x in buys_before), "sell_volume_before": sum(x["volume"] for x in sells_before), "buy_volume_after": sum(x["volume"] for x in buys_after), "sell_volume_after": sum(x["volume"] for x in sells_after)})
    events_df = pd.DataFrame(output)
    intervals = []
    for index in range(len(events_df) - 1):
        row, next_row = events_df.iloc[index], events_df.iloc[index + 1]
        start, end = row.event_time, next_row.event_time
        if end < start: raise ValueError("State interval has negative duration")
        intervals.append({"interval_id": index + 1, "start_time": start, "end_time": end, "duration_seconds": (end - start).total_seconds(), "state": row.state_after, "buy_position_id": None, "buy_volume": row.buy_volume_after, "buy_entry": None, "sell_position_id": None, "sell_volume": row.sell_volume_after, "sell_entry": None, "preceding_event_type": row.behavior_type, "following_event_type": next_row.behavior_type})
    return events_df, pd.DataFrame(intervals), pd.DataFrame(exceptions)
