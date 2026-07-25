from pathlib import Path
from src.xau_trigger.parsers.mt5_report import parse_report, parse_report_summary

def test_mt5_report_parser():
    tables = parse_report(Path(__file__).parent / "fixtures" / "mt5_report_minimal.html")
    assert len(tables["positions"]) == 2
    assert set(tables["positions"].side) == {"buy", "sell"}
    assert set(tables["positions"].volume) == {0.3, 1.0}
    assert len(tables["orders"]) == 1 and len(tables["deals"]) == 1 and len(tables["open_positions"]) == 1
    assert parse_report_summary(Path(__file__).parent / "fixtures" / "mt5_report_minimal.html")["reported_net_profit"] == 6.0
