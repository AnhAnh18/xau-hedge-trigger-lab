from __future__ import annotations

import pandas as pd
import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_005 import StateSnapshot
from xau_trigger.retro_bot_006 import FeatureSnapshot, RuleClause, TriggerRule
from xau_trigger.retro_bot_007 import (
    CandidatePolicy,
    OracleLabel,
    aggregate_candidate_results,
    evaluate_candidate,
    match_oracle_labels,
    match_oracle_sequence,
    timing_band,
)


def hedged() -> StateSnapshot:
    return StateSnapshot("HEDGED", 2, pd.Timestamp("2026-01-01T00:00:00Z"), 1.0)


def snap() -> FeatureSnapshot:
    return FeatureSnapshot(pd.Timestamp("2026-01-01T00:01:00Z"), {"state": "HEDGED", "side": "buy", "clock_id": "utc_plus_3"})


def test_first_legal_match_maps_close_direction_and_hold_policy() -> None:
    rule = TriggerRule("a", (RuleClause("state", "always"),), "CLOSE_BUY")
    assert evaluate_candidate(hedged(), snap(), CandidatePolicy("first_legal_match", (rule,)), expected_epoch=2).action_side == "sell"
    assert evaluate_candidate(hedged(), snap(), CandidatePolicy("always_hold"), expected_epoch=2).outcome == "hold"


def test_epoch_noneligible_censored_and_missing_are_fail_closed() -> None:
    rule = TriggerRule("a", (RuleClause("spread_points", "ge", 1),), "CLOSE_SELL")
    assert evaluate_candidate(hedged(), snap(), CandidatePolicy("first_legal_match", (rule,)), expected_epoch=1).outcome == "invalid_transition"
    one = StateSnapshot("ONE_BUY", 2, hedged().last_time, 1.0)
    assert evaluate_candidate(one, snap(), CandidatePolicy("first_legal_match", (rule,)), expected_epoch=2).outcome == "noneligible"
    censored = StateSnapshot("CENSORED", 0, hedged().last_time, 1.0)
    assert evaluate_candidate(censored, snap(), CandidatePolicy("first_legal_match", (rule,)), expected_epoch=0).outcome == "censored"
    assert evaluate_candidate(hedged(), snap(), CandidatePolicy("first_legal_match", (rule,)), expected_epoch=2).outcome == "feature_missing"
    bypass = CandidatePolicy("first_legal_match", (rule, TriggerRule("z", (RuleClause("state", "always"),), "CLOSE_SELL")))
    assert evaluate_candidate(hedged(), snap(), bypass, expected_epoch=2).outcome == "feature_missing"


def test_malformed_policy_and_duplicate_rules_fail_closed() -> None:
    rule = TriggerRule("a", (), "CLOSE_BUY")
    with pytest.raises(RetroBotInputError):
        CandidatePolicy("always_hold", (rule,)).validate()
    with pytest.raises(RetroBotInputError):
        CandidatePolicy("first_legal_match", (rule, rule)).validate()
    illegal = TriggerRule("b", (RuleClause("state", "always"),), "OPEN_BUY")
    with pytest.raises(RetroBotInputError):
        CandidatePolicy("first_legal_match", (illegal,)).validate()
    with pytest.raises(RetroBotInputError):
        CandidatePolicy("first_legal_match", (object(),)).validate()


def test_oracle_matching_and_timing_bands_are_deterministic() -> None:
    labels = (
        OracleLabel("case_1", pd.Timestamp("2026-01-01T00:00:01Z"), "CLOSE_BUY"),
        OracleLabel("case_1", pd.Timestamp("2026-01-01T00:00:08Z"), "CLOSE_BUY"),
    )
    assert match_oracle_labels("case_1", "2026-01-01T00:00:00Z", "CLOSE_BUY", labels) == "0-1s"
    assert timing_band(0) == "exact"
    assert timing_band(6) == "2-6s"
    assert match_oracle_labels("case_1", "2026-01-01T00:01:00Z", "CLOSE_BUY", labels) == "unmatched"
    counts = match_oracle_sequence((("case_1", "2026-01-01T00:00:00Z", "CLOSE_BUY"), ("case_1", "2026-01-01T00:00:00Z", "CLOSE_BUY"), ("case_1", "2026-01-01T00:00:00Z", "CLOSE_BUY")), labels)
    assert counts["unmatched"] == 1


def test_aggregate_is_redacted_and_reproducible() -> None:
    first = aggregate_candidate_results({"hold": 1}, policy_id="always_hold", eligible=1)
    assert first == aggregate_candidate_results({"hold": 1}, policy_id="always_hold", eligible=1)
    assert first["m5_firewall"] == "M5_FIREWALL_ATTESTATION_V1"
    with pytest.raises(RetroBotInputError):
        aggregate_candidate_results({"hold": 1}, policy_id="always_hold", eligible=1, case_id="bad/path")


def test_optional_tick_prefix_is_revalidated_at_engine_boundary() -> None:
    rule = TriggerRule("a", (RuleClause("state", "always"),), "CLOSE_BUY")
    ticks = [
        {"time": "2026-01-01T00:00:00Z", "bid": 2000.0, "ask": 2000.1},
        {"time": "2026-01-01T00:00:00Z", "bid": 2000.0, "ask": 2000.1},
    ]
    with pytest.raises(RetroBotInputError):
        evaluate_candidate(hedged(), snap(), CandidatePolicy("first_legal_match", (rule,)), expected_epoch=2, ticks=ticks)
    assert evaluate_candidate(hedged(), snap(), CandidatePolicy("always_hold"), expected_epoch=2, seen_decision_times=frozenset({snap().decision_time})).outcome == "invalid_transition"
