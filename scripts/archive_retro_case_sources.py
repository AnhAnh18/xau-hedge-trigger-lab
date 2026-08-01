"""Copy a bounded RETRO case source set into an append-only quarantine run."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(r"D:\Claude\1xau-hedge-trigger-lab")
QUARANTINE_ROOT = ROOT / "data" / "raw" / "passview_quarantine"
CASE_ID = "retro-001-20260731"
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
SENSITIVE_NAME_TOKENS = ("credential", "password", "secret", "token", "cookie", "private", "key")
EXPECTED_SOURCE_SHA256 = {
    "report-001.html": "0640f4b54a9fe7d40a03ae467eff600a2c675bfbb427fc4fe64373cb51f912f9",
    "ticks-001.csv": "ac319c2c17b5b23d395d0e00dd80631b76cf61a9def4473cb06517c09f2bd180",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _preflight_source(source: Path, alias: str) -> str:
    if not source.is_file():
        raise FileNotFoundError(f"Source file is missing for alias: {alias}")
    if source.suffix.lower() != Path(alias).suffix:
        raise ValueError(f"Source suffix is not allowed for alias: {alias}")
    if any(token in source.name.lower() for token in SENSITIVE_NAME_TOKENS):
        raise ValueError(f"Credential-like source name rejected for alias: {alias}")
    try:
        source.resolve().relative_to(QUARANTINE_ROOT.resolve())
    except ValueError as error:
        raise ValueError(f"Source is outside the approved quarantine for alias: {alias}") from error
    source_sha256 = sha256_file(source)
    if source_sha256 != EXPECTED_SOURCE_SHA256[alias]:
        raise ValueError(f"Source hash is not the approved RETRO-001 object: {alias}")
    return source_sha256


def copy_object(source: Path, destination: Path, alias: str, source_class: str) -> dict:
    if destination.exists() or destination.with_suffix(destination.suffix + ".partial").exists():
        raise RuntimeError(f"Refusing to overwrite archive object: {destination.name}")

    source_sha256 = _preflight_source(source, alias)
    partial = destination.with_suffix(destination.suffix + ".partial")
    with source.open("rb") as source_handle, partial.open("xb") as destination_handle:
        shutil.copyfileobj(source_handle, destination_handle, length=1024 * 1024)
    destination_sha256 = sha256_file(partial)
    if source_sha256 != destination_sha256:
        raise RuntimeError(f"Hash mismatch for {alias}")
    partial.replace(destination)
    return {
        "alias": alias,
        "relative_path": f"incoming/{alias}",
        "source_class": source_class,
        "bytes": destination.stat().st_size,
        "source_sha256": source_sha256,
        "destination_sha256": destination_sha256,
        "transfer_status": "accepted",
    }


def _require_ignored(path: Path) -> None:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", str(path.relative_to(ROOT))],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("RETRO quarantine destination is not ignored")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-source", type=Path, required=True)
    parser.add_argument("--tick-source", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()

    if not RUN_ID_PATTERN.fullmatch(args.run_id):
        raise ValueError("run-id must be a simple archive token without path separators")
    run_dir = QUARANTINE_ROOT / CASE_ID / args.run_id
    if run_dir.resolve().parent != (QUARANTINE_ROOT / CASE_ID).resolve():
        raise ValueError("run-id resolves outside the RETRO case quarantine directory")
    incoming_dir = run_dir / "incoming"
    manifest_dir = run_dir / "manifests"
    if run_dir.exists():
        raise RuntimeError(f"Archive run already exists: {args.run_id}")
    _require_ignored(run_dir)
    incoming_dir.mkdir(parents=True)
    manifest_dir.mkdir(parents=True)

    objects = [
        copy_object(
            args.report_source,
            incoming_dir / "report-001.html",
            "report-001.html",
            "retained_mt5_report_export",
        ),
        copy_object(
            args.tick_source,
            incoming_dir / "ticks-001.csv",
            "ticks-001.csv",
            "retained_mt5_xauusd_tick_export",
        ),
    ]
    payload = {
        "manifest_schema_version": 1,
        "archival_run_id": args.run_id,
        "capture_time_utc": datetime.now(timezone.utc).isoformat(),
        "source_scope": "owner-authorized RETRO-001 2026-07-31 report and XAUUSD tick case sources",
        "transfer_status": "accepted",
        "objects": objects,
    }
    payload_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    manifest = {
        "manifest_schema_version": 1,
        "manifest_sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        "payload": payload,
    }
    (manifest_dir / "archive-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    note = {
        "schema_version": 1,
        "record_type": "archive_authorization_transfer_note",
        "case_id": CASE_ID,
        "archival_run_id": args.run_id,
        "authorization_basis": "Owner RETRO-only raw-history authorization in current task",
        "authorization_date": "2026-08-01",
        "source_scope": "2026-07-31 MT5 report and retained XAUUSD 2026-07-25 through 2026-08-01 ticks",
        "retention_policy": "Retain until project close or earlier owner revocation",
        "credential_material_not_intentionally_collected": True,
        "m5_firewall": "quarantine_only; never reference by an M5 input manifest",
        "raw_rows_printed": False,
    }
    (manifest_dir / "authorization-transfer-note.json").write_text(
        json.dumps(note, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps({"run_id": args.run_id, "objects": len(objects), "manifest_sha256": manifest["manifest_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
