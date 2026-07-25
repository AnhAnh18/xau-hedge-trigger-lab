"""Inventory private raw data without copying it into reports."""
from __future__ import annotations

import csv, hashlib, json, re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "reports" / "phase_01"

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def audit_csv(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        sample = f.read(4096)
        f.seek(0)
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        reader = csv.DictReader(f, dialect=dialect)
        columns = reader.fieldnames or []
        normalized = {column: column.strip().strip("<>").lower() for column in columns}
        rows, timestamps, bad_spread, zero_quotes, duplicates = 0, [], 0, 0, 0
        previous = None
        for row in reader:
            rows += 1
            date_key = next((k for k in columns if normalized[k] == "date"), None)
            time_key = next((k for k in columns if normalized[k] == "time"), None)
            stamp = " ".join(filter(None, (row.get(date_key) if date_key else None, row.get(time_key) if time_key else None)))
            if not stamp:
                stamp = next((row.get(k) for k in columns if normalized[k] in {"timestamp", "datetime"}), None)
            if stamp:
                timestamps.append(stamp)
                if stamp == previous: duplicates += 1
                previous = stamp
            try:
                bid = float(next(row[k] for k in columns if normalized[k] == "bid"))
                ask = float(next(row[k] for k in columns if normalized[k] == "ask"))
                if bid == 0 or ask == 0: zero_quotes += 1
                if ask < bid: bad_spread += 1
            except (StopIteration, TypeError, ValueError):
                pass
    return {"rows": rows, "columns": columns, "first_timestamp": timestamps[0] if timestamps else None,
            "last_timestamp": timestamps[-1] if timestamps else None, "duplicate_timestamps": duplicates,
            "zero_bid_or_ask": zero_quotes, "ask_below_bid": bad_spread}

def main() -> None:
    files = sorted(p for p in RAW.rglob("*") if p.is_file()) if RAW.exists() else []
    result = {"root": str(RAW), "files": []}
    for path in files:
        item = {"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": digest(path)}
        if path.suffix.lower() == ".csv": item["tick_audit"] = audit_csv(path)
        elif path.suffix.lower() in {".html", ".htm"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            item["report_sections"] = {name: bool(re.search(rf"\b{name}\b", text, re.I)) for name in ("Positions", "Orders", "Deals")}
        result["files"].append(item)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "data_audit.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    audited = [item for item in result["files"] if "tick_audit" in item or "report_sections" in item]
    lines = ["# Data Audit", "", f"Files discovered: {len(files)}; data files audited: {len(audited)}", ""]
    for item in audited: lines.append(f"- `{item['path']}` — {item['bytes']} bytes — SHA-256 `{item['sha256']}`")
    (OUT / "data_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Audited {len(files)} raw file(s). Reports written to {OUT.relative_to(ROOT)}")

if __name__ == "__main__": main()
