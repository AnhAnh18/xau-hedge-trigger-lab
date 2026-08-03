"""RB-017 deterministic synthetic/shadow historical closeout.

The closeout combines a verified RB-016 package with one separately supplied
typed RB-015 fixture.  It intentionally produces only a redacted report and
never accepts or emits raw source data, paths, or execution controls.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Mapping

from .retro_bot import RetroBotInputError
from .retro_bot_009 import (
    M5_FIREWALL,
    RB008_CONFIG_SHA256,
    REPORT_MANIFEST_SHA256,
    TICK_MANIFEST_SHA256,
)
from .retro_bot_010 import ATTESTATION_FIELDS
from .retro_bot_011 import (
    FIXTURE_ID,
    PROJECTION_DIGEST,
    PROJECTION_VERSION,
    SLICE_IDS,
    _parse_stress_cycle,
    stress_replay_fixture,
    validate_stress_aggregate,
)
from .retro_bot_012 import (
    PACKAGE_ID,
    canonical_json,
    fixture_sha256,
    load_json_no_duplicates,
    validate_package,
)

RB017_ID = "RB-017"
SCHEMA_VERSION = 1
TERMINAL_STATUS = "behaviorally-compatible-accounting-inconclusive"
SHOWN = (
    "package_integrity",
    "rb015_projection_integrity",
    "holdout_replay_integrity",
    "accounting_bands_only",
    "deterministic_replay",
)
UNRESOLVED = (
    "no_candidate_selection",
    "synthetic_shadow_holdout",
    "raw_historical_scope",
    "profitability",
    "live_execution",
)
INPUT_FIELDS = ("package", "holdout_fixture")
INPUT_WITH_REPORT_FIELDS = ("package", "holdout_fixture", "report")
SOURCE_FIELDS = ("report_manifest_sha256", "tick_manifest_sha256")
REPORT_FIELDS = (
    "schema_version",
    "case_id",
    "package_id",
    "package_sha256",
    "package_aggregate_sha256",
    "holdout_fixture_sha256",
    "holdout_aggregate_sha256",
    "projection_digest",
    "source_manifest_digests",
    "attestation",
    "selection_performed",
    "holdout_supported",
    "terminal_status",
    "shown",
    "unresolved",
    "m5_firewall",
    "report_sha256",
)
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _sha(payload: object) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def _hex64(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX64.fullmatch(value))


def _reject_recursive_private(value: object) -> None:
    """Reject private/raw/M5/live aliases before any value can be echoed."""
    forbidden_keys = (
        "password",
        "credential",
        "journal",
        "ticket",
        ".ex5",
        "raw_path",
        "private_path",
        "account_id",
        "account_number",
        "login",
        "secret",
        "subprocess",
        "network",
        "mt5",
    )
    forbidden_values = forbidden_keys
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = key.casefold() if isinstance(key, str) else ""
            if any(token in key_text for token in forbidden_keys):
                raise RetroBotInputError("RB-017 privacy/firewall violation")
            _reject_recursive_private(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_recursive_private(item)
    elif isinstance(value, str):
        folded = value.casefold()
        if any(token in folded for token in forbidden_values) or ("m5" in folded and value != M5_FIREWALL):
            raise RetroBotInputError("RB-017 privacy/firewall violation")


def _expect_mapping(value: object, fields: tuple[str, ...], message: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or tuple(value.keys()) != fields:
        raise RetroBotInputError(message)
    return value


def _validate_holdout_fixture(document: object) -> None:
    """Validate holdout fold/alias constraints before invoking RB-015 replay."""
    if not isinstance(document, Mapping):
        raise RetroBotInputError("RB-017 holdout fixture is invalid")
    _expect_mapping(document, ("attestation", "projection", "cases", "cycles"), "RB-017 holdout fixture schema is invalid")
    cycles = document.get("cycles")
    if not isinstance(cycles, list) or len(cycles) != len(SLICE_IDS):
        raise RetroBotInputError("RB-017 holdout fixture coverage is invalid")
    seen: set[str] = set()
    for raw in cycles:
        wrapper = _expect_mapping(raw, ("slice_id", "cycle"), "RB-017 holdout cycle schema is invalid")
        slice_id = wrapper.get("slice_id")
        if not isinstance(slice_id, str) or slice_id not in SLICE_IDS or slice_id in seen:
            raise RetroBotInputError("RB-017 holdout cycle identity is invalid")
        seen.add(slice_id)
        cycle = wrapper.get("cycle")
        cycle_fields = ("cycle_id", "unit_id", "fold", "clock_id", "bootstrap_id", "candidate_id", "state", "actions", "quotes", "causal_window")
        cycle = _expect_mapping(cycle, cycle_fields, "RB-017 holdout cycle schema is invalid")
        if cycle.get("fold") != "holdout":
            raise RetroBotInputError("RB-017 holdout fold is invalid")
        causal = _expect_mapping(cycle.get("causal_window"), ("state", "close_snapshots", "rehedge_snapshots", "decision_records", "causal_cutoff_ns", "report_alias"), "RB-017 holdout causal window is invalid")
        if causal.get("report_alias") != "report-008.html":
            raise RetroBotInputError("RB-017 holdout report alias is invalid")
        records = causal.get("decision_records")
        if not isinstance(records, list):
            raise RetroBotInputError("RB-017 holdout decision records are invalid")
        for record in records:
            record = _expect_mapping(record, ("fold", "decision_time_ns", "future_read", "oracle_used", "report_alias"), "RB-017 holdout decision record is invalid")
            if record.get("fold") != "holdout" or type(record.get("future_read")) is not bool or record.get("future_read") is not False or type(record.get("oracle_used")) is not bool or record.get("oracle_used") is not False or record.get("report_alias") != "report-008.html":
                raise RetroBotInputError("RB-017 holdout decision record is invalid")
    if seen != set(SLICE_IDS):
        raise RetroBotInputError("RB-017 holdout fixture coverage is incomplete")


def validate_holdout_fixture(document: Mapping[str, object]) -> None:
    """Public strict holdout validator."""
    _reject_recursive_private(document)
    _validate_holdout_fixture(document)
    # RB-015 performs the complete typed parse and all replay invariants.
    try:
        stress_replay_fixture(document)
    except RetroBotInputError:
        raise
    except (TypeError, ValueError, KeyError, AttributeError, OverflowError) as error:
        raise RetroBotInputError("RB-017 holdout fixture is invalid") from error


def holdout_replay(document: Mapping[str, object]) -> dict[str, object]:
    validate_holdout_fixture(document)
    try:
        aggregate = stress_replay_fixture(document)
    except RetroBotInputError:
        raise
    except (TypeError, ValueError, KeyError, AttributeError, OverflowError) as error:
        raise RetroBotInputError("RB-017 holdout replay is invalid") from error
    validate_stress_aggregate(aggregate)
    return aggregate


def _expected_attestation() -> dict[str, object]:
    return {
        "schema_version": 1,
        "rb008_config_sha256": RB008_CONFIG_SHA256,
        "report_manifest_sha256": REPORT_MANIFEST_SHA256,
        "tick_manifest_sha256": TICK_MANIFEST_SHA256,
        "fixture_id": FIXTURE_ID,
        "m5_firewall": M5_FIREWALL,
    }


def _validate_inherited_aggregate(aggregate: Mapping[str, object], *, name: str) -> None:
    try:
        validate_stress_aggregate(aggregate)
    except (RetroBotInputError, TypeError, ValueError, KeyError) as error:
        raise RetroBotInputError(f"RB-017 {name} aggregate is invalid") from error
    if aggregate.get("projection_digest") != PROJECTION_DIGEST or aggregate.get("source_manifest_digests") != {
        "report_manifest_sha256": REPORT_MANIFEST_SHA256,
        "tick_manifest_sha256": TICK_MANIFEST_SHA256,
    } or aggregate.get("attestation") != _expected_attestation():
        raise RetroBotInputError(f"RB-017 {name} aggregate provenance mismatch")


def _validate_report(report: Mapping[str, object]) -> None:
    if not isinstance(report, Mapping) or tuple(report.keys()) != REPORT_FIELDS:
        raise RetroBotInputError("RB-017 report schema is invalid")
    if (
        type(report.get("schema_version")) is not int
        or report.get("schema_version") != SCHEMA_VERSION
        or report.get("case_id") != RB017_ID
        or report.get("package_id") != PACKAGE_ID
        or not _hex64(report.get("package_sha256"))
        or not _hex64(report.get("package_aggregate_sha256"))
        or not _hex64(report.get("holdout_fixture_sha256"))
        or not _hex64(report.get("holdout_aggregate_sha256"))
        or report.get("projection_digest") != PROJECTION_DIGEST
        or type(report.get("selection_performed")) is not bool
        or report.get("selection_performed") is not False
        or type(report.get("holdout_supported")) is not bool
        or report.get("holdout_supported") is not False
        or report.get("terminal_status") != TERMINAL_STATUS
        or report.get("shown") != list(SHOWN)
        or report.get("unresolved") != list(UNRESOLVED)
        or report.get("m5_firewall") != M5_FIREWALL
        or not _hex64(report.get("report_sha256"))
    ):
        raise RetroBotInputError("RB-017 report literals are invalid")
    source = report.get("source_manifest_digests")
    if not isinstance(source, Mapping) or tuple(source.keys()) != SOURCE_FIELDS or source != {
        "report_manifest_sha256": REPORT_MANIFEST_SHA256,
        "tick_manifest_sha256": TICK_MANIFEST_SHA256,
    }:
        raise RetroBotInputError("RB-017 report source digest is invalid")
    attestation = report.get("attestation")
    if not isinstance(attestation, Mapping) or tuple(attestation.keys()) != ATTESTATION_FIELDS or dict(attestation) != _expected_attestation():
        raise RetroBotInputError("RB-017 report attestation is invalid")
    if report["report_sha256"] != _sha({key: value for key, value in report.items() if key != "report_sha256"}):
        raise RetroBotInputError("RB-017 report digest mismatch")
    _reject_recursive_private(report)


def build_report(*, package: Mapping[str, object], holdout_fixture: Mapping[str, object], holdout_aggregate: Mapping[str, object] | None = None) -> dict[str, object]:
    """Build the fixed redacted report after package and holdout validation."""
    _reject_recursive_private(package)
    _reject_recursive_private(holdout_fixture)
    validate_package(package)
    _validate_inherited_aggregate(package["rb015_aggregate"], name="package")
    _validate_holdout_fixture(holdout_fixture)
    expected_holdout_aggregate = stress_replay_fixture(holdout_fixture)
    if holdout_aggregate is None:
        holdout_aggregate = expected_holdout_aggregate
    elif canonical_json(holdout_aggregate) != canonical_json(expected_holdout_aggregate):
        raise RetroBotInputError("RB-017 holdout aggregate does not match fixture")
    _validate_inherited_aggregate(holdout_aggregate, name="holdout")
    report: dict[str, object] = {
        "schema_version": SCHEMA_VERSION,
        "case_id": RB017_ID,
        "package_id": PACKAGE_ID,
        "package_sha256": package["package_sha256"],
        "package_aggregate_sha256": package["rb015_aggregate"]["aggregate_sha256"],
        "holdout_fixture_sha256": fixture_sha256(holdout_fixture),
        "holdout_aggregate_sha256": holdout_aggregate["aggregate_sha256"],
        "projection_digest": PROJECTION_DIGEST,
        "source_manifest_digests": {
            "report_manifest_sha256": REPORT_MANIFEST_SHA256,
            "tick_manifest_sha256": TICK_MANIFEST_SHA256,
        },
        "attestation": _expected_attestation(),
        "selection_performed": False,
        "holdout_supported": False,
        "terminal_status": TERMINAL_STATUS,
        "shown": list(SHOWN),
        "unresolved": list(UNRESOLVED),
        "m5_firewall": M5_FIREWALL,
        "report_sha256": "TO_BE_FILLED",
    }
    report["report_sha256"] = _sha({key: value for key, value in report.items() if key != "report_sha256"})
    _validate_report(report)
    return report


def closeout(document: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(document, Mapping) or tuple(document.keys()) != INPUT_FIELDS:
        raise RetroBotInputError("RB-017 closeout input schema is invalid")
    package = document.get("package")
    fixture = document.get("holdout_fixture")
    if not isinstance(package, Mapping) or not isinstance(fixture, Mapping):
        raise RetroBotInputError("RB-017 closeout input is invalid")
    aggregate = holdout_replay(fixture)
    return build_report(package=package, holdout_fixture=fixture, holdout_aggregate=aggregate)


def verify_closeout(document: Mapping[str, object]) -> bool:
    if not isinstance(document, Mapping) or tuple(document.keys()) not in (INPUT_FIELDS, INPUT_WITH_REPORT_FIELDS):
        raise RetroBotInputError("RB-017 verify input schema is invalid")
    expected = closeout({"package": document["package"], "holdout_fixture": document["holdout_fixture"]})
    if "report" in document:
        supplied = document["report"]
        if not isinstance(supplied, Mapping):
            raise RetroBotInputError("RB-017 supplied report is invalid")
        _validate_report(supplied)
        if canonical_json(supplied) != canonical_json(expected):
            raise RetroBotInputError("RB-017 supplied report mismatch")
    return True


def verify_report(report: Mapping[str, object]) -> bool:
    _validate_report(report)
    return True


parse_json_no_duplicates = load_json_no_duplicates
validate_closeout_report = _validate_report
closeout_report = closeout
verify_closeout_report = verify_closeout
replay_holdout_fixture = holdout_replay


__all__ = [
    "RB017_ID",
    "PACKAGE_ID",
    "PROJECTION_DIGEST",
    "TERMINAL_STATUS",
    "SHOWN",
    "UNRESOLVED",
    "REPORT_FIELDS",
    "build_report",
    "closeout",
    "closeout_report",
    "holdout_replay",
    "replay_holdout_fixture",
    "validate_holdout_fixture",
    "verify_closeout",
    "verify_closeout_report",
    "verify_report",
    "parse_json_no_duplicates",
    "load_json_no_duplicates",
]
