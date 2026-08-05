"""RB-012 causal one-leg re-hedge candidate engine."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Mapping

import pandas as pd

from .retro_bot import RetroBotInputError
from .retro_bot_005 import PolicyAction, StateSnapshot, apply_policy_action
from .retro_bot_006 import FeatureSnapshot, RuleClause, TriggerRule, evaluate_rule, validate_rule, validate_snapshot

CASE_ID = "RETRO-BOT-008"
RB008_CONFIG_SHA256 = "26fec4baa2b8e2680cc17afaad299bbbb00afba32810865ac60bf28eb2e49ebf"
REPORT_MANIFEST_SHA256 = "88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30"
TICK_MANIFEST_SHA256 = "a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c"
M5_FIREWALL = "M5_FIREWALL_ATTESTATION_V1"


@dataclass(frozen=True)
class RehedgePolicy:
    policy_id: str
    rules: tuple[TriggerRule, ...] = ()

    def validate(self) -> None:
        if self.policy_id not in {"always_hold", "first_legal_match"} or not isinstance(self.rules, tuple):
            raise RetroBotInputError("RB-012 policy schema is invalid")
        for rule in self.rules:
            if not isinstance(rule, TriggerRule):
                raise RetroBotInputError("RB-012 malformed policy")
            validate_rule(rule)
            if rule.candidate_kind not in {"OPEN_BUY", "OPEN_SELL"}:
                raise RetroBotInputError("RB-012 illegal action mapping")
        if len({rule.rule_id for rule in self.rules}) != len(self.rules):
            raise RetroBotInputError("RB-012 duplicate rule id")
        if self.policy_id == "always_hold" and self.rules:
            raise RetroBotInputError("RB-012 always_hold must have no rules")
        if self.policy_id == "first_legal_match":
            if len(self.rules) != 2:
                raise RetroBotInputError("RB-012 policy manifest is not frozen")
            expected = {"open_buy", "open_sell"}
            if {rule.rule_id for rule in self.rules} != expected:
                raise RetroBotInputError("RB-012 policy rule ids are not frozen")
            for rule in self.rules:
                if len(rule.clauses) != 1 or rule.clauses[0].feature != "state" or rule.clauses[0].operator != "always":
                    raise RetroBotInputError("RB-012 policy clauses are not frozen")
                if rule.candidate_kind != rule.rule_id.upper():
                    expected_kind = "OPEN_BUY" if rule.rule_id == "open_buy" else "OPEN_SELL"
                    if rule.candidate_kind != expected_kind:
                        raise RetroBotInputError("RB-012 policy direction is not frozen")


@dataclass(frozen=True)
class RehedgeDecision:
    outcome: str
    action_kind: str | None
    action_side: str | None
    state_epoch: int


def evaluate_rehedge(state: StateSnapshot, snapshot: FeatureSnapshot, policy: RehedgePolicy, *, expected_epoch: int) -> RehedgeDecision:
    try:
        policy.validate()
    except (RetroBotInputError, TypeError, AttributeError):
        return RehedgeDecision("censored", None, None, getattr(state, "epoch", 0))
    if type(expected_epoch) is not int or expected_epoch != state.epoch:
        return RehedgeDecision("censored", None, None, state.epoch)
    try:
        snapshot = validate_snapshot(snapshot)
    except (RetroBotInputError, AttributeError, TypeError, ValueError):
        return RehedgeDecision("censored", None, None, state.epoch)
    if snapshot.oracle_labels:
        return RehedgeDecision("censored", None, None, state.epoch)
    if state.state not in {"ONE_BUY", "ONE_SELL"}:
        return RehedgeDecision("censored", None, None, state.epoch)
    if state.last_time is not None:
        try:
            state_time = pd.Timestamp(state.last_time)
            state_time = state_time.tz_localize("UTC") if state_time.tzinfo is None else state_time.tz_convert("UTC")
            if snapshot.decision_time.floor("s") <= state_time.floor("s"):
                return RehedgeDecision("censored", None, None, state.epoch)
        except (TypeError, ValueError):
            return RehedgeDecision("censored", None, None, state.epoch)
    if policy.policy_id == "always_hold" or not policy.rules:
        return RehedgeDecision("hold", None, None, state.epoch)
    for rule in sorted(policy.rules, key=lambda item: item.rule_id):
        result = evaluate_rule(snapshot, rule)
        if result == "feature_missing":
            return RehedgeDecision("censored", None, None, state.epoch)
        if result != "candidate_action":
            continue
        expected_action = "OPEN_SELL" if state.state == "ONE_BUY" else "OPEN_BUY"
        if rule.candidate_kind != expected_action:
            return RehedgeDecision("censored", None, None, state.epoch)
        return RehedgeDecision("action", expected_action, "sell" if expected_action == "OPEN_SELL" else "buy", state.epoch)
    return RehedgeDecision("hold", None, None, state.epoch)


def replay_rehedge_window(state: StateSnapshot, snapshots: tuple[FeatureSnapshot, ...], policy: RehedgePolicy, *, expected_epoch: int) -> tuple[RehedgeDecision, StateSnapshot]:
    try:
        policy.validate()
    except (RetroBotInputError, TypeError, AttributeError):
        return RehedgeDecision("censored", None, None, state.epoch), state
    previous = state.last_time
    if previous is not None:
        previous = pd.Timestamp(previous)
        previous = previous.tz_localize("UTC") if previous.tzinfo is None else previous.tz_convert("UTC")
    for snapshot in snapshots:
        if not isinstance(snapshot, FeatureSnapshot):
            return RehedgeDecision("censored", None, None, state.epoch), state
        try:
            decision_time = pd.Timestamp(snapshot.decision_time)
        except (TypeError, ValueError):
            return RehedgeDecision("censored", None, None, state.epoch), state
        if decision_time.tzinfo is None:
            decision_time = decision_time.tz_localize("UTC")
        else:
            decision_time = decision_time.tz_convert("UTC")
        if previous is not None and decision_time.floor("s") <= previous.floor("s"):
            return RehedgeDecision("censored", None, None, state.epoch), state
        if state.last_time is not None:
            state_time = pd.Timestamp(state.last_time)
            state_time = state_time.tz_localize("UTC") if state_time.tzinfo is None else state_time.tz_convert("UTC")
            if decision_time < state_time:
                return RehedgeDecision("censored", None, None, state.epoch), state
        decision = evaluate_rehedge(state, snapshot, policy, expected_epoch=expected_epoch)
        if decision.outcome == "action":
            updated, result = apply_policy_action(state, PolicyAction(decision.action_kind, decision_time, expected_epoch))
            if result.status != "accepted":
                return RehedgeDecision("censored", None, None, state.epoch), state
            return decision, updated
        if decision.outcome == "censored":
            return decision, state
        previous = decision_time
    return RehedgeDecision("hold", None, None, state.epoch), state


def aggregate_rehedge_results(results: Mapping[str, int], *, policy_id: str, windows: int, case_id: str = "synthetic") -> dict:
    allowed = {"hold", "action", "censored"}
    if not isinstance(results, Mapping) or policy_id not in {"always_hold", "first_legal_match"} or not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", case_id) or not isinstance(windows, int) or windows < 0:
        raise RetroBotInputError("RB-012 aggregate identity is invalid")
    if set(results) != allowed or any(type(value) is not int or value < 0 for value in results.values()) or sum(results.values()) != windows:
        raise RetroBotInputError("RB-012 aggregate accounting is invalid")
    payload = {"schema_version": 1, "case_id": case_id, "retro_case": CASE_ID, "rb008_config_sha256": RB008_CONFIG_SHA256, "source_manifest_digests": {"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256}, "policy_id": policy_id, "windows": windows, "outcome_counts": {key: int(results.get(key, 0)) for key in ("hold", "action", "censored")}, "m5_firewall": M5_FIREWALL, "aggregate_sha256": "TO_BE_FILLED"}
    payload["aggregate_sha256"] = hashlib.sha256(json.dumps({key: value for key, value in payload.items() if key != "aggregate_sha256"}, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode()).hexdigest()
    validate_rehedge_aggregate(payload)
    return payload


def validate_rehedge_aggregate(payload: Mapping[str, object]) -> None:
    expected = {"schema_version", "case_id", "retro_case", "rb008_config_sha256", "source_manifest_digests", "policy_id", "windows", "outcome_counts", "m5_firewall", "aggregate_sha256"}
    if not isinstance(payload, Mapping) or set(payload) != expected or payload.get("schema_version") != 1 or payload.get("retro_case") != CASE_ID or payload.get("m5_firewall") != M5_FIREWALL:
        raise RetroBotInputError("RB-012 aggregate schema/firewall mismatch")
    if payload.get("rb008_config_sha256") != RB008_CONFIG_SHA256 or payload.get("source_manifest_digests") != {"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256}:
        raise RetroBotInputError("RB-012 aggregate provenance mismatch")
    case_id = payload.get("case_id")
    if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", case_id) or payload.get("policy_id") not in {"always_hold", "first_legal_match"} or type(payload.get("windows")) is not int or payload["windows"] < 0:
        raise RetroBotInputError("RB-012 aggregate identity/count invalid")
    outcomes = payload.get("outcome_counts")
    if not isinstance(outcomes, Mapping) or set(outcomes) != {"hold", "action", "censored"} or any(type(value) is not int or value < 0 for value in outcomes.values()) or sum(outcomes.values()) != payload["windows"]:
        raise RetroBotInputError("RB-012 aggregate accounting invalid")
    expected_digest = hashlib.sha256(json.dumps({key: value for key, value in payload.items() if key != "aggregate_sha256"}, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode()).hexdigest()
    if payload.get("aggregate_sha256") != expected_digest:
        raise RetroBotInputError("RB-012 aggregate digest mismatch")
