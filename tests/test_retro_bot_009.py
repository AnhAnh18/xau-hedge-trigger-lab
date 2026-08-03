from __future__ import annotations

import pytest
import pandas as pd

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_007 import CandidatePolicy, OracleLabel
from xau_trigger.retro_bot_008 import RehedgePolicy
from xau_trigger.retro_bot_009 import (
    BOOTSTRAPS,
    CANDIDATES,
    CLOCKS,
    FOLDS,
    M5_FIREWALL,
    REPORT_MANIFEST_SHA256,
    TICK_MANIFEST_SHA256,
    WalkForwardRow,
    build_oracle_diagnostic,
    evaluate_walk_forward,
    frozen_candidate_policies,
    run_causal_window,
    validate_frozen_candidate,
)
from xau_trigger.retro_bot_005 import StateSnapshot
from xau_trigger.retro_bot_006 import FeatureSnapshot, RuleClause, TriggerRule


def rows(pass_candidate: str | None = None) -> tuple[WalkForwardRow, ...]:
    return tuple(
        WalkForwardRow(fold, clock, bootstrap, candidate, 2 if candidate == pass_candidate else 1, 0 if candidate == pass_candidate else 1, 2 if candidate == pass_candidate else 0, 0, 2 if candidate == pass_candidate else 1, 0 if candidate == pass_candidate else 1, 2 if candidate == pass_candidate else 0, 0, candidate == pass_candidate, candidate == pass_candidate, 2, 2, 2, 1 if candidate == pass_candidate else 0, 1 if candidate == pass_candidate else 0, 2, 2, 1 if candidate == pass_candidate else 0, 1 if candidate == pass_candidate else 0)
        for fold in FOLDS for clock in CLOCKS for bootstrap in BOOTSTRAPS for candidate in CANDIDATES
    )


def test_complete_matrix_and_statuses_are_deterministic() -> None:
    first = evaluate_walk_forward(rows("always_hold__always_hold"))
    assert first["terminal_status"] == "package-ready"
    assert first == evaluate_walk_forward(rows("always_hold__always_hold"))
    assert evaluate_walk_forward(rows())["terminal_status"] == "no-supported-candidate"


def test_missing_or_duplicate_matrix_rows_fail_closed() -> None:
    incomplete = rows()[:-1]
    with pytest.raises(RetroBotInputError):
        evaluate_walk_forward(incomplete)
    duplicate = rows() + (rows()[0],)
    with pytest.raises(RetroBotInputError):
        evaluate_walk_forward(duplicate)


def test_row_conservation_is_locked() -> None:
    bad = list(rows())
    bad[0] = WalkForwardRow("development", CLOCKS[0], BOOTSTRAPS[0], CANDIDATES[0], 1, 0, 0, 0, 1, 1, 0, 0, False, False)
    with pytest.raises(RetroBotInputError):
        evaluate_walk_forward(bad)


def test_candidate_fingerprint_is_frozen() -> None:
    close, rehedge = frozen_candidate_policies("first_legal_match__first_legal_match")
    validate_frozen_candidate("first_legal_match__first_legal_match", close, rehedge)
    altered = CandidatePolicy("first_legal_match", (TriggerRule("x", (RuleClause("state", "always"),), "CLOSE_BUY"),))
    with pytest.raises(RetroBotInputError):
        validate_frozen_candidate("first_legal_match__first_legal_match", altered, rehedge)


def test_empty_rehedge_window_is_censored() -> None:
    close, rehedge = frozen_candidate_policies("first_legal_match__first_legal_match")
    row = run_causal_window(
        fold="development", clock_id="utc_plus_3", bootstrap_id="fixed_warmup_seed",
        candidate_id="first_legal_match__first_legal_match",
        state=StateSnapshot("HEDGED", 0, pd.Timestamp("2026-01-01T00:00:00Z"), 1.0),
        close_policy=close, rehedge_policy=rehedge,
        close_snapshots=(FeatureSnapshot("2026-01-01T00:00:01Z", {"state": "HEDGED", "side": "buy", "clock_id": "utc_plus_3"}),),
        rehedge_snapshots=(),
    )
    assert row.rehedge_censor == 1
    assert not row.safety_pass


def test_oracle_builder_recomputes_one_to_one_counts() -> None:
    labels = ({"cycle_id": "c1", "label_time": "2026-01-01T00:00:01Z", "action_kind": "CLOSE_BUY", "timing_band": "0-1s"},)
    actions = (("c1", "2026-01-01T00:00:00Z", "CLOSE_BUY"),)
    expected = {"exact": 0, "0-1s": 1, "2-6s": 0, "7-30s": 0, ">30s": 0, "unmatched": 0, "direction_mismatch": 0, "duplicate_label": 0, "unmatched_labels": 0}
    assert build_oracle_diagnostic(labels=labels, action_counts=expected, actions=actions)["action_counts"] == expected
