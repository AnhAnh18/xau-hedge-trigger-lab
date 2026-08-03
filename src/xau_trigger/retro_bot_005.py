"""RETRO-BOT-005 causal lifecycle/state reducer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal
import hashlib
import json
import math

import pandas as pd

from .retro_bot import RetroBotInputError
from .retro_bot_004 import BOOTSTRAP_IDS


CASE_ID = "RETRO-BOT-005"
SCHEMA_VERSION = 1
StateName = Literal["HEDGED", "ONE_BUY", "ONE_SELL", "TERMINAL", "CENSORED"]
ActionKind = Literal["CLOSE_BUY", "CLOSE_SELL", "OPEN_BUY", "OPEN_SELL", "TERMINATE"]
ACTIVE_STATES = {"HEDGED", "ONE_BUY", "ONE_SELL"}
ACTION_KINDS = {"CLOSE_BUY", "CLOSE_SELL", "OPEN_BUY", "OPEN_SELL", "TERMINATE"}


@dataclass(frozen=True)
class PolicyAction:
    kind: ActionKind
    decision_time: pd.Timestamp
    window_epoch: int
    source: str = "policy"


@dataclass(frozen=True)
class OracleLabel:
    kind: str
    label_time: pd.Timestamp


@dataclass(frozen=True)
class StateSnapshot:
    state: StateName
    epoch: int
    last_time: pd.Timestamp | None
    quantity: float
    seen_keys: tuple[tuple[int, int, str], ...] = ()

    def __post_init__(self) -> None:
        if self.state not in {"HEDGED", "ONE_BUY", "ONE_SELL", "TERMINAL", "CENSORED"}:
            raise RetroBotInputError("RB-009 state is invalid")
        if type(self.epoch) is not int or self.epoch < 0 or type(self.quantity) is not float or not math.isfinite(self.quantity) or self.quantity != 1.0:
            raise RetroBotInputError("RB-009 quantity/epoch invariant failed")


@dataclass(frozen=True)
class ActionResult:
    status: str
    next_state: StateName
    action_side: str | None
    mark_allowed: bool
    state_epoch: int


@dataclass(frozen=True)
class EmittedAction:
    kind: str
    action_side: str | None
    decision_time: pd.Timestamp | None
    state_epoch: int
    mark_allowed: bool


@dataclass(frozen=True)
class ReductionResult:
    bootstrap: str
    final_state: StateName
    accepted_count: int
    invalid_count: int
    action_counts: tuple[tuple[str, int], ...]
    status: str
    emitted_actions: tuple[EmittedAction, ...] = ()


def _canonical_digest(payload: dict) -> str:
    document = dict(payload)
    document.pop("aggregate_sha256", None)
    canonical = json.dumps(document, ensure_ascii=True, separators=(",", ":"), sort_keys=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _time(value: object) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError, pd.errors.OutOfBoundsDatetime) as error:
        raise RetroBotInputError("RB-009 timestamp is invalid") from error
    if pd.isna(timestamp):
        raise RetroBotInputError("RB-009 timestamp is invalid")
    timestamp = timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")
    return timestamp


def bootstrap_state(bootstrap_id: str, anchor_time: object) -> StateSnapshot:
    if bootstrap_id not in BOOTSTRAP_IDS:
        raise RetroBotInputError("RB-009 bootstrap id is not registered")
    anchor = _time(anchor_time)
    if bootstrap_id == "left_censored":
        return StateSnapshot("CENSORED", 0, anchor, 1.0)
    return StateSnapshot("HEDGED", 0, anchor - pd.Timedelta(nanoseconds=1), 1.0)


def _transition(state: StateName, action: ActionKind) -> tuple[StateName, str | None] | None:
    transitions = {
        ("HEDGED", "CLOSE_BUY"): ("ONE_SELL", "sell"),
        ("HEDGED", "CLOSE_SELL"): ("ONE_BUY", "buy"),
        ("ONE_BUY", "OPEN_SELL"): ("HEDGED", "sell"),
        ("ONE_SELL", "OPEN_BUY"): ("HEDGED", "buy"),
    }
    if action == "TERMINATE" and state in ACTIVE_STATES:
        return "TERMINAL", None
    return transitions.get((state, action))


def apply_policy_action(snapshot: StateSnapshot, action: PolicyAction) -> tuple[StateSnapshot, ActionResult]:
    if not isinstance(action, PolicyAction) or action.source != "policy" or not isinstance(action.kind, str) or action.kind not in ACTION_KINDS or type(action.window_epoch) is not int or action.window_epoch < 0:
        raise RetroBotInputError("RB-009 policy action schema is invalid")
    decision_time = _time(action.decision_time)
    if snapshot.state not in ACTIVE_STATES:
        return snapshot, ActionResult("invalid_transition", snapshot.state, None, False, snapshot.epoch)
    if snapshot.last_time is not None and decision_time.floor("s") <= snapshot.last_time.floor("s"):
        return snapshot, ActionResult("invalid_transition", snapshot.state, None, False, snapshot.epoch)
    key = (action.window_epoch, decision_time.floor("s").value, action.kind)
    if key in snapshot.seen_keys or snapshot.state not in ACTIVE_STATES:
        return snapshot, ActionResult("invalid_transition", snapshot.state, None, False, snapshot.epoch)
    transition = _transition(snapshot.state, action.kind)
    if transition is None:
        return snapshot, ActionResult("invalid_transition", snapshot.state, None, False, snapshot.epoch)
    next_state, side = transition
    updated = StateSnapshot(next_state, snapshot.epoch + 1, decision_time, snapshot.quantity, snapshot.seen_keys + (key,))
    return updated, ActionResult("accepted", next_state, side, side is not None, updated.epoch)


def reduce_policy_actions(bootstrap_id: str, anchor_time: object, actions: Iterable[PolicyAction]) -> ReductionResult:
    snapshot = bootstrap_state(bootstrap_id, anchor_time)
    counts = {kind: 0 for kind in sorted(ACTION_KINDS)}
    accepted = 0
    invalid = 0
    status = "censored" if snapshot.state == "CENSORED" else "ok"
    if status == "censored":
        return ReductionResult(bootstrap_id, snapshot.state, 0, 0, tuple(counts.items()), status, ())
    emitted: list[EmittedAction] = []
    for action in actions:
        snapshot, result = apply_policy_action(snapshot, action)
        if result.status != "accepted":
            invalid += 1
            status = "invalid_transition"
            continue
        accepted += 1
        counts[action.kind] += 1
        emitted.append(EmittedAction(action.kind, result.action_side, _time(action.decision_time), result.state_epoch, result.mark_allowed))
        if snapshot.state == "TERMINAL":
            if status == "ok":
                status = "terminal"
    return ReductionResult(bootstrap_id, snapshot.state, accepted, invalid, tuple(counts.items()), status, tuple(emitted))


def oracle_labels_do_not_mutate_policy_state(labels: Iterable[OracleLabel]) -> tuple[OracleLabel, ...]:
    """Materialize diagnostics separately; this function cannot call the reducer."""
    return tuple(labels)


def aggregate_reductions(results: Iterable[ReductionResult]) -> dict:
    materialized = tuple(results)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "case_id": CASE_ID,
        "result_count": len(materialized),
        "state_counts": {state: sum(item.final_state == state for item in materialized) for state in ("HEDGED", "ONE_BUY", "ONE_SELL", "TERMINAL", "CENSORED")},
        "status_counts": {status: sum(item.status == status for item in materialized) for status in ("ok", "terminal", "censored", "invalid_transition")},
        "accepted_action_count": sum(item.accepted_count for item in materialized),
        "invalid_action_count": sum(item.invalid_count for item in materialized),
        "aggregate_sha256": "TO_BE_FILLED",
    }
    payload["aggregate_sha256"] = _canonical_digest(payload)
    validate_aggregate(payload)
    return payload


def classify_continuation(start_time: object, end_time: object, fold_start: object, fold_end: object) -> str:
    start, end = _time(start_time), _time(end_time)
    left, right = _time(fold_start), _time(fold_end)
    if end <= start:
        return "invalid_transition"
    if start < left or end > right:
        return "cross_fold_continuation"
    return "valid"


def validate_aggregate(payload: dict) -> None:
    expected = {"schema_version", "case_id", "result_count", "state_counts", "status_counts", "accepted_action_count", "invalid_action_count", "aggregate_sha256"}
    if not isinstance(payload, dict) or set(payload) != expected or payload.get("schema_version") != SCHEMA_VERSION or payload.get("case_id") != CASE_ID:
        raise RetroBotInputError("RB-009 aggregate schema mismatch")
    if payload.get("aggregate_sha256") != _canonical_digest(payload):
        raise RetroBotInputError("RB-009 aggregate digest mismatch")
    numbers = [payload["result_count"], payload["accepted_action_count"], payload["invalid_action_count"]]
    if any(type(value) is not int or value < 0 for value in numbers):
        raise RetroBotInputError("RB-009 aggregate counts are invalid")
    if not isinstance(payload["state_counts"], dict) or set(payload["state_counts"]) != {"HEDGED", "ONE_BUY", "ONE_SELL", "TERMINAL", "CENSORED"}:
        raise RetroBotInputError("RB-009 state counts are invalid")
    if not isinstance(payload["status_counts"], dict) or set(payload["status_counts"]) != {"ok", "terminal", "censored", "invalid_transition"}:
        raise RetroBotInputError("RB-009 status counts are invalid")
    if any(type(value) is not int or value < 0 for value in (*payload["state_counts"].values(), *payload["status_counts"].values())):
        raise RetroBotInputError("RB-009 aggregate maps contain invalid counts")
    if sum(payload["state_counts"].values()) != payload["result_count"] or sum(payload["status_counts"].values()) != payload["result_count"]:
        raise RetroBotInputError("RB-009 aggregate conservation failed")
    for key, value in payload.items():
        if isinstance(value, str) and any(token in value.casefold() for token in ("\\", "/", ".csv", ".html", ".ex5", "password", "ticket")):
            raise RetroBotInputError(f"RB-009 aggregate contains prohibited value: {key}")
