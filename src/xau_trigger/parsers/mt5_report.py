from pathlib import Path
import re
import pandas as pd
from lxml import html

def _num(value):
    value = value.strip().replace(",", "").replace(" ", "")
    if not value: return None
    try: return float(value)
    except ValueError: return None

def _text(cell): return " ".join(cell.text_content().split())
def _dt(value): return pd.to_datetime(value, format="%Y.%m.%d %H:%M:%S") if value else pd.NaT

def parse_report_summary(path: str | Path) -> dict:
    """Read only anonymous numerical report totals and generated timestamp."""
    path = Path(path); raw = path.read_bytes()
    text = raw.decode("utf-16") if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else raw.decode("utf-8")
    tree = html.fromstring(text); summary = {"report_id": path.stem}
    for row in tree.xpath("//tr"):
        values = [_text(c) for c in row.xpath("./th|./td")]
        if not values: continue
        if values[0] == "Date:" and len(values) > 1: summary["generated_at"] = str(pd.to_datetime(values[1], format="mixed"))
        if values[0] == "Total Net Profit:" and len(values) > 1: summary["reported_net_profit"] = _num(values[1])
    if "reported_net_profit" not in summary: raise ValueError(f"Missing Results / Total Net Profit in {path.name}")
    return summary

def parse_report(path: str | Path, report_id: str | None = None) -> dict[str, pd.DataFrame]:
    path = Path(path); report_id = report_id or path.stem
    raw = path.read_bytes()
    text = raw.decode("utf-16") if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else raw.decode("utf-8")
    tree = html.fromstring(text)
    section, seen, tables = None, set(), {k: [] for k in ("positions", "orders", "deals", "open_positions")}
    for row in tree.xpath("//tr"):
        cells = row.xpath("./th|./td"); values = [_text(c) for c in cells]
        joined = " ".join(values).strip().lower()
        if joined in {"positions", "orders", "deals", "open positions"}:
            section = joined.replace(" ", "_"); seen.add(section); continue
        if section not in tables or not values: continue
        if any(v.lower() in {"time", "position", "order", "deal"} for v in values) and len(values) < 5: continue
        if section == "open_positions" and len(values) >= 12 and re.match(r"\d{4}\.\d{2}", values[0]):
            tables[section].append(dict(report_id=report_id, position_id=values[1], symbol=values[2], side=values[3].lower(), volume=_num(values[4]), open_time=_dt(values[0]), open_price=_num(values[5]), stop_loss=_num(values[6]), take_profit=_num(values[7]), close_time=pd.NaT, close_price=None, commission=None, swap=_num(values[9]), profit=_num(values[10])))
        elif section == "positions" and len(values) >= 13 and re.match(r"\d{4}\.\d{2}", values[0]):
            if len(values) == 14 and not values[4]: values.pop(4)
            values = values[:13]
            tables[section].append(dict(report_id=report_id, position_id=values[1], symbol=values[2], side=values[3].lower(), volume=_num(values[4]), open_time=pd.to_datetime(values[0], format="%Y.%m.%d %H:%M:%S"), open_price=_num(values[5]), stop_loss=_num(values[6]), take_profit=_num(values[7]), close_time=pd.to_datetime(values[8], format="%Y.%m.%d %H:%M:%S") if values[8] else pd.NaT, close_price=_num(values[9]), commission=_num(values[10]), swap=_num(values[11]), profit=_num(values[12])))
        elif section == "orders" and len(values) >= 11 and re.match(r"\d{4}\.\d{2}", values[0]):
            parts = [part.strip() for part in values[4].split("/")]
            requested, filled = (parts + [None, None])[:2]
            tables[section].append(dict(report_id=report_id, order_id=values[1], open_time=_dt(values[0]), symbol=values[2], order_type=values[3].lower(), volume_requested=_num(requested), volume_filled=_num(filled), price=_num(values[5]), stop_loss=_num(values[6]), take_profit=_num(values[7]), completion_time=_dt(values[8]), state=values[9].lower(), comment=values[10]))
        elif section == "deals" and len(values) >= 15 and re.match(r"\d{4}\.\d{2}", values[0]):
            tables[section].append(dict(report_id=report_id, deal_id=values[1], time=_dt(values[0]), symbol=values[2], deal_type=values[3].lower(), direction=values[4].lower(), volume=_num(values[5]), price=_num(values[6]), order_id=values[7], commission=_num(values[9]), fee=_num(values[10]), swap=_num(values[11]), profit=_num(values[12]), balance=_num(values[13].replace(" ", "")), comment=values[14]))
    if not {"positions", "orders", "deals"}.issubset(seen): raise ValueError(f"Missing required MT5 sections in {path.name}")
    schemas = {"positions": ["report_id","position_id","symbol","side","volume","open_time","open_price","stop_loss","take_profit","close_time","close_price","commission","swap","profit"], "open_positions": ["report_id","position_id","symbol","side","volume","open_time","open_price","stop_loss","take_profit","close_time","close_price","commission","swap","profit"], "orders": ["report_id","order_id","open_time","symbol","order_type","volume_requested","volume_filled","price","stop_loss","take_profit","completion_time","state","comment"], "deals": ["report_id","deal_id","time","symbol","deal_type","direction","volume","price","order_id","commission","fee","swap","profit","balance","comment"]}
    return {k: pd.DataFrame(v, columns=schemas[k]) for k, v in tables.items()}
