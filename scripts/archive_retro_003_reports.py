"""Archive the nine monthly RETRO-003 HTML report objects without parsing rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "raw"
QUARANTINE_ROOT = RAW_ROOT / "passview_quarantine"
SOURCE_ROOT = QUARANTINE_ROOT / "mt5-readable-reports-20260801"
CASE_ID = "retro-003-history-screening-20260801"
RUN_ID = "run-20260801T160000"
EXPECTED_COUNT = 9
SENSITIVE_NAME_TOKENS = ("credential", "password", "secret", "token", "cookie", "private", "key")


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
        raise RuntimeError("RETRO-003 destination is not ignored")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, default=SOURCE_ROOT)
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    if source_root != SOURCE_ROOT.resolve():
        raise ValueError("RETRO-003 source root is not the pinned report source")
    try:
        source_root.relative_to(QUARANTINE_ROOT.resolve())
    except ValueError as error:
        raise ValueError("RETRO-003 report source root escapes quarantine") from error
    if not source_root.is_dir():
        raise FileNotFoundError("RETRO-003 report source root is missing")
    sources = sorted(
        source_root.rglob("*.html"),
        key=lambda path: path.relative_to(source_root).as_posix().casefold(),
    )
    if len(sources) != EXPECTED_COUNT:
        raise ValueError("RETRO-003 requires exactly nine monthly HTML reports")
    if any(path.suffix.lower() != ".html" for path in sources):
        raise ValueError("RETRO-003 report suffix check failed")
    for source in sources:
        if any(token in source.name.lower() for token in SENSITIVE_NAME_TOKENS):
            raise ValueError("RETRO-003 credential-like report name rejected")
        try:
            source.resolve().relative_to(source_root)
        except ValueError as error:
            raise ValueError("RETRO-003 report source escapes the pinned root") from error

    run_dir = QUARANTINE_ROOT / CASE_ID / RUN_ID
    try:
        run_dir.resolve().relative_to(QUARANTINE_ROOT.resolve())
    except ValueError as error:
        raise ValueError("RETRO-003 destination run escapes quarantine") from error
    if run_dir.exists():
        raise RuntimeError("RETRO-003 archive run already exists")
    require_ignored(run_dir)
    incoming = run_dir / "incoming"
    manifests = run_dir / "manifests"
    incoming.mkdir(parents=True)
    manifests.mkdir(parents=True)

    objects = []
    try:
        for index, source in enumerate(sources, start=1):
            alias = f"report-{index:03d}.html"
            destination = incoming / alias
            partial = destination.with_suffix(destination.suffix + ".partial")
            source_hash = sha256_file(source)
            with source.open("rb") as source_handle, partial.open("xb") as destination_handle:
                shutil.copyfileobj(source_handle, destination_handle, length=1024 * 1024)
            destination_hash = sha256_file(partial)
            if source_hash != destination_hash:
                raise RuntimeError(f"RETRO-003 hash mismatch for {alias}")
            partial.replace(destination)
            objects.append(
                {
                    "alias": alias,
                    "relative_path": f"incoming/{alias}",
                    "source_class": "owner_monthly_report_export",
                    "bytes": destination.stat().st_size,
                    "source_sha256": source_hash,
                    "destination_sha256": destination_hash,
                    "transfer_status": "accepted",
                }
            )
    except Exception as error:
        (manifests / "failed-transfer-note.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "record_type": "archive_failed_transfer_note",
                    "case_id": CASE_ID,
                    "archival_run_id": RUN_ID,
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
        "archival_run_id": RUN_ID,
        "capture_time_utc": datetime.now(timezone.utc).isoformat(),
        "source_scope": "owner-authorized RETRO-003 monthly HTML report exports for 2025-11 through 2026-07",
        "transfer_status": "accepted",
        "objects": objects,
    }
    payload_json = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    manifest = {
        "manifest_schema_version": 1,
        "manifest_sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        "payload": payload,
    }
    (manifests / "archive-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    note = {
        "schema_version": 1,
        "record_type": "archive_authorization_transfer_note",
        "case_id": CASE_ID,
        "archival_run_id": RUN_ID,
        "authorization_basis": "Owner RETRO authorization in current task",
        "authorization_date": "2026-08-01",
        "retention_policy": "Retain until project close or earlier owner revocation",
        "credential_material_not_intentionally_collected": True,
        "m5_firewall": "quarantine_only; never reference by an M5 input manifest",
        "raw_rows_printed": False,
    }
    (manifests / "authorization-transfer-note.json").write_text(
        json.dumps(note, ensure_ascii=True, separators=(",", ":"), sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps({"case_id": CASE_ID, "run_id": RUN_ID, "objects": len(objects), "manifest_sha256": manifest["manifest_sha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
