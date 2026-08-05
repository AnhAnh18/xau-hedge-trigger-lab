from __future__ import annotations

import pandas as pd
import pytest

from xau_trigger.retro_bot_005 import StateSnapshot
from xau_trigger.retro_bot_006 import FeatureSnapshot, RuleClause, TriggerRule
from xau_trigger.retro_bot_008 import RehedgePolicy, aggregate_rehedge_results, evaluate_rehedge
from xau_trigger.retro_bot import RetroBotInputError


def state(name: str) -> StateSnapshot:
    return StateSnapshot(name, 1, pd.Timestamp("2026-01-01T00:00:00Z"), 1.0)


def snapshot() -> FeatureSnapshot:
    return FeatureSnapshot(pd.Timestamp("2026-01-01T00:01:00Z"), {"state": "ONE_BUY", "side": "buy", "clock_id": "utc_plus_3"})


def test_one_leg_direction_mapping_and_hold() -> None:
    rules = (TriggerRule("open_sell", (RuleClause("state", "always"),), "OPEN_SELL"), TriggerRule("open_buy", (RuleClause("state", "always"),), "OPEN_BUY"))
    result = evaluate_rehedge(state("ONE_BUY"), snapshot(), RehedgePolicy("first_legal_match", rules), expected_epoch=1)
    assert (result.outcome, result.action_kind, result.action_side) == ("action", "OPEN_SELL", "sell")
    assert evaluate_rehedge(state("ONE_SELL"), snapshot(), RehedgePolicy("always_hold"), expected_epoch=1).outcome == "hold"


def test_illegal_state_epoch_missing_and_oracle_are_censored() -> None:
    rules = (TriggerRule("open_sell", (RuleClause("state", "always"),), "OPEN_SELL"), TriggerRule("open_buy", (RuleClause("state", "always"),), "OPEN_BUY"))
    assert evaluate_rehedge(state("HEDGED"), snapshot(), RehedgePolicy("first_legal_match", rules), expected_epoch=1).outcome == "censored"
    assert evaluate_rehedge(state("ONE_BUY"), snapshot(), RehedgePolicy("first_legal_match", rules), expected_epoch=0).outcome == "censored"
    oracle = FeatureSnapshot(snapshot().decision_time, snapshot().values, ("future",))
    assert evaluate_rehedge(state("ONE_BUY"), oracle, RehedgePolicy("first_legal_match", rules), expected_epoch=1).outcome == "censored"


def test_missing_rule_feature_censors_and_aggregate_is_reproducible() -> None:
    rules = (TriggerRule("open_sell", (RuleClause("spread_points", "ge", 1),), "OPEN_SELL"), TriggerRule("open_buy", (RuleClause("state", "always"),), "OPEN_BUY"))
    assert evaluate_rehedge(state("ONE_BUY"), snapshot(), RehedgePolicy("first_legal_match", rules), expected_epoch=1).outcome == "censored"
    first = aggregate_rehedge_results({"hold": 1, "action": 0, "censored": 0}, policy_id="always_hold", windows=1)
    assert first == aggregate_rehedge_results({"hold": 1, "action": 0, "censored": 0}, policy_id="always_hold", windows=1)
    with pytest.raises(RetroBotInputError):
        aggregate_rehedge_results({"hold": 1}, policy_id="always_hold", windows=1)
