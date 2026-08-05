from __future__ import annotations

import json
import subprocess
import sys

import pandas as pd
import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_005 import PolicyAction, StateSnapshot
from xau_trigger.retro_bot_006 import FeatureSnapshot
from xau_trigger.retro_bot_009 import BOOTSTRAPS, CANDIDATES, CLOCKS, FOLDS, RB008_CONFIG_SHA256, REPORT_MANIFEST_SHA256, TICK_MANIFEST_SHA256, DecisionRecord, frozen_candidate_policies
from xau_trigger.retro_bot_010 import (
    PaperAttestation,
    PaperCycleResult,
    PaperQuote,
    PaperScenario,
    aggregate_paper_cycles,
    canonical_cycle_id,
    paper_backtest_cycle,
    paper_replay_fixture,
    scenario_fingerprint,
    validate_paper_aggregate,
    _action_digest,
)


def _actions() -> tuple[PolicyAction, ...]:
    return (
        PolicyAction("CLOSE_BUY", pd.Timestamp("2026-01-01T00:00:01Z"), 0),
        PolicyAction("OPEN_BUY", pd.Timestamp("2026-01-01T00:00:02Z"), 1),
    )


def _causal_window(candidate: str, state: StateSnapshot, *, snapshots: bool = True) -> dict[str, object]:
    close_policy, rehedge_policy = frozen_candidate_policies(candidate)
    close_snapshots = ()
    rehedge_snapshots = ()
    if snapshots:
        if state.state == "HEDGED":
            close_snapshots = (FeatureSnapshot(pd.Timestamp("2026-01-01T00:00:01Z"), {"state": "HEDGED", "side": "buy", "clock_id": "utc_plus_3"}, (), {}),)
            rehedge_snapshots = (FeatureSnapshot(pd.Timestamp("2026-01-01T00:00:02Z"), {"state": "ONE_SELL", "side": "sell", "clock_id": "utc_plus_3"}, (), {}),)
        elif state.state == "ONE_BUY":
            rehedge_snapshots = (FeatureSnapshot(pd.Timestamp("2026-01-01T00:00:01Z"), {"state": "ONE_BUY", "side": "buy", "clock_id": "utc_plus_3"}, (), {}),)
        elif state.state == "ONE_SELL":
            rehedge_snapshots = (FeatureSnapshot(pd.Timestamp("2026-01-01T00:00:01Z"), {"state": "ONE_SELL", "side": "sell", "clock_id": "utc_plus_3"}, (), {}),)
    cutoff = pd.Timestamp("2026-01-01T00:00:02Z").value
    return {
        "state": state,
        "close_policy": close_policy,
        "rehedge_policy": rehedge_policy,
        "close_snapshots": close_snapshots,
        "rehedge_snapshots": rehedge_snapshots,
        "decision_records": (DecisionRecord("development", cutoff, False, False, "report-001.html"),),
        "causal_cutoff_ns": cutoff,
        "report_alias": "report-001.html",
    }


def test_paper_accounting_uses_conservative_sides_and_is_deterministic() -> None:
    actions = _actions()
    quotes = tuple(PaperQuote(time, bid, ask) for time, bid, ask in (
        ("2026-01-01T00:00:00Z", 2000.0, 2000.2),
        ("2026-01-01T00:00:01Z", 2001.0, 2001.2),
        ("2026-01-01T00:00:02Z", 2002.0, 2002.2),
        ("2026-01-01T00:00:03Z", 2003.0, 2003.2),
    ))
    candidate = CANDIDATES[-1]
    state = StateSnapshot("HEDGED", 0, pd.Timestamp("2026-01-01T00:00:00Z"), 1.0)
    kwargs = dict(cycle_id=canonical_cycle_id("development", "utc_plus_3", "fixed_warmup_seed", candidate, "u1"), unit_id="u1", fold="development", clock_id="utc_plus_3", bootstrap_id="fixed_warmup_seed", candidate_id=candidate, state=state, actions=actions, quotes=quotes, causal_window=_causal_window(candidate, state), action_digest=_action_digest(actions))
    first = paper_backtest_cycle(**kwargs)
    assert first.status == "marked" and first.mark_count == 1
    assert first == paper_backtest_cycle(**kwargs)


def test_paper_matrix_and_attestation_are_locked() -> None:
    rows = []
    for fold in FOLDS:
        for clock in CLOCKS:
            for bootstrap in BOOTSTRAPS:
                for candidate in CANDIDATES:
                    index = len(rows)
                    unit = f"u{index}"
                    rows.append(PaperCycleResult(canonical_cycle_id(fold, clock, bootstrap, candidate, unit), fold, clock, bootstrap, candidate, "base_zero_cost", "marked", 1, 1, 1.0, "gain", True, unit, scenario_fingerprint(PaperScenario())))
    payload = aggregate_paper_cycles(rows, attestation=PaperAttestation(), report_manifest_sha256=REPORT_MANIFEST_SHA256, tick_manifest_sha256=TICK_MANIFEST_SHA256)
    validate_paper_aggregate(payload)
    assert payload == aggregate_paper_cycles(rows, attestation=PaperAttestation(), report_manifest_sha256=REPORT_MANIFEST_SHA256, tick_manifest_sha256=TICK_MANIFEST_SHA256)
    decimal_scenario = PaperScenario(fee_per_unit=0.00000001)
    decimal_rows = [PaperCycleResult(item.cycle_id, item.fold, item.clock_id, item.bootstrap_id, item.candidate_id, item.scenario_id, item.status, item.action_count, item.mark_count, item.net_return, item.return_band, item.accounting_pass, item.unit_id, scenario_fingerprint(decimal_scenario)) for item in rows]
    decimal_payload = aggregate_paper_cycles(decimal_rows, scenario=decimal_scenario, attestation=PaperAttestation(), report_manifest_sha256=REPORT_MANIFEST_SHA256, tick_manifest_sha256=TICK_MANIFEST_SHA256)
    assert decimal_payload["scenario"]["fee_per_unit"] == "0.00000001"
    malformed = dict(payload)
    malformed["rows"] = list(payload["rows"])
    malformed["rows"][0] = dict(malformed["rows"][0])
    malformed["rows"][0]["fold"] = []
    with pytest.raises(RetroBotInputError):
        validate_paper_aggregate(malformed)
    with pytest.raises(RetroBotInputError):
        aggregate_paper_cycles(rows, attestation=None)


def test_duplicate_quote_and_action_injection_fail_closed() -> None:
    actions = _actions()
    quotes = (PaperQuote("2026-01-01T00:00:00Z", 2000.0, 2000.2), PaperQuote("2026-01-01T00:00:00Z", 2001.0, 2001.2))
    state = StateSnapshot("HEDGED", 0, pd.Timestamp("2026-01-01T00:00:00Z"), 1.0)
    result = paper_backtest_cycle(cycle_id=canonical_cycle_id("development", "utc_plus_3", "fixed_warmup_seed", CANDIDATES[0], "u_dup"), unit_id="u_dup", fold="development", clock_id="utc_plus_3", bootstrap_id="fixed_warmup_seed", candidate_id=CANDIDATES[0], state=state, actions=(), quotes=quotes, causal_window=_causal_window(CANDIDATES[0], state, snapshots=False), action_digest=_action_digest(()))
    assert result.status == "source_censored"
    with pytest.raises(RetroBotInputError):
        paper_backtest_cycle(cycle_id=canonical_cycle_id("development", "utc_plus_3", "fixed_warmup_seed", CANDIDATES[-1], "u_inject"), unit_id="u_inject", fold="development", clock_id="utc_plus_3", bootstrap_id="fixed_warmup_seed", candidate_id=CANDIDATES[-1], state=state, actions=actions, quotes=(PaperQuote("2026-01-01T00:00:00Z", 2000.0, 2000.2),), causal_window=_causal_window(CANDIDATES[-1], state, snapshots=False))


def test_one_leg_accounting_and_mark_does_not_charge_fee() -> None:
    state = StateSnapshot("ONE_BUY", 1, pd.Timestamp("2026-01-01T00:00:00Z"), 1.0)
    candidate = CANDIDATES[-1]
    action = PolicyAction("OPEN_SELL", pd.Timestamp("2026-01-01T00:00:01Z"), 1)
    quotes = (PaperQuote("2026-01-01T00:00:00Z", 2000.0, 2000.2), PaperQuote("2026-01-01T00:00:01Z", 2001.0, 2001.2), PaperQuote("2026-01-01T00:00:02Z", 2002.0, 2002.2))
    result = paper_backtest_cycle(cycle_id=canonical_cycle_id("development", "utc_plus_3", "fixed_warmup_seed", candidate, "u_one"), unit_id="u_one", fold="development", clock_id="utc_plus_3", bootstrap_id="fixed_warmup_seed", candidate_id=candidate, state=state, actions=(action,), quotes=quotes, causal_window=_causal_window(candidate, state), scenario=PaperScenario(fee_per_unit=0.5))
    assert result.status == "marked"
    assert result.net_return == -0.4


def test_initial_slippage_is_applied_once_per_entry() -> None:
    state = StateSnapshot("HEDGED", 0, pd.Timestamp("2026-01-01T00:00:00Z"), 1.0)
    scenario = PaperScenario(slippage_points=10.0)
    candidate = CANDIDATES[0]
    result = paper_backtest_cycle(cycle_id=canonical_cycle_id("development", "utc_plus_3", "fixed_warmup_seed", candidate, "u_slip"), unit_id="u_slip", fold="development", clock_id="utc_plus_3", bootstrap_id="fixed_warmup_seed", candidate_id=candidate, state=state, actions=(), quotes=(PaperQuote("2026-01-01T00:00:00Z", 2000.0, 2000.2),), causal_window=_causal_window(candidate, state, snapshots=False), scenario=scenario)
    assert result.status == "marked"
    assert result.net_return == -0.6


def _fixture_state(state: StateSnapshot) -> dict[str, object]:
    return {"state": state.state, "epoch": state.epoch, "last_time": None if state.last_time is None else state.last_time.isoformat(), "quantity": state.quantity, "seen_keys": [list(item) for item in state.seen_keys]}


def _typed_fixture() -> dict[str, object]:
    scenario = PaperScenario()
    manifest = {}
    for candidate in CANDIDATES:
        close_policy, rehedge_policy = frozen_candidate_policies(candidate)
        manifest[candidate] = {"close_policy_id": close_policy.policy_id, "rehedge_policy_id": rehedge_policy.policy_id}
    cycles = []
    aliases = {"development": "report-001.html", "validation": "report-006.html", "holdout": "report-008.html"}
    cutoff = pd.Timestamp("2026-01-01T00:00:00Z").value
    for fold in FOLDS:
        for clock in CLOCKS:
            for bootstrap in BOOTSTRAPS:
                state = StateSnapshot("CENSORED" if bootstrap == "left_censored" else "HEDGED", 0, pd.Timestamp("2025-12-31T23:59:59Z"), 1.0)
                for candidate in CANDIDATES:
                    unit = f"{fold[:2]}-{clock[-1]}-{bootstrap[:2]}-{len(cycles)}"
                    cycles.append({
                        "cycle_id": canonical_cycle_id(fold, clock, bootstrap, candidate, unit), "unit_id": unit, "fold": fold, "clock_id": clock, "bootstrap_id": bootstrap, "candidate_id": candidate,
                        "state": _fixture_state(state), "actions": [], "quotes": [{"decision_time": "2026-01-01T00:00:00Z", "bid": 2000.0, "ask": 2000.2}],
                        "causal_window": {"state": _fixture_state(state), "close_snapshots": [], "rehedge_snapshots": [], "decision_records": [{"fold": fold, "decision_time_ns": cutoff, "future_read": False, "oracle_used": False, "report_alias": aliases[fold]}], "causal_cutoff_ns": cutoff, "report_alias": aliases[fold]},
                    })
    return {"attestation": {"schema_version": 1, "rb008_config_sha256": RB008_CONFIG_SHA256, "report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256, "fixture_id": "synthetic", "m5_firewall": "M5_FIREWALL_ATTESTATION_V1"}, "scenario": {"scenario_id": scenario.scenario_id, "fee_per_unit": scenario.fee_per_unit, "slippage_points": scenario.slippage_points, "latency_seconds": scenario.latency_seconds, "margin_per_unit": scenario.margin_per_unit, "fingerprint": scenario_fingerprint(scenario)}, "frozen_candidate_policies": manifest, "cycles": cycles}


def test_typed_fixture_replays_cycles_not_precomputed_rows() -> None:
    payload = paper_replay_fixture(_typed_fixture())
    validate_paper_aggregate(payload)
    repeat = paper_replay_fixture(_typed_fixture())
    assert json.dumps(payload, ensure_ascii=True, separators=(",", ":")) == json.dumps(repeat, ensure_ascii=True, separators=(",", ":"))
    completed = subprocess.run([sys.executable, "scripts/run_retro_bot_014.py", "paper-replay"], input=json.dumps(_typed_fixture()), text=True, capture_output=True, check=False)
    assert completed.returncode == 0, completed.stderr
    validate_paper_aggregate(json.loads(completed.stdout))


def test_typed_fixture_rejects_huge_numbers_and_digest_tampering() -> None:
    huge = _typed_fixture()
    huge["scenario"]["fee_per_unit"] = 10**1000
    with pytest.raises(RetroBotInputError):
        paper_replay_fixture(huge)
    huge_quote = _typed_fixture()
    huge_quote["cycles"][0]["quotes"][0]["bid"] = 10**1000
    with pytest.raises(RetroBotInputError):
        paper_replay_fixture(huge_quote)
    candidate = CANDIDATES[-1]
    state = StateSnapshot("HEDGED", 0, pd.Timestamp("2026-01-01T00:00:00Z"), 1.0)
    with pytest.raises(RetroBotInputError):
        paper_backtest_cycle(cycle_id=canonical_cycle_id("development", "utc_plus_3", "fixed_warmup_seed", candidate, "u_digest"), unit_id="u_digest", fold="development", clock_id="utc_plus_3", bootstrap_id="fixed_warmup_seed", candidate_id=candidate, state=state, actions=_actions(), quotes=(PaperQuote("2026-01-01T00:00:00Z", 2000.0, 2000.2),), causal_window=_causal_window(candidate, state), action_digest="0" * 64)


def test_causal_state_binding_is_required() -> None:
    candidate = CANDIDATES[-1]
    state = StateSnapshot("HEDGED", 0, pd.Timestamp("2026-01-01T00:00:00Z"), 1.0)
    causal = _causal_window(candidate, state)
    causal["state"] = StateSnapshot("ONE_SELL", 1, pd.Timestamp("2026-01-01T00:00:01Z"), 1.0)
    with pytest.raises(RetroBotInputError):
        paper_backtest_cycle(cycle_id=canonical_cycle_id("development", "utc_plus_3", "fixed_warmup_seed", candidate, "u_state"), unit_id="u_state", fold="development", clock_id="utc_plus_3", bootstrap_id="fixed_warmup_seed", candidate_id=candidate, state=state, actions=(), quotes=(PaperQuote("2026-01-01T00:00:00Z", 2000.0, 2000.2),), causal_window=causal)


def test_causal_feature_censor_cannot_be_marked_clean() -> None:
    candidate = CANDIDATES[-1]
    state = StateSnapshot("HEDGED", 0, pd.Timestamp("2026-01-01T00:00:00Z"), 1.0)
    causal = _causal_window(candidate, state)
    causal["close_snapshots"] = (FeatureSnapshot(pd.Timestamp("2026-01-01T00:00:01Z"), {"state": "HEDGED", "side": "buy", "clock_id": "utc_plus_3", "price_increment": 10**1000}, (), {}),)
    result = paper_backtest_cycle(cycle_id=canonical_cycle_id("development", "utc_plus_3", "fixed_warmup_seed", candidate, "u_censor"), unit_id="u_censor", fold="development", clock_id="utc_plus_3", bootstrap_id="fixed_warmup_seed", candidate_id=candidate, state=state, actions=(), quotes=(PaperQuote("2026-01-01T00:00:00Z", 2000.0, 2000.2),), causal_window=causal)
    assert result.status == "invalid_transition"
    assert result.accounting_pass is False


def test_one_leg_rehedge_censor_and_duplicate_cannot_be_marked_clean() -> None:
    candidate = CANDIDATES[-1]
    state = StateSnapshot("ONE_BUY", 1, pd.Timestamp("2026-01-01T00:00:00Z"), 1.0)
    causal = _causal_window(candidate, state)
    causal["rehedge_snapshots"] = (FeatureSnapshot(pd.Timestamp("2026-01-01T00:00:01Z"), {"state": "ONE_BUY", "side": "buy", "clock_id": "utc_plus_3", "price_increment": 10**1000}, (), {}),)
    result = paper_backtest_cycle(cycle_id=canonical_cycle_id("development", "utc_plus_3", "fixed_warmup_seed", candidate, "u_one_censor"), unit_id="u_one_censor", fold="development", clock_id="utc_plus_3", bootstrap_id="fixed_warmup_seed", candidate_id=candidate, state=state, actions=(), quotes=(PaperQuote("2026-01-01T00:00:00Z", 2000.0, 2000.2),), causal_window=causal)
    assert result.status == "invalid_transition"
    duplicate = _causal_window(candidate, state)
    snapshot = FeatureSnapshot(pd.Timestamp("2026-01-01T00:00:01Z"), {"state": "ONE_BUY", "side": "buy", "clock_id": "utc_plus_3"}, (), {})
    duplicate["rehedge_snapshots"] = (snapshot, snapshot)
    result = paper_backtest_cycle(cycle_id=canonical_cycle_id("development", "utc_plus_3", "fixed_warmup_seed", candidate, "u_one_duplicate"), unit_id="u_one_duplicate", fold="development", clock_id="utc_plus_3", bootstrap_id="fixed_warmup_seed", candidate_id=candidate, state=state, actions=(), quotes=(PaperQuote("2026-01-01T00:00:00Z", 2000.0, 2000.2),), causal_window=duplicate)
    assert result.status == "invalid_transition"
