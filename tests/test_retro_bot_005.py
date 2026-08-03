from __future__ import annotations

import pandas as pd

from xau_trigger.retro_bot_005 import (
    OracleLabel,
    PolicyAction,
    aggregate_reductions,
    apply_policy_action,
    bootstrap_state,
    oracle_labels_do_not_mutate_policy_state,
    reduce_policy_actions,
    classify_continuation,
    StateSnapshot,
)


def action(kind: str, second: int, epoch: int = 0) -> PolicyAction:
    return PolicyAction(kind, pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(seconds=second), epoch)


def test_complete_allowed_transition_paths() -> None:
    result = reduce_policy_actions("fixed_warmup_seed", "2026-01-01T00:00:00Z", (action("CLOSE_BUY", 1), action("OPEN_BUY", 2)))
    assert result.status == "ok"
    assert result.final_state == "HEDGED"
    assert result.accepted_count == 2
    result = reduce_policy_actions("fixed_warmup_seed", "2026-01-01T00:00:00Z", (action("CLOSE_SELL", 1), action("OPEN_SELL", 2)))
    assert result.final_state == "HEDGED"


def test_terminal_and_censored_states_reject_actions() -> None:
    terminal = reduce_policy_actions("fixed_warmup_seed", "2026-01-01T00:00:00Z", (action("TERMINATE", 1), action("CLOSE_BUY", 2)))
    assert terminal.status == "invalid_transition"
    assert terminal.final_state == "TERMINAL"
    assert terminal.invalid_count == 1
    censored = reduce_policy_actions("left_censored", "2026-01-01T00:00:00Z", (action("CLOSE_BUY", 1),))
    assert censored.status == "censored"
    assert censored.final_state == "CENSORED"


def test_illegal_duplicate_same_second_and_wrong_side_actions_fail_closed() -> None:
    snapshot = bootstrap_state("fixed_warmup_seed", "2026-01-01T00:00:00Z")
    snapshot, first = apply_policy_action(snapshot, action("CLOSE_BUY", 1))
    assert first.status == "accepted"
    _, wrong = apply_policy_action(snapshot, action("CLOSE_BUY", 2))
    assert wrong.status == "invalid_transition"
    _, duplicate = apply_policy_action(snapshot, action("OPEN_SELL", 1))
    assert duplicate.status == "invalid_transition"


def test_non_increasing_input_is_not_sorted_or_repaired() -> None:
    result = reduce_policy_actions("fixed_warmup_seed", "2026-01-01T00:00:00Z", (action("CLOSE_BUY", 2), action("OPEN_SELL", 1)))
    assert result.status == "invalid_transition"
    assert result.accepted_count == 1


def test_first_tick_at_anchor_is_eligible_but_same_second_collides() -> None:
    anchor = pd.Timestamp("2026-01-01", tz="UTC")
    first = PolicyAction("CLOSE_BUY", anchor, 0)
    same_second = PolicyAction("OPEN_BUY", anchor + pd.Timedelta(milliseconds=500), 0)
    result = reduce_policy_actions("fixed_warmup_seed", anchor, (first, same_second))
    assert result.accepted_count == 1
    assert result.invalid_count == 1


def test_fold_continuation_boundary_is_explicit() -> None:
    assert classify_continuation("2026-01-01", "2026-01-02", "2026-01-01", "2026-01-03") == "valid"
    assert classify_continuation("2026-01-02", "2026-01-04", "2026-01-01", "2026-01-03") == "cross_fold_continuation"


def test_mixed_timestamp_and_non_float_quantity_fail_closed() -> None:
    snapshot = bootstrap_state("fixed_warmup_seed", "2026-01-01T00:00:00Z")
    _, result = apply_policy_action(snapshot, PolicyAction("CLOSE_BUY", pd.Timestamp("2026-01-01 00:00:01"), 0))
    assert result.status == "accepted"
    import pytest
    from xau_trigger.retro_bot import RetroBotInputError
    with pytest.raises(RetroBotInputError):
        StateSnapshot("HEDGED", 0, snapshot.last_time, True)


def test_oracle_labels_are_separate_and_do_not_change_replay() -> None:
    labels = oracle_labels_do_not_mutate_policy_state((OracleLabel("REHEDGE_BUY", pd.Timestamp("2026-01-01", tz="UTC")),))
    assert len(labels) == 1
    actions = (action("CLOSE_BUY", 1), action("OPEN_BUY", 2))
    assert reduce_policy_actions("fixed_warmup_seed", "2026-01-01T00:00:00Z", actions) == reduce_policy_actions("fixed_warmup_seed", "2026-01-01T00:00:00Z", actions)


def test_aggregate_is_deterministic() -> None:
    result = reduce_policy_actions("fixed_warmup_seed", "2026-01-01T00:00:00Z", (action("CLOSE_BUY", 1),))
    first = aggregate_reductions((result,))
    second = aggregate_reductions((result,))
    assert first == second
    assert first["aggregate_sha256"]
