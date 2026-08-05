"""RB-013 walk-forward aggregate evaluator over locked candidate rows."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Iterable, Mapping, Sequence

import pandas as pd

from .retro_bot import RetroBotInputError
from .retro_bot_005 import PolicyAction, StateSnapshot, apply_policy_action
from .retro_bot_007 import CandidatePolicy, OracleLabel as CloseOracleLabel, evaluate_candidate, match_oracle_sequence
from .retro_bot_008 import RehedgePolicy, evaluate_rehedge

RB013_ID = "RB-013"
RB008_CONFIG_SHA256 = "26fec4baa2b8e2680cc17afaad299bbbb00afba32810865ac60bf28eb2e49ebf"
REPORT_MANIFEST_SHA256 = "88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30"
TICK_MANIFEST_SHA256 = "a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c"
M5_FIREWALL = "M5_FIREWALL_ATTESTATION_V1"
FOLDS = ("development", "validation", "holdout")
CLOCKS = ("utc_plus_2", "utc_plus_3", "eu_dst_2025_2026")
BOOTSTRAPS = ("left_censored", "fixed_warmup_seed")
POLICIES = ("always_hold", "first_legal_match")
CANDIDATES = tuple(f"{close}__{rehedge}" for close in POLICIES for rehedge in POLICIES)
STATUSES = ("package-ready", "tie_inconclusive", "inconclusive", "no-supported-candidate")
REPORT_ALIASES = tuple(f"report-{index:03d}.html" for index in range(1, 10))
MAX_COUNT = 1_000_000_000
LABEL_TIMING_BANDS = {"exact", "0-1s", "2-6s", "7-30s", ">30s"}


def _rule_signature(rule: object) -> tuple[object, ...]:
    try:
        return (rule.rule_id, tuple((clause.feature, clause.operator, clause.lower, clause.upper) for clause in rule.clauses), rule.candidate_kind)
    except AttributeError as error:
        raise RetroBotInputError("RB-013 policy fingerprint is invalid") from error


def _policy_signature(policy: object) -> tuple[object, ...]:
    if not isinstance(policy, (CandidatePolicy, RehedgePolicy)):
        raise RetroBotInputError("RB-013 policy fingerprint is invalid")
    return (policy.policy_id, tuple(_rule_signature(rule) for rule in policy.rules))


def _canonical_close_policy(policy_id: str) -> CandidatePolicy:
    if policy_id == "always_hold":
        return CandidatePolicy("always_hold")
    from .retro_bot_006 import RuleClause, TriggerRule
    return CandidatePolicy("first_legal_match", (
        TriggerRule("close_buy", (RuleClause("state", "always"),), "CLOSE_BUY"),
        TriggerRule("close_sell", (RuleClause("state", "always"),), "CLOSE_SELL"),
    ))


def _canonical_rehedge_policy(policy_id: str) -> RehedgePolicy:
    if policy_id == "always_hold":
        return RehedgePolicy("always_hold")
    from .retro_bot_006 import RuleClause, TriggerRule
    return RehedgePolicy("first_legal_match", (
        TriggerRule("open_buy", (RuleClause("state", "always"),), "OPEN_BUY"),
        TriggerRule("open_sell", (RuleClause("state", "always"),), "OPEN_SELL"),
    ))


FROZEN_POLICY_SIGNATURES = {
    "always_hold": _policy_signature(_canonical_close_policy("always_hold")),
    "first_legal_match": _policy_signature(_canonical_close_policy("first_legal_match")),
}
FROZEN_REHEDGE_SIGNATURES = {
    "always_hold": _policy_signature(_canonical_rehedge_policy("always_hold")),
    "first_legal_match": _policy_signature(_canonical_rehedge_policy("first_legal_match")),
}


def validate_frozen_candidate(candidate_id: str, close_policy: CandidatePolicy, rehedge_policy: RehedgePolicy) -> None:
    """Reject a registered id paired with an unregistered rule tuple."""
    validate_candidate_manifest(CANDIDATES)
    if candidate_id not in CANDIDATES or candidate_id != f"{close_policy.policy_id}__{rehedge_policy.policy_id}":
        raise RetroBotInputError("RB-013 candidate manifest is not frozen")
    try:
        close_policy.validate()
        rehedge_policy.validate()
    except (RetroBotInputError, TypeError, AttributeError) as error:
        raise RetroBotInputError("RB-013 candidate manifest is not frozen") from error
    if _policy_signature(close_policy) != FROZEN_POLICY_SIGNATURES[close_policy.policy_id] or _policy_signature(rehedge_policy) != FROZEN_REHEDGE_SIGNATURES[rehedge_policy.policy_id]:
        raise RetroBotInputError("RB-013 candidate policy fingerprint is not frozen")


def expanding_prefix(fold: str, report_alias: str | None = None) -> tuple[str, ...]:
    prefixes = {"development": ("report-001.html", "report-002.html", "report-003.html", "report-004.html", "report-005.html"), "validation": ("report-001.html", "report-002.html", "report-003.html", "report-004.html", "report-005.html"), "holdout": ("report-001.html", "report-002.html", "report-003.html", "report-004.html", "report-005.html", "report-006.html", "report-007.html")}
    if fold not in prefixes:
        raise RetroBotInputError("RB-013 fold is invalid")
    if report_alias is None:
        return prefixes[fold]
    aliases = tuple(f"report-{index:03d}.html" for index in range(1, 10))
    if report_alias not in aliases:
        raise RetroBotInputError("RB-013 report alias is invalid")
    index = aliases.index(report_alias)
    allowed = {"development": range(0, 5), "validation": range(5, 7), "holdout": range(7, 9)}[fold]
    if index not in allowed:
        raise RetroBotInputError("RB-013 report does not belong to fold")
    return aliases[:index]


def validate_candidate_manifest(manifest: tuple[str, ...]) -> tuple[str, ...]:
    if manifest != CANDIDATES:
        raise RetroBotInputError("RB-013 candidate manifest is not frozen")
    return manifest


def blind_structural_intake(*, manifest: tuple[str, ...], source_digests: Mapping[str, str], rows: Iterable[WalkForwardRow], config_sha256: str = RB008_CONFIG_SHA256, firewall: str = M5_FIREWALL) -> dict[str, object]:
    """Validate only structure before any behavioral row is opened."""
    validate_candidate_manifest(manifest)
    if config_sha256 != RB008_CONFIG_SHA256 or firewall != M5_FIREWALL or not isinstance(source_digests, Mapping) or tuple(source_digests.keys()) != ("report_manifest_sha256", "tick_manifest_sha256") or source_digests != {"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256}:
        raise RetroBotInputError("RB-013 source receipt mismatch")
    try:
        materialized = tuple(rows)
    except TypeError as error:
        raise RetroBotInputError("RB-013 structural rows are invalid") from error
    if len(materialized) != len(FOLDS) * len(CLOCKS) * len(BOOTSTRAPS) * len(CANDIDATES):
        raise RetroBotInputError("RB-013 structural matrix count mismatch")
    for row in materialized:
        if not isinstance(row, WalkForwardRow) or row.fold not in FOLDS or row.clock_id not in CLOCKS or row.bootstrap_id not in BOOTSTRAPS or row.candidate_id not in CANDIDATES:
            raise RetroBotInputError("RB-013 structural row identity mismatch")
    keys = {(row.fold, row.clock_id, row.bootstrap_id, row.candidate_id) for row in materialized}
    expected = {(fold, clock, bootstrap, candidate) for fold in FOLDS for clock in CLOCKS for bootstrap in BOOTSTRAPS for candidate in CANDIDATES}
    if keys != expected:
        raise RetroBotInputError("RB-013 structural matrix mismatch")
    return {"schema_version": 1, "source_verified": True, "manifest_verified": True, "matrix_complete": True, "m5_firewall": M5_FIREWALL, "behavior_opened": False}


ORACLE_FIELDS = ("exact", "0-1s", "2-6s", "7-30s", ">30s", "unmatched", "direction_mismatch", "duplicate_label", "unmatched_labels")


def _validate_oracle_labels(labels: Iterable[Mapping[str, object]], *, require_times: bool = False) -> tuple[Mapping[str, object], ...]:
    try:
        materialized = tuple(labels)
    except TypeError as error:
        raise RetroBotInputError("RB-013 oracle labels are invalid") from error
    allowed_keys = {("cycle_id", "action_kind", "timing_band"), ("cycle_id", "label_time", "action_kind", "timing_band")}
    if any(not isinstance(label, Mapping) or tuple(label.keys()) not in allowed_keys or (require_times and "label_time" not in label) or not isinstance(label["cycle_id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", label["cycle_id"]) or label["action_kind"] not in {"CLOSE_BUY", "CLOSE_SELL", "OPEN_BUY", "OPEN_SELL"} or label["timing_band"] not in LABEL_TIMING_BANDS for label in materialized):
        raise RetroBotInputError("RB-013 oracle label schema is invalid")
    if require_times:
        for label in materialized:
            try:
                timestamp = pd.Timestamp(label["label_time"])
                if pd.isna(timestamp):
                    raise ValueError
            except (TypeError, ValueError, pd.errors.OutOfBoundsDatetime) as error:
                raise RetroBotInputError("RB-013 oracle label time is invalid") from error
    return materialized


def build_oracle_diagnostic(*, labels: Iterable[Mapping[str, object]], action_counts: Mapping[str, int], actions: Iterable[tuple[str, object, str]] | None = None) -> dict[str, object]:
    """Keep oracle comparison in a separate aggregate namespace."""
    oracle_keys = set(ORACLE_FIELDS)
    if not isinstance(action_counts, Mapping) or tuple(action_counts.keys()) != ORACLE_FIELDS or any(type(value) is not int or value < 0 or value > MAX_COUNT for value in action_counts.values()):
        raise RetroBotInputError("RB-013 oracle action counts are invalid")
    labels = _validate_oracle_labels(labels, require_times=actions is not None)
    if actions is not None:
        computed = _match_oracle_actions(actions, labels)
        if dict(action_counts) != computed:
            raise RetroBotInputError("RB-013 oracle counts do not match one-to-one verifier")
    payload = {"schema_version": 1, "oracle_case": RB013_ID, "label_count": len(labels), "action_counts": {key: int(action_counts.get(key, 0)) for key in ("exact", "0-1s", "2-6s", "7-30s", ">30s", "unmatched", "direction_mismatch", "duplicate_label", "unmatched_labels")}, "source_manifest_digests": {"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256}, "m5_firewall": M5_FIREWALL, "oracle_only": True}
    payload["aggregate_sha256"] = hashlib.sha256(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode()).hexdigest()
    return payload


def _match_oracle_actions(actions: Iterable[tuple[str, object, str]], labels: Sequence[Mapping[str, object]]) -> dict[str, int]:
    labels = _validate_oracle_labels(labels, require_times=True)
    typed: list[CloseOracleLabel] = []
    for label in labels:
        typed.append(CloseOracleLabel(label["cycle_id"], label["label_time"], label["action_kind"]))
    return match_oracle_sequence(tuple(actions), tuple(typed))


def validate_oracle_diagnostic(payload: Mapping[str, object]) -> None:
    expected_order = ("schema_version", "oracle_case", "label_count", "action_counts", "source_manifest_digests", "m5_firewall", "oracle_only", "aggregate_sha256")
    if not isinstance(payload, Mapping) or tuple(payload.keys()) != expected_order or payload.get("schema_version") != 1 or payload.get("oracle_case") != RB013_ID or payload.get("m5_firewall") != M5_FIREWALL or payload.get("oracle_only") is not True:
        raise RetroBotInputError("RB-013 oracle aggregate schema/firewall mismatch")
    source_digests = payload.get("source_manifest_digests")
    if type(payload.get("label_count")) is not int or payload["label_count"] < 0 or payload["label_count"] > MAX_COUNT or not isinstance(source_digests, Mapping) or tuple(source_digests.keys()) != ("report_manifest_sha256", "tick_manifest_sha256") or source_digests != {"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256}:
        raise RetroBotInputError("RB-013 oracle aggregate provenance mismatch")
    counts = payload.get("action_counts")
    if not isinstance(counts, Mapping) or tuple(counts.keys()) != ORACLE_FIELDS or any(type(value) is not int or value < 0 or value > MAX_COUNT for value in counts.values()):
        raise RetroBotInputError("RB-013 oracle aggregate counts invalid")
    digest = hashlib.sha256(json.dumps({key: value for key, value in payload.items() if key != "aggregate_sha256"}, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode()).hexdigest()
    if payload.get("aggregate_sha256") != digest:
        raise RetroBotInputError("RB-013 oracle aggregate digest mismatch")


@dataclass(frozen=True)
class WalkForwardRow:
    fold: str
    clock_id: str
    bootstrap_id: str
    candidate_id: str
    eligible_close: int
    close_hold: int
    close_action: int
    close_censor: int
    eligible_rehedge: int
    rehedge_hold: int
    rehedge_action: int
    rehedge_censor: int
    safety_pass: bool
    support_pass: bool
    report_unit_count: int = 2
    close_buy_eligible: int = 2
    close_sell_eligible: int = 2
    close_buy_action: int = 0
    close_sell_action: int = 0
    rehedge_buy_eligible: int = 2
    rehedge_sell_eligible: int = 2
    rehedge_buy_action: int = 0
    rehedge_sell_action: int = 0
    close_invalid_transition: int = 0
    close_feature_missing: int = 0
    close_duplicate: int = 0
    close_noneligible: int = 0
    rehedge_invalid_transition: int = 0
    rehedge_feature_missing: int = 0
    rehedge_duplicate: int = 0
    rehedge_noneligible: int = 0

    def __post_init__(self) -> None:
        # Preserve the pre-RB-013 constructor while making direction counts explicit.
        if self.close_action and self.close_buy_action == 0 and self.close_sell_action == 0:
            object.__setattr__(self, "close_buy_action", self.close_action)
        if self.rehedge_action and self.rehedge_buy_action == 0 and self.rehedge_sell_action == 0:
            object.__setattr__(self, "rehedge_buy_action", self.rehedge_action)

    def validate(self) -> None:
        if self.fold not in FOLDS or self.clock_id not in CLOCKS or self.bootstrap_id not in BOOTSTRAPS or self.candidate_id not in CANDIDATES:
            raise RetroBotInputError("RB-013 row identity is invalid")
        counts = (self.eligible_close, self.close_hold, self.close_action, self.close_censor, self.eligible_rehedge, self.rehedge_hold, self.rehedge_action, self.rehedge_censor, self.report_unit_count, self.close_buy_eligible, self.close_sell_eligible, self.close_buy_action, self.close_sell_action, self.rehedge_buy_eligible, self.rehedge_sell_eligible, self.rehedge_buy_action, self.rehedge_sell_action, self.close_invalid_transition, self.close_feature_missing, self.close_duplicate, self.close_noneligible, self.rehedge_invalid_transition, self.rehedge_feature_missing, self.rehedge_duplicate, self.rehedge_noneligible)
        if any(type(value) is not int or value < 0 or value > 1_000_000_000 for value in counts) or self.close_hold + self.close_action + self.close_censor != self.eligible_close or self.rehedge_hold + self.rehedge_action + self.rehedge_censor != self.eligible_rehedge:
            raise RetroBotInputError("RB-013 row conservation failed")
        if self.close_buy_action + self.close_sell_action != self.close_action or self.rehedge_buy_action + self.rehedge_sell_action != self.rehedge_action:
            raise RetroBotInputError("RB-013 directional accounting failed")
        if self.close_invalid_transition + self.close_feature_missing + self.close_duplicate > self.close_censor or self.rehedge_invalid_transition + self.rehedge_feature_missing + self.rehedge_duplicate > self.rehedge_censor:
            raise RetroBotInputError("RB-013 error accounting failed")
        if type(self.safety_pass) is not bool or type(self.support_pass) is not bool:
            raise RetroBotInputError("RB-013 row gates are invalid")


@dataclass(frozen=True)
class DecisionRecord:
    fold: str
    decision_time_ns: int
    future_read: bool = False
    oracle_used: bool = False
    report_alias: str | None = None


def validate_causal_prefix(records: Iterable[DecisionRecord], fold: str) -> tuple[DecisionRecord, ...]:
    if fold not in FOLDS:
        raise RetroBotInputError("RB-013 fold is invalid")
    materialized = tuple(records)
    previous = None
    for record in materialized:
        if not isinstance(record, DecisionRecord) or record.fold != fold or type(record.decision_time_ns) is not int or record.decision_time_ns < 0 or type(record.future_read) is not bool or type(record.oracle_used) is not bool or record.future_read or record.oracle_used:
            raise RetroBotInputError("RB-013 causal prefix violation")
        if record.report_alias is not None and (record.report_alias not in REPORT_ALIASES or int(record.report_alias[7:10]) not in {"development": range(1, 6), "validation": range(6, 8), "holdout": range(8, 10)}[fold]):
            raise RetroBotInputError("RB-013 causal report alias violation")
        if previous is not None and record.decision_time_ns <= previous:
            raise RetroBotInputError("RB-013 decision chronology violation")
        previous = record.decision_time_ns
    return materialized


def run_causal_window(*, fold: str, clock_id: str, bootstrap_id: str, candidate_id: str, state: StateSnapshot, close_policy: CandidatePolicy, rehedge_policy: RehedgePolicy, close_snapshots: tuple[object, ...], rehedge_snapshots: tuple[object, ...]) -> WalkForwardRow:
    """Compose RB-009, RB-011, and RB-012 over validated causal snapshots."""
    if not isinstance(state, StateSnapshot) or not isinstance(close_policy, CandidatePolicy) or not isinstance(rehedge_policy, RehedgePolicy) or fold not in FOLDS or clock_id not in CLOCKS or bootstrap_id not in BOOTSTRAPS:
        raise RetroBotInputError("RB-013 window identity is invalid")
    validate_frozen_candidate(candidate_id, close_policy, rehedge_policy)
    try:
        close_items = tuple(close_snapshots)
        rehedge_items = tuple(rehedge_snapshots)
    except TypeError as error:
        raise RetroBotInputError("RB-013 snapshot sequence is invalid") from error
    close_counts = {"hold": 0, "action": 0, "censored": 0}
    close_errors = {"invalid_transition": 0, "feature_missing": 0, "duplicate": 0, "noneligible": 0}
    close_directional = {"CLOSE_BUY": 0, "CLOSE_SELL": 0}
    current = state
    close_accepted = False
    previous_time = None
    for snapshot in close_items:
        if not hasattr(snapshot, "decision_time"):
            close_counts["censored"] += 1
            close_errors["invalid_transition"] += 1
            break
        try:
            decision_time = pd.Timestamp(snapshot.decision_time)
            decision_time = decision_time.tz_localize("UTC") if decision_time.tzinfo is None else decision_time.tz_convert("UTC")
        except (AttributeError, TypeError, ValueError, pd.errors.OutOfBoundsDatetime):
            close_counts["censored"] += 1
            close_errors["invalid_transition"] += 1
            break
        if previous_time is not None and decision_time.floor("s") <= previous_time.floor("s"):
            close_counts["censored"] += 1
            close_errors["duplicate"] += 1
            break
        previous_time = decision_time
        try:
            decision = evaluate_candidate(current, snapshot, close_policy, expected_epoch=current.epoch)
        except (RetroBotInputError, AttributeError, TypeError, ValueError):
            decision = None
        if decision is None:
            close_counts["censored"] += 1
            close_errors["invalid_transition"] += 1
            break
        if decision.outcome == "noneligible":
            close_errors["noneligible"] += 1
            break
        if decision.outcome in {"feature_missing", "invalid_transition", "censored"}:
            close_counts["censored"] += 1
            close_errors["feature_missing" if decision.outcome == "feature_missing" else "invalid_transition"] += 1
            break
        close_counts["action" if decision.outcome == "candidate_action" else "hold"] += 1
        if decision.outcome == "candidate_action":
            current, result = apply_policy_action(current, PolicyAction(decision.action_kind, decision_time, current.epoch))
            if result.status != "accepted":
                close_counts["action"] -= 1
                close_counts["censored"] += 1
                close_errors["invalid_transition"] += 1
            else:
                close_accepted = True
                close_directional[decision.action_kind] += 1
            break
    rehedge_counts = {"hold": 0, "action": 0, "censored": 0}
    rehedge_errors = {"invalid_transition": 0, "feature_missing": 0, "duplicate": 0, "noneligible": 0}
    rehedge_directional = {"OPEN_BUY": 0, "OPEN_SELL": 0}
    rehedge_previous = previous_time
    if close_accepted and not rehedge_items:
        rehedge_counts["censored"] = 1
        rehedge_errors["invalid_transition"] = 1
    for snapshot in rehedge_items if close_accepted else ():
        if not hasattr(snapshot, "decision_time"):
            rehedge_counts["censored"] += 1
            rehedge_errors["invalid_transition"] += 1
            break
        try:
            snapshot_time = pd.Timestamp(snapshot.decision_time)
            snapshot_time = snapshot_time.tz_localize("UTC") if snapshot_time.tzinfo is None else snapshot_time.tz_convert("UTC")
        except (AttributeError, TypeError, ValueError, pd.errors.OutOfBoundsDatetime):
            rehedge_counts["censored"] += 1
            rehedge_errors["invalid_transition"] += 1
            break
        if rehedge_previous is not None and snapshot_time.floor("s") <= rehedge_previous.floor("s"):
            rehedge_counts["censored"] += 1
            rehedge_errors["duplicate"] += 1
            break
        rehedge_previous = snapshot_time
        try:
            decision = evaluate_rehedge(current, snapshot, rehedge_policy, expected_epoch=current.epoch)
        except (RetroBotInputError, AttributeError, TypeError, ValueError):
            decision = None
        if decision is None:
            rehedge_counts["censored"] += 1
            rehedge_errors["invalid_transition"] += 1
            break
        if decision.outcome == "noneligible":
            rehedge_errors["noneligible"] += 1
            break
        if decision.outcome not in {"hold", "action"}:
            rehedge_counts["censored"] += 1
            rehedge_errors["feature_missing" if decision.outcome == "feature_missing" else "invalid_transition"] += 1
            break
        rehedge_counts[decision.outcome] += 1
        if decision.outcome == "action":
            current, result = apply_policy_action(current, PolicyAction(decision.action_kind, snapshot.decision_time, current.epoch))
            if result.status != "accepted":
                rehedge_counts["action"] -= 1
                rehedge_counts["censored"] += 1
                rehedge_errors["invalid_transition"] += 1
            else:
                rehedge_directional[decision.action_kind] += 1
            break
    close_side = "ONE_SELL" if close_directional["CLOSE_BUY"] else "ONE_BUY" if close_directional["CLOSE_SELL"] else None
    rehedge_buy = 1 if close_side == "ONE_BUY" else 0
    rehedge_sell = 1 if close_side == "ONE_SELL" else 0
    safe = close_counts["censored"] == 0 and rehedge_counts["censored"] == 0 and not any(close_errors.values()) and not any(rehedge_errors.values())
    support = safe and close_counts["action"] > 0 and rehedge_counts["action"] > 0 and rehedge_buy + rehedge_sell > 0
    return WalkForwardRow(
        fold, clock_id, bootstrap_id, candidate_id,
        sum(close_counts.values()), close_counts["hold"], close_counts["action"], close_counts["censored"],
        sum(rehedge_counts.values()), rehedge_counts["hold"], rehedge_counts["action"], rehedge_counts["censored"], safe, support,
        1, 1 if close_side == "ONE_BUY" else 0, 1 if close_side == "ONE_SELL" else 0,
        close_directional["CLOSE_BUY"], close_directional["CLOSE_SELL"], rehedge_buy, rehedge_sell,
        rehedge_directional["OPEN_BUY"], rehedge_directional["OPEN_SELL"],
        close_errors["invalid_transition"], close_errors["feature_missing"], close_errors["duplicate"], close_errors["noneligible"],
        rehedge_errors["invalid_transition"], rehedge_errors["feature_missing"], rehedge_errors["duplicate"], rehedge_errors["noneligible"],
    )


def evaluate_walk_forward(rows: Iterable[WalkForwardRow], *, case_id: str = "synthetic") -> dict:
    materialized = tuple(rows)
    for row in materialized:
        if not isinstance(row, WalkForwardRow):
            raise RetroBotInputError("RB-013 row schema is invalid")
        row.validate()
    expected_keys = {(fold, clock, bootstrap, candidate) for fold in FOLDS for clock in CLOCKS for bootstrap in BOOTSTRAPS for candidate in CANDIDATES}
    actual_keys = {(row.fold, row.clock_id, row.bootstrap_id, row.candidate_id) for row in materialized}
    if actual_keys != expected_keys:
        raise RetroBotInputError("RB-013 complete matrix is required")
    support = {candidate: all(_row_support(row) for row in materialized if row.candidate_id == candidate) for candidate in CANDIDATES}
    safety = {candidate: all(row.safety_pass for row in materialized if row.candidate_id == candidate) for candidate in CANDIDATES}
    support_available = {candidate: all(_row_support(row) for row in materialized if row.candidate_id == candidate) for candidate in CANDIDATES}
    passing = tuple(candidate for candidate in CANDIDATES if support[candidate])
    if len(passing) == 1:
        status = "package-ready"
    elif len(passing) > 1:
        status = "tie_inconclusive"
    elif not any(safety.values()):
        status = "no-supported-candidate"
    elif not any(safety[candidate] and support_available[candidate] for candidate in CANDIDATES):
        status = "inconclusive"
    elif any(safety.values()):
        status = "no-supported-candidate"
    else:
        status = "inconclusive"
    payload = {
        "schema_version": 1, "case_id": case_id, "retro_case": RB013_ID,
        "rb008_config_sha256": RB008_CONFIG_SHA256,
        "source_manifest_digests": {"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256},
        "candidate_ids": list(CANDIDATES), "row_count": len(materialized),
        "rows": [_row_dict(row) for row in sorted(materialized, key=lambda item: (FOLDS.index(item.fold), CLOCKS.index(item.clock_id), BOOTSTRAPS.index(item.bootstrap_id), CANDIDATES.index(item.candidate_id)))],
        "candidate_gate_status": {candidate: "pass" if support[candidate] else "fail" for candidate in CANDIDATES},
        "terminal_status": status, "m5_firewall": M5_FIREWALL, "aggregate_sha256": "TO_BE_FILLED",
    }
    payload["aggregate_sha256"] = hashlib.sha256(json.dumps({key: value for key, value in payload.items() if key != "aggregate_sha256"}, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode()).hexdigest()
    validate_walk_forward_aggregate(payload)
    return payload


ROW_FIELDS = ("fold", "clock_id", "bootstrap_id", "candidate_id", "eligible_close", "close_hold", "close_action", "close_censor", "eligible_rehedge", "rehedge_hold", "rehedge_action", "rehedge_censor", "safety_pass", "support_pass", "report_unit_count", "close_buy_eligible", "close_sell_eligible", "close_buy_action", "close_sell_action", "rehedge_buy_eligible", "rehedge_sell_eligible", "rehedge_buy_action", "rehedge_sell_action", "close_invalid_transition", "close_feature_missing", "close_duplicate", "close_noneligible", "rehedge_invalid_transition", "rehedge_feature_missing", "rehedge_duplicate", "rehedge_noneligible")


def _row_dict(row: WalkForwardRow) -> dict[str, object]:
    return {field: getattr(row, field) for field in ROW_FIELDS}


def _row_support(row: WalkForwardRow) -> bool:
    return (
        row.safety_pass and row.support_pass and row.report_unit_count >= 2
        and row.close_buy_eligible >= 2 and row.close_sell_eligible >= 2
        and row.rehedge_buy_eligible >= 2 and row.rehedge_sell_eligible >= 2
        and row.close_buy_action > 0 and row.close_sell_action > 0
        and row.rehedge_buy_action > 0 and row.rehedge_sell_action > 0
        and row.close_invalid_transition == row.close_feature_missing == row.close_duplicate == 0
        and row.rehedge_invalid_transition == row.rehedge_feature_missing == row.rehedge_duplicate == 0
    )


def validate_walk_forward_aggregate(payload: Mapping[str, object]) -> None:
    expected_order = ("schema_version", "case_id", "retro_case", "rb008_config_sha256", "source_manifest_digests", "candidate_ids", "row_count", "rows", "candidate_gate_status", "terminal_status", "m5_firewall", "aggregate_sha256")
    expected = set(expected_order)
    if not isinstance(payload, Mapping) or tuple(payload.keys()) != expected_order or set(payload) != expected or payload.get("schema_version") != 1 or payload.get("retro_case") != RB013_ID or payload.get("m5_firewall") != M5_FIREWALL:
        raise RetroBotInputError("RB-013 aggregate schema/firewall mismatch")
    source_digests = payload.get("source_manifest_digests")
    if not isinstance(payload.get("case_id"), str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", payload["case_id"]) or payload.get("rb008_config_sha256") != RB008_CONFIG_SHA256 or source_digests != {"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256} or tuple(source_digests.keys()) != ("report_manifest_sha256", "tick_manifest_sha256") or payload.get("candidate_ids") != list(CANDIDATES) or payload.get("terminal_status") not in STATUSES:
        raise RetroBotInputError("RB-013 aggregate provenance/status mismatch")
    if type(payload.get("row_count")) is not int or payload["row_count"] != len(FOLDS) * len(CLOCKS) * len(BOOTSTRAPS) * len(CANDIDATES):
        raise RetroBotInputError("RB-013 matrix count mismatch")
    if not isinstance(payload.get("rows"), list) or len(payload["rows"]) != payload["row_count"]:
        raise RetroBotInputError("RB-013 rows are missing")
    row_field_order = ROW_FIELDS
    row_fields = set(row_field_order)
    parsed_rows: list[WalkForwardRow] = []
    for raw in payload["rows"]:
        if not isinstance(raw, Mapping) or tuple(raw.keys()) != row_field_order or set(raw) != row_fields:
            raise RetroBotInputError("RB-013 retained row schema is invalid")
        row = WalkForwardRow(**raw)
        row.validate()
        parsed_rows.append(row)
    keys = {(row.fold, row.clock_id, row.bootstrap_id, row.candidate_id) for row in parsed_rows}
    expected_keys = {(fold, clock, bootstrap, candidate) for fold in FOLDS for clock in CLOCKS for bootstrap in BOOTSTRAPS for candidate in CANDIDATES}
    if keys != expected_keys:
        raise RetroBotInputError("RB-013 retained matrix is incomplete or duplicated")
    expected_row_order = sorted(expected_keys, key=lambda key: (FOLDS.index(key[0]), CLOCKS.index(key[1]), BOOTSTRAPS.index(key[2]), CANDIDATES.index(key[3])))
    actual_row_order = [(row.fold, row.clock_id, row.bootstrap_id, row.candidate_id) for row in parsed_rows]
    if actual_row_order != expected_row_order:
        raise RetroBotInputError("RB-013 retained matrix order is not canonical")
    recomputed = {candidate: all(_row_support(row) for row in parsed_rows if row.candidate_id == candidate) for candidate in CANDIDATES}
    expected_gates = {candidate: "pass" if recomputed[candidate] else "fail" for candidate in CANDIDATES}
    if not isinstance(payload.get("candidate_gate_status"), Mapping) or tuple(payload["candidate_gate_status"].keys()) != CANDIDATES or payload["candidate_gate_status"] != expected_gates:
        raise RetroBotInputError("RB-013 gate status tampering detected")
    passing = tuple(candidate for candidate in CANDIDATES if recomputed[candidate])
    safety = {candidate: all(row.safety_pass for row in parsed_rows if row.candidate_id == candidate) for candidate in CANDIDATES}
    support_available = {candidate: all(_row_support(row) for row in parsed_rows if row.candidate_id == candidate) for candidate in CANDIDATES}
    expected_status = "package-ready" if len(passing) == 1 else "tie_inconclusive" if len(passing) > 1 else "no-supported-candidate" if not any(safety.values()) else "inconclusive" if not any(safety[candidate] and support_available[candidate] for candidate in CANDIDATES) else "no-supported-candidate"
    if payload["terminal_status"] != expected_status:
        raise RetroBotInputError("RB-013 terminal status tampering detected")
    gates = payload.get("candidate_gate_status")
    if not isinstance(gates, Mapping) or set(gates) != set(CANDIDATES) or any(value not in {"pass", "fail"} for value in gates.values()):
        raise RetroBotInputError("RB-013 candidate gate schema invalid")
    expected_digest = hashlib.sha256(json.dumps({key: value for key, value in payload.items() if key != "aggregate_sha256"}, ensure_ascii=True, separators=(",", ":"), sort_keys=False).encode()).hexdigest()
    if payload.get("aggregate_sha256") != expected_digest:
        raise RetroBotInputError("RB-013 aggregate digest mismatch")


def frozen_candidate_policies(candidate_id: str) -> tuple[CandidatePolicy, RehedgePolicy]:
    """Return fresh immutable policy objects for one registered candidate."""
    if candidate_id not in CANDIDATES:
        raise RetroBotInputError("RB-013 candidate id is invalid")
    close_id, rehedge_id = candidate_id.split("__", 1)
    return _canonical_close_policy(close_id), _canonical_rehedge_policy(rehedge_id)


def verify_oracle_diagnostic(*, payload: Mapping[str, object], actions: Iterable[tuple[str, object, str]], labels: Iterable[CloseOracleLabel]) -> None:
    """Recompute RB-011 earliest-unused matching without touching policy state."""
    validate_oracle_diagnostic(payload)
    typed_labels = tuple(labels)
    if any(not isinstance(label, CloseOracleLabel) for label in typed_labels):
        raise RetroBotInputError("RB-013 oracle labels are invalid")
    counts = match_oracle_sequence(tuple(actions), typed_labels)
    if payload["action_counts"] != counts or payload["label_count"] != len(typed_labels):
        raise RetroBotInputError("RB-013 oracle verifier mismatch")


def run_registered_walk_forward(*, records: Iterable[Mapping[str, object]], source_digests: Mapping[str, str], config_sha256: str = RB008_CONFIG_SHA256, firewall: str = M5_FIREWALL, case_id: str = "synthetic") -> dict:
    """Run the locked fold matrix over validated in-memory records.

    The API deliberately accepts records rather than paths. Callers perform
    source hashing/parsing outside this module; this layer enforces the locked
    receipt, aliases, fold prefixes, candidate freeze, and aggregate-only
    retention boundary.
    """
    if config_sha256 != RB008_CONFIG_SHA256 or firewall != M5_FIREWALL or source_digests != {"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256} or tuple(source_digests.keys()) != ("report_manifest_sha256", "tick_manifest_sha256"):
        raise RetroBotInputError("RB-013 source receipt mismatch")
    if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", case_id):
        raise RetroBotInputError("RB-013 case id is invalid")
    try:
        materialized = tuple(records)
    except TypeError as error:
        raise RetroBotInputError("RB-013 source population is invalid") from error
    if not materialized:
        raise RetroBotInputError("RB-013 source population is empty")
    grouped: dict[tuple[str, str, str, str], list[WalkForwardRow]] = {}
    grouped_aliases: dict[tuple[str, str, str, str], set[str]] = {}
    seen_source_units: set[tuple[str, str, str, str, str]] = set()
    for record in materialized:
        if not isinstance(record, Mapping):
            raise RetroBotInputError("RB-013 source record schema is invalid")
        required = {"fold", "report_alias", "clock_id", "bootstrap_id", "candidate_id", "state", "close_policy", "rehedge_policy", "close_snapshots", "rehedge_snapshots", "decision_records", "causal_cutoff_ns"}
        allowed = required | {"unit_id"}
        if set(record) - allowed:
            raise RetroBotInputError("RB-013 source record privacy violation")
        if not required.issubset(record):
            raise RetroBotInputError("RB-013 source record is incomplete")
        fold, alias = record["fold"], record["report_alias"]
        if fold not in FOLDS or alias not in REPORT_ALIASES:
            raise RetroBotInputError("RB-013 source fold alias is invalid")
        expected_range = {"development": range(1, 6), "validation": range(6, 8), "holdout": range(8, 10)}[fold]
        if int(alias[7:10]) not in expected_range or expanding_prefix(fold, alias) != tuple(REPORT_ALIASES[:int(alias[7:10]) - 1]):
            raise RetroBotInputError("RB-013 source fold prefix is invalid")
        unit_id = record.get("unit_id", alias.removesuffix(".html"))
        if not isinstance(unit_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", unit_id):
            raise RetroBotInputError("RB-013 source unit id is invalid")
        source_key = (fold, alias, record["clock_id"], record["bootstrap_id"], record["candidate_id"])
        if source_key in seen_source_units:
            raise RetroBotInputError("RB-013 duplicate source unit")
        seen_source_units.add(source_key)
        try:
            decision_records = tuple(record["decision_records"])
            close_items = tuple(record["close_snapshots"])
            rehedge_items = tuple(record["rehedge_snapshots"])
        except TypeError as error:
            raise RetroBotInputError("RB-013 source record sequence is invalid") from error
        if not decision_records or type(record["causal_cutoff_ns"]) is not int or record["causal_cutoff_ns"] < 0 or decision_records[-1].decision_time_ns != record["causal_cutoff_ns"]:
            raise RetroBotInputError("RB-013 causal cutoff is invalid")
        validated_records = validate_causal_prefix(decision_records, fold)
        if any(item.report_alias != alias for item in validated_records):
            raise RetroBotInputError("RB-013 source prefix identity is invalid")
        cutoff = record["causal_cutoff_ns"]
        for snapshot in close_items + rehedge_items:
            try:
                snapshot_time = pd.Timestamp(snapshot.decision_time)
                snapshot_time = snapshot_time.tz_localize("UTC") if snapshot_time.tzinfo is None else snapshot_time.tz_convert("UTC")
            except (AttributeError, TypeError, ValueError, pd.errors.OutOfBoundsDatetime) as error:
                raise RetroBotInputError("RB-013 snapshot time is invalid") from error
            if snapshot_time.value > cutoff:
                raise RetroBotInputError("RB-013 future snapshot is not causal")
        row = run_causal_window(
            fold=fold, clock_id=record["clock_id"], bootstrap_id=record["bootstrap_id"], candidate_id=record["candidate_id"],
            state=record["state"], close_policy=record["close_policy"], rehedge_policy=record["rehedge_policy"],
            close_snapshots=close_items, rehedge_snapshots=rehedge_items,
        )
        grouped.setdefault((row.fold, row.clock_id, row.bootstrap_id, row.candidate_id), []).append(row)
        grouped_aliases.setdefault((row.fold, row.clock_id, row.bootstrap_id, row.candidate_id), set()).add(alias)
    combined: list[WalkForwardRow] = []
    for key, rows_for_key in grouped.items():
        first = rows_for_key[0]
        sums = {field: sum(getattr(row, field) for row in rows_for_key) for field in ROW_FIELDS[4:] if field not in {"safety_pass", "support_pass"}}
        combined.append(WalkForwardRow(
            *key, sums["eligible_close"], sums["close_hold"], sums["close_action"], sums["close_censor"],
            sums["eligible_rehedge"], sums["rehedge_hold"], sums["rehedge_action"], sums["rehedge_censor"],
            all(row.safety_pass for row in rows_for_key), all(row.support_pass for row in rows_for_key),
            len(grouped_aliases[key]), sums["close_buy_eligible"], sums["close_sell_eligible"], sums["close_buy_action"], sums["close_sell_action"],
            sums["rehedge_buy_eligible"], sums["rehedge_sell_eligible"], sums["rehedge_buy_action"], sums["rehedge_sell_action"],
            sums["close_invalid_transition"], sums["close_feature_missing"], sums["close_duplicate"], sums["close_noneligible"],
            sums["rehedge_invalid_transition"], sums["rehedge_feature_missing"], sums["rehedge_duplicate"], sums["rehedge_noneligible"],
        ))
    return evaluate_walk_forward(combined, case_id=case_id)


orchestrate_walk_forward = run_registered_walk_forward
