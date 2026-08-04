"""RETRO-HIST-003 causal trigger and observed-sizing primitives."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
from typing import Callable, Iterable, Iterator, Mapping

from lxml import html
import pandas as pd

from .retro_hist_002 import (
    END_SERVER,
    FIXED8,
    MAX_QUANTITY,
    M5_FIREWALL,
    REPORT_MANIFEST_SHA256,
    START_SERVER,
    TICK_MANIFEST_SHA256,
    Position,
    RetroHistInputError,
    deduplicate_positions,
    verify_manifest,
)


CASE_ID = "RETRO-HIST-003"
CLOCK_IDS = ("utc_plus_2", "utc_plus_3")
CLOCK_OFFSETS = {"utc_plus_2": 2, "utc_plus_3": 3}
CANDIDATE_IDS = (
    "hold_only",
    "close_buy_increment_ge_0",
    "close_sell_increment_le_0",
    "close_buy_adverse_ge_10",
    "close_sell_adverse_ge_10",
    "rehedge_mirror_active_leg",
)
STATE_LABELS = (
    "FLAT",
    "ONE_BUY",
    "ONE_SELL",
    "HEDGED_1X1",
    "UNBALANCED_HEDGE",
    "MULTI_POSITION",
    "CENSORED",
)
OUTCOME_LABELS = ("hold", "action", "unsupported", "noneligible", "censored", "invalid")
SUPPORT_REASONS = ("supported", "empty_prefix", "no_anchor", "duplicate_timestamp", "invalid_row", "quote_gap", "state_ineligible")
ACTION_KINDS = ("CLOSE_BUY", "CLOSE_SELL", "OPEN_BUY", "OPEN_SELL")
QUANTITY_BANDS = ("0.01000000", "0.02000000", "0.05000000", "0.10000000", "0.20000000", "0.30000000", "1.00000000", "other")
ORACLE_KEYS = (
    "exact", "0-1s", "2-6s", "7-30s", "unmatched",
    "direction_match", "direction_mismatch", "quantity_match", "quantity_mismatch",
    "duplicate_label", "unmatched_label",
)
TOP_LEVEL_KEYS = (
    "schema_version", "case_id", "source_validation", "report_manifest_sha256",
    "tick_manifest_sha256", "population", "clocks", "candidate_ids",
    "support_counts", "outcome_counts", "action_counts", "quantity_bands",
    "oracle_diagnostics", "action_digests", "m5_firewall", "claims",
    "aggregate_sha256",
)
POPULATION_KEYS = ("start_server", "end_server_exclusive", "report_alias_count", "tick_alias_count", "tick_clock_scenarios")
CLOCK_KEYS = ("valid_rows", "invalid_rows", "duplicate_timestamps", "out_of_order", "crossed_quotes", "envelope_excluded_rows", "bootstrap_state")
CLAIM_KEYS = ("oracle_used_for_policy", "raw_rows_printed", "pnl_or_model_selection")
ACTION_RECORD_KEYS = ("candidate_id", "clock_id", "epoch", "decision_time_ns", "kind", "side", "quantity_fixed8")
ZERO = Decimal("0.00000000")
POINT = Decimal("0.01")
MAX_GAP_SECONDS = Decimal("6")
WINDOW_SECONDS = 60
MATCH_HORIZON_SECONDS = 30


def _report_text(cell) -> str:
    return " ".join(cell.text_content().split())


def load_positions_retro(report_paths: Mapping[str, Path]) -> tuple[list[Position], dict[str, int]]:
    """Parse only lifecycle position sections without touching frozen M5 parser code."""
    rows: list[dict[str, object]] = []
    for alias in sorted(report_paths):
        path = report_paths[alias]
        raw = path.read_bytes()
        text = raw.decode("utf-16") if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else raw.decode("utf-8")
        tree = html.fromstring(text)
        section = None
        seen_positions = False
        for row in tree.xpath("//tr"):
            cells = row.xpath("./th|./td")
            if not cells:
                continue
            heading = " ".join(_report_text(cell) for cell in cells).strip().lower()
            if heading in {"positions", "orders", "deals", "open positions"}:
                section = heading.replace(" ", "_")
                seen_positions = seen_positions or section == "positions"
                continue
            if section not in {"positions", "open_positions"}:
                continue
            values = [_report_text(cell) for cell in cells]
            if not values or not re.match(r"\d{4}\.\d{2}", values[0]):
                continue
            if section == "open_positions" and len(values) >= 12:
                rows.append({
                    "report_id": alias,
                    "position_id": values[1],
                    "symbol": values[2],
                    "side": values[3].lower(),
                    "volume": values[4],
                    "open_time": pd.to_datetime(values[0], format="%Y.%m.%d %H:%M:%S"),
                    "close_time": pd.NaT,
                })
            elif section == "positions" and len(values) >= 13:
                if len(values) == 14 and not values[4]:
                    values.pop(4)
                values = values[:13]
                rows.append({
                    "report_id": alias,
                    "position_id": values[1],
                    "symbol": values[2],
                    "side": values[3].lower(),
                    "volume": values[4],
                    "open_time": pd.to_datetime(values[0], format="%Y.%m.%d %H:%M:%S"),
                    "close_time": pd.to_datetime(values[8], format="%Y.%m.%d %H:%M:%S") if values[8] else pd.NaT,
                })
        if not seen_positions:
            raise RetroHistInputError("RH-003 report has no positions section")
    return deduplicate_positions(rows)


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def _utc(value: object) -> pd.Timestamp:
    try:
        timestamp = pd.Timestamp(value)
    except (TypeError, ValueError, pd.errors.OutOfBoundsDatetime) as error:
        raise RetroHistInputError("RH-003 timestamp is invalid") from error
    if pd.isna(timestamp):
        raise RetroHistInputError("RH-003 timestamp is invalid")
    return timestamp.tz_localize("UTC") if timestamp.tzinfo is None else timestamp.tz_convert("UTC")


def server_to_utc(value: object, clock_id: str) -> pd.Timestamp:
    if clock_id not in CLOCK_IDS:
        raise RetroHistInputError("RH-003 clock is invalid")
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        raise RetroHistInputError("RH-003 server timestamp must be naive")
    return timestamp.tz_localize("UTC") - pd.Timedelta(hours=CLOCK_OFFSETS[clock_id])


def _quantity(value: object, *, allow_zero: bool = False) -> Decimal:
    if isinstance(value, bool) or value is None:
        raise RetroHistInputError("RH-003 quantity is invalid")
    try:
        quantity = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise RetroHistInputError("RH-003 quantity is invalid") from None
    if not quantity.is_finite() or quantity < ZERO or quantity > MAX_QUANTITY or (quantity == ZERO and not allow_zero):
        raise RetroHistInputError("RH-003 quantity is outside bounds")
    if quantity.quantize(FIXED8) != quantity:
        raise RetroHistInputError("RH-003 quantity is not fixed8")
    rendered = format(quantity, "f")
    if "." not in rendered or len(rendered.rsplit(".", 1)[1]) != 8:
        raise RetroHistInputError("RH-003 quantity scale is not fixed8")
    return quantity


def quantity_band(quantity: Decimal) -> str:
    value = _quantity(quantity)
    rendered = format(value, "f")
    return rendered if rendered in QUANTITY_BANDS[:-1] else "other"


def _state_for_active(active: Mapping[str, Position]) -> tuple[str, Decimal, Decimal]:
    if any(item.censored for item in active.values()):
        return "CENSORED", ZERO, ZERO
    buys = [item for item in active.values() if item.side == "buy"]
    sells = [item for item in active.values() if item.side == "sell"]
    buy_quantity = sum((item.quantity for item in buys), ZERO)
    sell_quantity = sum((item.quantity for item in sells), ZERO)
    total = len(active)
    if total >= 2 and not (len(buys) == 1 and len(sells) == 1):
        return "MULTI_POSITION", buy_quantity, sell_quantity
    if total == 0:
        return "FLAT", ZERO, ZERO
    if total == 1:
        return ("ONE_BUY" if buys else "ONE_SELL"), buy_quantity, sell_quantity
    return ("HEDGED_1X1" if buy_quantity == sell_quantity else "UNBALANCED_HEDGE"), buy_quantity, sell_quantity


@dataclass(frozen=True)
class CausalState:
    state: str
    buy_quantity: Decimal = ZERO
    sell_quantity: Decimal = ZERO
    last_time_utc: pd.Timestamp | None = None
    epoch: int = 0

    def validate(self) -> None:
        if self.state not in STATE_LABELS:
            raise RetroHistInputError("RH-003 state is invalid")
        _quantity(self.buy_quantity, allow_zero=True)
        _quantity(self.sell_quantity, allow_zero=True)
        if self.state == "FLAT" and (self.buy_quantity != ZERO or self.sell_quantity != ZERO):
            raise RetroHistInputError("RH-003 flat state quantities are invalid")
        if self.state == "CENSORED" and (self.buy_quantity != ZERO or self.sell_quantity != ZERO):
            raise RetroHistInputError("RH-003 censored state quantities are invalid")
        if self.state == "ONE_BUY" and (self.buy_quantity <= ZERO or self.sell_quantity != ZERO):
            raise RetroHistInputError("RH-003 Buy-only state quantities are invalid")
        if self.state == "ONE_SELL" and (self.sell_quantity <= ZERO or self.buy_quantity != ZERO):
            raise RetroHistInputError("RH-003 Sell-only state quantities are invalid")
        if self.state == "HEDGED_1X1" and (self.buy_quantity <= ZERO or self.sell_quantity <= ZERO or self.buy_quantity != self.sell_quantity):
            raise RetroHistInputError("RH-003 hedged state quantities are invalid")
        if self.state == "UNBALANCED_HEDGE" and (self.buy_quantity <= ZERO or self.sell_quantity <= ZERO or self.buy_quantity == self.sell_quantity):
            raise RetroHistInputError("RH-003 unbalanced state quantities are invalid")
        if self.state == "MULTI_POSITION" and self.buy_quantity == ZERO and self.sell_quantity == ZERO:
            raise RetroHistInputError("RH-003 multi-position quantities are invalid")
        if type(self.epoch) is not int or self.epoch < 0:
            raise RetroHistInputError("RH-003 epoch is invalid")
        if self.last_time_utc is not None:
            _utc(self.last_time_utc)


def bootstrap_state(positions: Iterable[Position]) -> CausalState:
    active = {
        item.position_id: item
        for item in positions
        if item.open_time < START_SERVER and (item.close_time is None or item.close_time > START_SERVER)
    }
    state, buy_quantity, sell_quantity = _state_for_active(active)
    result = CausalState(state, buy_quantity, sell_quantity, None, 0)
    result.validate()
    return result


@dataclass(frozen=True)
class CausalTick:
    time_utc: pd.Timestamp
    bid: Decimal
    ask: Decimal
    duplicate_timestamp: bool = False
    invalid_reason: str | None = None

    def validate(self) -> None:
        timestamp = _utc(self.time_utc)
        if type(self.duplicate_timestamp) is not bool:
            raise RetroHistInputError("RH-003 duplicate flag is invalid")
        if self.invalid_reason is not None:
            if self.invalid_reason not in {"invalid_quote", "crossed_quote"}:
                raise RetroHistInputError("RH-003 invalid marker is invalid")
            return
        if self.bid <= ZERO or self.ask <= ZERO or self.ask < self.bid:
            raise RetroHistInputError("RH-003 quote is invalid")
        if not self.bid.is_finite() or not self.ask.is_finite():
            raise RetroHistInputError("RH-003 quote is invalid")
        _ = timestamp


@dataclass(frozen=True)
class FeatureSnapshot:
    decision_time_utc: pd.Timestamp
    clock_id: str
    state: str
    price_increment_points: Decimal | None
    buy_adverse_excursion_points: Decimal | None
    sell_adverse_excursion_points: Decimal | None
    spread_points: Decimal | None
    quote_gap_seconds: Decimal | None
    tick_count_60s: int
    support_status: str
    support_reason: str

    def validate(self) -> None:
        _utc(self.decision_time_utc)
        if self.clock_id not in CLOCK_IDS or self.state not in STATE_LABELS:
            raise RetroHistInputError("RH-003 snapshot identity is invalid")
        if self.support_status not in {"supported", "unsupported"} or self.support_reason not in SUPPORT_REASONS:
            raise RetroHistInputError("RH-003 snapshot support is invalid")
        if (self.support_status == "supported") != (self.support_reason == "supported"):
            raise RetroHistInputError("RH-003 snapshot support status/reason is inconsistent")
        if self.support_reason == "state_ineligible" and self.state in {"ONE_BUY", "ONE_SELL", "HEDGED_1X1", "UNBALANCED_HEDGE"}:
            raise RetroHistInputError("RH-003 state-ineligible snapshot state is invalid")
        if type(self.tick_count_60s) is not int or self.tick_count_60s < 0:
            raise RetroHistInputError("RH-003 tick count is invalid")
        for value in (self.price_increment_points, self.buy_adverse_excursion_points, self.sell_adverse_excursion_points, self.spread_points, self.quote_gap_seconds):
            if value is not None and (not isinstance(value, Decimal) or not value.is_finite()):
                raise RetroHistInputError("RH-003 feature value is invalid")
        for value in (self.buy_adverse_excursion_points, self.sell_adverse_excursion_points, self.spread_points, self.quote_gap_seconds):
            if value is not None and value < ZERO:
                raise RetroHistInputError("RH-003 feature value is negative")
        if self.support_status == "supported":
            if self.quote_gap_seconds is None or self.quote_gap_seconds > MAX_GAP_SECONDS:
                raise RetroHistInputError("RH-003 supported quote gap is invalid")
            if any(value is None for value in (self.price_increment_points, self.buy_adverse_excursion_points, self.sell_adverse_excursion_points, self.spread_points)):
                raise RetroHistInputError("RH-003 supported features are incomplete")
        elif self.support_reason == "quote_gap":
            if self.quote_gap_seconds is None or self.quote_gap_seconds <= MAX_GAP_SECONDS:
                raise RetroHistInputError("RH-003 unsupported quote gap is invalid")
        elif self.quote_gap_seconds is not None:
            raise RetroHistInputError("RH-003 unsupported quote gap is inconsistent")


def build_feature_snapshot(ticks: Iterable[CausalTick], decision_time_utc: object, *, clock_id: str, state: str) -> FeatureSnapshot:
    decision = _utc(decision_time_utc)
    parsed: list[CausalTick] = []
    previous_ns: int | None = None
    for item in ticks:
        if not isinstance(item, CausalTick):
            raise RetroHistInputError("RH-003 tick schema is invalid")
        item.validate()
        timestamp = _utc(item.time_utc)
        current_ns = int(timestamp.value)
        if timestamp > decision:
            raise RetroHistInputError("RH-003 future tick is not causal")
        if previous_ns is not None and current_ns < previous_ns:
            raise RetroHistInputError("RH-003 tick order decreased")
        previous_ns = current_ns
        if item.invalid_reason is not None:
            result = FeatureSnapshot(decision, clock_id, state, None, None, None, None, None, len(parsed), "unsupported", "invalid_row")
            result.validate()
            return result
        parsed.append(CausalTick(timestamp, item.bid, item.ask, item.duplicate_timestamp))
    if not parsed:
        result = FeatureSnapshot(decision, clock_id, state, None, None, None, None, None, 0, "unsupported", "empty_prefix")
        result.validate()
        return result
    anchor_cutoff = decision - pd.Timedelta(seconds=WINDOW_SECONDS)
    anchor_index = max((index for index, item in enumerate(parsed) if item.time_utc <= anchor_cutoff), default=None)
    if anchor_index is None:
        duplicate = any(
            item.duplicate_timestamp or parsed[index].time_utc == parsed[index - 1].time_utc
            for index, item in enumerate(parsed)
            if index > 0
        )
        reason = "duplicate_timestamp" if duplicate else "no_anchor"
        result = FeatureSnapshot(decision, clock_id, state, None, None, None, None, None, sum(item.time_utc >= anchor_cutoff for item in parsed), "unsupported", reason)
        result.validate()
        return result
    last = parsed[-1]
    window = parsed[anchor_index:]
    duplicate = window[0].duplicate_timestamp or (
        anchor_index > 0 and parsed[anchor_index - 1].time_utc == window[0].time_utc
    ) or any(
        item.duplicate_timestamp or window[index].time_utc == window[index - 1].time_utc
        for index, item in enumerate(window)
        if index > 0
    )
    if duplicate:
        result = FeatureSnapshot(decision, clock_id, state, None, None, None, None, None, len(window), "unsupported", "duplicate_timestamp")
        result.validate()
        return result
    gaps = [Decimal(int(window[index].time_utc.value - window[index - 1].time_utc.value)) / Decimal("1000000000") for index in range(1, len(window))]
    decision_gap = Decimal(int(decision.value - last.time_utc.value)) / Decimal("1000000000")
    quote_gap = max([decision_gap, *gaps])
    if quote_gap > MAX_GAP_SECONDS:
        result = FeatureSnapshot(decision, clock_id, state, None, None, None, None, quote_gap, sum(item.time_utc >= anchor_cutoff for item in parsed), "unsupported", "quote_gap")
        result.validate()
        return result
    mids = [(item.bid + item.ask) / Decimal("2") for item in window]
    anchor_mid = mids[0]
    last_mid = mids[-1]
    buy_adverse = max(ZERO, (anchor_mid - min(mids)) / POINT)
    sell_adverse = max(ZERO, (max(mids) - anchor_mid) / POINT)
    result = FeatureSnapshot(
        decision,
        clock_id,
        state,
        (last_mid - anchor_mid) / POINT,
        buy_adverse,
        sell_adverse,
        (last.ask - last.bid) / POINT,
        quote_gap,
        sum(item.time_utc >= anchor_cutoff for item in parsed),
        "supported",
        "supported",
    )
    result.validate()
    return result


@dataclass(frozen=True)
class CausalDecision:
    outcome: str
    candidate_id: str
    state: str
    decision_time_utc: pd.Timestamp
    action_kind: str | None = None
    side: str | None = None
    quantity: Decimal | None = None
    action_id: str | None = None
    clock_id: str = ""
    epoch: int = 0


def _action_record(candidate_id: str, clock_id: str, epoch: int, decision_time_utc: object, kind: str, side: str, quantity: Decimal) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "clock_id": clock_id,
        "epoch": epoch,
        "decision_time_ns": int(_utc(decision_time_utc).value),
        "kind": kind,
        "side": side,
        "quantity_fixed8": format(_quantity(quantity), "f"),
    }


def action_id(record: Mapping[str, object]) -> str:
    _validate_action_record(record)
    return hashlib.sha256(_canonical(record).encode("utf-8")).hexdigest()


def _validate_action_record(record: Mapping[str, object]) -> None:
    if not isinstance(record, Mapping) or tuple(record) != ACTION_RECORD_KEYS:
        raise RetroHistInputError("RH-003 action record schema is invalid")
    if type(record["candidate_id"]) is not str or record["candidate_id"] not in CANDIDATE_IDS:
        raise RetroHistInputError("RH-003 action record candidate is invalid")
    if type(record["clock_id"]) is not str or record["clock_id"] not in CLOCK_IDS:
        raise RetroHistInputError("RH-003 action record clock is invalid")
    if type(record["epoch"]) is not int or record["epoch"] < 0 or type(record["decision_time_ns"]) is not int:
        raise RetroHistInputError("RH-003 action record time is invalid")
    if type(record["kind"]) is not str or type(record["side"]) is not str or record["kind"] not in ACTION_KINDS or record["side"] not in {"buy", "sell"}:
        raise RetroHistInputError("RH-003 action record action is invalid")
    expected_side = {"CLOSE_BUY": "buy", "CLOSE_SELL": "sell", "OPEN_BUY": "buy", "OPEN_SELL": "sell"}[record["kind"]]
    if record["side"] != expected_side:
        raise RetroHistInputError("RH-003 action record side is inconsistent")
    if type(record["quantity_fixed8"]) is not str or format(_quantity(record["quantity_fixed8"]), "f") != record["quantity_fixed8"]:
        raise RetroHistInputError("RH-003 action record quantity is invalid")


def evaluate_candidate(state: CausalState, snapshot: FeatureSnapshot, candidate_id: str, *, validate: bool = True) -> CausalDecision:
    if type(validate) is not bool:
        raise RetroHistInputError("RH-003 validation flag is invalid")
    if validate:
        state.validate()
        snapshot.validate()
    if snapshot.state != state.state:
        raise RetroHistInputError("RH-003 snapshot state does not match policy state")
    if candidate_id not in CANDIDATE_IDS:
        return CausalDecision("invalid", candidate_id, state.state, snapshot.decision_time_utc)
    if state.last_time_utc is not None and snapshot.decision_time_utc <= _utc(state.last_time_utc):
        return CausalDecision("invalid", candidate_id, state.state, snapshot.decision_time_utc)
    if state.state == "CENSORED":
        return CausalDecision("censored", candidate_id, state.state, snapshot.decision_time_utc)
    if state.state not in {"ONE_BUY", "ONE_SELL", "HEDGED_1X1", "UNBALANCED_HEDGE"}:
        return CausalDecision("noneligible", candidate_id, state.state, snapshot.decision_time_utc)
    if snapshot.support_status != "supported":
        return CausalDecision("unsupported", candidate_id, state.state, snapshot.decision_time_utc)
    kind: str | None = None
    side: str | None = None
    quantity: Decimal | None = None
    if candidate_id == "rehedge_mirror_active_leg":
        if state.state == "ONE_BUY":
            kind, side, quantity = "OPEN_SELL", "sell", state.buy_quantity
        elif state.state == "ONE_SELL":
            kind, side, quantity = "OPEN_BUY", "buy", state.sell_quantity
    elif candidate_id == "close_buy_increment_ge_0" and state.state in {"HEDGED_1X1", "UNBALANCED_HEDGE"} and snapshot.price_increment_points is not None and snapshot.price_increment_points >= ZERO:
        kind, side, quantity = "CLOSE_BUY", "buy", state.buy_quantity
    elif candidate_id == "close_sell_increment_le_0" and state.state in {"HEDGED_1X1", "UNBALANCED_HEDGE"} and snapshot.price_increment_points is not None and snapshot.price_increment_points <= ZERO:
        kind, side, quantity = "CLOSE_SELL", "sell", state.sell_quantity
    elif candidate_id == "close_buy_adverse_ge_10" and state.state in {"HEDGED_1X1", "UNBALANCED_HEDGE"} and snapshot.buy_adverse_excursion_points is not None and snapshot.buy_adverse_excursion_points >= Decimal("10"):
        kind, side, quantity = "CLOSE_BUY", "buy", state.buy_quantity
    elif candidate_id == "close_sell_adverse_ge_10" and state.state in {"HEDGED_1X1", "UNBALANCED_HEDGE"} and snapshot.sell_adverse_excursion_points is not None and snapshot.sell_adverse_excursion_points >= Decimal("10"):
        kind, side, quantity = "CLOSE_SELL", "sell", state.sell_quantity
    if kind is None or side is None or quantity is None:
        return CausalDecision("hold", candidate_id, state.state, snapshot.decision_time_utc)
    record = _action_record(candidate_id, snapshot.clock_id, state.epoch, snapshot.decision_time_utc, kind, side, quantity)
    return CausalDecision("action", candidate_id, state.state, snapshot.decision_time_utc, kind, side, quantity, action_id(record), snapshot.clock_id, state.epoch)


def apply_decision(state: CausalState, decision: CausalDecision) -> CausalState:
    if decision.outcome != "action" or decision.action_kind not in ACTION_KINDS or decision.side not in {"buy", "sell"} or decision.quantity is None:
        raise RetroHistInputError("RH-003 decision is not an action")
    state.validate()
    quantity = _quantity(decision.quantity)
    decision_time = _utc(decision.decision_time_utc)
    expected_side = {"CLOSE_BUY": "buy", "CLOSE_SELL": "sell", "OPEN_BUY": "buy", "OPEN_SELL": "sell"}[decision.action_kind]
    if decision.state != state.state or decision.candidate_id not in CANDIDATE_IDS or decision.clock_id not in CLOCK_IDS or decision.epoch != state.epoch:
        raise RetroHistInputError("RH-003 action state metadata is invalid")
    expected_record = _action_record(decision.candidate_id, decision.clock_id, decision.epoch, decision_time, decision.action_kind, decision.side, quantity)
    if decision.side != expected_side or not isinstance(decision.action_id, str) or decision.action_id != action_id(expected_record):
        raise RetroHistInputError("RH-003 action metadata is invalid")
    if state.last_time_utc is not None and decision_time <= _utc(state.last_time_utc):
        raise RetroHistInputError("RH-003 action time is not increasing")
    buy, sell = state.buy_quantity, state.sell_quantity
    if decision.action_kind == "CLOSE_BUY":
        if state.state not in {"HEDGED_1X1", "UNBALANCED_HEDGE"} or buy != quantity:
            raise RetroHistInputError("RH-003 close Buy transition is invalid")
        buy = ZERO
    elif decision.action_kind == "CLOSE_SELL":
        if state.state not in {"HEDGED_1X1", "UNBALANCED_HEDGE"} or sell != quantity:
            raise RetroHistInputError("RH-003 close Sell transition is invalid")
        sell = ZERO
    elif decision.action_kind == "OPEN_BUY":
        if state.state != "ONE_SELL" or buy != ZERO or quantity != sell:
            raise RetroHistInputError("RH-003 open Buy transition is invalid")
        buy = quantity
    elif decision.action_kind == "OPEN_SELL":
        if state.state != "ONE_BUY" or sell != ZERO or quantity != buy:
            raise RetroHistInputError("RH-003 open Sell transition is invalid")
        sell = quantity
    else:
        raise RetroHistInputError("RH-003 action kind is invalid")
    if buy and sell:
        next_state = "HEDGED_1X1" if buy == sell else "UNBALANCED_HEDGE"
    elif buy:
        next_state = "ONE_BUY"
    elif sell:
        next_state = "ONE_SELL"
    else:
        next_state = "FLAT"
    result = CausalState(next_state, buy, sell, decision_time, state.epoch + 1)
    result.validate()
    return result


def action_digest(records: Iterable[Mapping[str, object]]) -> str:
    payloads = []
    for record in records:
        _validate_action_record(record)
        payloads.append(_canonical(dict(record)).encode("utf-8"))
    return hashlib.sha256(b"\n".join(payloads)).hexdigest()


@dataclass(frozen=True)
class OracleLabel:
    position_id: str
    kind: str
    side: str
    quantity: Decimal
    server_time: pd.Timestamp


def oracle_diagnostics(actions: Iterable[CausalDecision], labels: Iterable[OracleLabel], clock_id: str) -> dict[str, int]:
    counts = {key: 0 for key in ORACLE_KEYS}
    materialized = []
    for label in labels:
        if label.kind not in {"OPEN", "CLOSE"} or label.side not in {"buy", "sell"}:
            raise RetroHistInputError("RH-003 oracle label is invalid")
        materialized.append((server_to_utc(label.server_time, clock_id), label))
    materialized.sort(key=lambda item: (int(item[0].value), 0 if item[1].kind == "CLOSE" else 1, 0 if item[1].side == "buy" else 1, item[1].position_id))
    duplicate_keys = set()
    for index in range(1, len(materialized)):
        previous = materialized[index - 1]
        current = materialized[index]
        if (previous[0].value, previous[1].kind, previous[1].side, previous[1].position_id) == (current[0].value, current[1].kind, current[1].side, current[1].position_id):
            duplicate_keys.add((current[0].value, current[1].kind, current[1].side, current[1].position_id))
    counts["duplicate_label"] = len(duplicate_keys)
    used: set[int] = set()
    actions = sorted((item for item in actions if item.outcome == "action"), key=lambda item: (int(_utc(item.decision_time_utc).value), item.action_id or ""))
    for decision in actions:
        action_time = _utc(decision.decision_time_utc)
        candidates = []
        for index, (label_time, label) in enumerate(materialized):
            if index in used or label_time < action_time or label_time >= action_time + pd.Timedelta(seconds=MATCH_HORIZON_SECONDS):
                continue
            delta_ns = int(label_time.value - action_time.value)
            candidates.append((delta_ns, 0 if label.kind == "CLOSE" else 1, 0 if label.side == "buy" else 1, label.position_id, index, label))
        if not candidates:
            counts["unmatched"] += 1
            continue
        delta_ns, _, _, _, index, label = min(candidates)
        used.add(index)
        delta = Decimal(delta_ns) / Decimal("1000000000")
        if delta == ZERO:
            counts["exact"] += 1
        elif delta <= Decimal("1"):
            counts["0-1s"] += 1
        elif delta <= Decimal("6"):
            counts["2-6s"] += 1
        else:
            counts["7-30s"] += 1
        expected_kind = "CLOSE" if decision.action_kind.startswith("CLOSE") else "OPEN"
        expected_side = decision.side
        if label.kind == expected_kind and label.side == expected_side:
            counts["direction_match"] += 1
        else:
            counts["direction_mismatch"] += 1
        if label.quantity == decision.quantity:
            counts["quantity_match"] += 1
        else:
            counts["quantity_mismatch"] += 1
    counts["unmatched_label"] = len(materialized) - len(used)
    return counts


def _empty_state_map(factory):
    return {candidate: {clock: {state: factory() for state in STATE_LABELS} for clock in CLOCK_IDS} for candidate in CANDIDATE_IDS}


def _empty_reason_map():
    return {reason: 0 for reason in SUPPORT_REASONS}


def _empty_outcome_map():
    return {outcome: 0 for outcome in OUTCOME_LABELS}


def _empty_kind_map():
    return {kind: 0 for kind in ACTION_KINDS}


def _empty_quantity_map():
    return {band: 0 for band in QUANTITY_BANDS}


def _empty_oracle_map():
    return {key: 0 for key in ORACLE_KEYS}


def empty_aggregate_maps():
    return {
        "support_counts": _empty_state_map(_empty_reason_map),
        "outcome_counts": _empty_state_map(_empty_outcome_map),
        "action_counts": {candidate: {clock: _empty_kind_map() for clock in CLOCK_IDS} for candidate in CANDIDATE_IDS},
        "quantity_bands": {candidate: {clock: _empty_quantity_map() for clock in CLOCK_IDS} for candidate in CANDIDATE_IDS},
        "oracle_diagnostics": {candidate: {clock: _empty_oracle_map() for clock in CLOCK_IDS} for candidate in CANDIDATE_IDS},
    }


def _check_counts(value: object) -> None:
    if not isinstance(value, Mapping):
        raise RetroHistInputError("RH-003 aggregate count map is invalid")
    for nested in value.values():
        if isinstance(nested, Mapping):
            _check_counts(nested)
        elif type(nested) is not int or nested < 0:
            raise RetroHistInputError("RH-003 aggregate count value is invalid")


def _validate_fixed_shape(actual: object, expected: object, path: str) -> None:
    if isinstance(expected, Mapping):
        if not isinstance(actual, Mapping) or list(actual) != list(expected):
            raise RetroHistInputError(f"RH-003 aggregate dimension mismatch: {path}")
        for key in expected:
            _validate_fixed_shape(actual[key], expected[key], f"{path}.{key}")
        return
    if type(actual) is not int or actual < 0:
        raise RetroHistInputError(f"RH-003 aggregate count value is invalid: {path}")


def aggregate_trigger_results(*, clocks: Mapping[str, Mapping[str, object]], maps: Mapping[str, object], action_digests: Mapping[str, Mapping[str, str]], population: Mapping[str, object]) -> dict[str, object]:
    if set(clocks) != set(CLOCK_IDS) or set(action_digests) != set(CANDIDATE_IDS) or any(set(action_digests[candidate]) != set(CLOCK_IDS) for candidate in CANDIDATE_IDS):
        raise RetroHistInputError("RH-003 aggregate clock schema is invalid")
    for digest_map in action_digests.values():
        if any(not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value) for value in digest_map.values()):
            raise RetroHistInputError("RH-003 action digest is invalid")
    if set(maps) != {"support_counts", "outcome_counts", "action_counts", "quantity_bands", "oracle_diagnostics"}:
        raise RetroHistInputError("RH-003 aggregate maps are incomplete")
    if set(population) != {"start_server", "end_server_exclusive", "report_alias_count", "tick_alias_count", "tick_clock_scenarios"}:
        raise RetroHistInputError("RH-003 population schema is invalid")
    payload = {
        "schema_version": 1,
        "case_id": CASE_ID,
        "source_validation": "accepted_hash_verified_RETRO003_manifest_runs_all_objects",
        "report_manifest_sha256": REPORT_MANIFEST_SHA256,
        "tick_manifest_sha256": TICK_MANIFEST_SHA256,
        "population": dict(population),
        "clocks": {clock: dict(clocks[clock]) for clock in CLOCK_IDS},
        "candidate_ids": list(CANDIDATE_IDS),
        "support_counts": maps["support_counts"],
        "outcome_counts": maps["outcome_counts"],
        "action_counts": maps["action_counts"],
        "quantity_bands": maps["quantity_bands"],
        "oracle_diagnostics": maps["oracle_diagnostics"],
        "action_digests": {candidate: dict(action_digests[candidate]) for candidate in CANDIDATE_IDS},
        "m5_firewall": M5_FIREWALL,
        "claims": {"oracle_used_for_policy": False, "raw_rows_printed": False, "pnl_or_model_selection": False},
    }
    for name in ("support_counts", "outcome_counts", "action_counts", "quantity_bands", "oracle_diagnostics"):
        _check_counts(payload[name])
    payload["aggregate_sha256"] = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    validate_aggregate(payload)
    return payload


def validate_aggregate(payload: Mapping[str, object]) -> None:
    if not isinstance(payload, Mapping) or list(payload) != list(TOP_LEVEL_KEYS) or type(payload.get("schema_version")) is not int or payload.get("schema_version") != 1 or payload.get("case_id") != CASE_ID or payload.get("source_validation") != "accepted_hash_verified_RETRO003_manifest_runs_all_objects" or payload.get("m5_firewall") != M5_FIREWALL:
        raise RetroHistInputError("RH-003 aggregate schema/firewall mismatch")
    if payload.get("report_manifest_sha256") != REPORT_MANIFEST_SHA256 or payload.get("tick_manifest_sha256") != TICK_MANIFEST_SHA256 or payload.get("candidate_ids") != list(CANDIDATE_IDS):
        raise RetroHistInputError("RH-003 aggregate provenance mismatch")
    population = payload.get("population")
    if not isinstance(population, Mapping) or list(population) != list(POPULATION_KEYS) or population.get("start_server") != "2025-11-01 00:00:00" or population.get("end_server_exclusive") != "2026-07-31 00:00:00" or type(population.get("report_alias_count")) is not int or population.get("report_alias_count") != 9 or type(population.get("tick_alias_count")) is not int or population.get("tick_alias_count") != 39 or population.get("tick_clock_scenarios") != list(CLOCK_IDS):
        raise RetroHistInputError("RH-003 population schema mismatch")
    clocks = payload.get("clocks")
    if not isinstance(clocks, Mapping) or list(clocks) != list(CLOCK_IDS) or any(not isinstance(clocks[clock], Mapping) or list(clocks[clock]) != list(CLOCK_KEYS) for clock in CLOCK_IDS):
        raise RetroHistInputError("RH-003 clock schema mismatch")
    for clock in CLOCK_IDS:
        if any(type(clocks[clock][key]) is not int or clocks[clock][key] < 0 for key in CLOCK_KEYS[:-1]) or type(clocks[clock]["bootstrap_state"]) is not str or clocks[clock]["bootstrap_state"] not in STATE_LABELS:
            raise RetroHistInputError("RH-003 clock value is invalid")
    claims = payload.get("claims")
    if not isinstance(claims, Mapping) or list(claims) != list(CLAIM_KEYS) or any(type(claims[key]) is not bool or claims[key] is not False for key in CLAIM_KEYS):
        raise RetroHistInputError("RH-003 claims/firewall mismatch")
    action_digests = payload.get("action_digests")
    if not isinstance(action_digests, Mapping) or list(action_digests) != list(CANDIDATE_IDS) or any(not isinstance(action_digests[candidate], Mapping) or list(action_digests[candidate]) != list(CLOCK_IDS) for candidate in CANDIDATE_IDS):
        raise RetroHistInputError("RH-003 action digest schema mismatch")
    for digest_map in action_digests.values():
        if any(not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value) for value in digest_map.values()):
            raise RetroHistInputError("RH-003 action digest is invalid")
    expected_maps = empty_aggregate_maps()
    for name, expected_map in expected_maps.items():
        _validate_fixed_shape(payload.get(name), expected_map, name)
    expected_digest = hashlib.sha256(_canonical({key: value for key, value in payload.items() if key != "aggregate_sha256"}).encode("utf-8")).hexdigest()
    if payload.get("aggregate_sha256") != expected_digest:
        raise RetroHistInputError("RH-003 aggregate digest mismatch")


def iter_ticks_decimal(path: Path, *, broad_start: pd.Timestamp, broad_end: pd.Timestamp, previous_ns: int | None = None, invalid_timestamp_callback: Callable[[], None] | None = None) -> tuple[Iterator[CausalTick], dict[str, int]]:
    stats = {"valid_rows": 0, "invalid_rows": 0, "invalid_timestamp_rows": 0, "duplicate_timestamps": 0, "out_of_order": 0, "crossed_quotes": 0, "envelope_excluded_rows": 0, "last_time_ns": previous_ns}

    def generator() -> Iterator[CausalTick]:
        nonlocal previous_ns
        for chunk in pd.read_csv(path, usecols=["time_utc", "bid", "ask"], dtype=str, keep_default_na=False, chunksize=250_000):
            timestamps = pd.to_datetime(chunk["time_utc"], utc=True, errors="coerce")
            for timestamp, raw_bid, raw_ask in zip(timestamps, chunk["bid"], chunk["ask"]):
                if pd.isna(timestamp):
                    stats["invalid_rows"] += 1
                    stats["invalid_timestamp_rows"] += 1
                    if invalid_timestamp_callback is not None:
                        invalid_timestamp_callback()
                    continue
                current_ns = int(timestamp.value)
                duplicate = previous_ns == current_ns
                if previous_ns is not None and current_ns < previous_ns:
                    stats["out_of_order"] += 1
                    raise RetroHistInputError("RH-003 tick timestamp order decreased")
                if duplicate:
                    stats["duplicate_timestamps"] += 1
                previous_ns = current_ns
                stats["last_time_ns"] = current_ns
                try:
                    bid = Decimal(raw_bid)
                    ask = Decimal(raw_ask)
                except (InvalidOperation, TypeError, ValueError):
                    stats["invalid_rows"] += 1
                    if broad_start <= timestamp < broad_end:
                        yield CausalTick(timestamp, ZERO, ZERO, duplicate, "invalid_quote")
                    else:
                        stats["envelope_excluded_rows"] += 1
                    continue
                if not bid.is_finite() or not ask.is_finite() or bid <= ZERO or ask <= ZERO:
                    stats["invalid_rows"] += 1
                    if broad_start <= timestamp < broad_end:
                        yield CausalTick(timestamp, ZERO, ZERO, duplicate, "invalid_quote")
                    else:
                        stats["envelope_excluded_rows"] += 1
                    continue
                if ask < bid:
                    stats["crossed_quotes"] += 1
                    if broad_start <= timestamp < broad_end:
                        yield CausalTick(timestamp, ZERO, ZERO, duplicate, "crossed_quote")
                    else:
                        stats["envelope_excluded_rows"] += 1
                    continue
                if timestamp < broad_start or timestamp >= broad_end:
                    stats["envelope_excluded_rows"] += 1
                    continue
                stats["valid_rows"] += 1
                yield CausalTick(timestamp, bid, ask, duplicate)

    return generator(), stats
