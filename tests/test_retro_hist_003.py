from decimal import Decimal
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import pandas as pd
import pytest

from xau_trigger.retro_hist_002 import Position, RetroHistInputError
from scripts.analyze_retro_hist_003_trigger import _FeatureCursor, _OracleMatcher, _require_ignored, _run_replay
from xau_trigger.retro_hist_003 import (
    ACTION_KINDS,
    CASE_ID,
    CLOCK_IDS,
    CANDIDATE_IDS,
    CausalDecision,
    CausalState,
    CausalTick,
    FeatureSnapshot,
    OracleLabel,
    aggregate_trigger_results,
    action_digest,
    apply_decision,
    bootstrap_state,
    build_feature_snapshot,
    empty_aggregate_maps,
    evaluate_candidate,
    iter_ticks_decimal,
    load_positions_retro,
    oracle_diagnostics,
    validate_aggregate,
)
from xau_trigger import retro_hist_003 as rh003


ZERO = Decimal("0.00000000")


def _position(position_id, side, opened, closed, quantity="0.10000000", censored=False):
    return Position(position_id, side, Decimal(quantity), pd.Timestamp(opened), None if closed is None else pd.Timestamp(closed), censored)


def _ticks(*rows):
    return tuple(CausalTick(pd.Timestamp(time, tz="UTC"), Decimal(str(bid)), Decimal(str(ask)), duplicate) for time, bid, ask, duplicate in rows)


def _dense_ticks(start: str, end: str, *, start_bid: Decimal, end_bid: Decimal) -> tuple[CausalTick, ...]:
    start_time = pd.Timestamp(start, tz="UTC")
    end_time = pd.Timestamp(end, tz="UTC")
    count = int((end_time - start_time).total_seconds() // 6)
    rows = []
    for index in range(count + 1):
        timestamp = start_time + pd.Timedelta(seconds=index * 6)
        fraction = Decimal(index) / Decimal(count) if count else Decimal("0")
        bid = start_bid + (end_bid - start_bid) * fraction
        rows.append(CausalTick(timestamp, bid, bid + Decimal("0.01"), False))
    return tuple(rows)


def test_bootstrap_precedence_and_same_side_multi_position() -> None:
    assert bootstrap_state([]).state == "FLAT"
    assert bootstrap_state([_position("b", "buy", "2025-10-31 23:00", "2026-01-01")]).state == "ONE_BUY"
    assert bootstrap_state([
        _position("b", "buy", "2025-10-31 23:00", "2026-01-01"),
        _position("s", "sell", "2025-10-31 23:00", "2026-01-01", "0.20000000"),
    ]).state == "UNBALANCED_HEDGE"
    assert bootstrap_state([
        _position("b1", "buy", "2025-10-31 23:00", "2026-01-01"),
        _position("b2", "buy", "2025-10-31 23:00", "2026-01-01"),
    ]).state == "MULTI_POSITION"
    assert bootstrap_state([_position("c", "buy", "2025-10-31 23:00", None, censored=True)]).state == "CENSORED"


def test_feature_equations_and_exact_support_boundaries() -> None:
    ticks = _dense_ticks("2026-01-01 00:00:06", "2026-01-01 00:01:06", start_bid=Decimal("2000"), end_bid=Decimal("2001"))
    snapshot = build_feature_snapshot(ticks, pd.Timestamp("2026-01-01 00:01:06", tz="UTC"), clock_id="utc_plus_2", state="HEDGED_1X1")
    assert snapshot.support_status == "supported"
    assert snapshot.price_increment_points == Decimal("100")
    assert snapshot.spread_points == Decimal("1")
    assert snapshot.quote_gap_seconds == Decimal("6")
    too_late = build_feature_snapshot(ticks[:2], pd.Timestamp("2026-01-01 00:01:07", tz="UTC"), clock_id="utc_plus_2", state="HEDGED_1X1")
    assert too_late.support_reason == "quote_gap"


def test_stream_cursor_matches_window_equations() -> None:
    ticks = _dense_ticks("2026-01-01 00:00:00", "2026-01-01 00:01:06", start_bid=Decimal("2000"), end_bid=Decimal("2001"))
    cursor = _FeatureCursor()
    streamed = None
    for tick in ticks:
        streamed = cursor.push([tick], tick.time_utc, "utc_plus_2")
    expected = build_feature_snapshot(ticks, ticks[-1].time_utc, clock_id="utc_plus_2", state="HEDGED_1X1")
    assert streamed is not None
    assert streamed.support_status == expected.support_status
    assert streamed.price_increment_points == expected.price_increment_points
    assert streamed.buy_adverse_excursion_points == expected.buy_adverse_excursion_points
    assert streamed.sell_adverse_excursion_points == expected.sell_adverse_excursion_points
    assert streamed.quote_gap_seconds == expected.quote_gap_seconds


def test_stream_cursor_includes_decision_to_last_gap() -> None:
    ticks = tuple(
        CausalTick(
            pd.Timestamp("2026-01-01 00:00:00", tz="UTC") + pd.Timedelta(seconds=index),
            Decimal("2000"),
            Decimal("2000.01"),
        )
        for index in range(61)
    )
    cursor = _FeatureCursor()
    for tick in ticks[:-1]:
        cursor.push([tick], tick.time_utc, "utc_plus_2")
    streamed = cursor.push([ticks[-1]], pd.Timestamp("2026-01-01 00:01:07", tz="UTC"), "utc_plus_2")
    expected = build_feature_snapshot(ticks, pd.Timestamp("2026-01-01 00:01:07", tz="UTC"), clock_id="utc_plus_2", state="HEDGED_1X1")
    assert streamed.quote_gap_seconds == expected.quote_gap_seconds == Decimal("7")
    assert streamed.support_reason == expected.support_reason == "quote_gap"
    assert streamed.price_increment_points is None
    assert streamed.buy_adverse_excursion_points is None
    assert streamed.sell_adverse_excursion_points is None
    assert streamed.spread_points is None


def test_stream_cursor_matches_duplicate_at_anchor_and_clock_mapping() -> None:
    ticks = (
        CausalTick(pd.Timestamp("2026-01-01 00:00:00", tz="UTC"), Decimal("2000"), Decimal("2000.01")),
        CausalTick(pd.Timestamp("2026-01-01 00:00:01", tz="UTC"), Decimal("2000"), Decimal("2000.01"), True),
        CausalTick(pd.Timestamp("2026-01-01 00:00:01", tz="UTC"), Decimal("2000"), Decimal("2000.01")),
    )
    decision = pd.Timestamp("2026-01-01 00:01:01", tz="UTC")
    expected = build_feature_snapshot(ticks, decision, clock_id="utc_plus_2", state="HEDGED_1X1")
    cursor = _FeatureCursor()
    cursor.push([ticks[0]], ticks[0].time_utc, "utc_plus_2")
    cursor.push([ticks[1]], ticks[1].time_utc, "utc_plus_2")
    streamed = cursor.push([ticks[2]], decision, "utc_plus_2")
    assert expected.support_reason == streamed.support_reason == "duplicate_timestamp"
    assert rh003.server_to_utc("2026-01-01 00:00:00", "utc_plus_2") != rh003.server_to_utc("2026-01-01 00:00:00", "utc_plus_3")


def test_cross_alias_duplicate_order_and_path_firewall() -> None:
    handles = []
    try:
        for index in range(2):
            handle = NamedTemporaryFile(prefix=f"rh003-alias-{index}-", suffix=".csv", dir=Path.cwd(), delete=False, mode="w", encoding="utf-8")
            handle.write("time_utc,bid,ask\n2026-01-01T00:00:00Z,2000,2000.01\n")
            handle.close()
            handles.append(Path(handle.name))
        stats, replay = _run_replay({"a": handles[0], "b": handles[1]}, [])
        assert stats["utc_plus_2"]["duplicate_timestamps"] == 1
        assert stats["utc_plus_2"]["out_of_order"] == 0
        assert replay["action_digests"]["hold_only"]["utc_plus_2"] == hashlib.sha256(b"").hexdigest()
        with pytest.raises(ValueError):
            _require_ignored(Path(__file__))
    finally:
        for path in handles:
            path.unlink(missing_ok=True)


def test_retro_loader_resets_non_position_sections() -> None:
    positions, stats = load_positions_retro({"fixture": Path("tests/fixtures/mt5_report_minimal.html")})
    assert [item.position_id for item in positions] == ["1001", "1002"]
    assert stats["invalid_position_rows"] == 0


def test_flat_replay_counts_all_valid_out_of_window_groups() -> None:
    handle = NamedTemporaryFile(prefix="rh003-flat-envelope-", suffix=".csv", dir=Path.cwd(), delete=False, mode="w", encoding="utf-8")
    handle.write(
        "time_utc,bid,ask\n"
        "2025-10-31T20:30:00Z,2000,2000.01\n"
        "2025-10-31T21:00:00Z,2000,2000.01\n"
        "2025-10-31T21:59:30Z,2000,2000.01\n"
        "2025-10-31T22:00:00Z,2000,2000.01\n"
    )
    handle.close()
    path = Path(handle.name)
    try:
        stats, replay = _run_replay({"fixture": path}, [])
        assert stats["utc_plus_2"]["envelope_excluded_rows"] == 3
        assert stats["utc_plus_2"]["valid_rows"] == 1
        assert stats["utc_plus_3"]["envelope_excluded_rows"] == 1
        assert stats["utc_plus_3"]["valid_rows"] == 3
        assert replay["action_digests"]["hold_only"]["utc_plus_2"] == hashlib.sha256(b"").hexdigest()
    finally:
        path.unlink(missing_ok=True)


def test_flat_replay_flushes_before_invalid_timestamp() -> None:
    handle = NamedTemporaryFile(prefix="rh003-flat-invalid-time-", suffix=".csv", dir=Path.cwd(), delete=False, mode="w", encoding="utf-8")
    handle.write(
        "time_utc,bid,ask\n"
        "2025-10-31T22:00:00Z,2000,2000.01\n"
        "not-a-time,2000,2000.01\n"
        "2025-10-31T22:00:00Z,2000,2000.01\n"
    )
    handle.close()
    path = Path(handle.name)
    try:
        stats, replay = _run_replay({"fixture": path}, [])
        assert stats["utc_plus_2"]["invalid_rows"] == 1
        assert replay["maps"]["support_counts"]["hold_only"]["utc_plus_2"]["FLAT"]["state_ineligible"] == 2
    finally:
        path.unlink(missing_ok=True)


def _write_constant_ticks(path: Path, *, invalid_between: bool = False) -> None:
    lines = ["time_utc,bid,ask"]
    start = pd.Timestamp("2025-10-31 21:00:00", tz="UTC")
    for index in range(601):
        timestamp = start + pd.Timedelta(seconds=index * 6)
        lines.append(f"{timestamp.isoformat().replace('+00:00', 'Z')},2000,2000.01")
        if invalid_between and index == 600:
            lines.append("not-a-time,2000,2000.01")
    lines.append("2025-10-31T22:00:06Z,2000,2000.01")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_future_position_quantity_cannot_change_policy_replay() -> None:
    handle = NamedTemporaryFile(prefix="rh003-future-lot-", suffix=".csv", dir=Path.cwd(), delete=False)
    handle.close()
    path = Path(handle.name)
    try:
        _write_constant_ticks(path)
        carry = _position("carry", "buy", "2025-10-31 23:00:00", None, "0.10000000")
        future_a = _position("future", "sell", "2025-11-01 00:00:10", "2025-11-01 00:00:20", "0.20000000")
        future_b = _position("future", "sell", "2025-11-01 00:00:10", "2025-11-01 00:00:20", "0.90000000")
        stats_a, replay_a = _run_replay({"fixture": path}, [carry, future_a])
        stats_b, replay_b = _run_replay({"fixture": path}, [carry, future_b])
        assert stats_a == stats_b
        assert replay_a["action_digests"] == replay_b["action_digests"]
        for key in ("support_counts", "outcome_counts", "action_counts", "quantity_bands"):
            assert replay_a["maps"][key] == replay_b["maps"][key]
    finally:
        path.unlink(missing_ok=True)


def test_nonflat_invalid_timestamp_flushes_and_fails_closed() -> None:
    clean_handle = NamedTemporaryFile(prefix="rh003-nonflat-clean-", suffix=".csv", dir=Path.cwd(), delete=False)
    invalid_handle = NamedTemporaryFile(prefix="rh003-nonflat-invalid-", suffix=".csv", dir=Path.cwd(), delete=False)
    clean_handle.close()
    invalid_handle.close()
    clean_path = Path(clean_handle.name)
    invalid_path = Path(invalid_handle.name)
    try:
        _write_constant_ticks(clean_path)
        _write_constant_ticks(invalid_path, invalid_between=True)
        carry = _position("carry", "buy", "2025-10-31 23:00:00", None, "0.10000000")
        _, clean = _run_replay({"fixture": clean_path}, [carry])
        invalid_stats, invalid = _run_replay({"fixture": invalid_path}, [carry])
        assert invalid_stats["utc_plus_2"]["invalid_rows"] == 1
        for clock in CLOCK_IDS:
            assert clean["maps"]["action_counts"]["rehedge_mirror_active_leg"][clock]["OPEN_SELL"] == 1
            assert invalid["maps"]["action_counts"]["rehedge_mirror_active_leg"][clock]["OPEN_SELL"] == 1
            assert clean["maps"]["outcome_counts"]["rehedge_mirror_active_leg"][clock]["HEDGED_1X1"]["hold"] >= 1
            assert invalid["maps"]["outcome_counts"]["rehedge_mirror_active_leg"][clock]["HEDGED_1X1"]["unsupported"] >= 1
    finally:
        clean_path.unlink(missing_ok=True)
        invalid_path.unlink(missing_ok=True)


def test_online_oracle_matcher_matches_reference_diagnostics() -> None:
    label = OracleLabel("p1", "CLOSE", "buy", Decimal("0.10000000"), pd.Timestamp("2026-01-01 02:00:00"))
    decision = CausalDecision(
        "action",
        "close_buy_increment_ge_0",
        "HEDGED_1X1",
        pd.Timestamp("2026-01-01 00:00:00", tz="UTC"),
        "CLOSE_BUY",
        "buy",
        Decimal("0.10000000"),
        "a1",
        "utc_plus_2",
        0,
    )
    matcher = _OracleMatcher((label,), "utc_plus_2")
    matcher.consume(decision)
    assert matcher.result() == oracle_diagnostics((decision,), (label,), "utc_plus_2")


def test_old_duplicate_is_outside_window_and_cursor_remains_bounded() -> None:
    ticks = list(_dense_ticks("2026-01-01 00:00:00", "2026-01-01 00:02:00", start_bid=Decimal("2000"), end_bid=Decimal("2001")))
    ticks.insert(1, CausalTick(ticks[0].time_utc, ticks[0].bid, ticks[0].ask, True))
    cursor = _FeatureCursor()
    streamed = None
    for tick in ticks:
        streamed = cursor.push([tick], tick.time_utc, "utc_plus_2")
    expected = build_feature_snapshot(tuple(ticks), ticks[-1].time_utc, clock_id="utc_plus_2", state="HEDGED_1X1")
    assert streamed is not None and streamed.support_reason == expected.support_reason == "supported"
    assert len(cursor._ticks) <= 13
    assert len(cursor._min_deque) <= len(cursor._ticks)
    assert len(cursor._max_deque) <= len(cursor._ticks)


def test_old_duplicate_eviction_does_not_poison_new_anchor() -> None:
    base = list(_dense_ticks("2026-01-01 00:00:00", "2026-01-01 00:03:00", start_bid=Decimal("2000"), end_bid=Decimal("2001")))
    duplicate_index = next(index for index, item in enumerate(base) if item.time_utc == pd.Timestamp("2026-01-01 00:00:48", tz="UTC"))
    base.insert(duplicate_index + 1, CausalTick(base[duplicate_index].time_utc, base[duplicate_index].bid, base[duplicate_index].ask, True))
    cursor = _FeatureCursor()
    seen = []
    for index, tick in enumerate(base):
        streamed = cursor.push([tick], tick.time_utc, "utc_plus_2")
        if tick.time_utc == pd.Timestamp("2026-01-01 00:01:54", tz="UTC"):
            expected = build_feature_snapshot(tuple(base[: index + 1]), tick.time_utc, clock_id="utc_plus_2", state="HEDGED_1X1")
            seen.append((streamed.support_reason, expected.support_reason))
    assert seen == [("supported", "supported")]


def test_stream_cursor_retains_invalid_prefix_firewall() -> None:
    ticks = list(_dense_ticks("2026-01-01 00:00:00", "2026-01-01 00:02:00", start_bid=Decimal("2000"), end_bid=Decimal("2001")))
    cursor = _FeatureCursor()
    for tick in ticks:
        if tick.time_utc == pd.Timestamp("2026-01-01 00:01:00", tz="UTC"):
            tick = CausalTick(tick.time_utc, ZERO, ZERO, False, "crossed_quote")
        snapshot = cursor.push([tick], tick.time_utc, "utc_plus_2")
    assert snapshot.support_reason == "invalid_row"


def test_duplicate_and_future_tick_windows_fail_closed() -> None:
    duplicate = build_feature_snapshot(_ticks(
        ("2026-01-01 00:00:00", 2000, 2000.01, False),
        ("2026-01-01 00:00:00", 2000, 2000.01, True),
    ), pd.Timestamp("2026-01-01 00:00:00", tz="UTC"), clock_id="utc_plus_2", state="ONE_BUY")
    assert duplicate.support_reason == "duplicate_timestamp"
    with pytest.raises(RetroHistInputError, match="future tick"):
        build_feature_snapshot(_ticks(("2026-01-01 00:00:01", 2000, 2000.01, False)), pd.Timestamp("2026-01-01 00:00:00", tz="UTC"), clock_id="utc_plus_2", state="ONE_BUY")


def test_invalid_row_and_integer_gap_boundaries_fail_closed() -> None:
    invalid = CausalTick(pd.Timestamp("2026-01-01 00:01:00", tz="UTC"), ZERO, ZERO, False, "crossed_quote")
    ticks = _dense_ticks("2026-01-01 00:00:00", "2026-01-01 00:01:06", start_bid=Decimal("2000"), end_bid=Decimal("2001"))
    invalid_snapshot = build_feature_snapshot(tuple(ticks[:10]) + (invalid,) + tuple(ticks[11:]), ticks[-1].time_utc, clock_id="utc_plus_2", state="HEDGED_1X1")
    assert invalid_snapshot.support_reason == "invalid_row"
    gap_ticks = (
        CausalTick(pd.Timestamp("2026-01-01 00:00:06", tz="UTC"), Decimal("2000"), Decimal("2000.01")),
        CausalTick(pd.Timestamp("2026-01-01 00:01:00", tz="UTC"), Decimal("2000"), Decimal("2000.01")),
        CausalTick(pd.Timestamp("2026-01-01 00:01:06.000000001", tz="UTC"), Decimal("2000"), Decimal("2000.01")),
    )
    snapshot = build_feature_snapshot(gap_ticks, gap_ticks[-1].time_utc, clock_id="utc_plus_2", state="HEDGED_1X1")
    assert snapshot.support_reason == "quote_gap"


def test_candidate_side_specific_trigger_and_mirror_quantity() -> None:
    ticks = _dense_ticks("2026-01-01 00:00:00", "2026-01-01 00:02:00", start_bid=Decimal("2000"), end_bid=Decimal("1999"))
    snapshot = build_feature_snapshot(tuple(item for item in ticks if item.time_utc <= pd.Timestamp("2026-01-01 00:01:00", tz="UTC")), pd.Timestamp("2026-01-01 00:01:00", tz="UTC"), clock_id="utc_plus_2", state="UNBALANCED_HEDGE")
    state = CausalState("UNBALANCED_HEDGE", Decimal("0.20000000"), Decimal("0.10000000"))
    decision = evaluate_candidate(state, snapshot, "close_buy_adverse_ge_10")
    assert decision.outcome == "action"
    assert decision.action_kind == "CLOSE_BUY"
    assert decision.quantity == Decimal("0.20000000")
    after_close = apply_decision(state, decision)
    assert after_close.state == "ONE_SELL"
    rehedge_snapshot = build_feature_snapshot(ticks, pd.Timestamp("2026-01-01 00:02:00", tz="UTC"), clock_id="utc_plus_2", state="ONE_SELL")
    rehedge = evaluate_candidate(after_close, rehedge_snapshot, "rehedge_mirror_active_leg")
    assert rehedge.outcome == "action"
    assert rehedge.action_kind == "OPEN_BUY"
    assert rehedge.quantity == Decimal("0.10000000")
    assert apply_decision(after_close, rehedge).state == "HEDGED_1X1"


def test_reducer_rejects_nonmirror_action_metadata() -> None:
    state = CausalState("ONE_SELL", ZERO, Decimal("0.30000000"))
    bad_side = CausalDecision("action", "rehedge_mirror_active_leg", "ONE_SELL", pd.Timestamp("2026-01-01 00:01:00", tz="UTC"), "OPEN_BUY", "sell", Decimal("0.30000000"), "a" * 64)
    with pytest.raises(RetroHistInputError):
        apply_decision(state, bad_side)
    bad_quantity = CausalDecision("action", "rehedge_mirror_active_leg", "ONE_SELL", pd.Timestamp("2026-01-01 00:01:00", tz="UTC"), "OPEN_BUY", "buy", Decimal("0.10000000"), "a" * 64)
    with pytest.raises(RetroHistInputError):
        apply_decision(state, bad_quantity)
    valid = evaluate_candidate(
        state,
        FeatureSnapshot(pd.Timestamp("2026-01-01 00:01:00", tz="UTC"), "utc_plus_2", "ONE_SELL", Decimal("0"), Decimal("0"), Decimal("0"), Decimal("1"), Decimal("1"), 2, "supported", "supported"),
        "rehedge_mirror_active_leg",
    )
    tampered = CausalDecision(
        valid.outcome,
        valid.candidate_id,
        valid.state,
        valid.decision_time_utc,
        valid.action_kind,
        valid.side,
        valid.quantity,
        "a" * 64,
        valid.clock_id,
        valid.epoch,
    )
    with pytest.raises(RetroHistInputError):
        apply_decision(state, tampered)


def test_policy_rejects_repeated_timestamp_and_illegal_states() -> None:
    state = CausalState("HEDGED_1X1", Decimal("0.10000000"), Decimal("0.10000000"), pd.Timestamp("2026-01-01 00:01:00", tz="UTC"))
    snapshot = FeatureSnapshot(pd.Timestamp("2026-01-01 00:01:00", tz="UTC"), "utc_plus_2", "HEDGED_1X1", Decimal("1"), Decimal("0"), Decimal("0"), Decimal("1"), Decimal("1"), 2, "supported", "supported")
    assert evaluate_candidate(state, snapshot, "close_buy_increment_ge_0").outcome == "invalid"
    flat = CausalState("FLAT")
    later = FeatureSnapshot(pd.Timestamp("2026-01-01 00:02:00", tz="UTC"), "utc_plus_2", "FLAT", Decimal("1"), Decimal("0"), Decimal("0"), Decimal("1"), Decimal("1"), 2, "supported", "supported")
    assert evaluate_candidate(flat, later, "close_buy_increment_ge_0").outcome == "noneligible"
    contradictory = FeatureSnapshot(later.decision_time_utc, "utc_plus_2", "HEDGED_1X1", Decimal("1"), Decimal("0"), Decimal("0"), Decimal("1"), Decimal("7"), 2, "supported", "quote_gap")
    with pytest.raises(RetroHistInputError):
        contradictory.validate()
    with pytest.raises(RetroHistInputError):
        evaluate_candidate(flat, snapshot, "close_buy_increment_ge_0")
    with pytest.raises(RetroHistInputError):
        evaluate_candidate(
            CausalState("HEDGED_1X1", Decimal("0.10000000"), Decimal("0.10000000")),
            FeatureSnapshot(pd.Timestamp("2026-01-01 00:02:00", tz="UTC"), "utc_plus_2", "HEDGED_1X1", Decimal("1"), Decimal("0"), Decimal("0"), Decimal("1"), Decimal("7"), 2, "supported", "supported"),
            "close_buy_increment_ge_0",
        )
    with pytest.raises(RetroHistInputError):
        CausalState("FLAT", Decimal("0.10000000"), ZERO).validate()
    with pytest.raises(RetroHistInputError):
        CausalState("HEDGED_1X1", Decimal("0.10000000"), Decimal("0.20000000")).validate()
    with pytest.raises(RetroHistInputError):
        rh003.action_id({"candidate_id": "hold_only", "clock_id": "utc_plus_2", "epoch": 0, "decision_time_ns": 1, "kind": "CLOSE_BUY", "side": "buy", "quantity_fixed8": "0.1"})


def test_oracle_mutation_does_not_change_policy_digest() -> None:
    record = {"candidate_id": "close_buy_increment_ge_0", "clock_id": "utc_plus_2", "epoch": 0, "decision_time_ns": 1, "kind": "CLOSE_BUY", "side": "buy", "quantity_fixed8": "0.10000000"}
    first = action_digest([record])
    changed_label = OracleLabel("future", "OPEN", "sell", Decimal("0.90000000"), pd.Timestamp("2026-01-01 02:00:01"))
    diagnostics = oracle_diagnostics((CausalDecision("action", "close_buy_increment_ge_0", "HEDGED_1X1", pd.Timestamp("2026-01-01 00:00:00", tz="UTC"), "CLOSE_BUY", "buy", Decimal("0.10000000"), "a1"),), (changed_label,), "utc_plus_2")
    assert first == action_digest([record])
    assert diagnostics["direction_mismatch"] == 1


def test_action_digest_rejects_reordered_record_fields() -> None:
    record = {"candidate_id": "hold_only", "clock_id": "utc_plus_2", "epoch": 0, "decision_time_ns": 1, "kind": "CLOSE_BUY", "side": "buy", "quantity_fixed8": "0.10000000"}
    reordered = {key: record[key] for key in reversed(tuple(record))}
    with pytest.raises(RetroHistInputError):
        action_digest([reordered])


def test_raw_token_tick_adapter_preserves_decimal_and_global_order() -> None:
    handle = NamedTemporaryFile(prefix="rh003-ticks-", suffix=".csv", dir=Path.cwd(), delete=False, mode="w", encoding="utf-8")
    handle.write("time_utc,bid,ask\n2026-01-01T00:00:00Z,2000.123456789,2000.223456789\n2026-01-01T00:00:00Z,2000.1,2000.2\n2026-01-01T00:00:06Z,2000.3,2000.2\n")
    handle.close()
    path = Path(handle.name)
    try:
        ticks, stats = iter_ticks_decimal(path, broad_start=pd.Timestamp("2025-12-31 00:00:00", tz="UTC"), broad_end=pd.Timestamp("2026-01-02 00:00:00", tz="UTC"))
        parsed = list(ticks)
        assert parsed[0].bid == Decimal("2000.123456789")
        assert parsed[1].duplicate_timestamp is True
        assert stats["duplicate_timestamps"] == 1
        assert parsed[2].invalid_reason == "crossed_quote"
        assert stats["crossed_quotes"] == 1
    finally:
        path.unlink(missing_ok=True)


def test_raw_tick_adapter_marks_invalid_timestamp_callback() -> None:
    handle = NamedTemporaryFile(prefix="rh003-invalid-time-", suffix=".csv", dir=Path.cwd(), delete=False, mode="w", encoding="utf-8")
    handle.write("time_utc,bid,ask\nnot-a-time,2000,2000.01\n2026-01-01T00:00:00Z,2000,2000.01\n")
    handle.close()
    path = Path(handle.name)
    seen = []
    try:
        ticks, stats = iter_ticks_decimal(path, broad_start=pd.Timestamp("2025-12-31 00:00:00", tz="UTC"), broad_end=pd.Timestamp("2026-01-02 00:00:00", tz="UTC"), invalid_timestamp_callback=lambda: seen.append(True))
        assert len(list(ticks)) == 1
        assert stats["invalid_timestamp_rows"] == 1
        assert seen == [True]
    finally:
        path.unlink(missing_ok=True)


def test_aggregate_schema_digest_and_firewall() -> None:
    maps = empty_aggregate_maps()
    clocks = {clock: {"valid_rows": 0, "invalid_rows": 0, "duplicate_timestamps": 0, "out_of_order": 0, "crossed_quotes": 0, "envelope_excluded_rows": 0, "bootstrap_state": "FLAT"} for clock in CLOCK_IDS}
    digests = {candidate: {clock: hashlib.sha256(b"").hexdigest() for clock in CLOCK_IDS} for candidate in CANDIDATE_IDS}
    population = {"start_server": "2025-11-01 00:00:00", "end_server_exclusive": "2026-07-31 00:00:00", "report_alias_count": 9, "tick_alias_count": 39, "tick_clock_scenarios": list(CLOCK_IDS)}
    aggregate = aggregate_trigger_results(clocks=clocks, maps=maps, action_digests=digests, population=population)
    validate_aggregate(aggregate)
    assert aggregate["case_id"] == CASE_ID
    assert set(aggregate["action_counts"][CANDIDATE_IDS[0]][CLOCK_IDS[0]]) == set(ACTION_KINDS)
    tampered = dict(aggregate)
    tampered["claims"] = dict(aggregate["claims"])
    tampered["claims"]["raw_rows_printed"] = True
    with pytest.raises(RetroHistInputError):
        validate_aggregate(tampered)

    strict_bool = dict(aggregate)
    strict_bool["claims"] = dict(aggregate["claims"])
    strict_bool["claims"]["raw_rows_printed"] = 0
    strict_bool["aggregate_sha256"] = hashlib.sha256(json.dumps({key: value for key, value in strict_bool.items() if key != "aggregate_sha256"}, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    with pytest.raises(RetroHistInputError):
        validate_aggregate(strict_bool)

    missing_dimension = json.loads(json.dumps(aggregate))
    del missing_dimension["support_counts"][CANDIDATE_IDS[0]][CLOCK_IDS[0]]["FLAT"]
    missing_dimension["aggregate_sha256"] = hashlib.sha256(json.dumps({key: value for key, value in missing_dimension.items() if key != "aggregate_sha256"}, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    with pytest.raises(RetroHistInputError):
        validate_aggregate(missing_dimension)

    nested_private = json.loads(json.dumps(aggregate))
    nested_private["population"]["private_path"] = "raw"
    nested_private["aggregate_sha256"] = hashlib.sha256(json.dumps({key: value for key, value in nested_private.items() if key != "aggregate_sha256"}, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    with pytest.raises(RetroHistInputError):
        validate_aggregate(nested_private)

    reordered = {key: aggregate[key] for key in reversed(tuple(aggregate))}
    reordered["aggregate_sha256"] = hashlib.sha256(json.dumps({key: value for key, value in reordered.items() if key != "aggregate_sha256"}, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    with pytest.raises(RetroHistInputError):
        validate_aggregate(reordered)

    assert tuple(CANDIDATE_IDS) == tuple(rh003.CANDIDATE_IDS)
