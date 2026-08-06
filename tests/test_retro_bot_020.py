from __future__ import annotations

import copy
import json
from pathlib import Path
import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_020 import (
    oracle_diagnostic, parse_autonomous, parse_oracle, replay_autonomous,
    verify_aggregate, walk_forward, paper_account,
    validate_source, replay_decisions,
    consume_redacted_stream,
    adapt_rh_ticks, adapt_rh_lifecycle, build_autonomous_input, build_lane_inputs,
    account_lifecycle_records,
    seal_holdout, verify_holdout_receipt,
    AutonomousInput,
    replay_rh003_candidate,
)


def _auto(ticks=None, state="FLAT", bootstrap=True):
    return {"ticks": ticks or [{"time_ns": 10, "bid": "2000.00000000", "ask": "2000.20000000"}],
            "initial_state": state, "bootstrap_supported": bootstrap,
            "latency_ns": 2, "candidate": "open_on_first_tick"}


def test_autonomous_is_causal_and_oracle_fields_rejected():
    base = replay_autonomous(parse_autonomous(_auto()))
    altered = _auto([{"time_ns": 10, "bid": "2000.00000000", "ask": "2000.20000000"},
                     {"time_ns": 20, "bid": "1900.00000000", "ask": "1900.20000000"}])
    changed = replay_autonomous(parse_autonomous(altered))
    assert changed["action_counts"]["OPEN_BUY"] == base["action_counts"]["OPEN_BUY"]
    assert changed["future_read"] is False
    bad = copy.deepcopy(_auto()); bad["oracle_labels"] = []
    with pytest.raises(RetroBotInputError): parse_autonomous(bad)


def test_unknown_bootstrap_fails_closed_and_latency_is_causal():
    result = replay_autonomous(parse_autonomous(_auto(state="UNKNOWN", bootstrap=False)))
    assert result["decision_count"] == 0 and result["censored_count"] == 1
    result = replay_autonomous(parse_autonomous(_auto()))
    assert result["decision_count"] == 1


def test_oracle_diagnostic_is_separate_and_aggregate_verifies():
    diagnostic = oracle_diagnostic(parse_oracle({"observed_events": [{"time_ns": 12, "action": "OPEN_BUY"}]}))
    assert diagnostic["oracle_only"] is True
    assert diagnostic["match_bands"]["exact"] == 0
    assert verify_aggregate(replay_autonomous(parse_autonomous(_auto())))


def test_lifecycle_close_and_nonmatching_oracle_are_redacted():
    inp = parse_autonomous(_auto([{"time_ns": 10, "bid": "2000", "ask": "2000.2"}, {"time_ns": 20, "bid": "1999", "ask": "1999.2"}]))
    result = replay_autonomous(inp)
    assert result["action_counts"]["CLOSE_BUY"] == 1
    diagnostic = oracle_diagnostic(parse_oracle({"observed_events": [{"time_ns": 22, "action": "OPEN_SELL"}]}))
    assert diagnostic["oracle_only"] is True


def test_walk_forward_and_paper_account_have_distinct_stage_outputs():
    inp = parse_autonomous(_auto())
    raw_folds = {name: parse_autonomous(_auto([{"time_ns": t, "bid": "2000.00000000", "ask": "2000.20000000"}])) for name, t in (("development", 1), ("validation", 2), ("holdout", 3))}
    aliases_by_fold = {"development": [f"report-{i:03d}.html" for i in range(1, 6)], "validation": ["report-006.html", "report-007.html"], "holdout": ["report-008.html", "report-009.html"]}
    folds = {name: AutonomousInput(item.ticks, item.initial_state, item.bootstrap_supported, item.latency_ns, item.candidate, tuple(aliases_by_fold[name])) for name, item in raw_folds.items()}
    wf = walk_forward(inp, fold_inputs=folds, fold_aliases=aliases_by_fold, holdout_receipt=seal_holdout(holdout=folds["holdout"], nonce="nonce-1234"), used_nonces=set())
    pa = paper_account(inp)
    assert wf["stage"] == "walk-forward" and pa["stage"] == "paper-account"
    assert wf["folds"]["holdout"]["engine"] == "RH-003-causal"
    assert pa["accounting"]["conserved"] is True
    assert verify_aggregate(wf) and verify_aggregate(pa)


def test_tick_ordering_rejected():
    with pytest.raises(RetroBotInputError):
        parse_autonomous(_auto([{"time_ns": 2, "bid": "1", "ask": "1"}, {"time_ns": 1, "bid": "1", "ask": "1"}]))


def test_receipt_aliases_and_real_decision_wiring():
    report_aliases = [f"report-{i:03d}.html" for i in range(1,10)]
    pins = json.loads((Path(__file__).parents[1] / "docs" / "retro_bot" / "RETRO-BOT-020-object-hash-pins.json").read_text(encoding="utf-8-sig"))
    aliases = list(pins["tick_alias_hashes"])
    receipt = {"authorization": "RB020_OWNER_AUTHORIZED_2026-08-06", "report_manifest_sha256": "88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30", "tick_manifest_sha256": "a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c", "population": ["2025-11-01T00:00:00Z", "2026-07-31T00:00:00Z"], "report_aliases": report_aliases, "tick_aliases": aliases, "object_hashes": {"report_manifest": pins["report_manifest_sha256"], "tick_manifest": pins["tick_manifest_sha256"]}, "alias_hashes": {**pins["report_alias_hashes"], **pins["tick_alias_hashes"]}, "allowed_fields": {"reports": ["positions", "open_positions"], "ticks": ["time_utc", "bid", "ask"]}, "retention": "in-memory-aggregates-only"}
    assert validate_source(receipt)["validated"] is True
    assert replay_decisions(parse_autonomous(_auto()))[0].action == "OPEN_BUY"


def test_stream_adapter_retains_only_bounded_digest():
    result = consume_redacted_stream(iter([{"time_ns": 1, "bid": "1", "ask": "2"}]))
    assert result["row_count"] == 1 and len(result["stream_digest_sha256"]) == 64


def test_rh_adapters_produce_typed_redacted_inputs():
    ticks = adapt_rh_ticks([{"time_ns": 1, "bid": "1", "ask": "1.2"}, {"time_ns": 2, "bid": "2", "ask": "2.2"}])
    assert ticks[0].time_ns == 1
    actions = adapt_rh_lifecycle([{"kind": "OPEN", "side": "BUY", "quantity": "0.30000000", "time_ns": 1}])
    assert actions[0]["action"] == "OPEN_BUY"
    assert build_autonomous_input(ticks=ticks).ticks[0].bid == ticks[0].bid


def test_golden_lot_accounting_bid_ask_and_partial_close():
    actions = [{"kind": "OPEN", "side": "BUY", "quantity": "0.30000000", "time_ns": 1}, {"kind": "CLOSE", "side": "BUY", "quantity": "0.10000000", "time_ns": 2}]
    quotes = [{"time_ns": 1, "bid": "100.00000000", "ask": "101.00000000"}, {"time_ns": 2, "bid": "102.00000000", "ask": "103.00000000"}]
    result = account_lifecycle_records(actions, quotes, fee_per_unit="1.00000000")
    assert result["buy_remaining_fixed8"] == "0.20000000"
    assert result["closed_quantity_fixed8"] == "0.10000000"
    assert result["cash_fixed8"] == "-20.50000000"


def test_holdout_receipt_is_bound_and_one_shot():
    holdout = parse_autonomous(_auto())
    receipt = seal_holdout(holdout=holdout, nonce="nonce-1234")
    assert verify_holdout_receipt(receipt, holdout=holdout, used_nonces=set())
    with pytest.raises(RetroBotInputError): verify_holdout_receipt(receipt, holdout=holdout, used_nonces={"nonce-1234"})


def test_lane_adapter_keeps_policy_and_observed_labels_separate():
    autonomous, oracle = build_lane_inputs(
        ticks=[{"time_ns": 1, "bid": "100.00000000", "ask": "101.00000000"}],
        lifecycle=[{"kind": "OPEN", "side": "BUY", "quantity": "0.30000000", "time_ns": 1}],
    )
    assert autonomous.ticks[0].bid == 100
    assert oracle.observed_events[0]["action"] == "OPEN_BUY"


def test_rh003_candidate_engine_is_causal_and_oracle_free():
    inp = parse_autonomous(_auto([{"time_ns": 1_000_000_000, "bid": "2000.00000000", "ask": "2000.20000000"}, {"time_ns": 2_000_000_000, "bid": "2000.10000000", "ask": "2000.30000000"}], state="ONE_BUY"))
    result = replay_rh003_candidate(inp)
    assert result["engine"] == "RH-003-causal" and result["future_read"] is False and result["oracle_used"] is False
