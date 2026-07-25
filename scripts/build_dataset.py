from pathlib import Path
import json, sys
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from xau_trigger.parsers.mt5_report import parse_report, parse_report_summary
from xau_trigger.parsers.tick_export import parse_ticks
from xau_trigger.validation.dataset_checks import inventory_conservation, reconcile_report

def write_table(df, path):
    try: df.to_parquet(path, index=False)
    except ImportError as e: raise RuntimeError("Parquet output requires pyarrow or fastparquet; install project dependencies first") from e

def main():
    raw = ROOT / "data" / "raw"; interim = ROOT / "data" / "interim"; out = ROOT / "reports" / "phase_01"; interim.mkdir(parents=True, exist_ok=True); out.mkdir(parents=True, exist_ok=True)
    reports = sorted((raw / "trades").glob("*.html")); ticks = sorted((raw / "ticks").glob("*.csv"))
    if not reports or not ticks: raise SystemExit("Missing raw HTML reports or tick CSV under data/raw")
    tables = {k: [] for k in ("positions", "orders", "deals", "open_positions")}; reconciliations = []
    for p in reports:
        parsed = parse_report(p)
        for k, df in parsed.items(): tables[k].append(df)
        summary = parse_report_summary(p)
        reconciliations.append({"report_id": summary["report_id"], "positions": len(parsed["positions"]), "orders": len(parsed["orders"]), "deals": len(parsed["deals"]), **reconcile_report(parsed["positions"], summary["reported_net_profit"])})
    for k, frames in tables.items(): write_table(pd.concat(frames, ignore_index=True), interim / f"{k}.parquet")
    tick = parse_ticks(ticks[0]); write_table(tick, interim / "ticks.parquet")
    positions = pd.concat(tables["positions"], ignore_index=True)
    conservation = inventory_conservation(positions, tick.timestamp.min(), tick.timestamp.max())
    deals = pd.concat(tables["deals"], ignore_index=True); orders = pd.concat(tables["orders"], ignore_index=True)
    deal_groups = deals.groupby(["deal_type", "direction", "symbol", "volume"], dropna=False).size().reset_index(name="count").to_dict("records")
    out_by = int((deals.direction == "out by").sum())
    out_by_orders = int(deals.loc[deals.direction == "out by", "order_id"].nunique())
    open_snapshots = pd.concat(tables["open_positions"], ignore_index=True)
    integrity = {"position_id_unique": bool(positions.position_id.is_unique), "order_id_unique": bool(orders.order_id.is_unique), "deal_id_unique": bool(deals.deal_id.is_unique), "closed_position_time_order": bool((positions.close_time.dropna() >= positions.loc[positions.close_time.notna(), "open_time"]).all()), "position_open_snapshot_overlap": int(len(set(positions.position_id) & set(open_snapshots.position_id))), "required_volumes_present": all(volume in set(positions.volume) for volume in (0.2, 0.3, 1.0))}
    overlap = {"tick_first": str(tick.timestamp.min()), "tick_last": str(tick.timestamp.max()), **conservation}
    report = {"reports": len(reports), "positions": len(positions), "orders": len(orders), "deals": len(deals), "open_position_snapshots": sum(len(x) for x in tables["open_positions"]), "deal_order_difference": len(deals) - len(orders), "deal_order_explanation": f"{out_by} 'out by' deals map to {out_by_orders} orders; each of those orders produces two deal rows, explaining the net {len(deals) - len(orders)} additional deals.", "deal_groups": deal_groups, "per_report_reconciliation": reconciliations, "integrity_checks": integrity, "ticks": len(tick), "missing_quote_updates": tick.attrs.get("missing_quote_updates", {}), "duplicate_time_msc": int(tick.time_msc.duplicated().sum()), "symbols": sorted(positions.symbol.dropna().unique().tolist()), "volume_distribution": positions.volume.value_counts().sort_index().to_dict(), "earliest_trade": str(positions.open_time.min()), "latest_trade": str(positions.close_time.max()), "total_profit": float(positions.profit.sum()), "total_swap": float(positions.swap.sum()), "spread_min": float(tick.spread.min()), "spread_max": float(tick.spread.max()), "spread_mean": float(tick.spread.mean()), "trade_tick_overlap": overlap}
    if any(item["status"] != "PASS" for item in reconciliations) or conservation["status"] != "PASS" or not all(value is not False for value in integrity.values()): raise RuntimeError("Financial, inventory, or identifier reconciliation failed")
    (out / "normalized_dataset_report.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    lines = ["# Normalized Dataset Report", "", "## Per-report financial reconciliation", "", "| Report | Positions | Orders | Deals | Profit delta | Status |", "| --- | ---: | ---: | ---: | ---: | --- |"]
    lines += [f"| {x['report_id']} | {x['positions']} | {x['orders']} | {x['deals']} | {x['net_delta']:.2f} | {x['status']} |" for x in reconciliations]
    lines += ["", "## Reconciliation notes", "", f"- {report['deal_order_explanation']}", f"- Position inventory during tick coverage: {conservation['active_at_start']} + {conservation['opens']} - {conservation['closes']} = {conservation['active_at_end']} ({conservation['status']}).", "", "## Dataset summary", ""]
    lines += [f"- **{k}**: {v}" for k, v in report.items() if k not in {"per_report_reconciliation", "deal_groups"}]
    (out / "normalized_dataset_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

if __name__ == "__main__": main()
