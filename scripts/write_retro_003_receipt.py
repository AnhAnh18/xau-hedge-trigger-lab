"""Write the tracked RETRO-003 source receipt from hash-only manifests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUARANTINE_ROOT = ROOT / "data" / "raw" / "passview_quarantine"
REPORT_RUN = QUARANTINE_ROOT / "retro-003-history-screening-20260801" / "run-20260801T160000"
TICK_RUN = QUARANTINE_ROOT / "mt5-ticks-20260801" / "run-20260801T061208"
RECEIPT = ROOT / "docs" / "observational_cases" / "RETRO-003-2025-11_to_2026-07-history-screening-receipt.md"


def load_manifest(run_dir: Path, *, sort_keys: bool) -> dict:
    try:
        run_dir.resolve().relative_to(QUARANTINE_ROOT.resolve())
    except ValueError as error:
        raise ValueError("RETRO-003 receipt source run escapes quarantine") from error
    manifest = json.loads((run_dir / "manifests" / "archive-manifest.json").read_text(encoding="utf-8"))
    payload = manifest["payload"]
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=sort_keys)
    if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != manifest["manifest_sha256"]:
        raise ValueError("RETRO-003 receipt source manifest self-digest mismatch")
    if payload.get("transfer_status") != "accepted":
        raise ValueError("RETRO-003 receipt source manifest is not accepted")
    return manifest


def table_rows(objects: list[dict]) -> list[str]:
    return [
        f"| `{item['alias']}` | `{item['source_sha256']}` | {int(item['bytes']):,} | accepted |"
        for item in objects
    ]


def main() -> int:
    reports = load_manifest(REPORT_RUN, sort_keys=True)
    ticks = load_manifest(TICK_RUN, sort_keys=False)
    report_objects = reports["payload"]["objects"]
    tick_objects = ticks["payload"]["objects"]
    if [item["alias"] for item in report_objects] != [f"report-{index:03d}.html" for index in range(1, 10)]:
        raise ValueError("RETRO-003 report aliases are not the pinned set")
    if len(tick_objects) != 39 or any(Path(item["alias"]).suffix.lower() != ".csv" for item in tick_objects):
        raise ValueError("RETRO-003 tick aliases are not the pinned set")
    text = "\n".join(
        [
            "# RETRO-003 Source Receipt",
            "",
            "Status: accepted; source objects remain quarantine-only.",
            "",
            "Authorization: owner full-RETRO request in the current task, 2026-08-01.",
            "",
            "Retention: until project close or earlier owner revocation.",
            "",
            "Credential preflight: nine HTML reports and the accepted MT5 XAUUSD",
            "tick archive only; no credential, cookie, token, secret, or private-key",
            "material was accepted.",
            "",
            f"Report manifest digest: `{reports['manifest_sha256']}`.",
            f"Tick manifest digest: `{ticks['manifest_sha256']}`.",
            "",
            "## Reports",
            "",
            "| Generated alias | SHA-256 | Bytes | Status |",
            "| --- | --- | ---: | --- |",
            *table_rows(report_objects),
            "",
            "## UTC Tick Archive",
            "",
            "| Generated alias | SHA-256 | Bytes | Status |",
            "| --- | --- | ---: | --- |",
            *table_rows(tick_objects),
            "",
            "All objects are hash-verified and are not M5 inputs. The retained XLSX",
            "and PNG companions, journals, caches, and M1 objects are out of scope.",
            "",
        ]
    )
    RECEIPT.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    print(json.dumps({"case_id": "RETRO-003", "receipt_sha256": digest, "report_objects": len(report_objects), "tick_objects": len(tick_objects)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
