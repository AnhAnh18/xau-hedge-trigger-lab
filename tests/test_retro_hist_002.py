import hashlib
import json
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import pytest

from xau_trigger.retro_hist_002 import (
    CausalAction,
    LifecycleEvent,
    PolicyState,
    Position,
    RetroHistInputError,
    apply_causal_action,
    apply_oracle_label,
    iter_ticks,
    reconstruct_observed,
    state_for,
)
import xau_trigger.retro_hist_002 as rh002
import scripts.analyze_retro_hist_002_lifecycle as rh002_script


def _position(position_id, side, quantity, opened, closed, censored=False):
    return Position(position_id, side, Decimal(quantity), pd.Timestamp(opened), None if closed is None else pd.Timestamp(closed), censored)


def test_lifecycle_classifies_equal_unequal_and_multi_states() -> None:
    assert state_for({}) == "FLAT"
    assert state_for({"b": _position("b", "buy", "0.10000000", "2026-01-01", "2026-01-02")}) == "ONE_BUY"
    assert state_for({"b": _position("b", "buy", "0.10000000", "2026-01-01", "2026-01-02"), "s": _position("s", "sell", "0.10000000", "2026-01-01", "2026-01-02")}) == "HEDGED_1X1"
    assert state_for({"b": _position("b", "buy", "0.10000000", "2026-01-01", "2026-01-02"), "s": _position("s", "sell", "0.20000000", "2026-01-01", "2026-01-02")}) == "UNBALANCED_HEDGE"
    assert state_for({"b1": _position("b1", "buy", "0.10000000", "2026-01-01", "2026-01-02"), "b2": _position("b2", "buy", "0.10000000", "2026-01-01", "2026-01-02")}) == "MULTI_POSITION"
    assert state_for({"c": _position("c", "buy", "0.10000000", "2026-01-01", None, True)}) == "CENSORED"


def test_equal_time_close_before_open_is_deterministic() -> None:
    positions = [
        _position("old", "buy", "0.10000000", "2025-11-01", "2026-01-02 00:00:00"),
        _position("new", "sell", "0.10000000", "2026-01-02 00:00:00", "2026-01-03"),
    ]
    result = reconstruct_observed(positions)
    assert result["event_coverage"]["collision_timestamps"] == 1
    assert result["transition_counts"]["ONE_BUY"]["FLAT"] == 1
    assert result["transition_counts"]["FLAT"]["ONE_SELL"] == 1


def test_oracle_label_cannot_change_policy_state() -> None:
    initial = PolicyState()
    action = CausalAction("a1", 1, "OPEN", "buy", Decimal("0.10000000"))
    after_action = apply_causal_action(initial, action)
    label = LifecycleEvent("CLOSE", "oracle", "buy", Decimal("0.10000000"), pd.Timestamp("2026-01-01"))
    assert apply_oracle_label(after_action, label) == after_action
    assert apply_oracle_label(after_action, replace_label(label)) == after_action


def replace_label(label: LifecycleEvent) -> LifecycleEvent:
    return LifecycleEvent("OPEN", "oracle-2", "sell", Decimal("0.20000000"), label.time)


def test_invalid_action_has_no_partial_update() -> None:
    initial = PolicyState()
    opened = apply_causal_action(initial, CausalAction("a1", 1, "OPEN", "buy", Decimal("0.10000000")))
    with pytest.raises(RetroHistInputError):
        apply_causal_action(opened, CausalAction("a2", 2, "OPEN", "buy", Decimal("0.20000000")))
    assert opened.buy_quantity == Decimal("0.10000000")
    assert opened.seen_action_ids == ("a1",)


def _workspace_tick_file(content: str) -> Path:
    handle = NamedTemporaryFile(prefix="rh002-ticks-", suffix=".csv", dir=Path.cwd(), delete=False, mode="w", encoding="utf-8")
    handle.write(content)
    handle.close()
    return Path(handle.name)


def test_tick_adapter_accepts_equal_quotes_and_counts_duplicates() -> None:
    path = _workspace_tick_file("time_utc,bid,ask\n2025-11-01T00:00:00Z,2000.0,2000.0\n2025-11-01T00:00:00Z,2000.1,2000.2\n")
    try:
        ticks, stats = iter_ticks(path, broad_start=pd.Timestamp("2025-10-31 20:00:00", tz="UTC"), broad_end=pd.Timestamp("2025-11-01 02:00:00", tz="UTC"))
        assert len(list(ticks)) == 2
        assert stats["duplicate_timestamps"] == 1
        assert stats["crossed_quotes"] == 0
    finally:
        path.unlink(missing_ok=True)


def test_tick_adapter_rejects_decreasing_time() -> None:
    path = _workspace_tick_file("time_utc,bid,ask\n2025-11-01T00:00:01Z,2000.0,2000.1\n2025-11-01T00:00:00Z,2000.0,2000.1\n")
    try:
        ticks, _ = iter_ticks(path, broad_start=pd.Timestamp("2025-10-31 20:00:00", tz="UTC"), broad_end=pd.Timestamp("2025-11-01 02:00:00", tz="UTC"))
        with pytest.raises(RetroHistInputError):
            list(ticks)
    finally:
        path.unlink(missing_ok=True)


def test_conflicting_position_is_censored_without_definite_events() -> None:
    rows = [
        {"position_id": "conflict", "symbol": "XAUUSD", "side": "buy", "volume": "0.10000000", "open_time": "2026-01-01", "close_time": "2026-01-02"},
        {"position_id": "conflict", "symbol": "XAUUSD", "side": "sell", "volume": "0.20000000", "open_time": "2026-01-01", "close_time": "2026-01-02"},
    ]
    positions, stats = rh002.deduplicate_positions(rows)
    assert stats["conflicting_position_ids"] == 1
    assert stats["censored_position_ids"] == 1
    assert len(positions) == 1 and positions[0].censored is True
    result = reconstruct_observed(positions)
    assert result["event_coverage"]["open_events"] == 0
    assert result["event_coverage"]["close_events"] == 0
    assert result["state_counts"]["CENSORED"] >= 1


def test_lifecycle_carry_in_and_half_open_boundaries() -> None:
    start = pd.Timestamp("2025-11-01 00:00:00")
    end = pd.Timestamp("2026-07-31 00:00:00")
    positions = [
        _position("carry", "buy", "0.10000000", "2025-10-31 23:00:00", "2025-11-01 01:00:00"),
        _position("at-start", "sell", "0.10000000", start, "2025-11-01 02:00:00"),
        _position("at-end", "buy", "0.10000000", end, None),
    ]
    result = reconstruct_observed(positions)
    assert result["event_coverage"]["open_events"] == 1
    assert result["state_counts"]["ONE_BUY"] >= 1
    assert result["state_counts"]["HEDGED_1X1"] >= 1


def test_equal_time_policy_actions_use_action_id_tie_break() -> None:
    first = apply_causal_action(PolicyState(), CausalAction("a1", 100, "OPEN", "buy", Decimal("0.10000000")))
    second = apply_causal_action(first, CausalAction("a2", 100, "OPEN", "sell", Decimal("0.10000000")))
    assert second.state == "HEDGED_1X1"
    assert second.seen_action_ids == ("a1", "a2")


def test_manifest_duplicate_aliases_fail_before_mapping(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "run" / "manifests"
    run_dir.mkdir(parents=True)
    payload = {
        "transfer_status": "accepted",
        "objects": [
            {"alias": "a", "relative_path": "incoming/a", "source_sha256": "0" * 64, "destination_sha256": "0" * 64},
            {"alias": "a", "relative_path": "incoming/a-duplicate", "source_sha256": "0" * 64, "destination_sha256": "0" * 64},
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    (run_dir / "archive-manifest.json").write_text(json.dumps({"payload": payload, "manifest_sha256": digest}), encoding="utf-8")
    monkeypatch.setattr(rh002, "QUARANTINE_ROOT", tmp_path)
    with pytest.raises(RetroHistInputError, match="aliases contain duplicates"):
        rh002.verify_manifest("run", digest, {"a"}, sort_keys=True, check_objects=False)


def test_manifest_path_escape_fails_closed(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "run" / "manifests"
    run_dir.mkdir(parents=True)
    payload = {
        "transfer_status": "accepted",
        "objects": [{"alias": "a", "relative_path": "../outside", "source_sha256": "0" * 64, "destination_sha256": "0" * 64}],
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    (run_dir / "archive-manifest.json").write_text(json.dumps({"payload": payload, "manifest_sha256": digest}), encoding="utf-8")
    monkeypatch.setattr(rh002, "QUARANTINE_ROOT", tmp_path)
    with pytest.raises((RetroHistInputError, ValueError)):
        rh002.verify_manifest("run", digest, {"a"}, sort_keys=True, check_objects=False)


def test_manifest_object_digest_mismatch_fails_closed(tmp_path, monkeypatch) -> None:
    run_dir = tmp_path / "run"
    incoming = run_dir / "incoming"
    (run_dir / "manifests").mkdir(parents=True)
    incoming.mkdir()
    object_path = incoming / "a"
    object_path.write_text("tampered", encoding="utf-8")
    payload = {
        "transfer_status": "accepted",
        "objects": [{"alias": "a", "relative_path": "incoming/a", "source_sha256": "0" * 64, "destination_sha256": "0" * 64}],
    }
    encoded = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    (run_dir / "manifests" / "archive-manifest.json").write_text(json.dumps({"payload": payload, "manifest_sha256": digest}), encoding="utf-8")
    monkeypatch.setattr(rh002, "QUARANTINE_ROOT", tmp_path)
    with pytest.raises(RetroHistInputError, match="object digest mismatch"):
        rh002.verify_manifest("run", digest, {"a"}, sort_keys=True, check_objects=True)


@pytest.mark.parametrize(
    "first_row",
    [
        "2026-01-02T00:00:00Z,2000.2,2000.1",  # crossed quote, outside filtering must not hide ordering
        "2026-01-02T00:00:00Z,nan,2000.1",  # non-finite quote
    ],
)
def test_tick_order_is_checked_before_quote_filtering(first_row: str) -> None:
    path = _workspace_tick_file(f"time_utc,bid,ask\n{first_row}\n2026-01-01T00:00:00Z,2000.0,2000.1\n")
    try:
        ticks, _ = iter_ticks(path, broad_start=pd.Timestamp("2025-12-31 00:00:00", tz="UTC"), broad_end=pd.Timestamp("2026-01-03 00:00:00", tz="UTC"))
        with pytest.raises(RetroHistInputError):
            list(ticks)
    finally:
        path.unlink(missing_ok=True)


def test_tick_order_is_checked_before_envelope_exclusion() -> None:
    path = _workspace_tick_file("time_utc,bid,ask\n2026-01-03T00:00:00Z,2000.0,2000.1\n2026-01-01T00:00:00Z,2000.0,2000.1\n")
    try:
        ticks, _ = iter_ticks(path, broad_start=pd.Timestamp("2026-01-01 00:00:00", tz="UTC"), broad_end=pd.Timestamp("2026-01-02 00:00:00", tz="UTC"))
        with pytest.raises(RetroHistInputError):
            list(ticks)
    finally:
        path.unlink(missing_ok=True)


def test_tick_envelope_upper_bound_is_half_open() -> None:
    path = _workspace_tick_file("time_utc,bid,ask\n2026-01-02T00:00:00Z,2000.0,2000.1\n")
    try:
        ticks, stats = iter_ticks(path, broad_start=pd.Timestamp("2026-01-01 00:00:00", tz="UTC"), broad_end=pd.Timestamp("2026-01-02 00:00:00", tz="UTC"))
        assert list(ticks) == []
        assert stats["envelope_excluded_rows"] == 1
    finally:
        path.unlink(missing_ok=True)


def test_tick_order_is_global_across_aliases(monkeypatch) -> None:
    first = _workspace_tick_file("time_utc,bid,ask\n2025-11-01T00:00:01Z,2000.0,2000.1\n")
    second = _workspace_tick_file("time_utc,bid,ask\n2025-11-01T00:00:00Z,2000.0,2000.1\n")
    try:
        with pytest.raises(RetroHistInputError):
            rh002_script._scan_ticks({"a": first, "b": second})
    finally:
        first.unlink(missing_ok=True)
        second.unlink(missing_ok=True)


def test_aggregate_schema_and_digest_are_nested_and_firewalled(monkeypatch) -> None:
    empty_states = {label: 0 for label in rh002.STATE_LABELS}
    empty_matrix = {source: {target: 0 for target in rh002.STATE_LABELS} for source in rh002.STATE_LABELS}
    monkeypatch.setattr(rh002_script, "verify_manifest", lambda *args, **kwargs: {"synthetic": Path("synthetic")})
    monkeypatch.setattr(rh002_script, "load_positions", lambda paths: ([], {"reports_parsed": 9, "accepted_position_ids": 0, "conflicting_position_ids": 0, "invalid_position_rows": 0, "censored_position_ids": 0}))
    monkeypatch.setattr(rh002_script, "reconstruct_observed", lambda positions: {"event_coverage": {"open_events": 0, "close_events": 0, "duplicate_labels": 0, "collision_timestamps": 0}, "state_counts": empty_states, "transition_counts": empty_matrix})
    monkeypatch.setattr(rh002_script, "_scan_ticks", lambda paths: {"valid_rows": 0, "invalid_rows": 0, "duplicate_timestamps": 0, "out_of_order": 0, "crossed_quotes": 0, "envelope_excluded_rows": 0, "files_hash_verified": 39})
    result = rh002_script.run()
    assert set(result) == {
        "schema_version", "case_id", "source_validation", "report_manifest_sha256", "tick_manifest_sha256",
        "population", "event_coverage", "state_counts", "transition_counts", "tick_coverage",
        "m5_firewall", "claims", "aggregate_sha256",
    }
    assert set(result["state_counts"]) == {"oracle", "policy"}
    assert set(result["transition_counts"]) == {"oracle", "policy"}
    digest_payload = dict(result)
    digest = digest_payload.pop("aggregate_sha256")
    assert hashlib.sha256(rh002_script._canonical(digest_payload).encode()).hexdigest() == digest
    assert result["claims"]["raw_rows_printed"] is False
    assert result["m5_firewall"] == rh002.M5_FIREWALL
