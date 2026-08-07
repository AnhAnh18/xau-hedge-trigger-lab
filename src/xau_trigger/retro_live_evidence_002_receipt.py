"""Metadata-only validator for an owner-authorized E-002 source receipt.

The validator never opens, hashes, stores, or prints source rows. It accepts
only the receipt envelope needed to gate a later bounded intake.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Mapping

from .retro_bot import RetroBotInputError
from .retro_live_evidence_001 import assert_firewall_clean, digest

E002_RECEIPT_ID = "RETRO-LIVE-EVIDENCE-002"
REQUIRED_FIELDS = frozenset({
    "authorization_id", "owner_approval_utc", "scope", "new_sources_authorized",
    "execution_surface_authorized", "m5_inputs_models_thresholds_gates_untouched", "retention_deadline_utc",
    "source_aliases", "object_types", "sha256_by_alias", "byte_count_by_alias",
    "population_utc_half_open", "source_timezone_code", "allowed_fields_by_alias",
    "canonicalization_version", "parser_version", "retention", "source_receipt_sha256",
})
OBJECT_TYPES = frozenset({"tick", "report", "observation"})
TIME_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z\Z")
ALIAS_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
FIELD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,63}\Z")
ALLOWED_FIELDS = {
    "tick": frozenset({"time_utc", "bid", "ask"}),
    "report": frozenset({"time_utc", "side", "action", "state", "lot", "direction", "event", "position_id", "symbol", "volume", "open_time", "close_time"}),
    "observation": frozenset({"time_utc", "side", "action", "state", "lot", "direction", "event"}),
}


def validate_source_receipt(value: Mapping[str, Any]) -> bool:
    if not isinstance(value, Mapping) or set(value) != REQUIRED_FIELDS:
        raise RetroBotInputError("E-002 source receipt schema invalid")
    if not isinstance(value["authorization_id"], str) or not re.fullmatch(r"E002-[A-Za-z0-9._-]{4,80}", value["authorization_id"]):
        raise RetroBotInputError("E-002 authorization id invalid")
    if not isinstance(value["owner_approval_utc"], str) or not TIME_RE.fullmatch(value["owner_approval_utc"]):
        raise RetroBotInputError("E-002 approval timestamp invalid")
    try:
        approval_time = datetime.strptime(value["owner_approval_utc"], "%Y-%m-%dT%H:%M:%S.%fZ")
    except (TypeError, ValueError) as exc:
        raise RetroBotInputError("E-002 approval calendar timestamp invalid") from exc
    if not isinstance(value["retention_deadline_utc"], str) or not TIME_RE.fullmatch(value["retention_deadline_utc"]):
        raise RetroBotInputError("E-002 retention deadline invalid")
    try:
        retention_deadline = datetime.strptime(value["retention_deadline_utc"], "%Y-%m-%dT%H:%M:%S.%fZ")
    except (TypeError, ValueError) as exc:
        raise RetroBotInputError("E-002 retention deadline calendar invalid") from exc
    if retention_deadline <= approval_time:
        raise RetroBotInputError("E-002 retention deadline precedes approval")
    if value["scope"] != "bounded-actionful-capture-only" or value["new_sources_authorized"] is not True or value["execution_surface_authorized"] is not False or value["m5_inputs_models_thresholds_gates_untouched"] is not True:
        raise RetroBotInputError("E-002 authorization boundary invalid")
    aliases = value["source_aliases"]
    object_types = value["object_types"]
    if not isinstance(aliases, list) or not aliases or len(set(aliases)) != len(aliases) or any(not isinstance(item, str) or not ALIAS_RE.fullmatch(item) for item in aliases):
        raise RetroBotInputError("E-002 source aliases invalid")
    if not isinstance(object_types, list) or len(object_types) != len(aliases) or any(item not in OBJECT_TYPES for item in object_types):
        raise RetroBotInputError("E-002 object types invalid")
    if not isinstance(value["sha256_by_alias"], Mapping) or set(value["sha256_by_alias"]) != set(aliases) or any(not isinstance(item, str) or not re.fullmatch(r"[0-9a-f]{64}", item) for item in value["sha256_by_alias"].values()):
        raise RetroBotInputError("E-002 source hashes invalid")
    if not isinstance(value["byte_count_by_alias"], Mapping) or set(value["byte_count_by_alias"]) != set(aliases) or any(type(item) is not int or item <= 0 for item in value["byte_count_by_alias"].values()):
        raise RetroBotInputError("E-002 source byte counts invalid")
    population = value["population_utc_half_open"]
    if not isinstance(population, list) or len(population) != 2 or any(not isinstance(item, str) or not TIME_RE.fullmatch(item) for item in population):
        raise RetroBotInputError("E-002 population window invalid")
    try:
        population_times = [datetime.strptime(item, "%Y-%m-%dT%H:%M:%S.%fZ") for item in population]
    except (TypeError, ValueError) as exc:
        raise RetroBotInputError("E-002 population calendar timestamp invalid") from exc
    if population_times[0] >= population_times[1]:
        raise RetroBotInputError("E-002 population window is not half-open/ordered")
    if value["source_timezone_code"] not in {"UTC+2-winter", "UTC+3-summer", "ambiguous-censor"}:
        raise RetroBotInputError("E-002 source timezone invalid")
    fields = value["allowed_fields_by_alias"]
    if not isinstance(fields, Mapping) or set(fields) != set(aliases):
        raise RetroBotInputError("E-002 field allowlist invalid")
    for alias, object_type in zip(aliases, object_types):
        items = fields[alias]
        if not isinstance(items, list) or not items or len(set(items)) != len(items) or any(not isinstance(item, str) or not FIELD_RE.fullmatch(item) or item not in ALLOWED_FIELDS[object_type] for item in items):
            raise RetroBotInputError("E-002 field allowlist contains forbidden field")
    if value["retention"] != "redacted-aggregates-and-digests-only":
        raise RetroBotInputError("E-002 retention policy invalid")
    for key in ("canonicalization_version", "parser_version"):
        if not isinstance(value[key], str) or not value[key] or len(value[key]) > 120 or any(char in value[key] for char in "\\/\r\n"):
            raise RetroBotInputError("E-002 receipt metadata invalid")
    payload = {key: value[key] for key in value if key != "source_receipt_sha256"}
    if not isinstance(value["source_receipt_sha256"], str) or value["source_receipt_sha256"] != digest(payload):
        raise RetroBotInputError("E-002 receipt digest invalid")
    assert_firewall_clean([value["authorization_id"], value["scope"], value["source_timezone_code"], value["canonicalization_version"], value["parser_version"], value["retention"], aliases, object_types, list(fields.values()), list(value["sha256_by_alias"].values())])
    return True
