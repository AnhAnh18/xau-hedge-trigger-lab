from __future__ import annotations

import pandas as pd
import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_006 import (
    CATEGORICAL_VALUES,
    FeatureSnapshot,
    RuleClause,
    TriggerRule,
    aggregate_rule_results,
    build_causal_snapshot,
    evaluate_rule,
    evaluate_rules,
    validate_snapshot,
)


def snap(**values: object) -> FeatureSnapshot:
    base = {"state": "HEDGED", "side": "buy", "session_bucket": "europe", "clock_id": "utc_plus_3"}
    base.update(values)
    return FeatureSnapshot(pd.Timestamp("2026-01-01T00:00:00Z"), base)


def test_numeric_boundaries_and_parameterless_operators() -> None:
    assert evaluate_rule(snap(state_age_seconds=60), TriggerRule("a", (RuleClause("state_age_seconds", "ge", 60),), "CLOSE_BUY")) == "candidate_action"
    assert evaluate_rule(snap(state_age_seconds=59), TriggerRule("a", (RuleClause("state_age_seconds", "ge", 60),), "CLOSE_BUY")) == "hold"
    assert evaluate_rule(snap(), TriggerRule("always", (RuleClause("state", "always"),), "CLOSE_BUY")) == "candidate_action"


def test_missing_or_future_oracle_features_fail_closed() -> None:
    assert evaluate_rule(snap(), TriggerRule("missing", (RuleClause("spread_points", "ge", 1),), "CLOSE_BUY")) == "feature_missing"
    changed = FeatureSnapshot(pd.Timestamp("2026-01-01T00:00:00Z"), {"state": "HEDGED"}, ("future_rehedge",))
    assert evaluate_rule(changed, TriggerRule("state", (RuleClause("state", "always"),), "CLOSE_BUY")) == "candidate_action"


def test_invalid_grid_domain_and_digest_are_rejected() -> None:
    with pytest.raises(RetroBotInputError):
        evaluate_rule(snap(state_age_seconds=2), TriggerRule("bad", (RuleClause("state_age_seconds", "ge", 2),), "CLOSE_BUY"))
    with pytest.raises(RetroBotInputError):
        evaluate_rule(snap(state_age_seconds=60), TriggerRule("bad", (RuleClause("state_age_seconds", "ge", True),), "CLOSE_BUY"))
    with pytest.raises(RetroBotInputError):
        evaluate_rule(snap(session_bucket="other"), TriggerRule("bad", (RuleClause("session_bucket", "always"),), "CLOSE_BUY"))
    first = aggregate_rule_results({"hold": 1})
    assert first == aggregate_rule_results({"hold": 1})
    assert first["source_manifest_digests"]["report_manifest_sha256"]
    assert first["m5_firewall"] == "not_an_M5_input; descriptive RETRO only"


def test_causal_builder_uses_sixty_second_anchor_and_side_excursion() -> None:
    ticks = [
        {"time": "2026-01-01T00:00:00Z", "bid": 2000.0, "ask": 2000.1},
        {"time": "2026-01-01T00:00:30Z", "bid": 1998.0, "ask": 1998.1},
        {"time": "2026-01-01T00:01:00Z", "bid": 1999.0, "ask": 1999.1},
        {"time": "2026-01-01T00:01:10Z", "bid": 2001.0, "ask": 2001.1},
    ]
    snapshot = build_causal_snapshot(ticks, "2026-01-01T00:01:10Z", state="ONE_BUY", side="buy", clock_id="utc_plus_3")
    assert snapshot.values["price_increment"] == pytest.approx(1.0)
    assert snapshot.values["adverse_excursion"] == pytest.approx(2.0)
    assert snapshot.feature_times["price_increment"] <= snapshot.decision_time


def test_causal_builder_rejects_duplicate_order_future_and_bad_quotes() -> None:
    base = {"time": "2026-01-01T00:00:00Z", "bid": 2000.0, "ask": 2000.1}
    with pytest.raises(RetroBotInputError):
        build_causal_snapshot([base, dict(base)], base["time"], state="HEDGED", side="buy", clock_id="utc_plus_3")
    with pytest.raises(RetroBotInputError):
        build_causal_snapshot([dict(base, time="2026-01-01T00:00:01Z"), base], base["time"], state="HEDGED", side="buy", clock_id="utc_plus_3")
    with pytest.raises(RetroBotInputError):
        build_causal_snapshot([dict(base, bid="not-a-number")], base["time"], state="HEDGED", side="buy", clock_id="utc_plus_3")


def test_nonfinite_values_fail_closed_and_snapshot_config_is_immutable() -> None:
    checked = validate_snapshot(snap(spread_points=float("nan")))
    assert evaluate_rule(checked, TriggerRule("a", (RuleClause("state", "always"),), "CLOSE_BUY")) == "feature_missing"
    with pytest.raises(TypeError):
        checked.values["state"] = "ONE_BUY"
    with pytest.raises(AttributeError):
        CATEGORICAL_VALUES["state"].add("BAD")
    huge = validate_snapshot(snap(state_age_seconds=10**1000))
    assert evaluate_rule(huge, TriggerRule("a", (RuleClause("state", "always"),), "CLOSE_BUY")) == "feature_missing"


def test_illegal_action_is_reported_only_when_rule_matches_and_ties_are_by_id() -> None:
    illegal = TriggerRule("z", (RuleClause("state", "always"),), "OPEN_BUY")
    legal = TriggerRule("a", (RuleClause("state", "always"),), "CLOSE_BUY")
    assert evaluate_rule(snap(), illegal) == "invalid_transition"
    assert evaluate_rules(snap(), (illegal, legal)) == "candidate_action"
    assert evaluate_rules(snap(), (TriggerRule("a", (RuleClause("state", "never"),), "OPEN_BUY"), illegal)) == "invalid_transition"


def test_categorical_between_requires_equal_bounds_and_hedged_omits_excursion() -> None:
    with pytest.raises(RetroBotInputError):
        evaluate_rule(snap(session_bucket="asia"), TriggerRule("bad", (RuleClause("session_bucket", "between", "asia", "us"),), "CLOSE_BUY"))
    snapshot = build_causal_snapshot(
        [{"time": "2026-01-01T00:00:00Z", "bid": 2000.0, "ask": 2000.1}],
        "2026-01-01T00:00:00Z", state="HEDGED", side="buy", clock_id="utc_plus_3",
    )
    assert "adverse_excursion" not in snapshot.values


def test_tick_boundary_rejects_prohibited_extra_fields_and_duplicate_rule_ids() -> None:
    tick = {"time": "2026-01-01T00:00:00Z", "bid": 2000.0, "ask": 2000.1, "ticket": "private"}
    with pytest.raises(RetroBotInputError):
        build_causal_snapshot([tick], tick["time"], state="HEDGED", side="buy", clock_id="utc_plus_3")
    rule = TriggerRule("same", (RuleClause("state", "always"),), "CLOSE_BUY")
    with pytest.raises(RetroBotInputError):
        evaluate_rules(snap(), (rule, rule))
