"""RB-014 end-to-end offline paper accounting over locked causal actions."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping

import pandas as pd

from .retro_bot import RetroBotInputError
from .retro_bot_005 import ACTION_KINDS, PolicyAction, StateSnapshot, apply_policy_action
from .retro_bot_006 import NUMERIC_FEATURES, FeatureSnapshot, validate_snapshot
from .retro_bot_007 import evaluate_candidate
from .retro_bot_008 import evaluate_rehedge, replay_rehedge_window
from .retro_bot_009 import (
    BOOTSTRAPS,
    CANDIDATES,
    CLOCKS,
    FOLDS,
    M5_FIREWALL,
    RB008_CONFIG_SHA256,
    REPORT_MANIFEST_SHA256,
    TICK_MANIFEST_SHA256,
    validate_causal_prefix,
    run_causal_window,
    DecisionRecord,
    frozen_candidate_policies,
    validate_walk_forward_aggregate,
)

RB014_ID = "RB-014"
SCHEMA_VERSION = 1
MAX_COUNT = 1_000_000_000
STATUSES = ("marked", "mark_censored", "action_censored", "invalid_transition", "source_censored")
RETURN_BANDS = ("loss", "flat", "gain")
PAPER_TERMINAL_STATUSES = ("behaviorally-compatible-accounting-inconclusive", "no-supported-candidate")
ATTESTATION_FIELDS = ("schema_version", "rb008_config_sha256", "report_manifest_sha256", "tick_manifest_sha256", "fixture_id", "m5_firewall")


def _time(value: object) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
        if pd.isna(timestamp):
            raise ValueError
    except (TypeError, ValueError, pd.errors.OutOfBoundsDatetime) as error:
        raise RetroBotInputError("RB-014 timestamp is invalid") from error
    return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")


@dataclass(frozen=True)
class PaperScenario:
    scenario_id: str = "base_zero_cost"
    fee_per_unit: float = 0.0
    slippage_points: float = 0.0
    latency_seconds: int = 0
    margin_per_unit: float = 0.0

    def validate(self) -> None:
        if not isinstance(self.scenario_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.scenario_id):
            raise RetroBotInputError("RB-014 scenario id is invalid")
        values = (self.fee_per_unit, self.slippage_points, self.margin_per_unit)
        for value in values:
            try:
                converted = float(value)
            except (TypeError, ValueError, OverflowError) as error:
                raise RetroBotInputError("RB-014 scenario value is invalid") from error
            if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(converted) or (value == 0 and math.copysign(1.0, converted) < 0) or value < 0 or value > 1_000_000:
                raise RetroBotInputError("RB-014 scenario value is invalid")
        if any(float(value) != round(float(value), 8) for value in values):
            raise RetroBotInputError("RB-014 scenario precision is invalid")
        if type(self.latency_seconds) is not int or self.latency_seconds < 0 or self.latency_seconds > 86_400:
            raise RetroBotInputError("RB-014 latency is invalid")


@dataclass(frozen=True)
class PaperAttestation:
    schema_version: int = 1
    rb008_config_sha256: str = RB008_CONFIG_SHA256
    report_manifest_sha256: str = REPORT_MANIFEST_SHA256
    tick_manifest_sha256: str = TICK_MANIFEST_SHA256
    fixture_id: str = "synthetic"
    m5_firewall: str = M5_FIREWALL

    def validate(self) -> None:
        if type(self.schema_version) is not int or self.schema_version != 1 or self.rb008_config_sha256 != RB008_CONFIG_SHA256 or self.report_manifest_sha256 != REPORT_MANIFEST_SHA256 or self.tick_manifest_sha256 != TICK_MANIFEST_SHA256 or self.m5_firewall != M5_FIREWALL or not isinstance(self.fixture_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.fixture_id):
            raise RetroBotInputError("RB-014 source attestation mismatch")


@dataclass(frozen=True)
class PaperQuote:
    decision_time: pd.Timestamp
    bid: float
    ask: float

    def validate(self) -> None:
        timestamp = _time(self.decision_time)
        values = (self.bid, self.ask)
        converted = []
        for value in values:
            try:
                numeric = float(value)
            except (TypeError, ValueError, OverflowError) as error:
                raise RetroBotInputError("RB-014 quote is invalid") from error
            if type(value) not in (int, float) or isinstance(value, bool) or not math.isfinite(numeric) or value <= 0:
                raise RetroBotInputError("RB-014 quote is invalid")
            converted.append(numeric)
        if converted[1] < converted[0]:
            raise RetroBotInputError("RB-014 quote is invalid")
        object.__setattr__(self, "decision_time", timestamp)


@dataclass(frozen=True)
class PaperCycleResult:
    cycle_id: str
    fold: str
    clock_id: str
    bootstrap_id: str
    candidate_id: str
    scenario_id: str
    status: str
    action_count: int
    mark_count: int
    net_return: float | None
    return_band: str | None
    accounting_pass: bool
    unit_id: str = "unit"
    scenario_fingerprint: str = ""

    def validate(self) -> None:
        if not isinstance(self.cycle_id, str) or not re.fullmatch(r"[0-9a-f]{64}", self.cycle_id) or not isinstance(self.unit_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.unit_id) or self.fold not in FOLDS or self.clock_id not in CLOCKS or self.bootstrap_id not in BOOTSTRAPS or self.candidate_id not in CANDIDATES or self.cycle_id != canonical_cycle_id(self.fold, self.clock_id, self.bootstrap_id, self.candidate_id, self.unit_id) or self.status not in STATUSES or not isinstance(self.scenario_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.scenario_id) or not isinstance(self.scenario_fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", self.scenario_fingerprint):
            raise RetroBotInputError("RB-014 cycle result identity is invalid")
        if type(self.action_count) is not int or type(self.mark_count) is not int or self.action_count < 0 or self.mark_count < 0 or self.action_count > 2 or self.mark_count > MAX_COUNT or type(self.accounting_pass) is not bool:
            raise RetroBotInputError("RB-014 cycle accounting is invalid")
        if self.net_return is not None:
            try:
                finite_return = math.isfinite(float(self.net_return))
            except (TypeError, ValueError, OverflowError):
                finite_return = False
            if type(self.net_return) not in (int, float) or isinstance(self.net_return, bool) or not finite_return:
                raise RetroBotInputError("RB-014 return is invalid")
        if self.status == "marked" and (self.net_return is None or self.return_band not in RETURN_BANDS or self.mark_count != 1 or not self.accounting_pass):
            raise RetroBotInputError("RB-014 marked result is incomplete")
        if self.status != "marked" and (self.net_return is not None or self.return_band is not None or self.mark_count != 0 or self.accounting_pass):
            raise RetroBotInputError("RB-014 censored result carries return data")


def _return_band(value: float) -> str:
    return "loss" if value < 0 else "gain" if value > 0 else "flat"


def scenario_fingerprint(scenario: PaperScenario) -> str:
    scenario.validate()
    payload = {"scenario_id": scenario.scenario_id, "fee_per_unit": round(float(scenario.fee_per_unit), 8), "slippage_points": round(float(scenario.slippage_points), 8), "latency_seconds": scenario.latency_seconds, "margin_per_unit": round(float(scenario.margin_per_unit), 8)}
    return hashlib.sha256(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode()).hexdigest()


def _fixed_decimal(value: float) -> str:
    return format(Decimal(str(float(value))).quantize(Decimal("0.00000001")), "f")


def _parse_fixed_decimal(value: object) -> float:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]+\.[0-9]{8}", value):
        raise RetroBotInputError("RB-014 fixed decimal is invalid")
    try:
        decimal_value = Decimal(value)
        numeric = float(decimal_value)
    except (InvalidOperation, ValueError, OverflowError) as error:
        raise RetroBotInputError("RB-014 fixed decimal is invalid") from error
    if _fixed_decimal(numeric) != value:
        raise RetroBotInputError("RB-014 fixed decimal is not canonical")
    return numeric


def canonical_cycle_id(fold: str, clock_id: str, bootstrap_id: str, candidate_id: str, unit_id: str) -> str:
    return hashlib.sha256("|".join((fold, clock_id, bootstrap_id, candidate_id, unit_id)).encode("ascii")).hexdigest()


def _execution_quote(quotes: tuple[PaperQuote, ...], action_time: pd.Timestamp, latency_seconds: int) -> PaperQuote | None:
    target = action_time + pd.Timedelta(seconds=latency_seconds)
    for quote in quotes:
        if quote.decision_time >= target:
            return quote
    return None


def _action_digest(actions: tuple[PolicyAction, ...]) -> str:
    serial = []
    for action in actions:
        if not isinstance(action, PolicyAction) or action.source != "policy" or action.kind not in ACTION_KINDS or type(action.window_epoch) is not int or action.window_epoch < 0:
            raise RetroBotInputError("RB-014 action schema is invalid")
        serial.append({"kind": action.kind, "source": action.source, "decision_time": _time(action.decision_time).isoformat(), "window_epoch": action.window_epoch})
    return hashlib.sha256(json.dumps(serial, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode()).hexdigest()


def _validate_replay_snapshot(snapshot: object) -> FeatureSnapshot:
    if not isinstance(snapshot, FeatureSnapshot):
        raise RetroBotInputError("RB-014 causal snapshot is invalid")
    try:
        validated = validate_snapshot(snapshot)
    except (RetroBotInputError, TypeError, ValueError, AttributeError) as error:
        raise RetroBotInputError("RB-014 causal snapshot is invalid") from error
    for feature, value in validated.values.items():
        if feature in NUMERIC_FEATURES:
            try:
                finite = math.isfinite(float(value))
            except (TypeError, ValueError, OverflowError):
                finite = False
            if not finite:
                raise RetroBotInputError("RB-014 causal snapshot is non-finite")
    return validated


def _recompute_causal_actions(window: Mapping[str, object]) -> tuple[PolicyAction, ...]:
    required = {"state", "close_policy", "rehedge_policy", "close_snapshots", "rehedge_snapshots"}
    if not required.issubset(window):
        raise RetroBotInputError("RB-014 causal fixture is incomplete")
    try:
        current = window["state"]
        close_snapshots = tuple(window["close_snapshots"])
        rehedge_snapshots = tuple(window["rehedge_snapshots"])
    except TypeError as error:
        raise RetroBotInputError("RB-014 causal fixture sequence is invalid") from error
    if not isinstance(current, StateSnapshot):
        raise RetroBotInputError("RB-014 causal fixture state is invalid")
    close_policy, rehedge_policy = window["close_policy"], window["rehedge_policy"]
    actions: list[PolicyAction] = []
    for snapshot in close_snapshots:
        decision = evaluate_candidate(current, snapshot, close_policy, expected_epoch=current.epoch)
        if decision.outcome == "candidate_action":
            decision_time = _time(snapshot.decision_time)
            current, result = apply_policy_action(current, PolicyAction(decision.action_kind, decision_time, current.epoch))
            if result.status != "accepted":
                raise RetroBotInputError("RB-014 causal action application failed")
            actions.append(PolicyAction(decision.action_kind, decision_time, current.epoch - 1))
            break
        if decision.outcome != "hold":
            break
    for snapshot in rehedge_snapshots if current.state in {"ONE_BUY", "ONE_SELL"} else ():
        decision = evaluate_rehedge(current, snapshot, rehedge_policy, expected_epoch=current.epoch)
        if decision.outcome == "action":
            decision_time = _time(snapshot.decision_time)
            current, result = apply_policy_action(current, PolicyAction(decision.action_kind, decision_time, current.epoch))
            if result.status != "accepted":
                raise RetroBotInputError("RB-014 causal action application failed")
            actions.append(PolicyAction(decision.action_kind, decision_time, current.epoch - 1))
            break
        if decision.outcome != "hold":
            break
    return tuple(actions)


def paper_backtest_cycle(*, cycle_id: str, fold: str, clock_id: str, bootstrap_id: str, candidate_id: str, state: StateSnapshot, actions: Iterable[PolicyAction], quotes: Iterable[PaperQuote], scenario: PaperScenario = PaperScenario(), causal_window: Mapping[str, object] | None = None, action_digest: str | None = None, unit_id: str = "unit") -> PaperCycleResult:
    """Account one already-frozen causal action stream without source access."""
    if not isinstance(cycle_id, str) or not isinstance(unit_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", unit_id) or fold not in FOLDS or clock_id not in CLOCKS or bootstrap_id not in BOOTSTRAPS or candidate_id not in CANDIDATES or cycle_id != canonical_cycle_id(fold, clock_id, bootstrap_id, candidate_id, unit_id) or not isinstance(state, StateSnapshot):
        raise RetroBotInputError("RB-014 cycle identity is invalid")
    try:
        if len(state.seen_keys) != len(set(state.seen_keys)):
            raise RetroBotInputError("RB-014 state keys are duplicated")
    except (TypeError, AttributeError) as error:
        raise RetroBotInputError("RB-014 state keys are invalid") from error
    scenario.validate()
    try:
        materialized_quotes = tuple(quotes)
    except TypeError as error:
        raise RetroBotInputError("RB-014 cycle sequence is invalid") from error
    if not materialized_quotes:
        return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "source_censored", 0, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
    for quote in materialized_quotes:
        if not isinstance(quote, PaperQuote):
            return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "source_censored", 0, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
        try:
            quote.validate()
        except RetroBotInputError:
            return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "source_censored", 0, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
    previous_quote = None
    for quote in materialized_quotes:
        if previous_quote is not None and quote.decision_time.floor("s") <= previous_quote.floor("s"):
            return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "source_censored", 0, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
        previous_quote = quote.decision_time
    if causal_window is None:
        raise RetroBotInputError("RB-014 recomputed causal provenance is required")
    if causal_window is not None:
        if "decision_records" not in causal_window or "causal_cutoff_ns" not in causal_window:
            raise RetroBotInputError("RB-014 causal attestation is required")
        try:
            decision_records = validate_causal_prefix(tuple(causal_window["decision_records"]), fold)
            cutoff = causal_window["causal_cutoff_ns"]
            close_raw = tuple(causal_window["close_snapshots"])
            rehedge_raw = tuple(causal_window["rehedge_snapshots"])
        except (TypeError, KeyError, RetroBotInputError) as error:
            raise RetroBotInputError("RB-014 causal attestation is invalid") from error
        try:
            close_input = tuple(_validate_replay_snapshot(snapshot) for snapshot in close_raw)
            rehedge_input = tuple(_validate_replay_snapshot(snapshot) for snapshot in rehedge_raw)
        except RetroBotInputError:
            return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "invalid_transition", 0, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
        alias = causal_window.get("report_alias")
        if not isinstance(alias, str) or not decision_records or type(cutoff) is not int or cutoff != decision_records[-1].decision_time_ns or any(item.report_alias != alias for item in decision_records):
            raise RetroBotInputError("RB-014 causal cutoff is invalid")
        causal_state = causal_window.get("state")
        if not isinstance(causal_state, StateSnapshot) or causal_state != state:
            raise RetroBotInputError("RB-014 causal state provenance mismatch")
        for snapshot in close_input + rehedge_input:
            try:
                snapshot_time = _time(snapshot.decision_time)
            except (AttributeError, TypeError, ValueError, pd.errors.OutOfBoundsDatetime) as error:
                raise RetroBotInputError("RB-014 causal snapshot is invalid") from error
            if snapshot_time.value > cutoff:
                raise RetroBotInputError("RB-014 future snapshot is not causal")
        for sequence in (close_input, rehedge_input):
            previous_snapshot = None
            for snapshot in sequence:
                snapshot_time = _time(snapshot.decision_time)
                if previous_snapshot is not None and snapshot_time.floor("s") <= previous_snapshot.floor("s"):
                    return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "invalid_transition", 0, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
                previous_snapshot = snapshot_time
        causal_kwargs = {key: value for key, value in causal_window.items() if key not in {"decision_records", "causal_cutoff_ns", "report_alias"}}
        causal_kwargs.update(fold=fold, clock_id=clock_id, bootstrap_id=bootstrap_id, candidate_id=candidate_id)
        try:
            row = run_causal_window(**causal_kwargs)
        except (TypeError, RetroBotInputError) as error:
            raise RetroBotInputError("RB-014 causal window is invalid") from error
        if row.candidate_id != candidate_id or row.fold != fold or row.clock_id != clock_id or row.bootstrap_id != bootstrap_id:
            raise RetroBotInputError("RB-014 causal identity mismatch")
        if state.state == "HEDGED" and not row.safety_pass:
            return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "invalid_transition", 0, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
        if state.state in {"ONE_BUY", "ONE_SELL"}:
            previous_rehedge = state.last_time
            for snapshot in rehedge_input:
                snapshot_time = _time(snapshot.decision_time)
                if previous_rehedge is not None and snapshot_time.floor("s") <= _time(previous_rehedge).floor("s"):
                    return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "invalid_transition", 0, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
                previous_rehedge = snapshot_time
            try:
                rehedge_decision, _ = replay_rehedge_window(state, rehedge_input, causal_window["rehedge_policy"], expected_epoch=state.epoch)
            except (TypeError, RetroBotInputError, ValueError, AttributeError) as error:
                raise RetroBotInputError("RB-014 one-leg causal window is invalid") from error
            if rehedge_decision.outcome == "censored":
                return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "invalid_transition", 0, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
    try:
        materialized_actions = tuple(actions)
    except TypeError as error:
        raise RetroBotInputError("RB-014 cycle sequence is invalid") from error
    if action_digest is not None and (not isinstance(action_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", action_digest)):
        raise RetroBotInputError("RB-014 action digest is invalid")
    if action_digest is not None and action_digest != _action_digest(materialized_actions):
        raise RetroBotInputError("RB-014 action digest mismatch")
    if causal_window is not None:
        expected_actions = _recompute_causal_actions(causal_window)
        expected_count = row.close_action + row.rehedge_action if state.state == "HEDGED" else len(expected_actions)
        if _action_digest(expected_actions) != _action_digest(materialized_actions) or expected_count != len(materialized_actions):
            raise RetroBotInputError("RB-014 injected action stream mismatch")
    initial = materialized_quotes[0]
    initial_slip = scenario.slippage_points * 0.01
    if state.state == "HEDGED":
        cash = float(initial.bid - initial.ask) - 2.0 * initial_slip - 2.0 * scenario.fee_per_unit
        positions = {"buy": 1.0, "sell": -1.0}
    elif state.state == "ONE_BUY":
        cash = float(-initial.ask - initial_slip) - scenario.fee_per_unit
        positions = {"buy": 1.0, "sell": 0.0}
    elif state.state == "ONE_SELL":
        cash = float(initial.bid - initial_slip) - scenario.fee_per_unit
        positions = {"buy": 0.0, "sell": -1.0}
    else:
        return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "invalid_transition", 0, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
    current = state
    previous_action_time = current.last_time
    accepted = 0
    previous_execution_time = None
    for action in materialized_actions:
        if not isinstance(action, PolicyAction):
            raise RetroBotInputError("RB-014 action schema is invalid")
        if action.source != "policy" or action.window_epoch != current.epoch:
            return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "invalid_transition", accepted, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
        action_time = _time(action.decision_time)
        if previous_action_time is not None and action_time.floor("s") <= _time(previous_action_time).floor("s"):
            return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "invalid_transition", accepted, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
        quote = _execution_quote(materialized_quotes, action_time, scenario.latency_seconds)
        if previous_execution_time is not None and quote is not None and quote.decision_time.floor("s") <= previous_execution_time.floor("s"):
            quote = None
        if quote is None:
            return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "action_censored", accepted, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
        exec_slip = scenario.slippage_points * 0.01
        if action.kind == "CLOSE_BUY" and positions["buy"] > 0:
            cash += quote.bid - exec_slip - scenario.fee_per_unit
            positions["buy"] = 0.0
        elif action.kind == "CLOSE_SELL" and positions["sell"] < 0:
            cash -= quote.ask + exec_slip + scenario.fee_per_unit
            positions["sell"] = 0.0
        elif action.kind == "OPEN_BUY" and positions["buy"] == 0:
            cash -= quote.ask + exec_slip + scenario.fee_per_unit
            positions["buy"] = 1.0
        elif action.kind == "OPEN_SELL" and positions["sell"] == 0:
            cash += quote.bid - exec_slip - scenario.fee_per_unit
            positions["sell"] = -1.0
        else:
            return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "invalid_transition", accepted, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
        current, result = apply_policy_action(current, PolicyAction(action.kind, action_time, current.epoch))
        if result.status != "accepted":
            return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "invalid_transition", accepted, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
        accepted += 1
        previous_action_time = action_time
        previous_execution_time = quote.decision_time
    mark = materialized_quotes[-1]
    net = cash + positions["buy"] * mark.bid + positions["sell"] * mark.ask - scenario.margin_per_unit * (abs(positions["buy"]) + abs(positions["sell"]))
    if not math.isfinite(float(net)):
        return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "source_censored", accepted, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
    if accepted and mark.decision_time <= previous_action_time:
        return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "mark_censored", accepted, 0, None, None, False, unit_id, scenario_fingerprint(scenario))
    net = round(float(net), 8)
    return PaperCycleResult(cycle_id, fold, clock_id, bootstrap_id, candidate_id, scenario.scenario_id, "marked", accepted, 1, net, _return_band(net), True, unit_id, scenario_fingerprint(scenario))


def aggregate_paper_cycles(results: Iterable[PaperCycleResult], *, scenario: PaperScenario = PaperScenario(), attestation: PaperAttestation | None = None, report_manifest_sha256: str = REPORT_MANIFEST_SHA256, tick_manifest_sha256: str = TICK_MANIFEST_SHA256, causal_aggregate: Mapping[str, object] | None = None) -> dict[str, object]:
    scenario.validate()
    if not isinstance(attestation, PaperAttestation):
        raise RetroBotInputError("RB-014 source attestation is required")
    attestation.validate()
    if report_manifest_sha256 != REPORT_MANIFEST_SHA256 or tick_manifest_sha256 != TICK_MANIFEST_SHA256:
        raise RetroBotInputError("RB-014 source receipt mismatch")
    if causal_aggregate is not None:
        validate_walk_forward_aggregate(causal_aggregate)
    try:
        materialized = tuple(results)
    except TypeError as error:
        raise RetroBotInputError("RB-014 result sequence is invalid") from error
    expected = {(fold, clock, bootstrap, candidate) for fold in FOLDS for clock in CLOCKS for bootstrap in BOOTSTRAPS for candidate in CANDIDATES}
    grouped: dict[tuple[str, str, str, str], list[PaperCycleResult]] = {key: [] for key in expected}
    seen_cycles: set[str] = set()
    seen_units: set[tuple[str, str, str, str, str]] = set()
    for result in materialized:
        if not isinstance(result, PaperCycleResult):
            raise RetroBotInputError("RB-014 result schema is invalid")
        result.validate()
        if result.scenario_id != scenario.scenario_id or result.scenario_fingerprint != scenario_fingerprint(scenario) or result.cycle_id in seen_cycles:
            raise RetroBotInputError("RB-014 duplicate or mixed scenario result")
        unit_key = (result.fold, result.clock_id, result.bootstrap_id, result.candidate_id, result.unit_id)
        if unit_key in seen_units:
            raise RetroBotInputError("RB-014 duplicate unit result")
        seen_cycles.add(result.cycle_id)
        seen_units.add(unit_key)
        grouped[(result.fold, result.clock_id, result.bootstrap_id, result.candidate_id)].append(result)
    if any(not values for values in grouped.values()):
        raise RetroBotInputError("RB-014 complete candidate matrix is required")
    rows = []
    for key in sorted(expected, key=lambda item: (FOLDS.index(item[0]), CLOCKS.index(item[1]), BOOTSTRAPS.index(item[2]), CANDIDATES.index(item[3]))):
        values = grouped[key]
        counts = {status: sum(item.status == status for item in values) for status in STATUSES}
        bands = {band: sum(item.return_band == band for item in values) for band in RETURN_BANDS}
        rows.append({"fold": key[0], "clock_id": key[1], "bootstrap_id": key[2], "candidate_id": key[3], "unit_count": len({item.unit_id for item in values}), "total_cycle_count": len(values), "action_count": sum(item.action_count for item in values), "mark_count": sum(item.mark_count for item in values), "accounting_pass_count": sum(item.accounting_pass for item in values), "status_counts": counts, "return_bands": bands})
    terminal = "behaviorally-compatible-accounting-inconclusive" if all(row["accounting_pass_count"] == row["total_cycle_count"] for row in rows) else "no-supported-candidate"
    payload = {"schema_version": SCHEMA_VERSION, "case_id": RB014_ID, "rb008_config_sha256": RB008_CONFIG_SHA256, "source_manifest_digests": {"report_manifest_sha256": report_manifest_sha256, "tick_manifest_sha256": tick_manifest_sha256}, "attestation": {"schema_version": attestation.schema_version, "rb008_config_sha256": attestation.rb008_config_sha256, "report_manifest_sha256": attestation.report_manifest_sha256, "tick_manifest_sha256": attestation.tick_manifest_sha256, "fixture_id": attestation.fixture_id, "m5_firewall": attestation.m5_firewall}, "scenario": {"scenario_id": scenario.scenario_id, "fee_per_unit": _fixed_decimal(scenario.fee_per_unit), "slippage_points": _fixed_decimal(scenario.slippage_points), "latency_seconds": scenario.latency_seconds, "margin_per_unit": _fixed_decimal(scenario.margin_per_unit), "fingerprint": scenario_fingerprint(scenario)}, "row_count": len(rows), "rows": rows, "terminal_status": terminal, "m5_firewall": M5_FIREWALL, "aggregate_sha256": "TO_BE_FILLED"}
    payload["aggregate_sha256"] = hashlib.sha256(json.dumps({key: value for key, value in payload.items() if key != "aggregate_sha256"}, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode()).hexdigest()
    validate_paper_aggregate(payload)
    return payload


def validate_paper_aggregate(payload: Mapping[str, object]) -> None:
    expected_order = ("schema_version", "case_id", "rb008_config_sha256", "source_manifest_digests", "attestation", "scenario", "row_count", "rows", "terminal_status", "m5_firewall", "aggregate_sha256")
    if not isinstance(payload, Mapping) or tuple(payload.keys()) != expected_order or type(payload.get("schema_version")) is not int or payload.get("schema_version") != SCHEMA_VERSION or payload.get("case_id") != RB014_ID or payload.get("rb008_config_sha256") != RB008_CONFIG_SHA256 or payload.get("m5_firewall") != M5_FIREWALL or payload.get("terminal_status") not in PAPER_TERMINAL_STATUSES:
        raise RetroBotInputError("RB-014 aggregate schema/firewall mismatch")
    source = payload.get("source_manifest_digests")
    if not isinstance(source, Mapping) or tuple(source.keys()) != ("report_manifest_sha256", "tick_manifest_sha256") or source != {"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256}:
        raise RetroBotInputError("RB-014 aggregate source mismatch")
    attestation = payload.get("attestation")
    if not isinstance(attestation, Mapping) or tuple(attestation.keys()) != ATTESTATION_FIELDS:
        raise RetroBotInputError("RB-014 aggregate attestation schema mismatch")
    PaperAttestation(**attestation).validate()
    scenario = payload.get("scenario")
    if not isinstance(scenario, Mapping) or tuple(scenario.keys()) != ("scenario_id", "fee_per_unit", "slippage_points", "latency_seconds", "margin_per_unit", "fingerprint"):
        raise RetroBotInputError("RB-014 scenario schema mismatch")
    scenario_object = PaperScenario(scenario_id=scenario["scenario_id"], fee_per_unit=_parse_fixed_decimal(scenario["fee_per_unit"]), slippage_points=_parse_fixed_decimal(scenario["slippage_points"]), latency_seconds=scenario["latency_seconds"], margin_per_unit=_parse_fixed_decimal(scenario["margin_per_unit"]))
    scenario_object.validate()
    if scenario["fingerprint"] != scenario_fingerprint(scenario_object):
        raise RetroBotInputError("RB-014 scenario fingerprint mismatch")
    if type(payload.get("row_count")) is not int or payload["row_count"] != len(FOLDS) * len(CLOCKS) * len(BOOTSTRAPS) * len(CANDIDATES) or not isinstance(payload.get("rows"), list) or len(payload["rows"]) != payload["row_count"]:
        raise RetroBotInputError("RB-014 matrix count mismatch")
    row_keys = ("fold", "clock_id", "bootstrap_id", "candidate_id", "unit_count", "total_cycle_count", "action_count", "mark_count", "accounting_pass_count", "status_counts", "return_bands")
    expected = {(fold, clock, bootstrap, candidate) for fold in FOLDS for clock in CLOCKS for bootstrap in BOOTSTRAPS for candidate in CANDIDATES}
    seen = set()
    expected_row_order = sorted(expected, key=lambda key: (FOLDS.index(key[0]), CLOCKS.index(key[1]), BOOTSTRAPS.index(key[2]), CANDIDATES.index(key[3])))
    for index, row in enumerate(payload["rows"]):
        if not isinstance(row, Mapping) or tuple(row.keys()) != row_keys:
            raise RetroBotInputError("RB-014 row schema mismatch")
        if any(type(row[field]) is not str for field in ("fold", "clock_id", "bootstrap_id", "candidate_id")):
            raise RetroBotInputError("RB-014 row identity schema mismatch")
        key = (row["fold"], row["clock_id"], row["bootstrap_id"], row["candidate_id"])
        if key in seen or key not in expected or key != expected_row_order[index]:
            raise RetroBotInputError("RB-014 matrix identity mismatch")
        seen.add(key)
        counts = row["status_counts"]
        if not isinstance(counts, Mapping) or tuple(counts.keys()) != STATUSES or any(type(value) is not int or value < 0 or value > MAX_COUNT for value in counts.values()) or sum(counts.values()) != row["total_cycle_count"]:
            raise RetroBotInputError("RB-014 status accounting mismatch")
        for field in ("unit_count", "total_cycle_count", "action_count", "mark_count", "accounting_pass_count"):
            if type(row[field]) is not int or row[field] < 0 or row[field] > MAX_COUNT:
                raise RetroBotInputError("RB-014 row count is invalid")
        if row["unit_count"] < 1 or row["unit_count"] != row["total_cycle_count"] or row["accounting_pass_count"] != counts["marked"] or row["mark_count"] != counts["marked"] or row["action_count"] > 2 * row["total_cycle_count"]:
            raise RetroBotInputError("RB-014 row conservation mismatch")
        bands = row["return_bands"]
        if not isinstance(bands, Mapping) or tuple(bands.keys()) != RETURN_BANDS or any(type(value) is not int or value < 0 or value > MAX_COUNT for value in bands.values()) or sum(bands.values()) != counts["marked"]:
            raise RetroBotInputError("RB-014 return bands mismatch")
    if seen != expected:
        raise RetroBotInputError("RB-014 matrix is incomplete")
    expected_terminal = "behaviorally-compatible-accounting-inconclusive" if all(row["accounting_pass_count"] == row["total_cycle_count"] for row in payload["rows"]) else "no-supported-candidate"
    if payload["terminal_status"] != expected_terminal:
        raise RetroBotInputError("RB-014 terminal status tampering detected")
    digest = hashlib.sha256(json.dumps({key: value for key, value in payload.items() if key != "aggregate_sha256"}, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode()).hexdigest()
    if payload.get("aggregate_sha256") != digest:
        raise RetroBotInputError("RB-014 aggregate digest mismatch")


def _fixture_mapping(value: object, keys: tuple[str, ...], message: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or tuple(value.keys()) != keys:
        raise RetroBotInputError(message)
    return value


def _fixture_state(value: object) -> StateSnapshot:
    item = _fixture_mapping(value, ("state", "epoch", "last_time", "quantity", "seen_keys"), "RB-014 fixture state schema is invalid")
    seen_keys = item["seen_keys"]
    if not isinstance(seen_keys, list):
        raise RetroBotInputError("RB-014 fixture state keys are invalid")
    parsed_keys: list[tuple[int, int, str]] = []
    for key in seen_keys:
        if not isinstance(key, list) or len(key) != 3 or type(key[0]) is not int or type(key[1]) is not int or key[2] not in ACTION_KINDS:
            raise RetroBotInputError("RB-014 fixture state key is invalid")
        parsed_keys.append((key[0], key[1], key[2]))
    if len(parsed_keys) != len(set(parsed_keys)):
        raise RetroBotInputError("RB-014 fixture state keys are duplicated")
    quantity = item["quantity"]
    if type(quantity) not in (int, float) or isinstance(quantity, bool):
        raise RetroBotInputError("RB-014 fixture quantity is invalid")
    last_time = None if item["last_time"] is None else _time(item["last_time"])
    try:
        return StateSnapshot(item["state"], item["epoch"], last_time, float(quantity), tuple(parsed_keys))
    except (RetroBotInputError, TypeError, ValueError, OverflowError) as error:
        raise RetroBotInputError("RB-014 fixture state is invalid") from error


def _fixture_snapshot(value: object) -> FeatureSnapshot:
    item = _fixture_mapping(value, ("decision_time", "values", "feature_times", "oracle_labels"), "RB-014 fixture snapshot schema is invalid")
    if not isinstance(item["values"], Mapping) or not isinstance(item["feature_times"], Mapping) or not isinstance(item["oracle_labels"], list):
        raise RetroBotInputError("RB-014 fixture snapshot fields are invalid")
    try:
        snapshot = FeatureSnapshot(_time(item["decision_time"]), dict(item["values"]), tuple(item["oracle_labels"]), {key: _time(value) for key, value in item["feature_times"].items()})
        return _validate_replay_snapshot(snapshot)
    except (RetroBotInputError, TypeError, ValueError) as error:
        raise RetroBotInputError("RB-014 fixture snapshot is invalid") from error


def _fixture_action(value: object) -> PolicyAction:
    item = _fixture_mapping(value, ("kind", "decision_time", "window_epoch", "source"), "RB-014 fixture action schema is invalid")
    try:
        action = PolicyAction(item["kind"], _time(item["decision_time"]), item["window_epoch"], item["source"])
        _action_digest((action,))
        return action
    except (RetroBotInputError, TypeError, ValueError) as error:
        raise RetroBotInputError("RB-014 fixture action is invalid") from error


def _fixture_quote(value: object) -> PaperQuote:
    item = _fixture_mapping(value, ("decision_time", "bid", "ask"), "RB-014 fixture quote schema is invalid")
    try:
        quote = PaperQuote(_time(item["decision_time"]), item["bid"], item["ask"])
        quote.validate()
        return quote
    except (RetroBotInputError, TypeError, ValueError) as error:
        raise RetroBotInputError("RB-014 fixture quote is invalid") from error


def _fixture_decision_record(value: object) -> DecisionRecord:
    item = _fixture_mapping(value, ("fold", "decision_time_ns", "future_read", "oracle_used", "report_alias"), "RB-014 fixture decision record schema is invalid")
    if type(item["decision_time_ns"]) is not int or item["decision_time_ns"] < 0 or type(item["future_read"]) is not bool or type(item["oracle_used"]) is not bool or (item["report_alias"] is not None and not isinstance(item["report_alias"], str)):
        raise RetroBotInputError("RB-014 fixture decision record fields are invalid")
    try:
        return DecisionRecord(item["fold"], item["decision_time_ns"], item["future_read"], item["oracle_used"], item["report_alias"])
    except (TypeError, ValueError) as error:
        raise RetroBotInputError("RB-014 fixture decision record is invalid") from error


def _fixture_policy_manifest(value: object) -> None:
    if not isinstance(value, Mapping) or tuple(value.keys()) != CANDIDATES:
        raise RetroBotInputError("RB-014 frozen candidate manifest is invalid")
    for candidate_id in CANDIDATES:
        item = _fixture_mapping(value[candidate_id], ("close_policy_id", "rehedge_policy_id"), "RB-014 frozen candidate entry is invalid")
        close_policy, rehedge_policy = frozen_candidate_policies(candidate_id)
        if item["close_policy_id"] != close_policy.policy_id or item["rehedge_policy_id"] != rehedge_policy.policy_id:
            raise RetroBotInputError("RB-014 frozen candidate policy mismatch")


def paper_replay_fixture(document: Mapping[str, object]) -> dict[str, object]:
    """Replay typed causal cycles without accepting precomputed result rows."""
    top_keys = ("attestation", "scenario", "frozen_candidate_policies", "cycles")
    if not isinstance(document, Mapping) or tuple(document.keys()) != top_keys:
        raise RetroBotInputError("RB-014 fixture schema is invalid")
    attestation_item = _fixture_mapping(document["attestation"], ATTESTATION_FIELDS, "RB-014 fixture attestation schema is invalid")
    scenario_fields = ("scenario_id", "fee_per_unit", "slippage_points", "latency_seconds", "margin_per_unit", "fingerprint")
    scenario_item = _fixture_mapping(document["scenario"], scenario_fields, "RB-014 fixture scenario schema is invalid")
    _fixture_policy_manifest(document["frozen_candidate_policies"])
    if not isinstance(document["cycles"], list):
        raise RetroBotInputError("RB-014 fixture cycles are invalid")
    try:
        attestation = PaperAttestation(**attestation_item)
        scenario = PaperScenario(scenario_id=scenario_item["scenario_id"], fee_per_unit=scenario_item["fee_per_unit"], slippage_points=scenario_item["slippage_points"], latency_seconds=scenario_item["latency_seconds"], margin_per_unit=scenario_item["margin_per_unit"])
        attestation.validate()
        scenario.validate()
        if scenario_item["fingerprint"] != scenario_fingerprint(scenario):
            raise RetroBotInputError("RB-014 fixture scenario fingerprint mismatch")
        results: list[PaperCycleResult] = []
        for raw_cycle in document["cycles"]:
            cycle = _fixture_mapping(raw_cycle, ("cycle_id", "unit_id", "fold", "clock_id", "bootstrap_id", "candidate_id", "state", "actions", "quotes", "causal_window"), "RB-014 fixture cycle schema is invalid")
            state = _fixture_state(cycle["state"])
            if not isinstance(cycle["actions"], list) or not isinstance(cycle["quotes"], list):
                raise RetroBotInputError("RB-014 fixture cycle sequences are invalid")
            actions = tuple(_fixture_action(item) for item in cycle["actions"])
            quotes = tuple(_fixture_quote(item) for item in cycle["quotes"])
            causal_item = _fixture_mapping(cycle["causal_window"], ("state", "close_snapshots", "rehedge_snapshots", "decision_records", "causal_cutoff_ns", "report_alias"), "RB-014 fixture causal window schema is invalid")
            causal_state = _fixture_state(causal_item["state"])
            if causal_state != state:
                raise RetroBotInputError("RB-014 fixture state provenance mismatch")
            if not isinstance(causal_item["close_snapshots"], list) or not isinstance(causal_item["rehedge_snapshots"], list) or not isinstance(causal_item["decision_records"], list):
                raise RetroBotInputError("RB-014 fixture causal sequences are invalid")
            causal_window = {
                "state": causal_state,
                "close_policy": frozen_candidate_policies(cycle["candidate_id"])[0],
                "rehedge_policy": frozen_candidate_policies(cycle["candidate_id"])[1],
                "close_snapshots": tuple(_fixture_snapshot(item) for item in causal_item["close_snapshots"]),
                "rehedge_snapshots": tuple(_fixture_snapshot(item) for item in causal_item["rehedge_snapshots"]),
                "decision_records": tuple(_fixture_decision_record(item) for item in causal_item["decision_records"]),
                "causal_cutoff_ns": causal_item["causal_cutoff_ns"],
                "report_alias": causal_item["report_alias"],
            }
            results.append(paper_backtest_cycle(cycle_id=cycle["cycle_id"], unit_id=cycle["unit_id"], fold=cycle["fold"], clock_id=cycle["clock_id"], bootstrap_id=cycle["bootstrap_id"], candidate_id=cycle["candidate_id"], state=state, actions=actions, quotes=quotes, scenario=scenario, causal_window=causal_window))
    except (KeyError, TypeError, ValueError, RetroBotInputError) as error:
        if isinstance(error, RetroBotInputError):
            raise
        raise RetroBotInputError("RB-014 fixture record is invalid") from error
    return aggregate_paper_cycles(results, scenario=scenario, attestation=attestation)


paper_backtest = paper_backtest_cycle
aggregate_paper_bot = aggregate_paper_cycles
