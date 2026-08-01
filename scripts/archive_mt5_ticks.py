"""Bounded, read-only archival export of XAUUSD ticks from MT5."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import MetaTrader5 as mt5


TERMINAL_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"
SYMBOL = "XAUUSD"
CASE_ID = "mt5-ticks-20260801"
RUN_ID = "run-20260801T" + datetime.now(timezone.utc).strftime("%H%M%S")
ROOT = Path(r"D:\Claude\1xau-hedge-trigger-lab\data\raw\passview_quarantine")
RUN_DIR = ROOT / CASE_ID / RUN_ID
INCOMING_DIR = RUN_DIR / "incoming"
MANIFEST_DIR = RUN_DIR / "manifests"
START = datetime(2025, 11, 1, tzinfo=timezone.utc)
END = datetime(2026, 8, 1, tzinfo=timezone.utc)
SLICE = timedelta(minutes=15)
MAX_TICKS_PER_REQUEST = 100_000


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_week(week_start: datetime, week_end: datetime) -> dict:
    alias = f"XAUUSD_ticks_{week_start:%Y-%m-%d}_to_{week_end:%Y-%m-%d}.csv"
    destination = INCOMING_DIR / alias
    partial = destination.with_suffix(destination.suffix + ".partial")
    if destination.exists() or partial.exists():
        raise RuntimeError(f"Refusing to overwrite existing tick export: {alias}")

    rows = 0
    with partial.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("time_utc", "bid", "ask", "last", "volume", "flags", "volume_real"))
        cursor = week_start
        while cursor < week_end:
            slice_end = min(cursor + SLICE, week_end)
            ticks = mt5.copy_ticks_range(SYMBOL, cursor, slice_end - timedelta(microseconds=1), mt5.COPY_TICKS_ALL)
            if ticks is None:
                raise RuntimeError(f"MT5 tick request failed at {cursor.isoformat()}: {mt5.last_error()[0]}")
            if len(ticks) >= MAX_TICKS_PER_REQUEST:
                raise RuntimeError(f"Tick API limit reached at {cursor.isoformat()}; reduce slice size before retrying")
            start_ms = int(cursor.timestamp() * 1000)
            end_ms = int(slice_end.timestamp() * 1000)
            for tick in ticks:
                tick_ms = int(tick["time_msc"])
                if start_ms <= tick_ms < end_ms:
                    timestamp = datetime.fromtimestamp(tick_ms / 1000, tz=timezone.utc)
                    writer.writerow(
                        (
                            timestamp.isoformat(timespec="milliseconds"),
                            repr(float(tick["bid"])),
                            repr(float(tick["ask"])),
                            repr(float(tick["last"])),
                            repr(float(tick["volume"])),
                            int(tick["flags"]),
                            repr(float(tick["volume_real"])),
                        )
                    )
                    rows += 1
            cursor = slice_end

    source_hash = sha256_file(partial)
    partial.replace(destination)
    destination_hash = sha256_file(destination)
    if source_hash != destination_hash:
        raise RuntimeError(f"Hash mismatch for {alias}")
    return {
        "alias": alias,
        "relative_path": f"incoming/{alias}",
        "source_class": "mt5_python_tick_export",
        "bytes": destination.stat().st_size,
        "source_sha256": source_hash,
        "destination_sha256": destination_hash,
        "transfer_status": "accepted",
    }


def main() -> int:
    if RUN_DIR.exists():
        raise RuntimeError("Archive run directory already exists")
    INCOMING_DIR.mkdir(parents=True)
    MANIFEST_DIR.mkdir(parents=True)
    if not mt5.initialize(path=TERMINAL_PATH):
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()[0]}")

    objects = []
    try:
        if not mt5.symbol_select(SYMBOL, True):
            raise RuntimeError("XAUUSD symbol selection failed")
        week_start = START
        while week_start < END:
            week_end = min(week_start + timedelta(days=7), END)
            objects.append(write_week(week_start, week_end))
            checkpoint = MANIFEST_DIR / f"checkpoint-{len(objects):03d}.json"
            checkpoint.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "record_type": "archive_checkpoint",
                        "archival_run_id": RUN_ID,
                        "object": objects[-1],
                    },
                    ensure_ascii=True,
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            print(json.dumps({"completed": len(objects), "alias": objects[-1]["alias"], "bytes": objects[-1]["bytes"]}))
            week_start = week_end
    finally:
        mt5.shutdown()

    payload = {
        "manifest_schema_version": 1,
        "archival_run_id": RUN_ID,
        "capture_time_utc": datetime.now(timezone.utc).isoformat(),
        "source_scope": "owner-authorized read-only MT5 XAUUSD tick export for 2025-11 through 2026-07, split into weekly objects",
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
        "source_scope": "owner-authorized read-only MT5 XAUUSD tick export for 2025-11 through 2026-07, split into weekly objects",
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
