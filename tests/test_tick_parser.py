from pathlib import Path
from src.xau_trigger.parsers.tick_export import parse_ticks

def test_tick_parser():
    df = parse_ticks(Path(__file__).parent / "fixtures" / "ticks_minimal.tsv")
    assert len(df) == 3 and df.iloc[0].time_msc < df.iloc[-1].time_msc
    assert (df.spread > 0).all() and df.iloc[0].mid == 4000.10
