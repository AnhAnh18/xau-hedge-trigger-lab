from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from decimal import Decimal

import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_015 import (
    AGGREGATE_FIELDS,
    canonical_json,
    _cycle_accounting,
    _parse_cycle,
    parse_input,
    replay,
    verify_aggregate,
)


def _cycle_one() -> dict[str, object]:
    return {
        "cycle_id": "cycle_one",
        "start_state": "HEDGED",
        "initial": {"buy_quantity": "0.30000000", "sell_quantity": "0.10000000"},
        "initial_quote": {"bid": "2000.00000000", "ask": "2000.20000000"},
        "events": [
            {"kind": "CLOSE_BUY", "time_ns": 1, "bid": "2000.50000000", "ask": "2000.70000000", "quantity": "0.30000000"},
            {"kind": "OPEN_BUY", "time_ns": 2, "bid": "2000.40000000", "ask": "2000.60000000", "quantity": "0.50000000"},
        ],
        "terminal_quote": {"bid": "2000.00000000", "ask": "2000.20000000"},
    }


def _cycle_two() -> dict[str, object]:
    return {
        "cycle_id": "cycle_two",
        "start_state": "ONE_BUY",
        "initial": {"buy_quantity": "0.30000000", "sell_quantity": "0.00000000"},
        "initial_quote": {"bid": "2000.00000000", "ask": "2000.20000000"},
        "events": [],
        "terminal_quote": {"bid": "2000.20000000", "ask": "2000.40000000"},
    }


def _document() -> dict[str, object]:
    return {
        "schema_version": 1,
        "case_id": "RB-019",
        "attestation": {
            "schema_version": 1,
            "authorization": "RB019_TYPED_VARIABLE_LOT_AUTHORIZED",
            "source_kind": "typed-redacted",
            "m5_firewall": "M5_FIREWALL_ATTESTATION_V1",
            "live_execution": False,
        },
        "scenario": {
            "scenario_id": "zero",
            "fee_per_unit": "0.00000000",
            "slippage_points": "0.00000000",
            "fingerprint": "834b9a47b2dcbfaab283e4ae18fa86fb216476708b54cfea1939b3ad8f4075c8",
        },
        "cycles": [_cycle_one(), _cycle_two()],
    }


def test_uneven_lot_accounting_and_exact_population() -> None:
    aggregate = replay(_document())
    assert tuple(aggregate) == AGGREGATE_FIELDS
    assert aggregate["cycle_count"] == 2
    assert aggregate["marked_count"] == 2
    assert aggregate["invalid_count"] == 0
    assert aggregate["quantity_min_fixed8"] == "0.10000000"
    assert aggregate["quantity_max_fixed8"] == "0.50000000"
    assert aggregate["traded_quantity_total_fixed8"] == "1.50000000"
    assert aggregate["loss_count"] == 1
    assert aggregate["flat_count"] == 1


def test_verify_aggregate_accepts_only_optional_final_key() -> None:
    document = _document()
    aggregate = replay(document)
    assert verify_aggregate({**document, "aggregate": aggregate}) is True
    bad = copy.deepcopy(document)
    bad["aggregate"] = aggregate
    bad["extra"] = True
    with pytest.raises(RetroBotInputError):
        verify_aggregate(bad)
    bad = copy.deepcopy(document)
    bad["aggregate"] = aggregate
    bad["aggregate"]["aggregate_sha256"] = "f" * 64
    with pytest.raises(RetroBotInputError):
        verify_aggregate(bad)


def test_semantically_invalid_cycle_is_counted_without_raw_output() -> None:
    document = _document()
    invalid = copy.deepcopy(_cycle_one())
    invalid["cycle_id"] = "invalid_cycle"
    invalid["events"][0]["quantity"] = "0.20000000"
    document["cycles"].append(invalid)
    aggregate = replay(document)
    assert aggregate["cycle_count"] == 3
    assert aggregate["marked_count"] == 2
    assert aggregate["invalid_count"] == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["cycles"][0]["initial"]["buy_quantity"].__class__,
        lambda d: d["cycles"][0]["initial"]["buy_quantity"].__class__,
    ],
)
def test_fixed8_and_attestation_tampering_rejected(mutate) -> None:
    document = _document()
    document["cycles"][0]["initial"]["buy_quantity"] = "01.30000000"
    with pytest.raises(RetroBotInputError):
        replay(document)
    document = _document()
    document["attestation"]["authorization"] = "OTHER"
    with pytest.raises(RetroBotInputError):
        replay(document)


def test_time_quote_and_firewall_fail_closed() -> None:
    for mutation in (
        lambda d: d["cycles"][0]["events"][0].__setitem__("time_ns", True),
        lambda d: d["cycles"][0]["events"][0].__setitem__("ask", "1999.00000000"),
        lambda d: d.__setitem__("raw_path", "C:/history"),
    ):
        document = _document()
        mutation(document)
        with pytest.raises(RetroBotInputError):
            replay(document)


def test_cli_determinism_verify_and_exact_rejection() -> None:
    payload = json.dumps(_document(), ensure_ascii=True, separators=(",", ":"))
    command = [sys.executable, "scripts/run_retro_bot_019.py", "replay"]
    first = subprocess.run(command, input=payload, text=True, capture_output=True, check=False)
    second = subprocess.run(command, input=payload, text=True, capture_output=True, check=False)
    assert first.returncode == second.returncode == 0
    assert first.stdout == second.stdout
    aggregate = json.loads(first.stdout)
    verify_payload = json.dumps({**_document(), "aggregate": aggregate}, separators=(",", ":"))
    verified = subprocess.run(
        [sys.executable, "scripts/run_retro_bot_019.py", "verify-aggregate"],
        input=verify_payload,
        text=True,
        capture_output=True,
        check=False,
    )
    assert verified.returncode == 0
    assert json.loads(verified.stdout) == {"stage": "verify-aggregate", "verified": True}
    bad = subprocess.run(command, input='{"raw_path":"C:/history"}', text=True, capture_output=True, check=False)
    assert bad.returncode == 2
    assert bad.stdout == ""
    assert bad.stderr == "RB-019 input rejected\n"
    with pytest.raises(RetroBotInputError):
        parse_input(payload + " ")


def test_canonical_digest_is_stable() -> None:
    aggregate = replay(_document())
    digest = hashlib.sha256(
        canonical_json({key: aggregate[key] for key in AGGREGATE_FIELDS if key != "aggregate_sha256"}).encode()
    ).hexdigest()
    assert digest == aggregate["aggregate_sha256"]


def test_golden_bid_ask_and_cost_accounting_vector() -> None:
    cycle = _parse_cycle(_cycle_one())
    pnl, quantities, traded = _cycle_accounting(cycle, Decimal("0.10000000"), Decimal("2.00000000"))
    assert pnl == Decimal("-0.374000000000000000")
    assert quantities == [
        Decimal("0.30000000"),
        Decimal("0.10000000"),
        Decimal("0.30000000"),
        Decimal("0.50000000"),
    ]
    assert traded == Decimal("1.20000000")


def test_scenario_cost_label_and_cycle_identity_are_bound() -> None:
    document = _document()
    document["scenario"]["scenario_id"] = "zero"
    document["scenario"]["fee_per_unit"] = "0.10000000"
    with pytest.raises(RetroBotInputError):
        replay(document)
    mismatched = _document()
    mismatched["scenario"]["fingerprint"] = "0" * 64
    with pytest.raises(RetroBotInputError):
        replay(mismatched)
    duplicate = _document()
    duplicate["cycles"].append(copy.deepcopy(duplicate["cycles"][0]))
    with pytest.raises(RetroBotInputError):
        replay(duplicate)
