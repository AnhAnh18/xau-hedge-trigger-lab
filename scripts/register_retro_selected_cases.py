"""Register RETRO-004..006 contracts and source receipts from RETRO-003 selection."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUARANTINE_ROOT = ROOT / "data" / "raw" / "passview_quarantine"
INVENTORY = ROOT / "reports" / "private" / "retro-003" / "retro-003-aggregate.json"
REPORT_RUN = QUARANTINE_ROOT / "retro-003-history-screening-20260801" / "run-20260801T160000"
TICK_RUN = QUARANTINE_ROOT / "mt5-ticks-20260801" / "run-20260801T061208"
REPORT_MANIFEST_SHA256 = "88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30"
TICK_MANIFEST_SHA256 = "a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c"
DATE_RE = re.compile(r"XAUUSD_ticks_(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})\.csv\Z")


def load_manifest(path: Path, expected: str, sort_keys: bool) -> dict:
    try:
        path.resolve().relative_to(QUARANTINE_ROOT.resolve())
    except ValueError as error:
        raise ValueError("RETRO selected-case source run escapes quarantine") from error
    manifest = json.loads((path / "manifests" / "archive-manifest.json").read_text(encoding="utf-8"))
    payload = manifest["payload"]
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=sort_keys)
    if manifest.get("manifest_sha256") != expected or hashlib.sha256(canonical.encode("utf-8")).hexdigest() != expected:
        raise ValueError("RETRO selected-case source manifest is not pinned")
    return manifest


def write_case(case_id: str, selected: dict, report: dict, tick: dict) -> None:
    number = case_id.split("-")[-1]
    start = datetime.fromisoformat(selected["start_time"])
    end = datetime.fromisoformat(selected["end_time"])
    window_start = start - timedelta(seconds=120)
    window_end = end + timedelta(seconds=120)
    report_path = f"incoming/{selected['report_alias']}"
    tick_path = f"incoming/{tick['alias']}"
    contract = f"""# {case_id}: Historical One-Leg Case

Status: owner-authorized; source receipt accepted; independent review pending.

## Purpose

Describe one preselected historical one-leg interval from the RETRO-003
stratified inventory. This case is descriptive only and cannot change M5
contracts, models, thresholds, evaluations, or gates.

## Exact scope

- Server interval: inclusive `{window_start:%Y-%m-%d %H:%M:%S}` through
  `{window_end:%Y-%m-%d %H:%M:%S}`.
- Selected target date: `{selected['server_date']}`; selected side:
  `{selected['side']}`; inventory duration band: `{selected['duration_band']}`.
- Report alias: `{selected['report_alias']}`.
- Tick alias: `{tick['alias']}`.
- Registered clock candidates: UTC+2 and UTC+3. A tick metric is accepted
  only when exactly one candidate supports both report boundaries; otherwise
  the clock result and price-derived metric are unresolved.

No journal, terminal log, support cache, screenshot, M1 object, XLSX/PNG
companion, or other source is in scope.

## Questions

1. Is the selected one-leg interval and its following opposite-side re-hedge
   uniquely reconstructable?
2. Which registered clock candidate, if any, supports the tick window and
   report-boundary alignment?
3. What aggregate quote-quality, coarse adverse-excursion, and continuation
   indicators are observed without inferring a trigger or manual action?

## Safeguards and acceptance

- Verify both source objects against the accepted RETRO-003 manifests before
  parsing, including quarantine-root, exact parent/name/suffix, and SHA-256.
- Stream ticks and retain aggregate metrics only; never print or commit rows,
  prices, tickets, or detailed timelines.
- Keep journal/manual-intervention status unresolved because no journal is in
  scope.
- Preserve the M5 information firewall and obtain a fresh independent review
  before marking this case complete.

## Provenance

Report manifest digest: `{REPORT_MANIFEST_SHA256}`.
Tick manifest digest: `{TICK_MANIFEST_SHA256}`.
"""
    receipt = f"""# {case_id} Source Receipt

Status: accepted; source objects remain quarantine-only.

Authorization: owner full-RETRO request in the current task, 2026-08-01.
Retention: until project close or earlier owner revocation.

| Role | Generated alias | SHA-256 | Bytes | Status |
| --- | --- | --- | ---: | --- |
| Report | `{selected['report_alias']}` | `{report['source_sha256']}` | {int(report['bytes']):,} | accepted |
| UTC tick archive | `{tick['alias']}` | `{tick['source_sha256']}` | {int(tick['bytes']):,} | accepted |

Report manifest digest: `{REPORT_MANIFEST_SHA256}`.
Tick manifest digest: `{TICK_MANIFEST_SHA256}`.

No credentials, journal, private paths, raw rows, or detailed timeline are
accepted. This source pair is outside every M5 input manifest.
"""
    base = ROOT / "docs" / "observational_cases"
    (base / f"{case_id}-contract.md").write_text(contract, encoding="utf-8")
    (base / f"{case_id}-source-receipt.md").write_text(receipt, encoding="utf-8")


def main() -> int:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    recorded_digest = inventory.pop("aggregate_sha256", None)
    canonical = json.dumps(inventory, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    if recorded_digest is None or hashlib.sha256(canonical.encode("utf-8")).hexdigest() != recorded_digest:
        raise ValueError("RETRO-003 inventory aggregate digest mismatch")
    if inventory.get("schema_version") != 1 or inventory.get("case_id") != "RETRO-003":
        raise ValueError("RETRO-003 inventory schema is not pinned")
    if inventory.get("m5_firewall") != "not_an_M5_input; no fitting, evaluation, threshold change, or gate decision" or inventory.get("raw_rows_printed") is not False:
        raise ValueError("RETRO-003 inventory firewall is not pinned")
    selected = inventory["selected_cases"]
    if len(selected) != 3:
        raise ValueError("RETRO-003 did not select exactly three cases")
    reports = load_manifest(REPORT_RUN, REPORT_MANIFEST_SHA256, True)["payload"]["objects"]
    ticks = load_manifest(TICK_RUN, TICK_MANIFEST_SHA256, False)["payload"]["objects"]
    report_map = {item["alias"]: item for item in reports}
    tick_map = {item["alias"]: item for item in ticks}
    for index, item in enumerate(selected, start=4):
        day = datetime.fromisoformat(item["server_date"]).date()
        candidates = []
        for alias, tick in tick_map.items():
            match = DATE_RE.fullmatch(alias)
            if match and datetime.fromisoformat(match.group(1)).date() <= day < datetime.fromisoformat(match.group(2)).date():
                candidates.append(tick)
        if len(candidates) != 1:
            raise ValueError(f"Selected date does not map to one weekly tick object: {item['server_date']}")
        write_case(f"RETRO-{index:03d}", item, report_map[item["report_alias"]], candidates[0])
    print(json.dumps({"registered_cases": [f"RETRO-{index:03d}" for index in range(4, 7)], "status": "accepted_sources_pinned"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
