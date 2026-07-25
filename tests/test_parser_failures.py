from pathlib import Path
import pytest
from src.xau_trigger.parsers.mt5_report import parse_report
from src.xau_trigger.parsers.tick_export import parse_ticks

def test_missing_required_section_fails_cleanly(tmp_path):
    path = tmp_path / "bad.html"; path.write_text("<table><tr><th>Positions</th></tr></table>")
    with pytest.raises(ValueError, match="Missing required MT5 sections"): parse_report(path)

def test_duplicate_tick_timestamp_is_preserved(tmp_path):
    path = tmp_path / "ticks.tsv"; path.write_text("<DATE>\t<TIME>\t<BID>\t<ASK>\t<LAST>\t<VOLUME>\t<FLAGS>\n2026.07.23\t12:00:00.000\t1\t2\t1\t1\t4\n2026.07.23\t12:00:00.000\t1\t2\t1\t1\t4\n")
    assert len(parse_ticks(path)) == 2
