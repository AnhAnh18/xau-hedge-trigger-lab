from __future__ import annotations

import json
from pathlib import Path

from xau_trigger.unlock_cause import CAUSE_FEATURES, canonical_hash


ROOT = Path(__file__).resolve().parents[1]


def test_m5_004_frozen_manifest_contract() -> None:
    path = ROOT / "reports" / "phase_05" / "m5_004_frozen_model_manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    stored_hash = manifest.pop("frozen_manifest_sha256")

    assert canonical_hash(manifest) == stored_hash
    assert manifest["status"] == (
        "frozen_before_seen_reuse_and_future_external_loading"
    )
    assert manifest["predictor_allowlist"] == list(CAUSE_FEATURES)
    assert manifest["development_sessions"] == [
        "2026-07-20",
        "2026-07-21",
        "2026-07-22",
        "2026-07-23",
    ]
    assert manifest["internal_reuse_loaded_for_fit_or_selection"] is False
    assert manifest["seen_external_reuse_loaded_before_freeze"] is False
    assert manifest["future_external_loaded_before_freeze"] is False
    assert set(manifest["widths"]) == {"500", "1000"}


def test_m5_004_report_remains_external_pending() -> None:
    path = ROOT / "reports" / "phase_05" / "m5_004_unlock_cause_report.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    stored_hash = report.pop("deterministic_report_sha256")

    assert canonical_hash(report) == stored_hash
    assert report["status"] == (
        "development_package_frozen_future_external_pending"
    )
    assert report["decision"]["verdict"] is None
    assert report["predictor_allowlist"] == list(CAUSE_FEATURES)
    assert all(report["validation_gates"].values())
    assert report["event_accounting"]["1000"]["development"]["causes"] == {
        "UNLOCK_TO_BUY": 714,
        "UNLOCK_TO_SELL": 730,
    }
    assert report["event_accounting"]["500"]["development"]["causes"] == {
        "UNLOCK_TO_BUY": 715,
        "UNLOCK_TO_SELL": 730,
    }
