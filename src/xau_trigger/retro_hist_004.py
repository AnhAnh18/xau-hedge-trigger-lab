"""RETRO-HIST-004 typed observed-lot paper accounting primitives."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .retro_hist_002 import RetroHistInputError


CASE_ID = "RETRO-HIST-004"
SCHEMA_VERSION = 1
ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "docs" / "retro_bot" / "RETRO-HIST-004-contract.md"
SOURCE_RECEIPT_PATH = ROOT / "docs" / "retro_bot" / "RETRO-HIST-004-source-receipt.md"
CONTRACT_SHA256 = "f3a20298cea7e01844f6a349906ea92ab9dd494cd8a3fd5a48820a562dbcb1bc"
SOURCE_RECEIPT_SHA256 = "3611ee393cb00d71f4d1d05d546ab7c999d4e16de389ef012a1e7d7589f1e7f3"
FIXED8 = Decimal("0.00000001")
POINT = Decimal("0.01")
ZERO = Decimal("0.00000000")
MAX_QUANTITY = Decimal("1000.00000000")
MAX_PRICE = Decimal("10000000.00000000")
M5_FIREWALL = "M5_FIREWALL_ATTESTATION_V1"
SCENARIO_IDS = ("zero_cost", "fixed_fee", "per_lot_fee", "spread_slippage", "latency_slippage")
STATES = ("FLAT", "ONE_BUY", "ONE_SELL", "HEDGED_1X1", "UNBALANCED_HEDGE", "MULTI_POSITION", "CENSORED")
ACTION_KINDS = ("CLOSE_BUY", "CLOSE_SELL", "OPEN_BUY", "OPEN_SELL")
STATUSES = ("no_action", "accounted_action", "unsupported", "invalid", "censored")
QUANTITY_BANDS = ("0.01000000", "0.02000000", "0.05000000", "0.10000000", "0.20000000", "0.30000000", "1.00000000", "other")
LATENCY_BANDS = ("zero", "0-1s", "2-6s", "7-30s", "unsupported")
POPULATION_KEYS = ("start_server", "end_server_exclusive", "report_alias_count", "tick_alias_count", "tick_clock_scenarios")
POLICY_CANDIDATES = (
    "hold_only", "close_buy_increment_ge_0", "close_sell_increment_le_0",
    "close_buy_adverse_ge_10", "close_sell_adverse_ge_10",
    "rehedge_mirror_active_leg",
)
CLOCK_IDS = ("utc_plus_2", "utc_plus_3")
REPORT_MANIFEST_SHA256 = "88a5c98f919dad69da3eb97fba8bc2c8fd878fc2b3ce8d02011ea268d9642f30"
TICK_MANIFEST_SHA256 = "a9350b541ba0138b6d86b5ce013ad9e7ddb83cde9d7742e2d3d7deb2c38a1f0c"
TOP_LEVEL_KEYS = (
    "schema_version", "case_id", "source_validation", "report_manifest_sha256",
    "tick_manifest_sha256", "contract_sha256", "source_receipt_sha256", "population", "scenario_ids", "bootstrap_state",
    "state_counts", "action_counts", "accounting_counts", "quantity_bands",
    "latency_bands", "cost_fingerprints", "conservation", "policy_action_digests",
    "accounting_digests", "m5_firewall", "claims", "aggregate_sha256",
)
CLAIM_KEYS = ("oracle_used_for_policy", "raw_rows_printed", "pnl_or_model_selection", "live_execution")
SCENARIO_FIELDS = ("scenario_id", "fee_per_unit", "slippage_points", "latency_ns", "margin_reserve")
ACTION_FIELDS = ("kind", "side", "quantity_fixed8", "decision_time_ns", "action_id")
_FIXED8_RE = re.compile(r"^(0|[1-9][0-9]*)\.[0-9]{8}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_DIMENSION_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_PRIVATE_TOKEN_RE = re.compile(
    r"(?:raw|ticket|credential|password|secret|position[_ -]?id|journal|cache|terminal|deal|commission|swap|profit|\.ex5)",
    re.IGNORECASE,
)
_STRUCTURAL_KEYS = set(TOP_LEVEL_KEYS) | set(CLAIM_KEYS) | {
    *STATES, *ACTION_KINDS, *STATUSES, *QUANTITY_BANDS, *LATENCY_BANDS,
    *SCENARIO_IDS, "opened", "closed", "ending", "censored", "failures",
    "hold_only", "close_buy_increment_ge_0", "close_sell_increment_le_0",
    "close_buy_adverse_ge_10", "close_sell_adverse_ge_10", "rehedge_mirror_active_leg",
    "utc_plus_2", "utc_plus_3",
    "start_server", "end_server_exclusive", "report_alias_count", "tick_alias_count",
    "tick_clock_scenarios", "scenario_id", "fee_per_unit", "slippage_points", "latency_ns", "margin_reserve",
}
_PATHLIKE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.+-]*:[^ ]+$")


@dataclass(frozen=True)
class Quote:
    time_ns: int
    bid: Decimal
    ask: Decimal
    duplicate: bool = False
    invalid_reason: str | None = None


@dataclass(frozen=True)
class PaperAction:
    kind: str
    quantity: Decimal
    decision_time_ns: int
    action_id: str = ""


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    fee_per_unit: Decimal
    slippage_points: Decimal
    latency_ns: int
    margin_reserve: Decimal

    def payload(self) -> dict[str, object]:
        return {
            "scenario_id": self.scenario_id,
            "fee_per_unit": _fixed8(self.fee_per_unit),
            "slippage_points": _fixed8(self.slippage_points),
            "latency_ns": self.latency_ns,
            "margin_reserve": _fixed8(self.margin_reserve),
        }

    def fingerprint(self) -> str:
        return _sha(self.payload())


@dataclass(frozen=True)
class AccountingResult:
    status: str
    realized_price_units: Decimal
    unrealized_price_units: Decimal
    costs_price_units: Decimal
    margin_reserve: Decimal
    opened_buy: Decimal
    opened_sell: Decimal
    closed_buy: Decimal
    closed_sell: Decimal
    ending_buy: Decimal
    ending_sell: Decimal
    censored_quantity: Decimal
    selected_latency_ns: int | None
    action_count: int


def _canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False)


def _sha(value: object) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _governance_hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise RetroHistInputError("RH-004 governance artifact is unavailable") from error


def verify_governance_artifacts() -> tuple[str, str]:
    contract_sha = _governance_hash(CONTRACT_PATH)
    receipt_sha = _governance_hash(SOURCE_RECEIPT_PATH)
    if contract_sha != CONTRACT_SHA256 or receipt_sha != SOURCE_RECEIPT_SHA256:
        raise RetroHistInputError("RH-004 governance artifact hash mismatch")
    return contract_sha, receipt_sha


def _fixed8(value: object, *, allow_zero: bool = True) -> str:
    if isinstance(value, bool) or value is None or not isinstance(value, (str, Decimal)):
        raise RetroHistInputError("RH-004 fixed8 value is invalid")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise RetroHistInputError("RH-004 fixed8 value is invalid") from None
    if isinstance(value, str):
        # Do not let Decimal quantize hide lexical overprecision (including
        # trailing zeroes such as ``1.000000000``).
        raw = value.strip()
        if not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", raw):
            raise RetroHistInputError("RH-004 fixed8 format is invalid")
        if "." in raw and len(raw.split(".", 1)[1]) > 8:
            raise RetroHistInputError("RH-004 fixed8 precision is invalid")
    if not parsed.is_finite() or parsed < ZERO or (parsed == ZERO and not allow_zero) or parsed > MAX_QUANTITY:
        raise RetroHistInputError("RH-004 fixed8 value is outside bounds")
    if parsed.as_tuple().exponent < -8 or parsed.quantize(FIXED8) != parsed:
        raise RetroHistInputError("RH-004 fixed8 precision is invalid")
    rendered = format(parsed.quantize(FIXED8, rounding=ROUND_HALF_EVEN), "f")
    if not _FIXED8_RE.fullmatch(rendered):
        raise RetroHistInputError("RH-004 fixed8 format is invalid")
    return rendered


def _amount8(value: Decimal) -> str:
    if not value.is_finite():
        raise RetroHistInputError("RH-004 amount is invalid")
    rendered = format(value.quantize(FIXED8, rounding=ROUND_HALF_EVEN), "f")
    if not re.fullmatch(r"-?(0|[1-9][0-9]*)\.[0-9]{8}", rendered):
        raise RetroHistInputError("RH-004 amount format is invalid")
    return rendered


def parse_quantity(value: object, *, allow_zero: bool = True) -> Decimal:
    return Decimal(_fixed8(value, allow_zero=allow_zero))


def parse_price(value: object) -> Decimal:
    if isinstance(value, bool) or value is None or not isinstance(value, (str, Decimal)):
        raise RetroHistInputError("RH-004 price is invalid")
    if isinstance(value, str):
        raw = value.strip()
        if not re.fullmatch(r"(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", raw) or ("." in raw and len(raw.split(".", 1)[1]) > 8):
            raise RetroHistInputError("RH-004 price is invalid")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise RetroHistInputError("RH-004 price is invalid") from None
    if not parsed.is_finite() or parsed.as_tuple().exponent < -8 or parsed <= ZERO or parsed > MAX_PRICE or parsed.quantize(FIXED8) != parsed:
        raise RetroHistInputError("RH-004 price is invalid")
    return parsed


def validate_quote(quote: Quote) -> None:
    if type(quote.time_ns) is not int or quote.time_ns < 0:
        raise RetroHistInputError("RH-004 quote time is invalid")
    if quote.invalid_reason is not None:
        return
    bid, ask = parse_price(quote.bid), parse_price(quote.ask)
    if ask < bid:
        raise RetroHistInputError("RH-004 crossed quote")


def scenario_matrix() -> tuple[Scenario, ...]:
    return (
        Scenario("zero_cost", ZERO, ZERO, 0, ZERO),
        Scenario("fixed_fee", Decimal("0.10000000"), ZERO, 0, ZERO),
        Scenario("per_lot_fee", Decimal("0.25000000"), ZERO, 0, ZERO),
        Scenario("spread_slippage", ZERO, Decimal("2.00000000"), 0, ZERO),
        Scenario("latency_slippage", ZERO, Decimal("1.00000000"), 6_000_000_000, ZERO),
    )


def _validate_scenario(scenario: Scenario) -> None:
    if not isinstance(scenario, Scenario) or not isinstance(scenario.scenario_id, str) or scenario.scenario_id not in SCENARIO_IDS:
        raise RetroHistInputError("RH-004 scenario is invalid")
    if not isinstance(scenario.fee_per_unit, Decimal) or not isinstance(scenario.slippage_points, Decimal) or not isinstance(scenario.margin_reserve, Decimal) or type(scenario.latency_ns) is not int or scenario.latency_ns < 0:
        raise RetroHistInputError("RH-004 scenario is invalid")
    parse_quantity(scenario.fee_per_unit)
    parse_quantity(scenario.slippage_points)
    parse_quantity(scenario.margin_reserve)
    expected = {item.scenario_id: item for item in scenario_matrix()}[scenario.scenario_id]
    if scenario.payload() != expected.payload() or scenario.fingerprint() != expected.fingerprint():
        raise RetroHistInputError("RH-004 scenario fingerprint is invalid")


def select_execution_quote(quotes: Sequence[Quote], target_ns: int, horizon_ns: int) -> tuple[Quote | None, str]:
    if type(target_ns) is not int or target_ns < 0 or type(horizon_ns) is not int or horizon_ns < 0:
        raise RetroHistInputError("RH-004 execution window is invalid")
    candidates: list[Quote] = []
    invalid_times: set[int] = set()
    previous_ns: int | None = None
    for quote in quotes:
        validate_quote(quote)
        if previous_ns is not None and quote.time_ns < previous_ns:
            raise RetroHistInputError("RH-004 quote order decreased")
        previous_ns = quote.time_ns
        if quote.invalid_reason is not None and quote.time_ns >= target_ns:
            invalid_times.add(quote.time_ns)
        if quote.invalid_reason is None and quote.time_ns >= target_ns:
            candidates.append(quote)
    if not candidates:
        return None, "unsupported"
    first_time = candidates[0].time_ns
    same_time = [quote for quote in candidates if quote.time_ns == first_time]
    if first_time > target_ns + horizon_ns or any(time <= first_time for time in invalid_times) or len(same_time) != 1 or same_time[0].duplicate:
        return None, "unsupported"
    return same_time[0], "selected"


def select_mark_quote(quotes: Sequence[Quote], mark_time_ns: int, horizon_ns: int | None = None) -> tuple[Quote | None, str]:
    if type(mark_time_ns) is not int or mark_time_ns < 0 or (horizon_ns is not None and (type(horizon_ns) is not int or horizon_ns < 0)):
        raise RetroHistInputError("RH-004 mark time is invalid")
    selected: Quote | None = None
    invalid_times: list[int] = []
    previous_ns: int | None = None
    for quote in quotes:
        validate_quote(quote)
        if previous_ns is not None and quote.time_ns < previous_ns:
            raise RetroHistInputError("RH-004 quote order decreased")
        previous_ns = quote.time_ns
        if quote.invalid_reason is not None and quote.time_ns <= mark_time_ns:
            invalid_times.append(quote.time_ns)
            continue
        if quote.invalid_reason is None and quote.time_ns <= mark_time_ns:
            if selected is not None and quote.time_ns == selected.time_ns:
                return None, "unsupported"
            if quote.duplicate:
                return None, "unsupported"
            selected = quote
    if selected is None or (horizon_ns is not None and mark_time_ns - selected.time_ns > horizon_ns):
        return None, "unsupported"
    if any(time >= selected.time_ns for time in invalid_times):
        return None, "unsupported"
    return selected, "selected"


def _fail_result(status: str, *, buy: Decimal = ZERO, sell: Decimal = ZERO, censored: Decimal = ZERO, action_count: int = 0) -> AccountingResult:
    """Construct a fail-closed result without positional-field drift."""
    return AccountingResult(
        status=status,
        realized_price_units=ZERO,
        unrealized_price_units=ZERO,
        costs_price_units=ZERO,
        margin_reserve=ZERO,
        opened_buy=buy,
        opened_sell=sell,
        closed_buy=ZERO,
        closed_sell=ZERO,
        ending_buy=ZERO if censored else buy,
        ending_sell=ZERO if censored else sell,
        censored_quantity=censored,
        selected_latency_ns=None,
        action_count=action_count,
    )


def _action_side(kind: str) -> str:
    if kind not in ACTION_KINDS:
        raise RetroHistInputError("RH-004 action kind is invalid")
    return "buy" if kind.endswith("BUY") else "sell"


def _slipped_price(quote: Quote, kind: str, scenario: Scenario) -> Decimal:
    slip = scenario.slippage_points * POINT
    if kind == "OPEN_BUY":
        return quote.ask + slip
    if kind == "CLOSE_BUY":
        return quote.bid - slip
    if kind == "OPEN_SELL":
        return quote.bid - slip
    return quote.ask + slip


def _fee(quantity: Decimal, scenario: Scenario) -> Decimal:
    return scenario.fee_per_unit * quantity


def _state(buy: Decimal, sell: Decimal) -> str:
    if buy == ZERO and sell == ZERO:
        return "FLAT"
    if buy > ZERO and sell == ZERO:
        return "ONE_BUY"
    if sell > ZERO and buy == ZERO:
        return "ONE_SELL"
    return "HEDGED_1X1" if buy == sell else "UNBALANCED_HEDGE"


def account_cycle(
    *,
    start_state: str,
    initial_buy: Decimal,
    initial_sell: Decimal,
    initial_quote: Quote | None,
    actions: Sequence[PaperAction],
    quotes: Sequence[Quote],
    scenario: Scenario,
    mark_time_ns: int | None,
    mark_horizon_ns: int = 30_000_000_000,
) -> AccountingResult:
    _validate_scenario(scenario)
    if type(mark_horizon_ns) is not int or mark_horizon_ns < 0:
        raise RetroHistInputError("RH-004 mark horizon is invalid")
    if start_state not in STATES or start_state in {"MULTI_POSITION", "CENSORED"}:
        return _fail_result("censored", action_count=len(actions))
    buy, sell = parse_quantity(initial_buy), parse_quantity(initial_sell)
    if _state(buy, sell) != start_state and not (start_state == "FLAT" and buy == sell == ZERO):
        return _fail_result("invalid", action_count=len(actions))
    if initial_quote is None and (buy or sell):
        return _fail_result("censored", buy=buy, sell=sell, censored=buy + sell, action_count=len(actions))
    if initial_quote is not None:
        validate_quote(initial_quote)
        if initial_quote.invalid_reason is not None or initial_quote.duplicate:
            return _fail_result("censored", buy=buy, sell=sell, censored=buy + sell, action_count=len(actions))
        if actions and isinstance(actions[0], PaperAction) and initial_quote.time_ns > actions[0].decision_time_ns:
            return _fail_result("invalid", buy=buy, sell=sell, action_count=len(actions))
        decision_times = [action.decision_time_ns for action in actions if isinstance(action, PaperAction)]
        if decision_times and initial_quote.time_ns > min(decision_times):
            return _fail_result("censored", buy=buy, sell=sell, censored=buy + sell, action_count=len(actions))
        if mark_time_ns is not None and initial_quote.time_ns > mark_time_ns:
            return _fail_result("invalid", buy=buy, sell=sell, action_count=len(actions))
    cash = ZERO
    costs = ZERO
    realized = ZERO
    buy_basis = ZERO
    sell_basis = ZERO
    opened_buy, opened_sell = buy, sell
    closed_buy = closed_sell = ZERO
    selected_latency: int | None = None
    last_time = -1
    seen_ids: set[str] = set()
    status = "no_action" if not actions else "accounted_action"
    if initial_quote is not None and (buy or sell):
        if buy:
            entry = _slipped_price(initial_quote, "OPEN_BUY", scenario)
            cash -= entry * buy
            buy_basis += entry * buy
            costs += _fee(buy, scenario)
            cash -= _fee(buy, scenario)
        if sell:
            entry = _slipped_price(initial_quote, "OPEN_SELL", scenario)
            cash += entry * sell
            sell_basis += entry * sell
            costs += _fee(sell, scenario)
            cash -= _fee(sell, scenario)
    for action in actions:
        if not isinstance(action, PaperAction) or action.kind not in ACTION_KINDS or type(action.decision_time_ns) is not int or action.decision_time_ns <= last_time:
            status = "invalid"
            break
        if not isinstance(action.action_id, str):
            status = "invalid"
            break
        try:
            quantity = parse_quantity(action.quantity, allow_zero=False)
        except RetroHistInputError:
            status = "invalid"
            break
        if action.action_id and action.action_id in seen_ids:
            status = "invalid"
            break
        seen_ids.add(action.action_id)
        target = action.decision_time_ns + scenario.latency_ns
        quote, quote_status = select_execution_quote(quotes, target, mark_horizon_ns)
        if quote is None:
            status = "unsupported"
            break
        if selected_latency is None:
            selected_latency = quote.time_ns - action.decision_time_ns
        price = _slipped_price(quote, action.kind, scenario)
        if price <= ZERO:
            status = "invalid"
            break
        fee = _fee(quantity, scenario)
        next_buy, next_sell = buy, sell
        if action.kind == "CLOSE_BUY" and buy >= quantity:
            next_buy -= quantity
            cash += price * quantity
            average_basis = buy_basis / buy
            realized += (price - average_basis) * quantity
            buy_basis -= average_basis * quantity
            closed_buy += quantity
        elif action.kind == "CLOSE_SELL" and sell >= quantity:
            next_sell -= quantity
            cash -= price * quantity
            average_basis = sell_basis / sell
            realized += (average_basis - price) * quantity
            sell_basis -= average_basis * quantity
            closed_sell += quantity
        elif action.kind == "OPEN_BUY":
            next_buy += quantity
            cash -= price * quantity
            buy_basis += price * quantity
            opened_buy += quantity
        elif action.kind == "OPEN_SELL":
            next_sell += quantity
            cash += price * quantity
            sell_basis += price * quantity
            opened_sell += quantity
        else:
            status = "invalid"
            break
        cash -= fee
        costs += fee
        buy, sell = next_buy, next_sell
        last_time = action.decision_time_ns
    unrealized = ZERO
    censored = ZERO
    ending_buy, ending_sell = buy, sell
    if status in {"accounted_action", "no_action"} and mark_time_ns is not None and (buy or sell):
        mark, mark_status = select_mark_quote(quotes, mark_time_ns, mark_horizon_ns)
        if mark is None:
            status = "censored"
            censored = buy + sell
            ending_buy = ending_sell = ZERO
        else:
            if buy:
                unrealized += mark.bid * buy - buy_basis
            if sell:
                unrealized += sell_basis - mark.ask * sell
    margin = scenario.margin_reserve * (buy + sell)
    if buy + closed_buy > opened_buy or sell + closed_sell > opened_sell:
        status = "invalid"
    return AccountingResult(
        status, realized, unrealized, costs, margin, opened_buy, opened_sell,
        closed_buy, closed_sell, ending_buy, ending_sell, censored, selected_latency, len(actions),
    )


def latency_band(value: int | None) -> str:
    if value is None:
        return "unsupported"
    seconds = Decimal(value) / Decimal(1_000_000_000)
    if seconds == 0:
        return "zero"
    if seconds <= 1:
        return "0-1s"
    if seconds <= 6:
        return "2-6s"
    if seconds <= 30:
        return "7-30s"
    return "unsupported"


def result_digest(result: AccountingResult) -> str:
    payload = {
        "status": result.status,
        "realized": _amount8(result.realized_price_units),
        "unrealized": _amount8(result.unrealized_price_units),
        "costs": _amount8(result.costs_price_units),
        "margin": _amount8(result.margin_reserve),
        "opened_buy": _fixed8(result.opened_buy),
        "opened_sell": _fixed8(result.opened_sell),
        "closed_buy": _fixed8(result.closed_buy),
        "closed_sell": _fixed8(result.closed_sell),
        "ending_buy": _fixed8(result.ending_buy),
        "ending_sell": _fixed8(result.ending_sell),
        "censored": _fixed8(result.censored_quantity),
        "latency_band": latency_band(result.selected_latency_ns),
        "action_count": result.action_count,
    }
    return _sha(payload)


def empty_aggregate(*, report_manifest_sha256: str, tick_manifest_sha256: str, population: Mapping[str, object], policy_action_digests: Mapping[str, object]) -> dict[str, object]:
    scenarios = scenario_matrix()
    for scenario in scenarios:
        _validate_scenario(scenario)
    contract_sha, receipt_sha = verify_governance_artifacts()
    state_counts = {state: 0 for state in STATES}
    action_counts = {scenario.scenario_id: {kind: 0 for kind in ACTION_KINDS} for scenario in scenarios}
    accounting_counts = {scenario.scenario_id: {status: 0 for status in STATUSES} for scenario in scenarios}
    quantity_bands = {scenario.scenario_id: {band: 0 for band in QUANTITY_BANDS} for scenario in scenarios}
    latency_bands = {scenario.scenario_id: {band: 0 for band in LATENCY_BANDS} for scenario in scenarios}
    conservation = {scenario.scenario_id: {"opened": "0.00000000", "closed": "0.00000000", "ending": "0.00000000", "censored": "0.00000000", "failures": 0} for scenario in scenarios}
    accounting_digests = {scenario.scenario_id: hashlib.sha256(b"").hexdigest() for scenario in scenarios}
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": CASE_ID,
        "source_validation": "accepted_hash_verified_RH002_manifest_runs_all_objects",
        "report_manifest_sha256": report_manifest_sha256,
        "tick_manifest_sha256": tick_manifest_sha256,
        "contract_sha256": contract_sha,
        "source_receipt_sha256": receipt_sha,
        "population": dict(population),
        "scenario_ids": [scenario.scenario_id for scenario in scenarios],
        "bootstrap_state": "FLAT",
        "state_counts": state_counts,
        "action_counts": action_counts,
        "accounting_counts": accounting_counts,
        "quantity_bands": quantity_bands,
        "latency_bands": latency_bands,
        "cost_fingerprints": {scenario.scenario_id: scenario.fingerprint() for scenario in scenarios},
        "conservation": conservation,
        "policy_action_digests": json.loads(json.dumps(policy_action_digests)),
        "accounting_digests": accounting_digests,
        "m5_firewall": M5_FIREWALL,
        "claims": {key: False for key in CLAIM_KEYS},
        "aggregate_sha256": "",
    }


def finalize_aggregate(aggregate: dict[str, object]) -> dict[str, object]:
    aggregate = dict(aggregate)
    aggregate["aggregate_sha256"] = _sha({key: aggregate[key] for key in TOP_LEVEL_KEYS if key != "aggregate_sha256"})
    return aggregate


def _privacy_scan(value: object, path: str = "aggregate") -> None:
    """Reject raw identifiers, paths, and non-finite values anywhere nested."""
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise RetroHistInputError(f"RH-004 aggregate key is invalid: {path}")
            if key not in _STRUCTURAL_KEYS and ("/" in key or "\\" in key or _PRIVATE_TOKEN_RE.search(key) or ":" in key):
                raise RetroHistInputError(f"RH-004 aggregate privacy violation: {path}.{key}")
            _privacy_scan(nested, f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _privacy_scan(nested, f"{path}[{index}]")
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise RetroHistInputError(f"RH-004 aggregate non-finite value: {path}")
    if isinstance(value, str):
        if "/" in value or "\\" in value or _PATHLIKE_RE.fullmatch(value) or _PRIVATE_TOKEN_RE.search(value):
            raise RetroHistInputError(f"RH-004 aggregate privacy violation: {path}")


def _validate_hash(value: object, path: str) -> None:
    if not isinstance(value, str) or not _HEX64_RE.fullmatch(value):
        raise RetroHistInputError(f"RH-004 aggregate hash is invalid: {path}")


def _validate_count_map(value: object, keys: Sequence[str], path: str) -> None:
    if not isinstance(value, Mapping) or list(value) != list(keys):
        raise RetroHistInputError(f"RH-004 aggregate dimension mismatch: {path}")
    for key in keys:
        if type(value[key]) is not int or value[key] < 0:
            raise RetroHistInputError(f"RH-004 aggregate count is invalid: {path}.{key}")


def _validate_fixed8_text(value: object, path: str) -> Decimal:
    if not isinstance(value, str) or not _FIXED8_RE.fullmatch(value):
        raise RetroHistInputError(f"RH-004 aggregate fixed8 is invalid: {path}")
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        raise RetroHistInputError(f"RH-004 aggregate fixed8 is invalid: {path}") from None
    if parsed < ZERO or parsed > MAX_QUANTITY:
        raise RetroHistInputError(f"RH-004 aggregate fixed8 is outside bounds: {path}")
    return parsed


def validate_aggregate(aggregate: Mapping[str, object]) -> None:
    if not isinstance(aggregate, Mapping) or tuple(aggregate) != TOP_LEVEL_KEYS:
        raise RetroHistInputError("RH-004 aggregate schema is invalid")
    _privacy_scan(aggregate)
    if aggregate["schema_version"] != SCHEMA_VERSION or aggregate["case_id"] != CASE_ID:
        raise RetroHistInputError("RH-004 aggregate identity is invalid")
    if aggregate["source_validation"] != "accepted_hash_verified_RH002_manifest_runs_all_objects":
        raise RetroHistInputError("RH-004 source validation is invalid")
    if type(aggregate["schema_version"]) is not int or aggregate["m5_firewall"] != M5_FIREWALL or aggregate["bootstrap_state"] not in STATES:
        raise RetroHistInputError("RH-004 firewall or bootstrap is invalid")
    if aggregate["report_manifest_sha256"] != REPORT_MANIFEST_SHA256 or aggregate["tick_manifest_sha256"] != TICK_MANIFEST_SHA256:
        raise RetroHistInputError("RH-004 aggregate provenance mismatch")
    if aggregate["contract_sha256"] != CONTRACT_SHA256 or aggregate["source_receipt_sha256"] != SOURCE_RECEIPT_SHA256:
        raise RetroHistInputError("RH-004 governance artifact hash mismatch")
    if aggregate["scenario_ids"] != list(SCENARIO_IDS):
        raise RetroHistInputError("RH-004 scenario dimension is invalid")
    population = aggregate["population"]
    if not isinstance(population, Mapping) or list(population) != list(POPULATION_KEYS):
        raise RetroHistInputError("RH-004 population schema is invalid")
    for key in ("start_server", "end_server_exclusive"):
        if not isinstance(population[key], str):
            raise RetroHistInputError("RH-004 population boundary is invalid")
    if population["start_server"] != "2025-11-01 00:00:00" or population["end_server_exclusive"] != "2026-07-31 00:00:00":
        raise RetroHistInputError("RH-004 population boundary is invalid")
    for key in ("report_alias_count", "tick_alias_count"):
        if type(population[key]) is not int or population[key] < 0:
            raise RetroHistInputError("RH-004 population count is invalid")
    if population["report_alias_count"] != 9 or population["tick_alias_count"] != 39:
        raise RetroHistInputError("RH-004 population count is invalid")
    if population["tick_clock_scenarios"] != list(CLOCK_IDS):
        raise RetroHistInputError("RH-004 population clock dimension is invalid")
    _validate_count_map(aggregate["state_counts"], STATES, "state_counts")
    for name, keys in (("action_counts", ACTION_KINDS), ("accounting_counts", STATUSES), ("quantity_bands", QUANTITY_BANDS), ("latency_bands", LATENCY_BANDS)):
        value = aggregate[name]
        if not isinstance(value, Mapping) or list(value) != list(SCENARIO_IDS):
            raise RetroHistInputError(f"RH-004 aggregate dimension mismatch: {name}")
        for scenario_id in SCENARIO_IDS:
            _validate_count_map(value[scenario_id], keys, f"{name}.{scenario_id}")
    fingerprints = aggregate["cost_fingerprints"]
    if not isinstance(fingerprints, Mapping) or list(fingerprints) != list(SCENARIO_IDS):
        raise RetroHistInputError("RH-004 cost fingerprint schema is invalid")
    for scenario_id in SCENARIO_IDS:
        expected = next(item for item in scenario_matrix() if item.scenario_id == scenario_id).fingerprint()
        if fingerprints[scenario_id] != expected:
            raise RetroHistInputError(f"RH-004 cost fingerprint mismatch: {scenario_id}")
    conservation = aggregate["conservation"]
    conservation_keys = ("opened", "closed", "ending", "censored", "failures")
    if not isinstance(conservation, Mapping) or list(conservation) != list(SCENARIO_IDS):
        raise RetroHistInputError("RH-004 conservation schema is invalid")
    for scenario_id in SCENARIO_IDS:
        row = conservation[scenario_id]
        if not isinstance(row, Mapping) or list(row) != list(conservation_keys):
            raise RetroHistInputError(f"RH-004 conservation dimension is invalid: {scenario_id}")
        opened = _validate_fixed8_text(row["opened"], f"conservation.{scenario_id}.opened")
        closed = _validate_fixed8_text(row["closed"], f"conservation.{scenario_id}.closed")
        ending = _validate_fixed8_text(row["ending"], f"conservation.{scenario_id}.ending")
        censored = _validate_fixed8_text(row["censored"], f"conservation.{scenario_id}.censored")
        if opened != closed + ending + censored or type(row["failures"]) is not int or row["failures"] < 0:
            raise RetroHistInputError(f"RH-004 conservation failure: {scenario_id}")
    policy = aggregate["policy_action_digests"]
    if not isinstance(policy, Mapping):
        raise RetroHistInputError("RH-004 policy digest schema is invalid")
    if list(policy) != list(POLICY_CANDIDATES):
        raise RetroHistInputError("RH-004 policy digest schema is invalid")
    for candidate in POLICY_CANDIDATES:
        clocks = policy[candidate]
        if not isinstance(clocks, Mapping) or list(clocks) != list(CLOCK_IDS):
            raise RetroHistInputError("RH-004 policy digest schema is invalid")
        for clock in CLOCK_IDS:
            digest = clocks[clock]
            _validate_hash(digest, f"policy_action_digests.{candidate}.{clock}")
    accounting_digests = aggregate["accounting_digests"]
    if not isinstance(accounting_digests, Mapping) or list(accounting_digests) != list(SCENARIO_IDS):
        raise RetroHistInputError("RH-004 accounting digest schema is invalid")
    for scenario_id in SCENARIO_IDS:
        _validate_hash(accounting_digests[scenario_id], f"accounting_digests.{scenario_id}")
    claims = aggregate["claims"]
    if not isinstance(claims, Mapping) or tuple(claims) != CLAIM_KEYS or any(type(claims[key]) is not bool or claims[key] is not False for key in CLAIM_KEYS):
        raise RetroHistInputError("RH-004 claims are invalid")
    if aggregate["aggregate_sha256"] != _sha({key: aggregate[key] for key in TOP_LEVEL_KEYS if key != "aggregate_sha256"}):
        raise RetroHistInputError("RH-004 aggregate digest mismatch")
