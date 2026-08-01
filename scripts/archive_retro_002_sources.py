"""Create the append-only RETRO-002 source receipt without parsing rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw"
QUARANTINE_ROOT = RAW_ROOT / "passview_quarantine"
CASE_ID = "retro-002-20260731"
RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")
SENSITIVE_NAME_TOKENS = ("credential", "password", "secret", "token", "cookie", "private", "key")
SOURCE_SPECS = {
    "report-002.html": {
        "suffix": ".html",
        "source_class": "owner_daily_report_export",
        "sha256": "0ff0519ea9a4b72a4805aa227b39c65e942ba9bcbdd881952319372a848a54a0",
    },
    "ticks-original-002.csv": {
        "suffix": ".csv",
        "source_class": "owner_original_xauusd_tick_export",
        "sha256": "7ff026ec217fa809b41ca61b55e22a51395d809491ccaea899a0700d879839d9",
    },
    "ticks-archive-002.csv": {
        "suffix": ".csv",
        "source_class": "accepted_retro_001_tick_archive",
        "sha256": "ac319c2c17b5b23d395d0e00dd80631b76cf61a9def4473cb06517c09f2bd180",
    },
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_ignored(path: Path) -> None:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", str(path.relative_to(ROOT))],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("RETRO-002 quarantine destination is not ignored")


def preflight_source(source: Path, alias: str) -> str:
    spec = SOURCE_SPECS[alias]
    if not source.is_file():
        raise FileNotFoundError(f"Source file is missing for alias: {alias}")
    if source.suffix.lower() != spec["suffix"]:
        raise ValueError(f"Source suffix is not allowed for alias: {alias}")
    if any(token in source.name.lower() for token in SENSITIVE_NAME_TOKENS):
        raise ValueError(f"Credential-like source name rejected for alias: {alias}")
    try:
        source.resolve().relative_to(RAW_ROOT.resolve())
    except ValueError as error:
        raise ValueError(f"Source is outside the approved raw-data root for alias: {alias}") from error
    actual = sha256_file(source)
    if actual != spec["sha256"]:
        raise ValueError(f"Source hash is not the approved RETRO-002 object: {alias}")
    return actual


def copy_object(source: Path, destination: Path, alias: str) -> dict:
    if destination.exists() or destination.with_suffix(destination.suffix + ".partial").exists():
        raise RuntimeError(f"Refusing to overwrite archive object: {alias}")
    source_sha256 = preflight_source(source, alias)
    partial = destination.with_suffix(destination.suffix + ".partial")
    with source.open("rb") as source_handle, partial.open("xb") as destination_handle:
        shutil.copyfileobj(source_handle, destination_handle, length=1024 * 1024)
    destination_sha256 = sha256_file(partial)
    if source_sha256 != destination_sha256:
        raise RuntimeError(f"Hash mismatch for alias: {alias}")
    partial.replace(destination)
    return {
        "alias": alias,
        "relative_path": f"incoming/{alias}",
        "source_class": SOURCE_SPECS[alias]["source_class"],
        "bytes": destination.stat().st_size,
        "source_sha256": source_sha256,
        "destination_sha256": destination_sha256,
        "transfer_status": "accepted",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-source", type=Path, required=True)
    parser.add_argument("--original-ticks-source", type=Path, required=True)
    parser.add_argument("--archive-ticks-source", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if not RUN_ID_PATTERN.fullmatch(args.run_id):
        raise ValueError("run-id must be a simple archive token without path separators")

    run_dir = QUARANTINE_ROOT / CASE_ID / args.run_id
    if run_dir.resolve().parent != (QUARANTINE_ROOT / CASE_ID).resolve():
        raise ValueError("run-id resolves outside the RETRO-002 case quarantine directory")
    if run_dir.exists():
        raise RuntimeError(f"Archive run already exists: {args.run_id}")
    require_ignored(run_dir)
    incoming_dir = run_dir / "incoming"
    manifests_dir = run_dir / "manifests"
    incoming_dir.mkdir(parents=True)
    manifests_dir.mkdir(parents=True)

    objects = []
    try:
        objects = [
            copy_object(args.report_source, incoming_dir / "report-002.html", "report-002.html"),
            copy_object(
                args.original_ticks_source,
                incoming_dir / "ticks-original-002.csv",
                "ticks-original-002.csv",
            ),
            copy_object(
                args.archive_ticks_source,
                incoming_dir / "ticks-archive-002.csv",
                "ticks-archive-002.csv",
            ),
        ]
    except Exception as error:
        (manifests_dir / "failed-transfer-note.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "record_type": "archive_failed_transfer_note",
                    "case_id": CASE_ID,
                    "archival_run_id": args.run_id,
                    "authorization_date": "2026-08-01",
                    "status": "failed",
                    "error_type": type(error).__name__,
                    "raw_rows_printed": False,
                },
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        raise
    payload = {
        "manifest_schema_version": 1,
        "archival_run_id": args.run_id,
        "capture_time_utc": datetime.now(timezone.utc).isoformat(),
        "source_scope": "owner-authorized RETRO-002 2026-07-31 report and original/archive XAUUSD tick comparison",
        "transfer_status": "accepted",
        "objects": objects,
    }
    payload_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    manifest = {
        "manifest_schema_version": 1,
        "manifest_sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        "payload": payload,
    }
    (manifests_dir / "archive-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    note = {
        "schema_version": 1,
        "record_type": "archive_authorization_transfer_note",
        "case_id": CASE_ID,
        "archival_run_id": args.run_id,
        "authorization_basis": "Owner RETRO-002 request in current task",
        "authorization_date": "2026-08-01",
        "source_scope": "3107 report, original 2026-07-31 XAUUSD ticks, and accepted RETRO-001 weekly tick archive",
        "retention_policy": "Retain until project close or earlier owner revocation",
        "credential_material_not_intentionally_collected": True,
        "m5_firewall": "quarantine_only; never reference by an M5 input manifest",
        "raw_rows_printed": False,
    }
    (manifests_dir / "authorization-transfer-note.json").write_text(
        json.dumps(note, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps({"case_id": CASE_ID, "run_id": args.run_id, "objects": len(objects), "manifest_sha256": manifest["manifest_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
