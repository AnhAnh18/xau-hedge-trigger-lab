"""RB-016 deterministic packaging and freeze over the RB-015 typed fixture.

This module intentionally accepts only the bounded, synthetic RB-015 JSON
fixture.  It produces a redacted package with independently verifiable nested
digests and has no source-data, network, MT5, or execution surface.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import json
import math
import re
from typing import IO, Mapping

import pandas as pd

from .retro_bot import RetroBotInputError
from .retro_bot_005 import ACTION_KINDS, PolicyAction, StateSnapshot
from .retro_bot_009 import (
    M5_FIREWALL,
    RB008_CONFIG_SHA256,
    REPORT_MANIFEST_SHA256,
    TICK_MANIFEST_SHA256,
)
from .retro_bot_010 import (
    PaperAttestation,
    PaperQuote,
    PaperScenario,
    _time,
    scenario_fingerprint,
)
from .retro_bot_011 import (
    ATTESTATION_FIELDS,
    FIXTURE_ID,
    PROJECTION_DIGEST,
    PROJECTION_VERSION,
    SLICE_IDS,
    _parse_stress_cycle,
    locked_stress_cases,
    stress_replay_fixture,
    validate_stress_aggregate,
)

RB016_ID = "RB-016"
PACKAGE_ID = "RB016_PACKAGE_V1"
SCHEMA_VERSION = 1
STATE_SCHEMA_VERSION = 1
STATE_ID = "RB016_STATE_V1"
RB014_SCHEMA_VERSION = 1
RB014_PROVENANCE_SHA256 = "3621048bc7ca84d4be0717b0599cc1bfed5d8d565f5502f20543873aeabfde44"
RB014_PROVENANCE_DIGEST = RB014_PROVENANCE_SHA256
RB016_PACKAGE_V1 = PACKAGE_ID
RB016_STATE_V1 = STATE_ID

_COST_FINGERPRINTS = {
    "zero": "94e0bdfde7445b7fbb442ffefefe6cdf972b1f524b60d6c637b6e97200acc1e2",
    "spread_slippage": "8b5544bbbcbc7b76247c95d152b2a9d1cef77f99e96123a64b86e01baddcc71b",
    "latency_margin": "682392bd46841d8de5bc777993df3bb39c563ce844fc27b92f2a5a7056f8d312",
}
_COST_VALUES = {
    "zero": ("0.00000000", "0.00000000", 0, "0.00000000"),
    "spread_slippage": ("0.00000000", "10.00000000", 0, "0.00000000"),
    "latency_margin": ("0.25000000", "5.00000000", 1, "2.00000000"),
}

MANIFEST_FIELDS = (
    "schema_version", "package_id", "projection_version", "projection_digest",
    "fixture_id", "rb014_schema_version", "rb014_provenance_sha256",
    "rb008_config_sha256", "source_manifest_digests", "cost_scenarios",
    "m5_firewall", "live_execution", "manifest_sha256",
)
COST_FIELDS = ("scenario_id", "fee_per_unit", "slippage_points", "latency_seconds", "margin_per_unit", "fingerprint")
STATE_FIELDS = ("schema_version", "state", "epoch", "last_time", "quantity", "seen_keys", "state_sha256")
RECEIPT_FIELDS = (
    "schema_version", "package_id", "manifest_sha256", "fixture_id", "fixture_sha256",
    "rb015_aggregate_sha256", "state_snapshot_sha256", "terminal_status", "live_execution", "receipt_sha256",
)
PACKAGE_FIELDS = ("schema_version", "case_id", "package_id", "manifest", "rb015_aggregate", "state_snapshot", "receipt", "package_sha256")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_FIXED_DECIMAL = re.compile(r"^[0-9]+\.[0-9]{8}$")


def _sha(payload: object) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def canonical_json(payload: object) -> str:
    """Return the locked UTF-8 JSON representation used by all digests."""
    try:
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=False, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise RetroBotInputError("RB-016 canonical JSON is invalid") from error


def _iso(value: object) -> str:
    timestamp = _time(value)
    return timestamp.isoformat().replace("+00:00", "Z")


def _is_hex(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX64.fullmatch(value))


def load_json_no_duplicates(stream: IO[str] | str) -> object:
    """Parse JSON while rejecting duplicate object keys at every nesting level."""
    def hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise RetroBotInputError("RB-016 duplicate JSON key")
            result[key] = value
        return result

    try:
        text = stream if isinstance(stream, str) else stream.read()
        return json.loads(text, object_pairs_hook=hook, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except RetroBotInputError:
        raise
    except (json.JSONDecodeError, TypeError, ValueError, UnicodeError) as error:
        raise RetroBotInputError("RB-016 input JSON is invalid") from error


def _reject_recursive_private(value: object, *, allow_m5: bool = False) -> None:
    """Fail closed on private/raw/live aliases without echoing their values."""
    forbidden = ("password", "credential", "journal", "ticket", ".ex5", "raw_path", "private_path", "account_id", "account_number", "login", "secret", "live_execution")
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = key.casefold() if isinstance(key, str) else ""
            if key_text in {"m5_firewall"} and item == M5_FIREWALL:
                continue
            if any(token in key_text for token in forbidden):
                if key_text == "live_execution" and item is False:
                    continue
                raise RetroBotInputError("RB-016 privacy/firewall violation")
            _reject_recursive_private(item, allow_m5=allow_m5)
    elif isinstance(value, list):
        for item in value:
            _reject_recursive_private(item, allow_m5=allow_m5)
    elif isinstance(value, str):
        folded = value.casefold()
        if "m5" in folded and value != M5_FIREWALL:
            raise RetroBotInputError("RB-016 privacy/firewall violation")
        if any(token in folded for token in forbidden[:-1]):
            raise RetroBotInputError("RB-016 privacy/firewall violation")


def _fixed(value: object) -> None:
    if not isinstance(value, str) or not _FIXED_DECIMAL.fullmatch(value):
        raise RetroBotInputError("RB-016 fixed decimal is invalid")
    try:
        numeric = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise RetroBotInputError("RB-016 fixed decimal is invalid") from error
    if not math.isfinite(numeric):
        raise RetroBotInputError("RB-016 fixed decimal is invalid")


def build_manifest() -> dict[str, object]:
    costs = []
    for scenario_id in ("zero", "spread_slippage", "latency_margin"):
        fee, slippage, latency, margin = _COST_VALUES[scenario_id]
        costs.append({
            "scenario_id": scenario_id,
            "fee_per_unit": fee,
            "slippage_points": slippage,
            "latency_seconds": latency,
            "margin_per_unit": margin,
            "fingerprint": _COST_FINGERPRINTS[scenario_id],
        })
    payload: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "package_id": PACKAGE_ID,
        "projection_version": PROJECTION_VERSION,
        "projection_digest": PROJECTION_DIGEST,
        "fixture_id": FIXTURE_ID,
        "rb014_schema_version": RB014_SCHEMA_VERSION,
        "rb014_provenance_sha256": RB014_PROVENANCE_SHA256,
        "rb008_config_sha256": RB008_CONFIG_SHA256,
        "source_manifest_digests": {"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256},
        "cost_scenarios": costs,
        "m5_firewall": M5_FIREWALL,
        "live_execution": False,
        "manifest_sha256": "TO_BE_FILLED",
    }
    payload["manifest_sha256"] = _sha({key: value for key, value in payload.items() if key != "manifest_sha256"})
    validate_manifest(payload)
    return payload


def validate_manifest(payload: Mapping[str, object]) -> None:
    if not isinstance(payload, Mapping) or tuple(payload.keys()) != MANIFEST_FIELDS:
        raise RetroBotInputError("RB-016 manifest schema is invalid")
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != SCHEMA_VERSION or payload.get("package_id") != PACKAGE_ID or payload.get("projection_version") != PROJECTION_VERSION or payload.get("projection_digest") != PROJECTION_DIGEST or payload.get("fixture_id") != FIXTURE_ID or type(payload.get("rb014_schema_version")) is not int or payload.get("rb014_schema_version") != RB014_SCHEMA_VERSION or payload.get("rb014_provenance_sha256") != RB014_PROVENANCE_SHA256 or payload.get("rb008_config_sha256") != RB008_CONFIG_SHA256 or payload.get("m5_firewall") != M5_FIREWALL or type(payload.get("live_execution")) is not bool or payload.get("live_execution") is not False or not _is_hex(payload.get("manifest_sha256")):
        raise RetroBotInputError("RB-016 manifest provenance mismatch")
    source = payload.get("source_manifest_digests")
    if not isinstance(source, Mapping) or tuple(source.keys()) != ("report_manifest_sha256", "tick_manifest_sha256") or source != {"report_manifest_sha256": REPORT_MANIFEST_SHA256, "tick_manifest_sha256": TICK_MANIFEST_SHA256}:
        raise RetroBotInputError("RB-016 source manifest mismatch")
    costs = payload.get("cost_scenarios")
    if not isinstance(costs, list) or len(costs) != 3:
        raise RetroBotInputError("RB-016 cost manifest is invalid")
    for item, expected_id in zip(costs, ("zero", "spread_slippage", "latency_margin")):
        if not isinstance(item, Mapping) or tuple(item.keys()) != COST_FIELDS:
            raise RetroBotInputError("RB-016 cost manifest is invalid")
        if item.get("scenario_id") != expected_id or item.get("fingerprint") != _COST_FINGERPRINTS[expected_id]:
            raise RetroBotInputError("RB-016 cost fingerprint mismatch")
        expected = _COST_VALUES[expected_id]
        if (item.get("fee_per_unit"), item.get("slippage_points"), item.get("latency_seconds"), item.get("margin_per_unit")) != expected:
            raise RetroBotInputError("RB-016 cost scenario mismatch")
        _fixed(item["fee_per_unit"]); _fixed(item["slippage_points"]); _fixed(item["margin_per_unit"])
        if type(item["latency_seconds"]) is not int or item["latency_seconds"] < 0:
            raise RetroBotInputError("RB-016 latency scenario is invalid")
    if payload["manifest_sha256"] != _sha({key: value for key, value in payload.items() if key != "manifest_sha256"}):
        raise RetroBotInputError("RB-016 manifest digest mismatch")


def _state_payload(state: StateSnapshot, *, include_digest: bool = True) -> dict[str, object]:
    if not isinstance(state, StateSnapshot) or state.state not in {"HEDGED", "ONE_BUY", "ONE_SELL"}:
        raise RetroBotInputError("RB-016 state is invalid")
    if type(state.epoch) is not int or state.epoch < 0 or state.quantity != 1.0 or not math.isfinite(float(state.quantity)):
        raise RetroBotInputError("RB-016 state is invalid")
    if state.last_time is not None:
        last_time = _iso(state.last_time)
    else:
        last_time = None
    seen = []
    for item in state.seen_keys:
        if not isinstance(item, tuple) or len(item) != 3 or type(item[0]) is not int or item[0] < 0 or type(item[1]) is not int or item[1] < 0 or item[2] not in ACTION_KINDS:
            raise RetroBotInputError("RB-016 state key is invalid")
        seen.append([item[0], item[1], item[2]])
    if len(seen) != len({tuple(item) for item in seen}):
        raise RetroBotInputError("RB-016 duplicate state key")
    payload: dict[str, object] = {"schema_version": STATE_SCHEMA_VERSION, "state": state.state, "epoch": state.epoch, "last_time": last_time, "quantity": 1.0, "seen_keys": seen}
    if include_digest:
        payload["state_sha256"] = _sha(payload)
    return payload


def initial_state_snapshot(state: StateSnapshot) -> dict[str, object]:
    if not isinstance(state, StateSnapshot) or state.state != "HEDGED" or state.epoch != 0 or state.quantity != 1.0 or state.seen_keys:
        raise RetroBotInputError("RB-016 initial state is invalid")
    return _state_payload(state)


def validate_state_snapshot(payload: Mapping[str, object]) -> None:
    if not isinstance(payload, Mapping) or tuple(payload.keys()) != STATE_FIELDS:
        raise RetroBotInputError("RB-016 state snapshot schema is invalid")
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != STATE_SCHEMA_VERSION or payload.get("state") != "HEDGED" or type(payload.get("epoch")) is not int or payload.get("epoch") != 0 or payload.get("quantity") != 1.0 or type(payload.get("quantity")) is not float or not math.isfinite(payload["quantity"]):
        raise RetroBotInputError("RB-016 initial state mismatch")
    last_time = payload.get("last_time")
    if last_time is not None:
        if not isinstance(last_time, str) or not re.search(r"(?:Z|[+]00:00)$", last_time):
            raise RetroBotInputError("RB-016 state timestamp must be UTC")
        if _iso(last_time) != last_time:
            raise RetroBotInputError("RB-016 state timestamp is not canonical")
    seen = payload.get("seen_keys")
    if not isinstance(seen, list) or seen:
        raise RetroBotInputError("RB-016 initial state keys are invalid")
    if not _is_hex(payload.get("state_sha256")) or payload["state_sha256"] != _sha({key: value for key, value in payload.items() if key != "state_sha256"}):
        raise RetroBotInputError("RB-016 state digest mismatch")


def _canonical_state(state: StateSnapshot) -> dict[str, object]:
    return _state_payload(state, include_digest=False)


def _canonical_action(action: PolicyAction) -> dict[str, object]:
    if not isinstance(action, PolicyAction):
        raise RetroBotInputError("RB-016 action is invalid")
    return {"kind": action.kind, "decision_time": _iso(action.decision_time), "window_epoch": action.window_epoch, "source": action.source}


def _canonical_quote(quote: PaperQuote) -> dict[str, object]:
    if not isinstance(quote, PaperQuote):
        raise RetroBotInputError("RB-016 quote is invalid")
    quote.validate()
    return {"decision_time": _iso(quote.decision_time), "bid": float(quote.bid), "ask": float(quote.ask)}


def _canonical_snapshot(snapshot: object) -> dict[str, object]:
    values = getattr(snapshot, "values", None)
    feature_times = getattr(snapshot, "feature_times", None)
    if values is None or feature_times is None:
        raise RetroBotInputError("RB-016 feature snapshot is invalid")
    return {"decision_time": _iso(snapshot.decision_time), "values": {key: values[key] for key in sorted(values)}, "feature_times": {key: _iso(feature_times[key]) for key in sorted(feature_times)}, "oracle_labels": list(snapshot.oracle_labels)}


def _canonical_decision(record: object) -> dict[str, object]:
    return {"fold": record.fold, "decision_time_ns": record.decision_time_ns, "future_read": record.future_read, "oracle_used": record.oracle_used, "report_alias": record.report_alias}


def _canonical_fixture(document: Mapping[str, object]) -> dict[str, object]:
    """Normalize the validated fixture through RB-015's typed parser."""
    attestation = PaperAttestation(**dict(document["attestation"]))
    attestation.validate()
    parsed = {}
    for raw in document["cycles"]:
        slice_id, cycle = _parse_stress_cycle(raw)
        if slice_id in parsed:
            raise RetroBotInputError("RB-016 duplicate fixture slice")
        parsed[slice_id] = cycle
    cycles = []
    for slice_id in SLICE_IDS:
        cycle = parsed[slice_id]
        window = cycle["causal_window"]
        cycles.append({
            "slice_id": slice_id,
            "cycle": {
                "cycle_id": cycle["cycle_id"], "unit_id": cycle["unit_id"], "fold": cycle["fold"], "clock_id": cycle["clock_id"], "bootstrap_id": cycle["bootstrap_id"], "candidate_id": cycle["candidate_id"],
                "state": _canonical_state(cycle["state"]),
                "actions": [_canonical_action(item) for item in cycle["actions"]],
                "quotes": [_canonical_quote(item) for item in cycle["quotes"]],
                "causal_window": {
                    "state": _canonical_state(window["state"]),
                    "close_snapshots": [_canonical_snapshot(item) for item in window["close_snapshots"]],
                    "rehedge_snapshots": [_canonical_snapshot(item) for item in window["rehedge_snapshots"]],
                    "decision_records": [_canonical_decision(item) for item in window["decision_records"]],
                    "causal_cutoff_ns": window["causal_cutoff_ns"], "report_alias": window["report_alias"],
                },
            },
        })
    return {
        "attestation": {"schema_version": attestation.schema_version, "rb008_config_sha256": attestation.rb008_config_sha256, "report_manifest_sha256": attestation.report_manifest_sha256, "tick_manifest_sha256": attestation.tick_manifest_sha256, "fixture_id": attestation.fixture_id, "m5_firewall": attestation.m5_firewall},
        "projection": {"projection_version": PROJECTION_VERSION, "fixture_id": FIXTURE_ID, "projection_digest": PROJECTION_DIGEST},
        "cases": [{"case_id": case.case_id, "family": case.family, "clock_id": case.clock_id, "timestamp_mode": case.timestamp_mode, "quote_mode": case.quote_mode, "cost_scenario_id": case.cost_scenario_id, "coverage_mode": case.coverage_mode, "slice_id": case.slice_id, "ablation_id": case.ablation_id} for case in locked_stress_cases()],
        "cycles": cycles,
    }


def fixture_sha256(document: Mapping[str, object]) -> str:
    _reject_recursive_private(document)
    stress_replay_fixture(document)
    return _sha(_canonical_fixture(document))


def _aggregate_sha256(aggregate: Mapping[str, object]) -> str:
    return str(aggregate["aggregate_sha256"])


def package_replay_fixture(document: Mapping[str, object]) -> dict[str, object]:
    _reject_recursive_private(document)
    if not isinstance(document, Mapping):
        raise RetroBotInputError("RB-016 fixture must be an object")
    aggregate = stress_replay_fixture(document)
    validate_stress_aggregate(aggregate)
    canonical = _canonical_fixture(document)
    parsed = {slice_id: _parse_stress_cycle(next(item for item in document["cycles"] if item["slice_id"] == slice_id))[1] for slice_id in SLICE_IDS}
    state = parsed["all"]["state"]
    snapshot = initial_state_snapshot(state)
    manifest = build_manifest()
    receipt: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "package_id": PACKAGE_ID,
        "manifest_sha256": manifest["manifest_sha256"],
        "fixture_id": FIXTURE_ID,
        "fixture_sha256": _sha(canonical),
        "rb015_aggregate_sha256": _aggregate_sha256(aggregate),
        "state_snapshot_sha256": snapshot["state_sha256"],
        "terminal_status": "descriptive-only-no-selection",
        "live_execution": False,
        "receipt_sha256": "TO_BE_FILLED",
    }
    receipt["receipt_sha256"] = _sha({key: value for key, value in receipt.items() if key != "receipt_sha256"})
    package: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "case_id": RB016_ID,
        "package_id": PACKAGE_ID,
        "manifest": manifest,
        "rb015_aggregate": aggregate,
        "state_snapshot": snapshot,
        "receipt": receipt,
        "package_sha256": "TO_BE_FILLED",
    }
    package["package_sha256"] = _sha({key: value for key, value in package.items() if key != "package_sha256"})
    validate_package(package)
    return package


def validate_receipt(receipt: Mapping[str, object], *, manifest: Mapping[str, object], aggregate: Mapping[str, object], state: Mapping[str, object]) -> None:
    if not isinstance(receipt, Mapping) or tuple(receipt.keys()) != RECEIPT_FIELDS:
        raise RetroBotInputError("RB-016 receipt schema is invalid")
    validate_manifest(manifest); validate_stress_aggregate(aggregate); validate_state_snapshot(state)
    if type(receipt.get("schema_version")) is not int or receipt["schema_version"] != SCHEMA_VERSION or receipt.get("package_id") != PACKAGE_ID or receipt.get("manifest_sha256") != manifest["manifest_sha256"] or receipt.get("fixture_id") != FIXTURE_ID or not _is_hex(receipt.get("fixture_sha256")) or receipt.get("rb015_aggregate_sha256") != aggregate["aggregate_sha256"] or receipt.get("state_snapshot_sha256") != state["state_sha256"] or receipt.get("terminal_status") != "descriptive-only-no-selection" or type(receipt.get("live_execution")) is not bool or receipt.get("live_execution") is not False or not _is_hex(receipt.get("receipt_sha256")):
        raise RetroBotInputError("RB-016 receipt provenance mismatch")
    if receipt["receipt_sha256"] != _sha({key: value for key, value in receipt.items() if key != "receipt_sha256"}):
        raise RetroBotInputError("RB-016 receipt digest mismatch")


def validate_package(payload: Mapping[str, object]) -> None:
    _reject_recursive_private(payload)
    if not isinstance(payload, Mapping) or tuple(payload.keys()) != PACKAGE_FIELDS:
        raise RetroBotInputError("RB-016 package schema is invalid")
    if type(payload.get("schema_version")) is not int or payload["schema_version"] != SCHEMA_VERSION or payload.get("case_id") != RB016_ID or payload.get("package_id") != PACKAGE_ID or not _is_hex(payload.get("package_sha256")):
        raise RetroBotInputError("RB-016 package identity mismatch")
    manifest = payload.get("manifest"); aggregate = payload.get("rb015_aggregate"); state = payload.get("state_snapshot"); receipt = payload.get("receipt")
    if not isinstance(manifest, Mapping) or not isinstance(aggregate, Mapping) or not isinstance(state, Mapping) or not isinstance(receipt, Mapping):
        raise RetroBotInputError("RB-016 package nested object is invalid")
    validate_manifest(manifest); validate_stress_aggregate(aggregate); validate_state_snapshot(state)
    validate_receipt(receipt, manifest=manifest, aggregate=aggregate, state=state)
    if payload["package_sha256"] != _sha({key: value for key, value in payload.items() if key != "package_sha256"}):
        raise RetroBotInputError("RB-016 package digest mismatch")


def verify_package(payload: Mapping[str, object]) -> bool:
    validate_package(payload)
    return True


package_replay = package_replay_fixture
verify_receipt = verify_package
parse_json_no_duplicates = load_json_no_duplicates
serialize_state_snapshot = _state_payload
verify_receipt_artifact = verify_package
validate_rb015_aggregate = validate_stress_aggregate


__all__ = [
    "RB016_ID", "PACKAGE_ID", "RB016_PACKAGE_V1", "RB016_STATE_V1", "RB014_PROVENANCE_SHA256", "RB014_PROVENANCE_DIGEST", "MANIFEST_FIELDS", "STATE_FIELDS", "RECEIPT_FIELDS", "PACKAGE_FIELDS",
    "build_manifest", "validate_manifest", "load_json_no_duplicates", "initial_state_snapshot", "validate_state_snapshot", "fixture_sha256",
    "package_replay_fixture", "package_replay", "validate_receipt", "validate_package", "verify_package", "verify_receipt", "verify_receipt_artifact",
    "parse_json_no_duplicates", "serialize_state_snapshot", "validate_rb015_aggregate", "canonical_json",
]
