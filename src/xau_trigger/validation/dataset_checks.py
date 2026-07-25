import pandas as pd

def reconcile_report(positions: pd.DataFrame, reported_net_profit: float, tolerance: float = 0.01) -> dict:
    profit = float(positions.profit.sum()); swap = float(positions.swap.sum()); commission = float(positions.commission.sum())
    calculated = profit + swap + commission; delta = calculated - reported_net_profit
    return {"profit": profit, "swap": swap, "commission": commission, "calculated_net": calculated, "reported_net": reported_net_profit, "net_delta": delta, "status": "PASS" if abs(delta) <= tolerance else "FAIL"}

def inventory_conservation(positions: pd.DataFrame, tick_start, tick_end) -> dict:
    start = int(((positions.open_time <= tick_start) & (positions.close_time > tick_start)).sum())
    opens = int(positions.open_time.between(tick_start, tick_end).sum())
    closes = int(positions.close_time.between(tick_start, tick_end).sum())
    end = int(((positions.open_time <= tick_end) & (positions.close_time > tick_end)).sum())
    return {"active_at_start": start, "opens": opens, "closes": closes, "active_at_end": end, "equation_result": start + opens - closes, "status": "PASS" if start + opens - closes == end else "FAIL"}
