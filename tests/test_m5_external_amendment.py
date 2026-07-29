from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = ROOT / "data" / "m5_003_external_amendment.json"
DOC_PATH = ROOT / ".local_ai" / "M5_003_EXTERNAL_AMENDMENT.md"


def _load() -> dict:
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def _canonical_text_sha256(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return sha256(normalized.encode("utf-8")).hexdigest()


def test_external_amendment_is_pre_prediction_and_non_adaptive() -> None:
    amendment = _load()

    assert amendment["recorded_on"] == "2026-07-30"
    assert amendment["recorded_before_external_feature_construction"] is True
    assert amendment["recorded_before_external_prediction"] is True
    assert not any(amendment["scope"].values())
    exposure = amendment["qualitative_exposure"]
    assert exposure["external_sessions_are_analyst_blinded"] is False
    assert exposure["external_features_or_predictions_computed_before_amendment"] is False


def test_external_inputs_and_replicated_gap_are_pinned() -> None:
    amendment = _load()
    inputs = amendment["canonical_external_inputs"]
    ticks = inputs["tick_files"]

    assert [row["alias"] for row in ticks] == [
        "external-tick-2026-07-27",
        "external-tick-2026-07-28",
        "external-tick-2026-07-29",
    ]
    assert len({row["sha256"] for row in ticks}) == 3
    assert [row["rows"] for row in ticks] == [642462, 683869, 716152]
    gap = amendment["replicated_source_quote_gap"]
    assert gap["duration_seconds"] == 106.357
    assert gap["classification"] == "replicated_source_quote_gap"
    assert gap["same_boundary_ticks_in_both_exports"] is True
    assert gap["reported_events_inside_gap"] is True
    assert gap["interpolation_allowed"] is False


def test_external_decision_gate_is_unchanged() -> None:
    contract = _load()["external_decision_contract"]

    assert contract["registered_sessions"] == [
        "2026-07-27",
        "2026-07-28",
        "2026-07-29",
    ]
    assert contract["headline"] == "C_session_minus_A_session_at_1000ms"
    assert contract["pooled_familywise_gate_unchanged"] is True
    assert contract["two_of_three_positive_session_gate_unchanged"] is True
    assert contract["tradeable_edge_claim_allowed"] is False


def test_external_amendment_text_hashes_are_locked_in_manifest() -> None:
    manifest = (ROOT / "data" / "manifest.yaml").read_text(encoding="utf-8")

    assert _canonical_text_sha256(PLAN_PATH) in manifest
    assert _canonical_text_sha256(DOC_PATH) in manifest
