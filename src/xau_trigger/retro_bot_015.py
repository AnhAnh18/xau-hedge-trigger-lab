"""RB-019 typed variable-lot offline paper bot."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, getcontext
import hashlib
import json
import math
import re
from typing import IO, Mapping

from .retro_bot import RetroBotInputError
from .retro_bot_012 import load_json_no_duplicates

getcontext().prec = 50

RB019_ID = "RB-019"
SCHEMA_VERSION = 1
AUTHORIZATION = "RB019_TYPED_VARIABLE_LOT_AUTHORIZED"
M5_FIREWALL = "M5_FIREWALL_ATTESTATION_V1"
ROOT_FIELDS = ("schema_version", "case_id", "attestation", "scenario", "cycles")
VERIFY_FIELDS = ROOT_FIELDS + ("aggregate",)
ATTESTATION_FIELDS = ("schema_version", "authorization", "source_kind", "m5_firewall", "live_execution")
SCENARIO_FIELDS = ("scenario_id", "fee_per_unit", "slippage_points", "fingerprint")
CYCLE_FIELDS = ("cycle_id", "start_state", "initial", "initial_quote", "events", "terminal_quote")
INITIAL_FIELDS = ("buy_quantity", "sell_quantity")
QUOTE_FIELDS = ("bid", "ask")
EVENT_FIELDS = ("kind", "time_ns", "bid", "ask", "quantity")
AGGREGATE_FIELDS = (
    "schema_version", "case_id", "scenario_id", "scenario_fingerprint",
    "cycle_count", "marked_count",
    "invalid_count", "loss_count", "flat_count", "gain_count",
    "quantity_min_fixed8", "quantity_max_fixed8",
    "traded_quantity_total_fixed8", "aggregate_sha256",
)
STATES = {"HEDGED", "ONE_BUY", "ONE_SELL"}
KINDS = {"CLOSE_BUY", "CLOSE_SELL", "OPEN_BUY", "OPEN_SELL"}
FIXED8 = re.compile(r"^(0|[1-9][0-9]*)\.[0-9]{8}$")
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
ZERO = Decimal("0")
ONE_CENT = Decimal("0.01")
QUANT = Decimal("0.00000001")
FORBIDDEN = ("password", "credential", "secret", "journal", "ticket", ".ex5", "raw", "private", "mt5", "network", "subprocess", "order", "path")


class InvalidCycle(Exception):
    """A semantically invalid typed cycle, counted without retaining detail."""


def canonical_json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=False, allow_nan=False)
    except (TypeError, ValueError, OverflowError) as error:
        raise RetroBotInputError("RB-019 canonical JSON is invalid") from error


def _sha(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _fields(value: object, expected: tuple[str, ...], message: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or tuple(value.keys()) != expected:
        raise RetroBotInputError(message)
    return value


def _firewall(value: object, *, key: str = "") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise RetroBotInputError("RB-019 non-finite value")
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                raise RetroBotInputError("RB-019 invalid key")
            folded = raw_key.casefold()
            if folded != "live_execution" and any(token in folded for token in FORBIDDEN):
                raise RetroBotInputError("RB-019 privacy/firewall violation")
            _firewall(item, key=folded)
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _firewall(item, key=key)
        return
    if isinstance(value, str):
        if value == M5_FIREWALL:
            return
        folded = value.casefold()
        if any(token in folded for token in FORBIDDEN) or "m5" in folded or "live" in folded:
            raise RetroBotInputError("RB-019 privacy/firewall violation")
        if "/" in value or "\\" in value or ":" in value:
            raise RetroBotInputError("RB-019 path-like value")


def _fixed(value: object, *, maximum: Decimal, positive: bool = False) -> Decimal:
    if not isinstance(value, str) or not FIXED8.fullmatch(value):
        raise RetroBotInputError("RB-019 fixed8 value is invalid")
    try:
        parsed = Decimal(value)
    except (InvalidOperation, ValueError) as error:
        raise RetroBotInputError("RB-019 fixed8 value is invalid") from error
    if parsed < ZERO or parsed > maximum or (positive and parsed <= ZERO):
        raise RetroBotInputError("RB-019 fixed8 bound is invalid")
    return parsed


def _quantity(value: object, *, positive: bool = False) -> Decimal:
    return _fixed(value, maximum=Decimal("1000.00000000"), positive=positive)


def _price(value: object) -> Decimal:
    return _fixed(value, maximum=Decimal("10000000.00000000"), positive=True)


def _time(value: object) -> int:
    if type(value) is not int or value < 0:
        raise RetroBotInputError("RB-019 time is invalid")
    return value


def _quote(value: object) -> tuple[Decimal, Decimal]:
    item = _fields(value, QUOTE_FIELDS, "RB-019 quote schema is invalid")
    bid, ask = _price(item["bid"]), _price(item["ask"])
    if ask < bid:
        raise RetroBotInputError("RB-019 quote ordering is invalid")
    return bid, ask


def _event_quote(value: Mapping[str, object]) -> tuple[Decimal, Decimal]:
    """Validate the quote fields embedded in an event without changing its schema."""
    bid, ask = _price(value["bid"]), _price(value["ask"])
    if ask < bid:
        raise RetroBotInputError("RB-019 quote ordering is invalid")
    return bid, ask


def _cost(quantity: Decimal, fee: Decimal, slippage: Decimal) -> Decimal:
    return fee * quantity + ONE_CENT * slippage * quantity


def _validate_attestation(value: object) -> Mapping[str, object]:
    item = _fields(value, ATTESTATION_FIELDS, "RB-019 attestation schema is invalid")
    if (
        type(item["schema_version"]) is not int or item["schema_version"] != 1
        or item["authorization"] != AUTHORIZATION
        or item["source_kind"] != "typed-redacted"
        or item["m5_firewall"] != M5_FIREWALL
        or type(item["live_execution"]) is not bool or item["live_execution"] is not False
    ):
        raise RetroBotInputError("RB-019 attestation is invalid")
    return item


def _validate_scenario(value: object) -> tuple[Mapping[str, object], Decimal, Decimal]:
    item = _fields(value, SCENARIO_FIELDS, "RB-019 scenario schema is invalid")
    if item["scenario_id"] not in {"zero", "spread_slippage"}:
        raise RetroBotInputError("RB-019 scenario id is invalid")
    fee = _fixed(item["fee_per_unit"], maximum=Decimal("1000.00000000"))
    slippage = _fixed(item["slippage_points"], maximum=Decimal("1000.00000000"))
    if item["scenario_id"] == "zero" and (fee != ZERO or slippage != ZERO):
        raise RetroBotInputError("RB-019 zero scenario costs are invalid")
    expected = _sha({key: item[key] for key in SCENARIO_FIELDS[:3]})
    if not isinstance(item["fingerprint"], str) or not re.fullmatch(r"^[0-9a-f]{64}$", item["fingerprint"]):
        raise RetroBotInputError("RB-019 scenario fingerprint is invalid")
    if item["fingerprint"] != expected:
        raise RetroBotInputError("RB-019 scenario fingerprint mismatch")
    return item, fee, slippage


def _parse_cycle(value: object) -> Mapping[str, object]:
    item = _fields(value, CYCLE_FIELDS, "RB-019 cycle schema is invalid")
    if not isinstance(item["cycle_id"], str) or not ID_RE.fullmatch(item["cycle_id"]):
        raise RetroBotInputError("RB-019 cycle id is invalid")
    if item["start_state"] not in STATES:
        raise RetroBotInputError("RB-019 state is invalid")
    initial = _fields(item["initial"], INITIAL_FIELDS, "RB-019 initial schema is invalid")
    buy, sell = _quantity(initial["buy_quantity"]), _quantity(initial["sell_quantity"])
    if item["start_state"] == "HEDGED" and (buy <= ZERO or sell <= ZERO):
        raise RetroBotInputError("RB-019 HEDGED quantity is invalid")
    if item["start_state"] == "ONE_BUY" and (buy <= ZERO or sell != ZERO):
        raise RetroBotInputError("RB-019 ONE_BUY quantity is invalid")
    if item["start_state"] == "ONE_SELL" and (sell <= ZERO or buy != ZERO):
        raise RetroBotInputError("RB-019 ONE_SELL quantity is invalid")
    _quote(item["initial_quote"])
    events = item["events"]
    if not isinstance(events, list) or len(events) > 16:
        raise RetroBotInputError("RB-019 event list is invalid")
    for event in events:
        parsed = _fields(event, EVENT_FIELDS, "RB-019 event schema is invalid")
        if parsed["kind"] not in KINDS:
            raise RetroBotInputError("RB-019 event kind is invalid")
        _time(parsed["time_ns"])
        _event_quote(parsed)
        _quantity(parsed["quantity"], positive=True)
    _quote(item["terminal_quote"])
    return item


def _cycle_accounting(item: Mapping[str, object], fee: Decimal, slippage: Decimal) -> tuple[Decimal, list[Decimal], Decimal]:
    state = item["start_state"]
    initial = item["initial"]
    buy = _quantity(initial["buy_quantity"])
    sell = _quantity(initial["sell_quantity"])
    initial_bid, initial_ask = _quote(item["initial_quote"])
    cash = -initial_ask * buy + initial_bid * sell
    traded = ZERO
    quantities = [quantity for quantity in (buy, sell) if quantity > ZERO]
    for quantity in quantities:
        traded += quantity
        cash -= _cost(quantity, fee, slippage)
    last_time = -1
    seen: set[tuple[int, str]] = set()
    for raw in item["events"]:
        event = _fields(raw, EVENT_FIELDS, "RB-019 event schema is invalid")
        kind = event["kind"]
        time_ns = _time(event["time_ns"])
        bid, ask = _event_quote(event)
        quantity = _quantity(event["quantity"], positive=True)
        if time_ns <= last_time or (time_ns, kind) in seen:
            raise InvalidCycle
        last_time = time_ns
        seen.add((time_ns, kind))
        quantities.append(quantity)
        traded += quantity
        cash -= _cost(quantity, fee, slippage)
        if state == "HEDGED" and kind == "CLOSE_BUY" and quantity == buy:
            cash += bid * quantity
            buy, state = ZERO, "ONE_SELL"
        elif state == "HEDGED" and kind == "CLOSE_SELL" and quantity == sell:
            cash -= ask * quantity
            sell, state = ZERO, "ONE_BUY"
        elif state == "ONE_BUY" and kind == "OPEN_SELL" and sell == ZERO:
            cash += bid * quantity
            sell, state = quantity, "HEDGED"
        elif state == "ONE_SELL" and kind == "OPEN_BUY" and buy == ZERO:
            cash -= ask * quantity
            buy, state = quantity, "HEDGED"
        else:
            raise InvalidCycle
    terminal_bid, terminal_ask = _quote(item["terminal_quote"])
    pnl = cash + terminal_bid * buy - terminal_ask * sell
    return pnl, quantities, traded


def _format(value: Decimal) -> str:
    return format(value.quantize(QUANT, rounding=ROUND_HALF_EVEN), "f")


def replay(document: Mapping[str, object]) -> dict[str, object]:
    _firewall(document)
    root = _fields(document, ROOT_FIELDS, "RB-019 root schema is invalid")
    if type(root["schema_version"]) is not int or root["schema_version"] != 1 or root["case_id"] != RB019_ID:
        raise RetroBotInputError("RB-019 root is invalid")
    _validate_attestation(root["attestation"])
    scenario, fee, slippage = _validate_scenario(root["scenario"])
    cycles = root["cycles"]
    if not isinstance(cycles, list) or not cycles:
        raise RetroBotInputError("RB-019 cycles are invalid")
    valid = invalid = loss = flat = gain = 0
    all_quantities: list[Decimal] = []
    traded_total = ZERO
    cycle_ids: set[str] = set()
    for raw in cycles:
        item = _parse_cycle(raw)
        if item["cycle_id"] in cycle_ids:
            raise RetroBotInputError("RB-019 duplicate cycle id")
        cycle_ids.add(item["cycle_id"])
        try:
            pnl, quantities, traded = _cycle_accounting(item, fee, slippage)
        except InvalidCycle:
            invalid += 1
            continue
        valid += 1
        all_quantities.extend(quantity for quantity in quantities if quantity > ZERO)
        traded_total += traded
        if pnl < ZERO:
            loss += 1
        elif pnl > ZERO:
            gain += 1
        else:
            flat += 1
    if valid == 0:
        raise RetroBotInputError("RB-019 no valid cycles")
    aggregate: dict[str, object] = {
        "schema_version": 1,
        "case_id": RB019_ID,
        "scenario_id": scenario["scenario_id"],
        "scenario_fingerprint": scenario["fingerprint"],
        "cycle_count": len(cycles),
        "marked_count": valid,
        "invalid_count": invalid,
        "loss_count": loss,
        "flat_count": flat,
        "gain_count": gain,
        "quantity_min_fixed8": _format(min(all_quantities)),
        "quantity_max_fixed8": _format(max(all_quantities)),
        "traded_quantity_total_fixed8": _format(traded_total),
        "aggregate_sha256": "TO_BE_FILLED",
    }
    aggregate["aggregate_sha256"] = _sha({key: aggregate[key] for key in AGGREGATE_FIELDS if key != "aggregate_sha256"})
    return aggregate


def _validate_aggregate(value: object) -> Mapping[str, object]:
    item = _fields(value, AGGREGATE_FIELDS, "RB-019 aggregate schema is invalid")
    if type(item["schema_version"]) is not int or item["schema_version"] != 1 or item["case_id"] != RB019_ID:
        raise RetroBotInputError("RB-019 aggregate literals are invalid")
    for key in ("cycle_count", "marked_count", "invalid_count", "loss_count", "flat_count", "gain_count"):
        if type(item[key]) is not int or item[key] < 0:
            raise RetroBotInputError("RB-019 aggregate counts are invalid")
    for key in ("quantity_min_fixed8", "quantity_max_fixed8", "traded_quantity_total_fixed8"):
        _fixed(item[key], maximum=Decimal("1000000000.00000000"))
    if not isinstance(item["scenario_fingerprint"], str) or not re.fullmatch(r"^[0-9a-f]{64}$", item["scenario_fingerprint"]):
        raise RetroBotInputError("RB-019 scenario fingerprint is invalid")
    if not isinstance(item["aggregate_sha256"], str) or not re.fullmatch(r"^[0-9a-f]{64}$", item["aggregate_sha256"]):
        raise RetroBotInputError("RB-019 aggregate digest is invalid")
    expected = _sha({key: item[key] for key in AGGREGATE_FIELDS if key != "aggregate_sha256"})
    if item["aggregate_sha256"] != expected:
        raise RetroBotInputError("RB-019 aggregate digest mismatch")
    return item


def verify_aggregate(document: Mapping[str, object]) -> bool:
    _firewall(document)
    root = _fields(document, VERIFY_FIELDS, "RB-019 verify schema is invalid")
    expected = replay({key: root[key] for key in ROOT_FIELDS})
    supplied = _validate_aggregate(root["aggregate"])
    if canonical_json(expected) != canonical_json(supplied):
        raise RetroBotInputError("RB-019 aggregate mismatch")
    return True


def parse_input(stream: IO[str] | str) -> object:
    try:
        text = stream if isinstance(stream, str) else stream.read()
        if not isinstance(text, str) or text != text.rstrip():
            raise RetroBotInputError("RB-019 trailing bytes")
        value = load_json_no_duplicates(text)
        _firewall(value)
        return value
    except RetroBotInputError:
        raise
    except Exception as error:
        raise RetroBotInputError("RB-019 input rejected") from error


__all__ = ["replay", "verify_aggregate", "parse_input", "canonical_json", "AGGREGATE_FIELDS"]
