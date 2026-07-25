import pandas as pd
from src.xau_trigger.validation.dataset_checks import inventory_conservation, reconcile_report

def test_report_financial_reconciliation():
    positions = pd.DataFrame({"profit": [6.0], "swap": [0.0], "commission": [0.0]})
    assert reconcile_report(positions, 6.0)["status"] == "PASS"

def test_position_inventory_conservation():
    positions = pd.DataFrame({"open_time": pd.to_datetime(["2026-07-23 11:59", "2026-07-23 12:01"]), "close_time": pd.to_datetime(["2026-07-23 12:02", "2026-07-23 12:03"])})
    result = inventory_conservation(positions, pd.Timestamp("2026-07-23 12:00"), pd.Timestamp("2026-07-23 12:04"))
    assert result["status"] == "PASS" and result["active_at_start"] == 1
