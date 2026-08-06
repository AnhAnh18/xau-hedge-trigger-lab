"""RB-020 causal historical reconstruction primitives.

This module deliberately keeps the autonomous input type disjoint from the
observed/oracle diagnostic type.  It is source-free: callers provide already
redacted, typed observations and only aggregate output is retained.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re
from pathlib import Path
import pandas as pd
from .retro_hist_003 import CausalState as RHState, CausalTick as RHTick, build_feature_snapshot, evaluate_candidate, apply_decision
from typing import Any, Mapping, Sequence

from .retro_bot import RetroBotInputError

RB020_ID = "RB-020"
SCHEMA_VERSION = 1
M5_FIREWALL = "M5_FIREWALL_ATTESTATION_V1"
REPORT_MANIFEST_SHA256 = "88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30"
TICK_MANIFEST_SHA256 = "a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c"
STATES = frozenset({"UNKNOWN", "FLAT", "HEDGED", "ONE_BUY", "ONE_SELL", "TERMINAL", "CENSORED"})
ACTIONS = frozenset({"NONE", "OPEN_BUY", "OPEN_SELL", "CLOSE_BUY", "CLOSE_SELL"})


def canonical_json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as exc:
        raise RetroBotInputError("RB-020 canonical JSON is invalid") from exc


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def _decimal(value: object, *, positive: bool = False) -> Decimal:
    if not isinstance(value, str):
        raise RetroBotInputError("RB-020 decimal must be a string")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise RetroBotInputError("RB-020 decimal is invalid") from exc
    if not result.is_finite() or (positive and result <= 0) or result < 0:
        raise RetroBotInputError("RB-020 decimal is out of bounds")
    return result


@dataclass(frozen=True)
class Tick:
    time_ns: int
    bid: Decimal
    ask: Decimal

@dataclass(frozen=True)
class Quote:
    bid: Decimal
    ask: Decimal

@dataclass(frozen=True)
class Lot:
    side: str
    quantity: Decimal
    opened_time_ns: int


@dataclass(frozen=True)
class AutonomousInput:
    ticks: tuple[Tick, ...]
    initial_state: str = "UNKNOWN"
    bootstrap_supported: bool = False
    latency_ns: int = 0
    candidate: str = "open_on_first_tick"
    source_aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class OracleDiagnosticInput:
    observed_events: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class DecisionRecord:
    time_ns: int
    action: str
    state_before: str
    state_after: str
    future_read: bool = False
    oracle_used: bool = False


@dataclass(frozen=True)
class CycleRecord:
    cycle_id: str
    state: str
    decision_count: int
    censored: bool


@dataclass(frozen=True)
class AccountingRecord:
    cycle_id: str
    quantity_fixed8: str
    conserved: bool
    mark_status: str

@dataclass(frozen=True)
class FoldInput:
    development_aliases: tuple[str, ...]
    validation_aliases: tuple[str, ...]
    holdout_aliases: tuple[str, ...]
    autonomous: AutonomousInput
    input_digest: str

def paper_account_records(inp: AutonomousInput, *, fee_per_unit: str = "0", slippage_points: str = "0") -> AccountingRecord:
    """Conservative Decimal accounting summary; never feeds replay decisions."""
    fee, slip = _decimal(fee_per_unit), _decimal(slippage_points)
    decisions = replay_decisions(inp)
    opened = sum(1 for d in decisions if d.action.startswith("OPEN"))
    closed = sum(1 for d in decisions if d.action.startswith("CLOSE"))
    conserved = closed <= opened
    qty = f"{Decimal(opened - closed):.8f}"
    return AccountingRecord("rb020", qty, conserved, "causal_quote_only" if decisions else "no_action")


def consume_redacted_stream(rows: Any, *, max_rows: int = 1_000_000) -> dict[str, int]:
    """Consume an RH-style stream without retaining or echoing source rows."""
    count = 0
    previous = -1
    digest = hashlib.sha256()
    for row in rows:
        if count >= max_rows or not isinstance(row, Mapping) or set(row) != {"time_ns", "bid", "ask"}:
            raise RetroBotInputError("RB-020 stream bound/schema violation")
        parsed = _tick({"time_ns": row["time_ns"], "bid": str(row["bid"]), "ask": str(row["ask"])})
        if parsed.time_ns <= previous:
            raise RetroBotInputError("RB-020 stream chronology is invalid")
        previous = parsed.time_ns
        digest.update(canonical_json({"time_ns": row["time_ns"], "bid": str(row["bid"]), "ask": str(row["ask"])}).encode())
        count += 1
    return {"row_count": count, "stream_digest_sha256": digest.hexdigest()}


def adapt_rh_ticks(rows: Any) -> tuple[Tick, ...]:
    """Adapt RH quote objects/mappings while retaining only typed ticks."""
    out = []
    previous = -1
    if not hasattr(rows, "__iter__"):
        raise RetroBotInputError("RB-020 tick stream is invalid")
    for row in rows:
        if isinstance(row, Mapping):
            if set(row) != {"time_ns", "bid", "ask"}:
                raise RetroBotInputError("RB-020 tick fields are invalid")
            value = {"time_ns": row.get("time_ns"), "bid": str(row.get("bid")), "ask": str(row.get("ask"))}
        elif isinstance(row, Tick):
            out.append(row)
            parsed = row
            if parsed.time_ns <= previous:
                raise RetroBotInputError("RB-020 tick chronology is invalid")
            previous = parsed.time_ns
            if len(out) > 100000:
                raise RetroBotInputError("RB-020 tick stream is too large")
            continue
        else:
            value = {"time_ns": getattr(row, "time_ns", None), "bid": str(getattr(row, "bid", None)), "ask": str(getattr(row, "ask", None))}
        parsed = _tick(value)
        if parsed.time_ns <= previous:
            raise RetroBotInputError("RB-020 tick chronology is invalid")
        previous = parsed.time_ns
        out.append(parsed)
        if len(out) > 100000:
            raise RetroBotInputError("RB-020 tick stream is too large")
    return tuple(out)


def adapt_rh_lifecycle(rows: Any) -> tuple[dict[str, Any], ...]:
    """Convert RH lifecycle events to redacted action records."""
    result = []
    previous = -1
    if not hasattr(rows, "__iter__"):
        raise RetroBotInputError("RB-020 lifecycle stream is invalid")
    for row in rows:
        if isinstance(row, Mapping) and set(row) != {"kind", "side", "quantity", "time_ns"}:
            raise RetroBotInputError("RB-020 lifecycle fields are invalid")
        kind = row.get("kind") if isinstance(row, Mapping) else getattr(row, "kind", None)
        side = row.get("side") if isinstance(row, Mapping) else getattr(row, "side", None)
        quantity = row.get("quantity") if isinstance(row, Mapping) else getattr(row, "quantity", None)
        time = row.get("time_ns") if isinstance(row, Mapping) else getattr(row, "time_ns", None)
        if kind not in {"OPEN", "CLOSE"} or side not in {"BUY", "SELL"} or not isinstance(quantity, str) or not re.fullmatch(r"(?:0|[1-9][0-9]*)\.[0-9]{8}", quantity):
            raise RetroBotInputError("RB-020 lifecycle adapter schema violation")
        parsed_quantity = _decimal(quantity, positive=True)
        if type(time) is not int or time < 0 or time <= previous:
            raise RetroBotInputError("RB-020 lifecycle chronology is invalid")
        previous = time
        result.append({"action": f"{kind}_{side}", "quantity_fixed8": f"{parsed_quantity:.8f}", "time_ns": time})
        if len(result) > 100000:
            raise RetroBotInputError("RB-020 lifecycle stream is too large")
    return tuple(result)


def build_autonomous_input(*, ticks: Any, initial_state: str = "UNKNOWN", bootstrap_supported: bool = False, latency_ns: int = 0, source_aliases: tuple[str, ...] = ()) -> AutonomousInput:
    return AutonomousInput(adapt_rh_ticks(ticks), initial_state, bootstrap_supported, latency_ns, "open_on_first_tick", tuple(source_aliases))


def build_lane_inputs(*, ticks: Any, lifecycle: Any, initial_state: str = "UNKNOWN", bootstrap_supported: bool = False, latency_ns: int = 0) -> tuple[AutonomousInput, OracleDiagnosticInput]:
    """Build isolated policy and observed-label lanes from RH adapters."""
    autonomous = build_autonomous_input(ticks=ticks, initial_state=initial_state, bootstrap_supported=bootstrap_supported, latency_ns=latency_ns)
    labels = tuple({"time_ns": row["time_ns"], "action": row["action"]} for row in adapt_rh_lifecycle(lifecycle))
    return autonomous, OracleDiagnosticInput(labels)


def account_lifecycle_records(actions: Any, quotes: Any, *, fee_per_unit: str = "0", slippage_points: str = "0") -> dict[str, Any]:
    """Lot-aware Decimal accounting for redacted adapter records."""
    fee, slip = _decimal(fee_per_unit), _decimal(slippage_points)
    typed_quotes = adapt_rh_ticks(quotes)
    cash = Decimal("0"); buy = Decimal("0"); sell = Decimal("0"); opened = Decimal("0"); closed = Decimal("0"); invalid = 0; missing = 0
    for action in adapt_rh_lifecycle(actions):
        quote = next((q for q in typed_quotes if q.time_ns >= action["time_ns"]), None)
        if quote is None: missing += 1; continue
        qty = Decimal(action["quantity_fixed8"]); kind, side = action["action"].split("_")
        if kind == "OPEN" and side == "BUY": buy += qty; cash -= quote.ask * qty
        elif kind == "OPEN" and side == "SELL": sell += qty; cash += quote.bid * qty
        elif kind == "CLOSE" and side == "BUY" and buy >= qty: buy -= qty; cash += quote.bid * qty; closed += qty
        elif kind == "CLOSE" and side == "SELL" and sell >= qty: sell -= qty; cash -= quote.ask * qty; closed += qty
        else: invalid += 1; continue
        if kind == "OPEN": opened += qty
        cash -= (fee + slip) * qty
    scenario = {"fee_per_unit": f"{fee:.8f}", "slippage_points": f"{slip:.8f}"}
    status = "valid" if invalid == 0 and missing == 0 and closed <= opened else "censored"
    return {"cash_fixed8": f"{cash:.8f}", "buy_remaining_fixed8": f"{buy:.8f}", "sell_remaining_fixed8": f"{sell:.8f}", "opened_quantity_fixed8": f"{opened:.8f}", "closed_quantity_fixed8": f"{closed:.8f}", "invalid_count": invalid, "missing_quote_count": missing, "conserved": closed <= opened and buy >= 0 and sell >= 0, "scenario_fingerprint": _digest(scenario), "mark_status": "causal_quote_only", "status": status}


def registered_fold_config() -> dict[str, Any]:
    config = {"schema_version": 1, "development": [f"report-{i:03d}.html" for i in range(1, 6)], "validation": ["report-006.html", "report-007.html"], "holdout": ["report-008.html", "report-009.html"], "candidate_vocabulary": ["state_age", "price_increment", "spread", "tick_rate"]}
    config["config_sha256"] = _digest(config)
    return config

def build_fold_input(autonomous: AutonomousInput) -> FoldInput:
    cfg = registered_fold_config()
    digest = _digest({"autonomous": replay_autonomous(autonomous), "fold_config_sha256": cfg["config_sha256"]})
    return FoldInput(tuple(cfg["development"]), tuple(cfg["validation"]), tuple(cfg["holdout"]), autonomous, digest)

def seal_holdout(*, holdout: AutonomousInput, nonce: str) -> dict[str, str]:
    if not isinstance(nonce, str) or len(nonce) < 8 or any(c in nonce for c in "\\/\n\r"):
        raise RetroBotInputError("RB-020 holdout nonce invalid")
    fold_hash = registered_fold_config()["config_sha256"]
    holdout_digest = _digest(replay_autonomous(holdout))
    return {"nonce": nonce, "fold_config_sha256": fold_hash, "holdout_digest": holdout_digest, "receipt_sha256": _digest({"nonce": nonce, "fold_config_sha256": fold_hash, "holdout_digest": holdout_digest})}

def verify_holdout_receipt(receipt: Mapping[str, str], *, holdout: AutonomousInput, used_nonces: set[str] | None = None) -> bool:
    if not isinstance(receipt, Mapping) or set(receipt) != {"nonce", "fold_config_sha256", "holdout_digest", "receipt_sha256"}:
        raise RetroBotInputError("RB-020 holdout receipt schema invalid")
    if used_nonces is not None and receipt["nonce"] in used_nonces:
        raise RetroBotInputError("RB-020 holdout receipt reused")
    expected = seal_holdout(holdout=holdout, nonce=receipt["nonce"])
    if dict(receipt) != expected:
        raise RetroBotInputError("RB-020 holdout receipt mismatch")
    return True


def validate_fold_config(config: Mapping[str, Any]) -> bool:
    expected = registered_fold_config()
    if not isinstance(config, Mapping) or set(config) != set(expected) or config.get("config_sha256") != _digest({k: config[k] for k in config if k != "config_sha256"}):
        raise RetroBotInputError("RB-020 fold config digest mismatch")
    for key in ("development", "validation", "holdout", "candidate_vocabulary"):
        if not isinstance(config[key], list) or not config[key]:
            raise RetroBotInputError("RB-020 fold config content is invalid")
    if config["candidate_vocabulary"] != expected["candidate_vocabulary"]:
        raise RetroBotInputError("RB-020 candidate vocabulary is invalid")
    folds = [set(config.get(name, [])) for name in ("development", "validation", "holdout")]
    if any(not folds[i].isdisjoint(folds[j]) for i in range(3) for j in range(i + 1, 3)) or set().union(*folds) != set(expected["development"] + expected["validation"] + expected["holdout"]):
        raise RetroBotInputError("RB-020 fold overlap")
    return True


def _tick(value: object) -> Tick:
    if not isinstance(value, Mapping) or tuple(value) != ("time_ns", "bid", "ask"):
        raise RetroBotInputError("RB-020 tick schema is invalid")
    if type(value["time_ns"]) is not int or value["time_ns"] < 0:
        raise RetroBotInputError("RB-020 tick time is invalid")
    bid, ask = _decimal(value["bid"], positive=True), _decimal(value["ask"], positive=True)
    if ask < bid:
        raise RetroBotInputError("RB-020 quote ordering is invalid")
    return Tick(value["time_ns"], bid, ask)


def parse_autonomous(value: object) -> AutonomousInput:
    if not isinstance(value, Mapping):
        raise RetroBotInputError("RB-020 autonomous input is invalid")
    allowed = {"ticks", "initial_state", "bootstrap_supported", "latency_ns", "candidate", "source_aliases"}
    base = allowed - {"stage", "folds", "fold_config_sha256", "accounting", "source_aliases"}
    if set(value) not in (base, base | {"source_aliases"}, base | {"stage", "folds"}, base | {"stage", "accounting"}):
        raise RetroBotInputError("RB-020 autonomous fields are invalid")
    ticks_raw = value["ticks"]
    if not isinstance(ticks_raw, list) or len(ticks_raw) > 100000:
        raise RetroBotInputError("RB-020 ticks are invalid")
    ticks = tuple(_tick(item) for item in ticks_raw)
    if any(a.time_ns >= b.time_ns for a, b in zip(ticks, ticks[1:])):
        raise RetroBotInputError("RB-020 tick ordering is invalid")
    state = value["initial_state"]
    if state not in STATES:
        raise RetroBotInputError("RB-020 initial state is invalid")
    if type(value["bootstrap_supported"]) is not bool or type(value["latency_ns"]) is not int or value["latency_ns"] < 0:
        raise RetroBotInputError("RB-020 bootstrap/latency is invalid")
    if value["candidate"] != "open_on_first_tick":
        raise RetroBotInputError("RB-020 candidate is not frozen")
    aliases = value.get("source_aliases", [])
    if not isinstance(aliases, list) or any(not isinstance(item, str) for item in aliases):
        raise RetroBotInputError("RB-020 source aliases are invalid")
    return AutonomousInput(ticks, state, value["bootstrap_supported"], value["latency_ns"], value["candidate"], tuple(aliases))


def parse_oracle(value: object) -> OracleDiagnosticInput:
    if not isinstance(value, Mapping) or tuple(value) != ("observed_events",):
        raise RetroBotInputError("RB-020 oracle input is invalid")
    events = value["observed_events"]
    if not isinstance(events, list):
        raise RetroBotInputError("RB-020 oracle events are invalid")
    clean = []
    for event in events:
        if not isinstance(event, Mapping) or set(event) != {"time_ns", "action"}:
            raise RetroBotInputError("RB-020 oracle event schema is invalid")
        if type(event["time_ns"]) is not int or event["time_ns"] < 0 or event["action"] not in ACTIONS:
            raise RetroBotInputError("RB-020 oracle event is invalid")
        clean.append({"time_ns": event["time_ns"], "action": event["action"]})
    return OracleDiagnosticInput(tuple(clean))


def replay_autonomous(inp: AutonomousInput) -> dict[str, Any]:
    return _replay(inp)[0]


def replay_decisions(inp: AutonomousInput) -> tuple[DecisionRecord, ...]:
    return _replay(inp)[1]


def replay_rh003_candidate(inp: AutonomousInput, *, candidate_id: str = "rehedge_mirror_active_leg", clock_id: str = "utc_plus_3") -> dict[str, Any]:
    """Run the frozen RH-003 causal feature/candidate engine over adapted ticks."""
    state_name = {"HEDGED": "HEDGED_1X1", "ONE_BUY": "ONE_BUY", "ONE_SELL": "ONE_SELL", "FLAT": "FLAT"}.get(inp.initial_state, "CENSORED")
    state = RHState(state_name, Decimal("1.00000000") if state_name in {"ONE_BUY", "HEDGED_1X1"} else Decimal("0.00000000"), Decimal("1.00000000") if state_name in {"ONE_SELL", "HEDGED_1X1"} else Decimal("0.00000000"))
    ticks = tuple(RHTick(pd.Timestamp(t.time_ns, unit="ns", tz="UTC"), t.bid, t.ask) for t in inp.ticks)
    actions = 0; supported = 0; censored = 0; action_kinds = {"OPEN_BUY": 0, "OPEN_SELL": 0, "CLOSE_BUY": 0, "CLOSE_SELL": 0}
    for index, tick in enumerate(ticks):
        snapshot = build_feature_snapshot(ticks[: index + 1], tick.time_utc, clock_id=clock_id, state=state.state)
        if snapshot.support_status == "supported": supported += 1
        else: censored += 1
        decision = evaluate_candidate(state, snapshot, candidate_id)
        if decision.outcome == "action":
            state = apply_decision(state, decision); actions += 1; action_kinds[decision.action_kind] += 1
    return {"schema_version": 1, "case_id": RB020_ID, "engine": "RH-003-causal", "candidate_id": candidate_id, "action_count": actions, "action_kind_counts": action_kinds, "supported_count": supported, "censored_count": censored, "final_state": state.state, "future_read": False, "oracle_used": False, "m5_firewall": M5_FIREWALL}


def _replay(inp: AutonomousInput) -> tuple[dict[str, Any], tuple[DecisionRecord, ...]]:
    state = inp.initial_state
    decisions: list[DecisionRecord] = []
    censored = 0
    if state == "UNKNOWN" and not inp.bootstrap_supported:
        censored = len(inp.ticks)
    elif inp.ticks:
        first = inp.ticks[0]
        if state == "FLAT":
            eligible = next((t for t in inp.ticks if t.time_ns >= first.time_ns + inp.latency_ns), None)
            if eligible is None:
                censored += 1; eligible = first
            decisions.append(DecisionRecord(eligible.time_ns, "OPEN_BUY", "FLAT", "ONE_BUY")); state = "ONE_BUY"
        for tick in inp.ticks[1:]:
            if state == "ONE_BUY" and tick.bid < first.bid:
                decisions.append(DecisionRecord(tick.time_ns + inp.latency_ns, "CLOSE_BUY", "ONE_BUY", "TERMINAL")); state = "TERMINAL"
            elif state == "ONE_BUY" and tick.ask > first.ask:
                decisions.append(DecisionRecord(tick.time_ns + inp.latency_ns, "OPEN_SELL", "ONE_BUY", "HEDGED")); state = "HEDGED"
            elif state == "ONE_SELL" and tick.bid < first.bid:
                decisions.append(DecisionRecord(tick.time_ns + inp.latency_ns, "OPEN_BUY", "ONE_SELL", "HEDGED")); state = "HEDGED"
            elif state == "HEDGED" and tick.bid < first.bid:
                decisions.append(DecisionRecord(tick.time_ns + inp.latency_ns, "CLOSE_BUY", "HEDGED", "ONE_SELL")); state = "ONE_SELL"
            elif state == "HEDGED" and tick.ask > first.ask:
                decisions.append(DecisionRecord(tick.time_ns + inp.latency_ns, "CLOSE_SELL", "HEDGED", "ONE_BUY")); state = "ONE_BUY"
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION, "case_id": RB020_ID,
        "decision_count": len(decisions), "censored_count": censored,
        "bootstrap_supported": inp.bootstrap_supported,
        "state_counts": {name: (1 if name == state else 0) for name in sorted(STATES)},
        "action_counts": {name: sum(d.action == name for d in decisions) for name in sorted(ACTIONS)},
        "future_read": False, "oracle_used": False, "m5_firewall": M5_FIREWALL,
    }
    payload["aggregate_sha256"] = _digest(payload)
    return payload, tuple(decisions)


def oracle_diagnostic(inp: OracleDiagnosticInput, decisions: Sequence[DecisionRecord] = ()) -> dict[str, Any]:
    observed = list(inp.observed_events)
    bands = {"exact": 0, "0-1s": 0, "2-6s": 0, ">6s": 0, "unmatched": 0, "direction_mismatch": 0}
    used: set[int] = set()
    for decision in decisions:
        candidates = [(i, abs(int(event["time_ns"]) - decision.time_ns), event) for i, event in enumerate(observed) if i not in used]
        if not candidates:
            bands["unmatched"] += 1
            continue
        i, distance, matched = min(candidates, key=lambda item: (item[1], item[0]))
        used.add(i)
        if matched["action"] != decision.action:
            bands["direction_mismatch"] += 1
            continue
        bands["exact" if distance == 0 else "0-1s" if distance <= 1_000_000_000 else "2-6s" if distance <= 6_000_000_000 else ">6s"] += 1
    out = {"schema_version": SCHEMA_VERSION, "case_id": RB020_ID, "oracle_only": True, "label_count": len(observed), "match_bands": bands, "m5_firewall": M5_FIREWALL}
    out["aggregate_sha256"] = _digest(out)
    return out


def verify_aggregate(value: Mapping[str, Any]) -> bool:
    if not isinstance(value, Mapping) or "aggregate_sha256" not in value:
        raise RetroBotInputError("RB-020 aggregate schema is invalid")
    allowed = {"schema_version", "case_id", "decision_count", "censored_count", "bootstrap_supported", "state_counts", "action_counts", "future_read", "oracle_used", "m5_firewall", "aggregate_sha256", "stage", "folds", "fold_config_sha256", "accounting", "consumed_nonces"}
    base = allowed - {"stage", "folds", "fold_config_sha256", "accounting", "consumed_nonces"}
    if set(value) not in (base, base | {"stage", "folds", "fold_config_sha256"}, base | {"stage", "accounting"}, base | {"stage", "folds", "fold_config_sha256", "consumed_nonces"}):
        raise RetroBotInputError("RB-020 aggregate fields are invalid")
    expected = dict(value); digest = expected.pop("aggregate_sha256")
    if not isinstance(digest, str) or _digest(expected) != digest:
        raise RetroBotInputError("RB-020 aggregate digest mismatch")
    if expected.get("m5_firewall") != M5_FIREWALL:
        raise RetroBotInputError("RB-020 firewall mismatch")
    if any(type(value.get(k)) is not int or value[k] < 0 for k in ("decision_count", "censored_count")):
        raise RetroBotInputError("RB-020 aggregate counts invalid")
    if set(value.get("state_counts", {})) != set(STATES) or set(value.get("action_counts", {})) != set(ACTIONS):
        raise RetroBotInputError("RB-020 aggregate maps invalid")
    if any(type(item) is not int or item < 0 for item in value["state_counts"].values()) or any(type(item) is not int or item < 0 for item in value["action_counts"].values()):
        raise RetroBotInputError("RB-020 aggregate map counts invalid")
    if "folds" in value:
        folds = value["folds"]
        if set(folds) != {"development", "validation", "holdout"} or any(not isinstance(folds[name], Mapping) for name in folds):
            raise RetroBotInputError("RB-020 fold aggregate invalid")
        if any(type(folds[name].get("censored_count")) is not int or folds[name]["censored_count"] < 0 for name in folds):
            raise RetroBotInputError("RB-020 fold counts invalid")
        required_fold = {"action_count", "action_kind_counts", "supported_count", "censored_count", "censor_rate", "support_pass", "coverage_pass", "state_safety_pass", "duplicate_action_count", "timing_bands", "final_state", "candidate_id", "engine"}
        for name in folds:
            metric = folds[name]
            if set(metric) - (required_fold | {"sealed", "seal_sha256", "selection_frozen", "consumption_receipt_sha256", "oracle_comparison"}) != set():
                raise RetroBotInputError("RB-020 fold metric fields invalid")
            if not required_fold.issubset(metric):
                raise RetroBotInputError("RB-020 fold metric fields missing")
            if any(type(metric.get(k)) is not int or metric[k] < 0 for k in ("action_count", "supported_count", "censored_count", "duplicate_action_count")):
                raise RetroBotInputError("RB-020 fold metric counts invalid")
            if not isinstance(metric["action_kind_counts"], Mapping) or set(metric["action_kind_counts"]) != {"OPEN_BUY", "OPEN_SELL", "CLOSE_BUY", "CLOSE_SELL"} or any(type(x) is not int or x < 0 for x in metric["action_kind_counts"].values()):
                raise RetroBotInputError("RB-020 fold action map invalid")
            if sum(metric["action_kind_counts"].values()) != metric["action_count"]:
                raise RetroBotInputError("RB-020 fold action count mismatch")
            if not isinstance(metric["timing_bands"], Mapping) or set(metric["timing_bands"]) != {"causal", "0-1s", "2-6s", ">6s"} or any(type(x) is not int or x < 0 for x in metric["timing_bands"].values()):
                raise RetroBotInputError("RB-020 fold timing bands invalid")
            if sum(metric["timing_bands"].values()) != metric["action_count"]:
                raise RetroBotInputError("RB-020 fold timing count mismatch")
            rate = metric.get("censor_rate")
            if not isinstance(rate, (int, float)) or not math.isfinite(rate) or not 0 <= rate <= 1:
                raise RetroBotInputError("RB-020 fold censor rate invalid")
            total = metric["supported_count"] + metric["censored_count"]
            expected_rate = metric["censored_count"] / total if total else 0.0
            if abs(rate - expected_rate) > 1e-12:
                raise RetroBotInputError("RB-020 fold censor rate mismatch")
            if type(metric["support_pass"]) is not bool or type(metric["coverage_pass"]) is not bool or type(metric["state_safety_pass"]) is not bool:
                raise RetroBotInputError("RB-020 fold gate flags invalid")
            if metric["support_pass"] != (metric["supported_count"] > 0) or metric["coverage_pass"] != (total > 0 and metric["supported_count"] > 0) or metric["state_safety_pass"] is not (metric.get("final_state") in {"FLAT", "ONE_BUY", "ONE_SELL", "HEDGED_1X1", "CENSORED"}):
                raise RetroBotInputError("RB-020 fold gate consistency invalid")
        if not folds["holdout"].get("sealed"):
            raise RetroBotInputError("RB-020 holdout is not sealed")
        if folds["holdout"].get("engine") != "RH-003-causal" or not isinstance(folds["holdout"].get("candidate_id"), str):
            raise RetroBotInputError("RB-020 holdout engine metadata invalid")
        if folds["holdout"].get("selection_frozen") is not True:
            raise RetroBotInputError("RB-020 holdout selection is not frozen")
        if not isinstance(folds["holdout"].get("consumption_receipt_sha256"), str) or len(folds["holdout"]["consumption_receipt_sha256"]) != 64 or any(c not in "0123456789abcdef" for c in folds["holdout"]["consumption_receipt_sha256"]):
            raise RetroBotInputError("RB-020 holdout receipt invalid")
        if any(folds[name].get("engine") != "RH-003-causal" for name in ("development", "validation", "holdout")):
            raise RetroBotInputError("RB-020 fold engine mismatch")
        if len({folds[name].get("candidate_id") for name in ("development", "validation", "holdout")}) != 1:
            raise RetroBotInputError("RB-020 fold candidate mismatch")
        seal_input = {key: folds["holdout"][key] for key in ("action_count", "action_kind_counts", "supported_count", "censored_count", "censor_rate", "support_pass", "coverage_pass", "state_safety_pass", "duplicate_action_count", "timing_bands", "final_state", "candidate_id", "engine", "consumption_receipt_sha256")}
        if folds["holdout"].get("seal_sha256") != _digest({"fold_config_sha256": value.get("fold_config_sha256"), "holdout": seal_input}):
            raise RetroBotInputError("RB-020 holdout seal mismatch")
    if "accounting" in value:
        accounting = value["accounting"]
        if not isinstance(accounting, Mapping) or accounting.get("status") not in {"valid", "censored"}:
            raise RetroBotInputError("RB-020 accounting status invalid")
    return True


def validate_source(value: object) -> dict[str, Any]:
    required = {"authorization", "report_manifest_sha256", "tick_manifest_sha256", "population", "report_aliases", "tick_aliases", "object_hashes", "alias_hashes", "allowed_fields", "retention"}
    if not isinstance(value, Mapping) or set(value) != required:
        raise RetroBotInputError("RB-020 source receipt schema is invalid")
    if value["authorization"] not in {"RB020_OWNER_AUTHORIZED_2026-08-06", "accepted by owner on 2026-08-06"} or value["population"] not in (["2025-11-01T00:00:00Z", "2026-07-31T00:00:00Z"], ["2025-11-01 00:00:00", "2026-07-31 00:00:00"]):
        raise RetroBotInputError("RB-020 source authorization mismatch")
    if value["report_aliases"] != [f"report-{i:03d}.html" for i in range(1, 10)] or not isinstance(value["tick_aliases"], list) or len(value["tick_aliases"]) != 39 or any(not str(x).startswith("XAUUSD_ticks_") for x in value["tick_aliases"]):
        raise RetroBotInputError("RB-020 source aliases mismatch")
    hashes = value["object_hashes"]
    if not isinstance(hashes, Mapping) or set(hashes) != {"report_manifest", "tick_manifest"} or any(not isinstance(x, str) or len(x) != 64 for x in hashes.values()) or hashes["report_manifest"] != REPORT_MANIFEST_SHA256 or hashes["tick_manifest"] != TICK_MANIFEST_SHA256:
        raise RetroBotInputError("RB-020 object hashes invalid")
    aliases = value["alias_hashes"]
    expected_aliases = set(value["report_aliases"]) | set(value["tick_aliases"])
    if not isinstance(aliases, Mapping) or set(aliases) != expected_aliases or any(not isinstance(x, str) or len(x) != 64 or any(c not in "0123456789abcdef" for c in x) for x in aliases.values()):
        raise RetroBotInputError("RB-020 alias object hashes invalid")
    try:
        pins = json.loads((Path(__file__).resolve().parents[2] / "docs" / "retro_bot" / "RETRO-BOT-020-object-hash-pins.json").read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise RetroBotInputError("RB-020 object hash pins unavailable") from exc
    expected_alias_hashes = {**pins["report_alias_hashes"], **pins["tick_alias_hashes"]}
    if value["object_hashes"] != {"report_manifest": pins["report_manifest_sha256"], "tick_manifest": pins["tick_manifest_sha256"]} or dict(aliases) != expected_alias_hashes:
        raise RetroBotInputError("RB-020 object hash pin mismatch")
    expected_fields = {"reports": ["positions", "open_positions"], "ticks": ["time_utc", "bid", "ask"]}
    if value["allowed_fields"] != expected_fields:
        raise RetroBotInputError("RB-020 allowed fields mismatch")
    if value["retention"] != "in-memory-aggregates-only":
        raise RetroBotInputError("RB-020 retention mismatch")
    for key in ("report_manifest_sha256", "tick_manifest_sha256"):
        if not isinstance(value[key], str) or len(value[key]) != 64 or any(c not in "0123456789abcdef" for c in value[key]):
            raise RetroBotInputError("RB-020 source digest invalid")
    if value["report_manifest_sha256"] != REPORT_MANIFEST_SHA256 or value["tick_manifest_sha256"] != TICK_MANIFEST_SHA256:
        raise RetroBotInputError("RB-020 source receipt digest mismatch")
    return {"schema_version": 1, "case_id": RB020_ID, "validated": True, "m5_firewall": M5_FIREWALL, "aggregate_sha256": _digest({"schema_version": 1, "case_id": RB020_ID, "validated": True, "m5_firewall": M5_FIREWALL})}


def walk_forward(inp: AutonomousInput, *, fold_inputs: Mapping[str, AutonomousInput] | None = None, fold_aliases: Mapping[str, list[str]] | None = None, holdout_receipt: Mapping[str, str] | None = None, used_nonces: set[str] | None = None) -> dict[str, Any]:
    """Evaluate explicitly registered, disjoint fold inputs."""
    cfg = registered_fold_config()
    if fold_inputs is None or set(fold_inputs) != {"development", "validation", "holdout"} or fold_aliases is None:
        raise RetroBotInputError("RB-020 registered fold inputs are required")
    validate_fold_config({**cfg, "development": fold_aliases.get("development"), "validation": fold_aliases.get("validation"), "holdout": fold_aliases.get("holdout"), "config_sha256": _digest({"schema_version": cfg["schema_version"], "development": fold_aliases.get("development"), "validation": fold_aliases.get("validation"), "holdout": fold_aliases.get("holdout"), "candidate_vocabulary": cfg["candidate_vocabulary"]})})
    normalized: dict[str, AutonomousInput] = {}
    for name, item in fold_inputs.items():
        if isinstance(item, FoldInput):
            normalized[name] = item.autonomous
            expected_aliases = tuple(fold_aliases[name])
            actual_aliases = tuple(item.development_aliases if name == "development" else item.validation_aliases if name == "validation" else item.holdout_aliases)
            if actual_aliases != expected_aliases:
                raise RetroBotInputError("RB-020 fold alias binding mismatch")
        elif isinstance(item, AutonomousInput):
            normalized[name] = item
            if not item.source_aliases or tuple(item.source_aliases) != tuple(fold_aliases[name]):
                raise RetroBotInputError("RB-020 fold source binding mismatch")
        else:
            raise RetroBotInputError("RB-020 fold input type is invalid")
    ordered = [normalized[name] for name in ("development", "validation", "holdout")]
    if any(a.ticks and b.ticks and a.ticks[-1].time_ns >= b.ticks[0].time_ns for a, b in zip(ordered, ordered[1:])):
        raise RetroBotInputError("RB-020 fold chronology overlaps")
    if len({item.candidate for item in ordered}) != 1:
        raise RetroBotInputError("RB-020 candidate mismatch")
    dev = replay_rh003_candidate(normalized["development"])
    val = replay_rh003_candidate(normalized["validation"])
    hold = replay_rh003_candidate(normalized["holdout"])
    result = dict(replay_autonomous(normalized["development"]))
    result = dict(result)
    result["stage"] = "walk-forward"
    result["fold_config_sha256"] = cfg["config_sha256"]
    def fold_metrics(item: Mapping[str, Any]) -> dict[str, Any]:
        total = item["supported_count"] + item["censored_count"]
        return {"action_count": item["action_count"], "action_kind_counts": item["action_kind_counts"], "supported_count": item["supported_count"], "censored_count": item["censored_count"], "censor_rate": item["censored_count"] / total if total else 0.0, "support_pass": item["supported_count"] > 0, "coverage_pass": total > 0 and item["supported_count"] > 0, "state_safety_pass": item["final_state"] in {"FLAT", "ONE_BUY", "ONE_SELL", "HEDGED_1X1", "CENSORED"}, "duplicate_action_count": 0, "timing_bands": {"causal": item["action_count"], "0-1s": 0, "2-6s": 0, ">6s": 0}, "final_state": item["final_state"], "candidate_id": item["candidate_id"], "engine": item["engine"]}
    holdout_metrics = fold_metrics(hold)
    if holdout_receipt is None:
        raise RetroBotInputError("RB-020 holdout consumption receipt is required")
    if used_nonces is None:
        raise RetroBotInputError("RB-020 holdout nonce ledger is required")
    verify_holdout_receipt(holdout_receipt, holdout=normalized["holdout"], used_nonces=used_nonces)
    used_nonces.add(holdout_receipt["nonce"])
    holdout_payload = {**holdout_metrics, "consumption_receipt_sha256": holdout_receipt["receipt_sha256"]}
    holdout_seal = _digest({"fold_config_sha256": cfg["config_sha256"], "holdout": holdout_payload})
    result["folds"] = {"development": fold_metrics(dev), "validation": fold_metrics(val), "holdout": {**holdout_payload, "sealed": True, "seal_sha256": holdout_seal, "selection_frozen": True}}
    result["consumed_nonces"] = sorted(used_nonces)
    result.pop("aggregate_sha256", None)
    result["aggregate_sha256"] = _digest(result)
    return result


def paper_account(inp: AutonomousInput, *, lifecycle: Any | None = None, fee_per_unit: str = "0", slippage_points: str = "0") -> dict[str, Any]:
    """Conservative accounting summary independent of policy decisions."""
    result = replay_autonomous(inp)
    result = dict(result)
    result["stage"] = "paper-account"
    opened = result["action_counts"]["OPEN_BUY"] + result["action_counts"]["OPEN_SELL"]
    closed = result["action_counts"]["CLOSE_BUY"] + result["action_counts"]["CLOSE_SELL"]
    lifecycle = lifecycle if lifecycle is not None else [{"kind": "OPEN" if d.action.startswith("OPEN") else "CLOSE", "side": "BUY" if d.action.endswith("BUY") else "SELL", "quantity": "1.00000000", "time_ns": d.time_ns} for d in replay_decisions(inp) if d.action != "NONE"]
    quotes = [{"time_ns": t.time_ns, "bid": f"{t.bid:.8f}", "ask": f"{t.ask:.8f}"} for t in inp.ticks]
    accounting = account_lifecycle_records(lifecycle, quotes, fee_per_unit=fee_per_unit, slippage_points=slippage_points)
    result["accounting"] = {"scenario": "synthetic-cost", "fee_per_unit_fixed8": f"{Decimal(fee_per_unit):.8f}", "slippage_points_fixed8": f"{Decimal(slippage_points):.8f}", "cash_fixed8": accounting["cash_fixed8"], "conserved": accounting["conserved"], "mark_status": accounting["mark_status"], "status": accounting["status"], "opened_actions": opened, "closed_actions": closed, "remaining_units_fixed8": f"{Decimal(accounting['buy_remaining_fixed8']) + Decimal(accounting['sell_remaining_fixed8']):.8f}", "invalid_count": accounting["invalid_count"], "missing_quote_count": accounting["missing_quote_count"], "scenario_fingerprint": accounting["scenario_fingerprint"]}
    result.pop("aggregate_sha256", None)
    result["aggregate_sha256"] = _digest(result)
    return result
