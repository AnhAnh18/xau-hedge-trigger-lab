"""Archive monthly XAUUSD M1 bars through the already logged-in MT5 terminal."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5


TERMINAL_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"
SYMBOL = "XAUUSD"
CASE_ID = "mt5-m1-bars-20260801"
RUN_ID = "run-20260801T" + datetime.now(timezone.utc).strftime("%H%M%S")
CASE_DIR = Path(r"D:\Claude\1xau-hedge-trigger-lab\data\raw\passview_quarantine") / CASE_ID
RUN_DIR = CASE_DIR / RUN_ID
INCOMING_DIR = RUN_DIR / "incoming"
MANIFEST_DIR = RUN_DIR / "manifests"


MONTHS = [
    ("2025-11", datetime(2025, 11, 1, tzinfo=timezone.utc), datetime(2025, 12, 1, tzinfo=timezone.utc)),
    ("2025-12", datetime(2025, 12, 1, tzinfo=timezone.utc), datetime(2026, 1, 1, tzinfo=timezone.utc)),
    ("2026-01", datetime(2026, 1, 1, tzinfo=timezone.utc), datetime(2026, 2, 1, tzinfo=timezone.utc)),
    ("2026-02", datetime(2026, 2, 1, tzinfo=timezone.utc), datetime(2026, 3, 1, tzinfo=timezone.utc)),
    ("2026-03", datetime(2026, 3, 1, tzinfo=timezone.utc), datetime(2026, 4, 1, tzinfo=timezone.utc)),
    ("2026-04", datetime(2026, 4, 1, tzinfo=timezone.utc), datetime(2026, 5, 1, tzinfo=timezone.utc)),
    ("2026-05", datetime(2026, 5, 1, tzinfo=timezone.utc), datetime(2026, 6, 1, tzinfo=timezone.utc)),
    ("2026-06", datetime(2026, 6, 1, tzinfo=timezone.utc), datetime(2026, 7, 1, tzinfo=timezone.utc)),
    ("2026-07", datetime(2026, 7, 1, tzinfo=timezone.utc), datetime(2026, 8, 1, tzinfo=timezone.utc)),
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_payload(path: Path, rows) -> None:
    digits = int(mt5.symbol_info(SYMBOL).digits)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("time", "open", "high", "low", "close", "tick_volume", "spread", "real_volume"))
        for row in rows:
            timestamp = datetime.fromtimestamp(int(row["time"]), tz=timezone.utc)
            writer.writerow(
                (
                    timestamp.strftime("%Y-%m-%d %H:%M"),
                    f'{float(row["open"]):.{digits}f}',
                    f'{float(row["high"]):.{digits}f}',
                    f'{float(row["low"]):.{digits}f}',
                    f'{float(row["close"]):.{digits}f}',
                    int(row["tick_volume"]),
                    int(row["spread"]),
                    int(row["real_volume"]),
                )
            )


def main() -> int:
    if RUN_DIR.exists():
        raise RuntimeError("Archive run directory already exists")
    if not CASE_DIR.parent.exists():
        raise RuntimeError("Quarantine root is missing")
    INCOMING_DIR.mkdir(parents=True)
    MANIFEST_DIR.mkdir(parents=True)

    if not mt5.initialize(path=TERMINAL_PATH):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()[0]}")

    objects = []
    try:
        if not mt5.symbol_select(SYMBOL, True):
            raise RuntimeError("XAUUSD symbol selection failed")
        symbol_info = mt5.symbol_info(SYMBOL)
        if symbol_info is None:
            raise RuntimeError("XAUUSD symbol metadata unavailable")

        fetched = []
        for label, start, end in MONTHS:
            rates = mt5.copy_rates_range(SYMBOL, mt5.TIMEFRAME_M1, start, end - timedelta(seconds=1))
            if rates is None or len(rates) == 0:
                raise RuntimeError(f"No M1 history returned for {label}")
            first_ts = int(rates[0]["time"])
            last_ts = int(rates[-1]["time"])
            if first_ts > int(start.timestamp()) + 4 * 86400 or last_ts < int(end.timestamp()) - 4 * 86400:
                raise RuntimeError(f"Incomplete M1 history range for {label}")
            fetched.append((label, rates))

        for label, rates in fetched:
            alias = f"XAUUSD_M1_{label}.csv"
            destination = INCOMING_DIR / alias
            partial = destination.with_suffix(destination.suffix + ".partial")
            write_payload(partial, rates)
            source_hash = sha256_file(partial)
            partial.replace(destination)
            destination_hash = sha256_file(destination)
            if source_hash != destination_hash:
                raise RuntimeError(f"Hash mismatch for {label}")
            objects.append(
                {
                    "alias": alias,
                    "relative_path": f"incoming/{alias}",
                    "source_class": "mt5_python_m1_export",
                    "bytes": destination.stat().st_size,
                    "source_sha256": source_hash,
                    "destination_sha256": destination_hash,
                    "transfer_status": "accepted",
                }
            )
    finally:
        mt5.shutdown()

    payload = {
        "manifest_schema_version": 1,
        "archival_run_id": RUN_ID,
        "capture_time_utc": datetime.now(timezone.utc).isoformat(),
        "source_scope": "owner-authorized read-only MT5 XAUUSD M1 export for 2025-11 through 2026-07",
        "transfer_status": "accepted",
        "objects": objects,
    }
    payload_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    manifest = {
        "manifest_schema_version": 1,
        "manifest_sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        "payload": payload,
    }
    (MANIFEST_DIR / "archive-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=True, separators=(",", ":")), encoding="utf-8"
    )
    note = {
        "schema_version": 1,
        "record_type": "archive_authorization_transfer_note",
        "case_id": CASE_ID,
        "archival_run_id": RUN_ID,
        "authorization_basis": "Owner request in the current thread",
        "authorization_date": "2026-08-01",
        "source_scope": "owner-authorized read-only MT5 XAUUSD M1 export for 2025-11 through 2026-07",
        "retention_policy": "Retain until owner directs a specific retention change or deletion",
        "credential_material_not_intentionally_collected": True,
        "m5_firewall": "quarantine_only; never reference by an M5 input manifest",
        "raw_rows_printed": False,
    }
    (MANIFEST_DIR / "authorization-transfer-note.json").write_text(
        json.dumps(note, ensure_ascii=True, separators=(",", ":")), encoding="utf-8"
    )
    print(json.dumps({"run_id": RUN_ID, "objects": len(objects), "bytes": sum(item["bytes"] for item in objects), "manifest_sha256": manifest["manifest_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
