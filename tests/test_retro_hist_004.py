from decimal import Decimal
import hashlib
import json

import pytest

import scripts.analyze_retro_hist_004_accounting as analyzer
from xau_trigger.retro_hist_002 import RetroHistInputError
from xau_trigger.retro_hist_004 import (
    ACTION_KINDS,
    CASE_ID,
    CLAIM_KEYS,
    LATENCY_BANDS,
    M5_FIREWALL,
    QUANTITY_BANDS,
    SCENARIO_IDS,
    STATUSES,
    TOP_LEVEL_KEYS,
    AccountingResult,
    PaperAction,
    Quote,
    account_cycle,
    empty_aggregate,
    finalize_aggregate,
    latency_band,
    result_digest,
    scenario_matrix,
    select_execution_quote,
    select_mark_quote,
    parse_price,
    parse_quantity,
    REPORT_MANIFEST_SHA256,
    TICK_MANIFEST_SHA256,
    validate_aggregate,
)


def _quote(time_ns: int, bid: str = "2000.00000000", ask: str = "2000.20000000", duplicate: bool = False) -> Quote:
    return Quote(time_ns, Decimal(bid), Decimal(ask), duplicate)


def _population() -> dict[str, object]:
    return {
        "start_server": "2025-11-01 00:00:00",
        "end_server_exclusive": "2026-07-31 00:00:00",
        "report_alias_count": 9,
        "tick_alias_count": 39,
        "tick_clock_scenarios": ["utc_plus_2", "utc_plus_3"],
    }


def _policy_digests() -> dict[str, dict[str, str]]:
    digest = "c" * 64
    candidates = (
        "hold_only", "close_buy_increment_ge_0", "close_sell_increment_le_0",
        "close_buy_adverse_ge_10", "close_sell_adverse_ge_10", "rehedge_mirror_active_leg",
    )
    return {candidate: {clock: digest for clock in ("utc_plus_2", "utc_plus_3")} for candidate in candidates}


def test_scenario_matrix_is_frozen_and_fingerprinted() -> None:
    scenarios = scenario_matrix()
    assert tuple(item.scenario_id for item in scenarios) == SCENARIO_IDS
    assert len({item.fingerprint() for item in scenarios}) == len(scenarios)
    assert scenarios[-1].latency_ns == 6_000_000_000


def test_bid_ask_signs_and_uneven_close_conservation() -> None:
    result = account_cycle(
        start_state="UNBALANCED_HEDGE",
        initial_buy=Decimal("0.30000000"),
        initial_sell=Decimal("0.10000000"),
        initial_quote=_quote(0),
        actions=(PaperAction("CLOSE_BUY", Decimal("0.20000000"), 10, "a"),),
        quotes=(_quote(10, "2001.00000000", "2001.20000000"), _quote(20, "2002.00000000", "2002.20000000")),
        scenario=scenario_matrix()[0],
        mark_time_ns=20,
    )
    assert result.status == "accounted_action"
    assert result.opened_buy == Decimal("0.30000000")
    assert result.closed_buy == Decimal("0.20000000")
    assert result.ending_buy == Decimal("0.10000000")
    assert result.opened_buy - result.closed_buy == result.ending_buy
    assert result.realized_price_units == Decimal("0.16000000000000000")
    assert result.unrealized_price_units == Decimal("-0.04000000000000000")


def test_all_action_quote_directions_are_legal() -> None:
    cases = (
        ("ONE_BUY", "OPEN_SELL", Decimal("0.10000000"), Decimal("0"), Decimal("0.10000000")),
        ("ONE_SELL", "OPEN_BUY", Decimal("0"), Decimal("0.10000000"), Decimal("0.10000000")),
        ("HEDGED_1X1", "CLOSE_BUY", Decimal("0.10000000"), Decimal("0.10000000"), Decimal("0.10000000")),
        ("HEDGED_1X1", "CLOSE_SELL", Decimal("0.10000000"), Decimal("0.10000000"), Decimal("0.10000000")),
    )
    for state, kind, buy, sell, quantity in cases:
        result = account_cycle(
            start_state=state,
            initial_buy=buy,
            initial_sell=sell,
            initial_quote=_quote(0),
            actions=(PaperAction(kind, quantity, 10, kind),),
            quotes=(_quote(10),),
            scenario=scenario_matrix()[0],
            mark_time_ns=None,
        )
        assert result.status == "accounted_action"


def test_latency_selects_exact_target_and_rejects_late_quote() -> None:
    scenario = scenario_matrix()[-1]
    selected, status = select_execution_quote((_quote(16),), 15, 2)
    assert selected is not None and status == "selected"
    missing, missing_status = select_execution_quote((_quote(14),), 15, 2)
    assert missing is None and missing_status == "unsupported"
    result = account_cycle(
        start_state="ONE_BUY",
        initial_buy=Decimal("0.10000000"),
        initial_sell=Decimal("0.00000000"),
        initial_quote=_quote(0),
        actions=(PaperAction("OPEN_SELL", Decimal("0.10000000"), 9, "lat"),),
        quotes=(_quote(6_000_000_009),),
        scenario=scenario,
        mark_time_ns=None,
    )
    assert result.status == "accounted_action"
    assert latency_band(result.selected_latency_ns) == "2-6s"


def test_marking_uses_last_quote_at_or_before_mark() -> None:
    selected, status = select_mark_quote((_quote(5), _quote(10)), 10)
    assert status == "selected" and selected is not None and selected.time_ns == 10
    missing, missing_status = select_mark_quote((_quote(11),), 10)
    assert missing is None and missing_status == "unsupported"


def test_duplicate_mark_quote_fails_closed() -> None:
    selected, status = select_mark_quote((_quote(10), _quote(10)), 10)
    assert selected is None and status == "unsupported"


def test_mark_horizon_rejects_stale_quote() -> None:
    selected, status = select_mark_quote((_quote(0),), 10, horizon_ns=1)
    assert selected is None and status == "unsupported"


def test_mark_skips_older_invalid_quote_when_later_valid_quote_is_available() -> None:
    invalid = Quote(5, Decimal("0"), Decimal("0"), invalid_reason="crossed_quote")
    selected, status = select_mark_quote((invalid, _quote(10)), 10)
    assert status == "selected" and selected is not None and selected.time_ns == 10


def test_duplicate_mark_quote_fails_closed_even_when_latest() -> None:
    selected, status = select_mark_quote((_quote(10, duplicate=True),), 10)
    assert selected is None and status == "unsupported"


def test_duplicate_initial_quote_fails_closed() -> None:
    result = account_cycle(
        start_state="ONE_BUY",
        initial_buy=Decimal("0.10000000"),
        initial_sell=Decimal("0.00000000"),
        initial_quote=_quote(0, duplicate=True),
        actions=(),
        quotes=(),
        scenario=scenario_matrix()[0],
        mark_time_ns=None,
    )
    assert result.status == "censored"


def test_fail_closed_paths_return_typed_results() -> None:
    for state, initial_quote in (("MULTI_POSITION", None), ("ONE_BUY", None)):
        result = account_cycle(
            start_state=state,
            initial_buy=Decimal("0.10000000"),
            initial_sell=Decimal("0.00000000"),
            initial_quote=initial_quote,
            actions=(),
            quotes=(),
            scenario=scenario_matrix()[0],
            mark_time_ns=None,
        )
        assert result.status in {"censored", "invalid"}
        assert result.action_count == 0


def test_fixed8_rejects_lexical_overprecision() -> None:
    with pytest.raises(RetroHistInputError):
        parse_quantity("1.000000000")
    with pytest.raises(RetroHistInputError):
        parse_price("2000.000000000")
    with pytest.raises(RetroHistInputError):
        parse_quantity(0.1)
    with pytest.raises(RetroHistInputError):
        parse_price(2000.1)


def test_partial_same_side_opens_are_accounted() -> None:
    result = account_cycle(
        start_state="ONE_BUY",
        initial_buy=Decimal("0.10000000"),
        initial_sell=Decimal("0.00000000"),
        initial_quote=_quote(0),
        actions=(PaperAction("OPEN_BUY", Decimal("0.20000000"), 10, "open"),),
        quotes=(_quote(10),),
        scenario=scenario_matrix()[0],
        mark_time_ns=None,
    )
    assert result.status == "accounted_action"
    assert result.opened_buy == Decimal("0.30000000")
    assert result.ending_buy == Decimal("0.30000000")


def test_future_initial_quote_is_rejected_as_lookahead() -> None:
    result = account_cycle(
        start_state="ONE_BUY",
        initial_buy=Decimal("0.10000000"),
        initial_sell=Decimal("0.00000000"),
        initial_quote=_quote(20),
        actions=(PaperAction("OPEN_SELL", Decimal("0.10000000"), 10, "future"),),
        quotes=(_quote(10),),
        scenario=scenario_matrix()[0],
        mark_time_ns=None,
    )
    assert result.status == "invalid"


def test_censored_mark_preserves_quantity_conservation() -> None:
    result = account_cycle(
        start_state="ONE_BUY",
        initial_buy=Decimal("0.10000000"),
        initial_sell=Decimal("0.00000000"),
        initial_quote=_quote(0),
        actions=(),
        quotes=(),
        scenario=scenario_matrix()[0],
        mark_time_ns=10,
    )
    assert result.status == "censored"
    assert result.opened_buy == result.censored_quantity
    assert result.ending_buy == Decimal("0.00000000")


def test_scenario_parameters_are_frozen() -> None:
    with pytest.raises(RetroHistInputError):
        account_cycle(
            start_state="FLAT",
            initial_buy=Decimal("0.00000000"),
            initial_sell=Decimal("0.00000000"),
            initial_quote=None,
            actions=(),
            quotes=(),
            scenario=type(scenario_matrix()[0])("zero_cost", Decimal("1.00000000"), Decimal("0"), 0, Decimal("0")),
            mark_time_ns=None,
        )


def test_invalid_quote_cannot_be_used_for_execution_or_marking() -> None:
    invalid = Quote(10, Decimal("0"), Decimal("0"), invalid_reason="crossed_quote")
    selected, status = select_execution_quote((invalid, _quote(11)), 10, 5)
    assert selected is None and status == "unsupported"
    marked, mark_status = select_mark_quote((_quote(5), invalid), 10)
    assert marked is None and mark_status == "unsupported"


def test_invalid_transition_does_not_mutate_ledger() -> None:
    result = account_cycle(
        start_state="ONE_BUY",
        initial_buy=Decimal("0.10000000"),
        initial_sell=Decimal("0.00000000"),
        initial_quote=_quote(0),
        actions=(PaperAction("CLOSE_BUY", Decimal("0.20000000"), 10, "over"),),
        quotes=(_quote(10),),
        scenario=scenario_matrix()[0],
        mark_time_ns=None,
    )
    assert result.status == "invalid"
    assert result.closed_buy == Decimal("0.00000000")
    assert result.ending_buy == Decimal("0.10000000")


def test_no_quote_is_censored_without_fabricated_fill() -> None:
    result = account_cycle(
        start_state="ONE_BUY",
        initial_buy=Decimal("0.10000000"),
        initial_sell=Decimal("0.00000000"),
        initial_quote=_quote(0),
        actions=(PaperAction("OPEN_SELL", Decimal("0.10000000"), 10, "missing"),),
        quotes=(),
        scenario=scenario_matrix()[0],
        mark_time_ns=None,
    )
    assert result.status == "unsupported"
    assert result.closed_sell == Decimal("0.00000000")


def test_cost_scenario_changes_accounting_only() -> None:
    action = PaperAction("CLOSE_BUY", Decimal("0.10000000"), 10, "same")
    kwargs = dict(
        start_state="HEDGED_1X1",
        initial_buy=Decimal("0.10000000"),
        initial_sell=Decimal("0.10000000"),
        initial_quote=_quote(0),
        actions=(action,),
        quotes=(_quote(10),),
        mark_time_ns=None,
    )
    zero = account_cycle(scenario=scenario_matrix()[0], **kwargs)
    fee = account_cycle(scenario=scenario_matrix()[1], **kwargs)
    assert zero.status == fee.status == "accounted_action"
    assert zero.action_count == fee.action_count == 1
    assert fee.costs_price_units > zero.costs_price_units


def test_empty_aggregate_schema_and_digest() -> None:
    aggregate = empty_aggregate(
        report_manifest_sha256=REPORT_MANIFEST_SHA256,
        tick_manifest_sha256=TICK_MANIFEST_SHA256,
        population=_population(),
        policy_action_digests=_policy_digests(),
    )
    aggregate = finalize_aggregate(aggregate)
    validate_aggregate(aggregate)
    assert tuple(aggregate) == TOP_LEVEL_KEYS
    assert aggregate["case_id"] == CASE_ID
    assert aggregate["m5_firewall"] == M5_FIREWALL
    assert tuple(aggregate["claims"]) == CLAIM_KEYS


def test_aggregate_rejects_reordered_or_private_claims() -> None:
    aggregate = finalize_aggregate(empty_aggregate(
        report_manifest_sha256=REPORT_MANIFEST_SHA256,
        tick_manifest_sha256=TICK_MANIFEST_SHA256,
        population=_population(),
        policy_action_digests=_policy_digests(),
    ))
    reordered = {key: aggregate[key] for key in reversed(tuple(aggregate))}
    with pytest.raises(RetroHistInputError):
        validate_aggregate(reordered)
    private = json.loads(json.dumps(aggregate))
    private["claims"]["raw_rows_printed"] = True
    private["aggregate_sha256"] = hashlib.sha256(b"tampered").hexdigest()
    with pytest.raises(RetroHistInputError):
        validate_aggregate(private)


def test_aggregate_rejects_nested_unknown_and_path_payloads() -> None:
    aggregate = finalize_aggregate(empty_aggregate(
        report_manifest_sha256=REPORT_MANIFEST_SHA256,
        tick_manifest_sha256=TICK_MANIFEST_SHA256,
        population=_population(),
        policy_action_digests=_policy_digests(),
    ))
    nested = json.loads(json.dumps(aggregate))
    nested["population"] = {"path": "C:\\secret"}
    nested["aggregate_sha256"] = hashlib.sha256(b"tampered").hexdigest()
    with pytest.raises(RetroHistInputError):
        validate_aggregate(nested)


def test_aggregate_rejects_private_mapping_key_and_colon_path() -> None:
    aggregate = finalize_aggregate(empty_aggregate(
        report_manifest_sha256=REPORT_MANIFEST_SHA256,
        tick_manifest_sha256=TICK_MANIFEST_SHA256,
        population=_population(),
        policy_action_digests=_policy_digests(),
    ))
    nested = json.loads(json.dumps(aggregate))
    nested["policy_action_digests"] = {"ticket": {"utc_plus_2": "c" * 64}}
    with pytest.raises(RetroHistInputError):
        validate_aggregate(nested)
    nested = json.loads(json.dumps(aggregate))
    nested["population"] = {"start_server": "C:secret"}
    with pytest.raises(RetroHistInputError):
        validate_aggregate(nested)
    nested = json.loads(json.dumps(aggregate))
    nested["policy_action_digests"] = {"raw": {"ticket": "123"}}
    nested["aggregate_sha256"] = hashlib.sha256(b"tampered").hexdigest()
    with pytest.raises(RetroHistInputError):
        validate_aggregate(nested)


def test_result_digest_is_deterministic() -> None:
    result = AccountingResult("no_action", Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), Decimal("0"), None, 0)
    assert result_digest(result) == result_digest(result)
    assert set(ACTION_KINDS) == {"CLOSE_BUY", "CLOSE_SELL", "OPEN_BUY", "OPEN_SELL"}
    assert set(STATUSES) == {"no_action", "accounted_action", "unsupported", "invalid", "censored"}
    assert len(QUANTITY_BANDS) == 8
    assert len(LATENCY_BANDS) == 5


def test_historical_analyzer_composes_flat_policy_without_oracle_actions(monkeypatch) -> None:
    monkeypatch.setattr(analyzer, "verify_manifest", lambda *args, **kwargs: {})
    monkeypatch.setattr(analyzer, "load_positions_retro", lambda paths: ([], {}))
    candidates = (
        "hold_only", "close_buy_increment_ge_0", "close_sell_increment_le_0",
        "close_buy_adverse_ge_10", "close_sell_adverse_ge_10", "rehedge_mirror_active_leg",
    )
    empty_digests = {candidate: {clock: hashlib.sha256(b"").hexdigest() for clock in ("utc_plus_2", "utc_plus_3")} for candidate in candidates}
    monkeypatch.setattr(analyzer, "_run_replay", lambda paths, positions: ({}, {"action_digests": empty_digests}))
    aggregate = analyzer.run()
    validate_aggregate(aggregate)
    assert aggregate["bootstrap_state"] == "FLAT"
    assert all(aggregate["accounting_counts"][scenario]["no_action"] == 1 for scenario in SCENARIO_IDS)
