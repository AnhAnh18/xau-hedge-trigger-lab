"""RB-011 causal hedged-state close candidate engine."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Iterable, Mapping

import pandas as pd

from .retro_bot import RetroBotInputError
from .retro_bot_005 import StateSnapshot
from .retro_bot_006 import FeatureSnapshot, TriggerRule, build_causal_snapshot, evaluate_rule, validate_rule, validate_snapshot

CASE_ID = "RETRO-BOT-007"
RB008_CONFIG_SHA256 = "26fec4baa2b8e2680cc17afaad299bbbb00afba32810865ac60bf28eb2e49ebf"
REPORT_MANIFEST_SHA256 = "88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30"
TICK_MANIFEST_SHA256 = "a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c"
M5_FIREWALL = "M5_FIREWALL_ATTESTATION_V1"
POLICY_IDS = ("always_hold", "first_legal_match")
OUTCOMES = ("hold", "candidate_action", "feature_missing", "invalid_transition", "censored", "noneligible")


@dataclass(frozen=True)
class CandidatePolicy:
    policy_id: str
    rules: tuple[TriggerRule, ...] = ()

    def validate(self) -> None:
        if self.policy_id not in POLICY_IDS or not isinstance(self.rules, tuple):
            raise RetroBotInputError("RB-011 policy schema is invalid")
        if self.policy_id == "always_hold" and self.rules:
            raise RetroBotInputError("RB-011 always_hold must be empty")
        for rule in self.rules:
            if not isinstance(rule, TriggerRule):
                raise RetroBotInputError("RB-011 malformed policy")
            validate_rule(rule)
            if rule.candidate_kind not in {"CLOSE_BUY", "CLOSE_SELL"}:
                raise RetroBotInputError("RB-011 policy action is invalid")
        if len({rule.rule_id for rule in self.rules}) != len(self.rules):
            raise RetroBotInputError("RB-011 duplicate rule id")


@dataclass(frozen=True)
class CandidateDecision:
    outcome: str
    action_kind: str | None
    action_side: str | None
    state_epoch: int


@dataclass(frozen=True)
class OracleLabel:
    cycle_id: str
    label_time: pd.Timestamp
    action_kind: str


def evaluate_candidate(
    state: StateSnapshot,
    snapshot: FeatureSnapshot,
    policy: CandidatePolicy,
    *,
    expected_epoch: int,
    ticks: list[Mapping[str, object]] | None = None,
    seen_decision_times: frozenset[pd.Timestamp] = frozenset(),
) -> CandidateDecision:
    try:
        policy.validate()
    except (AttributeError, TypeError, RetroBotInputError):
        return CandidateDecision("invalid_transition", None, None, getattr(state, "epoch", 0))
    snapshot = validate_snapshot(snapshot)
    if snapshot.oracle_labels:
        return CandidateDecision("invalid_transition", None, None, state.epoch)
    if any(pd.Timestamp(item).floor("s") == snapshot.decision_time.floor("s") for item in seen_decision_times):
        return CandidateDecision("invalid_transition", None, None, state.epoch)
    if ticks is not None:
        snapshot = build_causal_snapshot(
            ticks, snapshot.decision_time, state=str(snapshot.values.get("state")),
            side=str(snapshot.values.get("side")), clock_id=str(snapshot.values.get("clock_id")),
        )
    if type(expected_epoch) is not int or expected_epoch != state.epoch:
        return CandidateDecision("invalid_transition", None, None, state.epoch)
    if state.state == "CENSORED":
        return CandidateDecision("censored", None, None, state.epoch)
    if state.state != "HEDGED":
        return CandidateDecision("noneligible", None, None, state.epoch)
    if state.last_time is not None and snapshot.decision_time.floor("s") <= state.last_time.floor("s"):
        return CandidateDecision("invalid_transition", None, None, state.epoch)
    if policy.policy_id == "always_hold":
        return CandidateDecision("hold", None, None, state.epoch)
    if not policy.rules:
        return CandidateDecision("hold", None, None, state.epoch)
    # Missing/non-finite inputs fail closed for the whole policy.
    preliminary = [evaluate_rule(snapshot, rule) for rule in policy.rules]
    if "feature_missing" in preliminary:
        return CandidateDecision("feature_missing", None, None, state.epoch)
    missing = False
    matched = sorted(policy.rules, key=lambda rule: rule.rule_id)
    for rule in matched:
        outcome = evaluate_rule(snapshot, rule)
        if outcome == "feature_missing":
            missing = True
            continue
        if outcome == "invalid_transition":
            return CandidateDecision("invalid_transition", None, None, state.epoch)
        if outcome == "candidate_action":
            side = "sell" if rule.candidate_kind == "CLOSE_BUY" else "buy"
            return CandidateDecision("candidate_action", rule.candidate_kind, side, state.epoch)
    return CandidateDecision("hold", None, None, state.epoch)


def timing_band(delta_seconds: float) -> str:
    if delta_seconds < 0 or not pd.notna(delta_seconds):
        raise RetroBotInputError("RB-011 timing delta is invalid")
    if delta_seconds == 0:
        return "exact"
    if delta_seconds <= 1:
        return "0-1s"
    if delta_seconds <= 6:
        return "2-6s"
    if delta_seconds <= 30:
        return "7-30s"
    return ">30s"


def match_oracle_labels(cycle_id: str, action_time: object, action_kind: str, labels: Iterable[OracleLabel], *, used_indices: frozenset[int] = frozenset()) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", cycle_id):
        raise RetroBotInputError("RB-011 cycle id is invalid")
    action = pd.Timestamp(action_time)
    candidates: list[tuple[float, OracleLabel]] = []
    for index, label in enumerate(labels):
        if index in used_indices:
            continue
        if label.cycle_id != cycle_id:
            continue
        delta = (pd.Timestamp(label.label_time) - action).total_seconds()
        if delta >= 0:
            candidates.append((delta, label))
    if not candidates:
        return "unmatched"
    delta, label = min(candidates, key=lambda item: item[0])
    return "direction_mismatch" if label.action_kind != action_kind else timing_band(delta)


def match_oracle_sequence(actions: Iterable[tuple[str, object, str]], labels: tuple[OracleLabel, ...]) -> dict[str, int]:
    used: set[int] = set()
    counts = {"exact": 0, "0-1s": 0, "2-6s": 0, "7-30s": 0, ">30s": 0, "unmatched": 0, "direction_mismatch": 0, "duplicate_label": 0, "unmatched_labels": 0}
    seen_label_keys: set[tuple[str, object, str]] = set()
    for label in labels:
        key = (label.cycle_id, pd.Timestamp(label.label_time).floor("s"), label.action_kind)
        if key in seen_label_keys:
            counts["duplicate_label"] += 1
        seen_label_keys.add(key)
    for cycle_id, action_time, action_kind in actions:
        candidates = []
        action = pd.Timestamp(action_time)
        for index, label in enumerate(labels):
            if index in used or label.cycle_id != cycle_id:
                continue
            delta = (pd.Timestamp(label.label_time) - action).total_seconds()
            if delta >= 0:
                candidates.append((delta, index, label))
        if not candidates:
            counts["unmatched"] += 1
            continue
        delta, index, label = min(candidates, key=lambda item: (item[0], item[1]))
        used.add(index)
        if label.action_kind != action_kind:
            counts["direction_mismatch"] += 1
            continue
        counts[timing_band(delta)] += 1
    counts["unmatched_labels"] = len(labels) - len(used)
    return counts


def aggregate_candidate_results(results: Mapping[str, int], *, policy_id: str, eligible: int, case_id: str = "synthetic", directional_action_counts: Mapping[str, int] | None = None, oracle_counts: Mapping[str, int] | None = None) -> dict:
    if policy_id not in POLICY_IDS or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", case_id):
        raise RetroBotInputError("RB-011 aggregate identity is invalid")
    allowed_results = set(OUTCOMES) | {"noneligible_terminal", "noneligible_one_leg", "duplicate_action"}
    if set(results) - allowed_results or any(type(value) is not int or value < 0 for value in results.values()):
        raise RetroBotInputError("RB-011 aggregate outcomes are invalid")
    if type(eligible) is not int or eligible < 0:
        raise RetroBotInputError("RB-011 eligible count is invalid")
    mapped_noneligible = results.get("noneligible", 0) + results.get("noneligible_terminal", 0) + results.get("noneligible_one_leg", 0)
    mapped_invalid = results.get("invalid_transition", 0) + results.get("duplicate_action", 0)
    if sum(results.get(key, 0) for key in ("hold", "candidate_action", "feature_missing", "censored")) + mapped_noneligible + mapped_invalid != eligible:
        raise RetroBotInputError("RB-011 aggregate conservation failed")
    directional = {"CLOSE_BUY": 0, "CLOSE_SELL": 0} if directional_action_counts is None else dict(directional_action_counts)
    if set(directional) != {"CLOSE_BUY", "CLOSE_SELL"} or any(type(value) is not int or value < 0 for value in directional.values()):
        raise RetroBotInputError("RB-011 directional counts are invalid")
    oracle = {"exact": 0, "0-1s": 0, "2-6s": 0, "7-30s": 0, ">30s": 0, "unmatched": 0, "direction_mismatch": 0, "duplicate_label": 0, "unmatched_labels": 0} if oracle_counts is None else dict(oracle_counts)
    if set(oracle) != {"exact", "0-1s", "2-6s", "7-30s", ">30s", "unmatched", "direction_mismatch", "duplicate_label", "unmatched_labels"} or any(type(value) is not int or value < 0 for value in oracle.values()):
        raise RetroBotInputError("RB-011 oracle counts are invalid")
    payload = {
        "schema_version": 1, "case_id": case_id, "retro_case": CASE_ID,
        "rb008_config_sha256": RB008_CONFIG_SHA256,
        "source_manifest_digests": {"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256},
        "policy_id": policy_id, "eligible": eligible,
        "outcome_counts": {
            "hold": int(results.get("hold", 0)),
            "candidate_action": int(results.get("candidate_action", 0)),
            "feature_missing": int(results.get("feature_missing", 0)),
            "invalid_transition": int(results.get("invalid_transition", 0) + results.get("duplicate_action", 0)),
            "censored": int(results.get("censored", 0)),
            "noneligible": int(results.get("noneligible", 0) + results.get("noneligible_terminal", 0) + results.get("noneligible_one_leg", 0)),
        },
        "noneligible_counts": {"terminal": int(results.get("noneligible_terminal", 0)), "one_leg": int(results.get("noneligible_one_leg", 0)), "censored": int(results.get("censored", 0))},
        "duplicate_action_count": int(results.get("duplicate_action", 0)),
        "directional_action_counts": directional,
        "oracle_counts": oracle,
        "gate_status": {"support": "inconclusive", "coverage": "exploratory", "timing": "exploratory"},
        "m5_firewall": M5_FIREWALL,
        "aggregate_sha256": "TO_BE_FILLED",
    }
    payload["aggregate_sha256"] = hashlib.sha256(json.dumps({key: value for key, value in payload.items() if key != "aggregate_sha256"}, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode()).hexdigest()
    validate_candidate_aggregate(payload)
    return payload


def validate_candidate_aggregate(payload: Mapping[str, object]) -> None:
    expected = {"schema_version", "case_id", "retro_case", "rb008_config_sha256", "source_manifest_digests", "policy_id", "eligible", "outcome_counts", "noneligible_counts", "duplicate_action_count", "directional_action_counts", "oracle_counts", "gate_status", "m5_firewall", "aggregate_sha256"}
    if not isinstance(payload, Mapping) or set(payload) != expected or payload.get("schema_version") != 1 or payload.get("retro_case") != CASE_ID or payload.get("m5_firewall") != M5_FIREWALL:
        raise RetroBotInputError("RB-011 aggregate schema/firewall mismatch")
    if payload.get("policy_id") not in POLICY_IDS or not isinstance(payload.get("case_id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", payload["case_id"]):
        raise RetroBotInputError("RB-011 aggregate policy is invalid")
    if payload.get("rb008_config_sha256") != RB008_CONFIG_SHA256 or payload.get("source_manifest_digests") != {"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256}:
        raise RetroBotInputError("RB-011 aggregate provenance mismatch")
    if type(payload.get("eligible")) is not int or payload["eligible"] < 0:
        raise RetroBotInputError("RB-011 aggregate eligible count is invalid")
    if payload.get("aggregate_sha256") != hashlib.sha256(json.dumps({key: value for key, value in payload.items() if key != "aggregate_sha256"}, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode()).hexdigest():
        raise RetroBotInputError("RB-011 aggregate digest mismatch")
    outcomes = payload.get("outcome_counts")
    if not isinstance(outcomes, Mapping) or set(outcomes) != set(OUTCOMES) or any(type(value) is not int or value < 0 for value in outcomes.values()):
        raise RetroBotInputError("RB-011 aggregate outcomes are invalid")
    if sum(outcomes.values()) != payload.get("eligible"):
        raise RetroBotInputError("RB-011 aggregate conservation failed")
    directional = payload.get("directional_action_counts")
    if not isinstance(directional, Mapping) or set(directional) != {"CLOSE_BUY", "CLOSE_SELL"} or any(type(value) is not int or value < 0 for value in directional.values()) or sum(directional.values()) != outcomes["candidate_action"]:
        raise RetroBotInputError("RB-011 directional accounting is invalid")
    oracle = payload.get("oracle_counts")
    if not isinstance(oracle, Mapping) or set(oracle) != {"exact", "0-1s", "2-6s", "7-30s", ">30s", "unmatched", "direction_mismatch", "duplicate_label", "unmatched_labels"} or any(type(value) is not int or value < 0 for value in oracle.values()):
        raise RetroBotInputError("RB-011 oracle accounting is invalid")
    gates = payload.get("gate_status")
    if gates != {"support": "inconclusive", "coverage": "exploratory", "timing": "exploratory"}:
        raise RetroBotInputError("RB-011 gate schema is invalid")
    noneligible = payload.get("noneligible_counts")
    if not isinstance(noneligible, Mapping) or set(noneligible) != {"terminal", "one_leg", "censored"} or any(type(value) is not int or value < 0 for value in noneligible.values()):
        raise RetroBotInputError("RB-011 noneligible accounting is invalid")
    duplicate = payload.get("duplicate_action_count")
    if type(duplicate) is not int or duplicate < 0:
        raise RetroBotInputError("RB-011 duplicate accounting is invalid")
    if noneligible["terminal"] + noneligible["one_leg"] != outcomes["noneligible"] or noneligible["censored"] != outcomes["censored"]:
        raise RetroBotInputError("RB-011 noneligible conservation failed")
    if duplicate > outcomes["invalid_transition"]:
        raise RetroBotInputError("RB-011 duplicate conservation failed")
