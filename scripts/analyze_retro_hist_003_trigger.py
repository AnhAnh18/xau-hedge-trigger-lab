"""Aggregate-only RH-003 causal trigger replay over the accepted archive."""
from __future__ import annotations

from collections import deque
from dataclasses import replace
from decimal import Decimal
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from xau_trigger.retro_hist_002 import (
    END_SERVER,
    REPORT_ALIASES,
    REPORT_MANIFEST_SHA256,
    REPORT_RUN_ID,
    START_SERVER,
    TICK_ALIASES,
    TICK_MANIFEST_SHA256,
    TICK_RUN_ID,
    load_positions,
    verify_manifest,
)
from xau_trigger.retro_hist_003 import (
    CANDIDATE_IDS,
    CLOCK_IDS,
    CausalState,
    CausalTick,
    FeatureSnapshot,
    MATCH_HORIZON_SECONDS,
    OracleLabel,
    ORACLE_KEYS,
    aggregate_trigger_results,
    action_digest,
    apply_decision,
    bootstrap_state,
    build_feature_snapshot,
    empty_aggregate_maps,
    evaluate_candidate,
    iter_ticks_decimal,
    load_positions_retro,
    oracle_diagnostics,
    server_to_utc,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "reports" / "private" / "retro-hist-003" / "trigger-aggregate.json"


def _utc_window(clock_id: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    return (
        server_to_utc(START_SERVER, clock_id),
        server_to_utc(END_SERVER, clock_id),
    )


def _labels(positions) -> tuple[OracleLabel, ...]:
    labels = []
    for position in positions:
        if position.censored:
            continue
        if START_SERVER <= position.open_time < END_SERVER:
            labels.append(OracleLabel(position.position_id, "OPEN", position.side, position.quantity, position.open_time))
        if position.close_time is not None and START_SERVER < position.close_time < END_SERVER:
            labels.append(OracleLabel(position.position_id, "CLOSE", position.side, position.quantity, position.close_time))
    return tuple(labels)


def _state_ineligible_snapshot(decision: pd.Timestamp, clock_id: str, state: str, tick_count: int) -> FeatureSnapshot:
    return FeatureSnapshot(decision, clock_id, state, None, None, None, None, None, tick_count, "unsupported", "state_ineligible")


def _increment_support(maps, candidate: str, clock: str, state: str, reason: str) -> None:
    maps["support_counts"][candidate][clock][state][reason] += 1


def _increment_outcome(maps, candidate: str, clock: str, state: str, outcome: str) -> None:
    maps["outcome_counts"][candidate][clock][state][outcome] += 1


def _run_flat_replay(tick_paths: dict[str, Path], labels: tuple[OracleLabel, ...]) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    """Replay source counters without feature work when every policy is FLAT."""
    maps = empty_aggregate_maps()
    empty_digest = hashlib.sha256(b"").hexdigest()
    action_digests = {candidate: {clock: empty_digest for clock in CLOCK_IDS} for candidate in CANDIDATE_IDS}
    clock_stats = {
        clock: {
            "valid_rows": 0,
            "invalid_rows": 0,
            "duplicate_timestamps": 0,
            "out_of_order": 0,
            "crossed_quotes": 0,
            "envelope_excluded_rows": 0,
            "bootstrap_state": "FLAT",
        }
        for clock in CLOCK_IDS
    }
    windows = {clock: _utc_window(clock) for clock in CLOCK_IDS}
    pending: list[CausalTick] = []
    pending_group_ns: int | None = None
    source_previous_ns: int | None = None

    def invalid_timestamp() -> None:
        nonlocal pending, pending_group_ns
        if pending:
            process_group(pending)
            pending = []
            pending_group_ns = None

    def process_group(group: list[CausalTick]) -> None:
        nonlocal pending_group_ns
        if not group:
            return
        decision = group[0].time_utc
        valid_count = sum(item.invalid_reason is None for item in group)
        for clock in CLOCK_IDS:
            start_utc, end_utc = windows[clock]
            if decision < start_utc or decision >= end_utc:
                clock_stats[clock]["envelope_excluded_rows"] += valid_count
                continue
            clock_stats[clock]["valid_rows"] += valid_count
            for candidate in CANDIDATE_IDS:
                _increment_support(maps, candidate, clock, "FLAT", "state_ineligible")
                _increment_outcome(maps, candidate, clock, "FLAT", "noneligible")

    for alias in sorted(tick_paths):
        ticks, stats = iter_ticks_decimal(
            tick_paths[alias],
            broad_start=server_to_utc(START_SERVER, "utc_plus_3") - pd.Timedelta(seconds=60),
            broad_end=server_to_utc(END_SERVER, "utc_plus_2") + pd.Timedelta(seconds=60),
            previous_ns=source_previous_ns,
            invalid_timestamp_callback=invalid_timestamp,
        )
        for tick in ticks:
            timestamp_ns = int(tick.time_utc.value)
            if pending_group_ns is None:
                pending_group_ns = timestamp_ns
            if timestamp_ns != pending_group_ns:
                process_group(pending)
                pending = []
                pending_group_ns = timestamp_ns
            pending.append(tick)
        source_previous_ns = stats["last_time_ns"]
        for clock in CLOCK_IDS:
            clock_stats[clock]["invalid_rows"] += stats["invalid_rows"]
            clock_stats[clock]["duplicate_timestamps"] += stats["duplicate_timestamps"]
            clock_stats[clock]["out_of_order"] += stats["out_of_order"]
            clock_stats[clock]["crossed_quotes"] += stats["crossed_quotes"]
            clock_stats[clock]["envelope_excluded_rows"] += stats["envelope_excluded_rows"]
    process_group(pending)
    for clock in CLOCK_IDS:
        diagnostics = oracle_diagnostics((), labels, clock)
        for candidate in CANDIDATE_IDS:
            maps["oracle_diagnostics"][candidate][clock] = dict(diagnostics)
    return clock_stats, {"maps": maps, "action_digests": action_digests}


class _DigestAccumulator:
    """Build the action digest without retaining the action stream."""

    def __init__(self) -> None:
        self._hasher = hashlib.sha256()
        self._count = 0

    def add(self, record: dict[str, object]) -> None:
        if self._count:
            self._hasher.update(b"\n")
        self._hasher.update(json.dumps(record, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))
        self._count += 1

    def hexdigest(self) -> str:
        return self._hasher.hexdigest()


class _OracleMatcher:
    """Consume bounded report labels as policy actions arrive."""

    def __init__(self, labels: tuple[OracleLabel, ...], clock_id: str) -> None:
        materialized = []
        for label in labels:
            if label.kind not in {"OPEN", "CLOSE"} or label.side not in {"buy", "sell"}:
                raise ValueError("RH-003 oracle label is invalid")
            materialized.append((server_to_utc(label.server_time, clock_id), label))
        self._materialized = sorted(
            materialized,
            key=lambda item: (
                int(item[0].value),
                0 if item[1].kind == "CLOSE" else 1,
                0 if item[1].side == "buy" else 1,
                item[1].position_id,
            ),
        )
        duplicate_keys = set()
        for index in range(1, len(self._materialized)):
            previous = self._materialized[index - 1]
            current = self._materialized[index]
            if (previous[0].value, previous[1].kind, previous[1].side, previous[1].position_id) == (current[0].value, current[1].kind, current[1].side, current[1].position_id):
                duplicate_keys.add((current[0].value, current[1].kind, current[1].side, current[1].position_id))
        self._used: set[int] = set()
        self._cursor = 0
        self._counts = {key: 0 for key in ORACLE_KEYS}
        self._counts["duplicate_label"] = len(duplicate_keys)

    def consume(self, decision) -> None:
        if decision.outcome != "action":
            return
        action_time = decision.decision_time_utc
        while self._cursor < len(self._materialized) and self._materialized[self._cursor][0] < action_time:
            self._cursor += 1
        horizon = action_time + pd.Timedelta(seconds=MATCH_HORIZON_SECONDS)
        index = self._cursor
        while index < len(self._materialized) and self._materialized[index][0] < horizon and index in self._used:
            index += 1
        if index >= len(self._materialized) or self._materialized[index][0] >= horizon:
            self._counts["unmatched"] += 1
            return
        label_time, label = self._materialized[index]
        delta_ns = int(label_time.value - action_time.value)
        self._used.add(index)
        delta = Decimal(delta_ns) / Decimal("1000000000")
        if delta == Decimal("0"):
            self._counts["exact"] += 1
        elif delta <= Decimal("1"):
            self._counts["0-1s"] += 1
        elif delta <= Decimal("6"):
            self._counts["2-6s"] += 1
        else:
            self._counts["7-30s"] += 1
        expected_kind = "CLOSE" if decision.action_kind.startswith("CLOSE") else "OPEN"
        if label.kind == expected_kind and label.side == decision.side:
            self._counts["direction_match"] += 1
        else:
            self._counts["direction_mismatch"] += 1
        if label.quantity == decision.quantity:
            self._counts["quantity_match"] += 1
        else:
            self._counts["quantity_mismatch"] += 1

    def result(self) -> dict[str, int]:
        result = dict(self._counts)
        result["unmatched_label"] = len(self._materialized) - len(self._used)
        return result


class _FeatureCursor:
    """Maintain the exact 60-second feature window without rescanning ticks."""

    def __init__(self) -> None:
        self._sequence = 0
        self._ticks = deque()
        self._min_deque = deque()
        self._max_deque = deque()
        self._gap_deque = deque()
        self._duplicate_sequences = deque()
        self._invalid_sequences = deque()
        self._previous = None
        self._invalid_stream = False

    def mark_invalid_stream(self) -> None:
        self._invalid_stream = True

    def push(self, group: list[CausalTick], decision: pd.Timestamp, clock_id: str) -> FeatureSnapshot:
        if self._invalid_stream:
            return FeatureSnapshot(decision, clock_id, "HEDGED_1X1", None, None, None, None, None, 0, "unsupported", "invalid_row")
        duplicate_group = len(group) > 1
        for tick in group:
            self._sequence += 1
            sequence = self._sequence
            if tick.invalid_reason is not None:
                self._invalid_stream = True
                self._ticks.append((sequence, tick))
                self._invalid_sequences.append(sequence)
                self._previous = tick
                continue
            mid = (tick.bid + tick.ask) / 2
            self._ticks.append((sequence, tick))
            while self._min_deque and self._min_deque[-1][1] >= mid:
                self._min_deque.pop()
            self._min_deque.append((sequence, mid))
            while self._max_deque and self._max_deque[-1][1] <= mid:
                self._max_deque.pop()
            self._max_deque.append((sequence, mid))
            if self._previous is not None:
                gap_ns = int(tick.time_utc.value - self._previous.time_utc.value)
                while self._gap_deque and self._gap_deque[-1][1] <= gap_ns:
                    self._gap_deque.pop()
                self._gap_deque.append((sequence, gap_ns))
            if tick.duplicate_timestamp:
                self._duplicate_sequences.append(sequence)
            self._previous = tick
        cutoff = decision - pd.Timedelta(seconds=60)
        last_evicted_time = None
        while len(self._ticks) >= 2 and self._ticks[1][1].time_utc <= cutoff:
            last_evicted_time = self._ticks.popleft()[1].time_utc
        if not self._ticks:
            return FeatureSnapshot(decision, clock_id, "HEDGED_1X1", None, None, None, None, None, 0, "unsupported", "empty_prefix")
        anchor_sequence, anchor = self._ticks[0]
        while self._duplicate_sequences and self._duplicate_sequences[0] < anchor_sequence:
            self._duplicate_sequences.popleft()
        duplicate_at_anchor = last_evicted_time == anchor.time_utc
        if duplicate_at_anchor or duplicate_group or self._duplicate_sequences:
            return FeatureSnapshot(decision, clock_id, "HEDGED_1X1", None, None, None, None, None, len(self._ticks), "unsupported", "duplicate_timestamp")
        if anchor.time_utc > cutoff:
            return FeatureSnapshot(decision, clock_id, "HEDGED_1X1", None, None, None, None, None, len(self._ticks), "unsupported", "no_anchor")
        while self._invalid_sequences and self._invalid_sequences[0] < anchor_sequence:
            self._invalid_sequences.popleft()
        if self._invalid_sequences:
            return FeatureSnapshot(decision, clock_id, "HEDGED_1X1", None, None, None, None, None, len(self._ticks), "unsupported", "invalid_row")
        duplicate = duplicate_group or bool(self._duplicate_sequences)
        if duplicate:
            return FeatureSnapshot(decision, clock_id, "HEDGED_1X1", None, None, None, None, None, len(self._ticks), "unsupported", "duplicate_timestamp")
        while self._min_deque and self._min_deque[0][0] < anchor_sequence:
            self._min_deque.popleft()
        while self._max_deque and self._max_deque[0][0] < anchor_sequence:
            self._max_deque.popleft()
        while self._gap_deque and self._gap_deque[0][0] <= anchor_sequence:
            self._gap_deque.popleft()
        anchor_mid = (anchor.bid + anchor.ask) / 2
        last = self._ticks[-1][1]
        min_mid = self._min_deque[0][1]
        max_mid = self._max_deque[0][1]
        decision_gap_ns = int(decision.value - last.time_utc.value)
        max_gap_ns = max(decision_gap_ns, self._gap_deque[0][1] if self._gap_deque else 0)
        quote_gap = Decimal(max_gap_ns) / Decimal("1000000000")
        window_count = len(self._ticks) if anchor.time_utc >= cutoff else len(self._ticks) - 1
        if quote_gap > Decimal("6"):
            snapshot = FeatureSnapshot(
                decision,
                clock_id,
                "HEDGED_1X1",
                None,
                None,
                None,
                None,
                quote_gap,
                window_count,
                "unsupported",
                "quote_gap",
            )
            snapshot.validate()
            return snapshot
        snapshot = FeatureSnapshot(
            decision,
            clock_id,
            "HEDGED_1X1",
            ((last.bid + last.ask) / 2 - anchor_mid) / Decimal("0.01"),
            max(Decimal("0"), (anchor_mid - min_mid) / Decimal("0.01")),
            max(Decimal("0"), (max_mid - anchor_mid) / Decimal("0.01")),
            (last.ask - last.bid) / Decimal("0.01"),
            quote_gap,
            window_count,
            "supported" if quote_gap <= Decimal("6") else "unsupported",
            "supported" if quote_gap <= Decimal("6") else "quote_gap",
        )
        snapshot.validate()
        return snapshot


def _run_replay(tick_paths: dict[str, Path], positions) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    maps = empty_aggregate_maps()
    initial = bootstrap_state(positions)
    labels = _labels(positions)
    if initial.state == "FLAT":
        return _run_flat_replay(tick_paths, labels)
    states = {candidate: {clock: initial for clock in CLOCK_IDS} for candidate in CANDIDATE_IDS}
    action_digests = {candidate: {clock: _DigestAccumulator() for clock in CLOCK_IDS} for candidate in CANDIDATE_IDS}
    oracle_matchers = {candidate: {clock: _OracleMatcher(labels, clock) for clock in CLOCK_IDS} for candidate in CANDIDATE_IDS}
    cursors = {clock: _FeatureCursor() for clock in CLOCK_IDS}
    clock_stats = {
        clock: {
            "valid_rows": 0,
            "invalid_rows": 0,
            "duplicate_timestamps": 0,
            "out_of_order": 0,
            "crossed_quotes": 0,
            "envelope_excluded_rows": 0,
            "bootstrap_state": initial.state,
        }
        for clock in CLOCK_IDS
    }
    windows = {clock: _utc_window(clock) for clock in CLOCK_IDS}
    pending: list[CausalTick] = []
    pending_group_ns: int | None = None
    source_previous_ns: int | None = None

    def invalid_timestamp() -> None:
        nonlocal pending, pending_group_ns
        if pending:
            process_group(pending)
            pending = []
            pending_group_ns = None
        for cursor in cursors.values():
            cursor.mark_invalid_stream()

    def process_group(group: list[CausalTick]) -> None:
        if not group:
            return
        decision = group[0].time_utc
        for clock in CLOCK_IDS:
            start_utc, end_utc = windows[clock]
            warm_start = start_utc - pd.Timedelta(seconds=60)
            valid_group_count = sum(item.invalid_reason is None for item in group)
            if decision < warm_start or decision >= end_utc:
                clock_stats[clock]["envelope_excluded_rows"] += valid_group_count
                continue
            if decision < start_utc:
                cursors[clock].push(group, decision, clock)
                clock_stats[clock]["envelope_excluded_rows"] += valid_group_count
                continue
            clock_stats[clock]["valid_rows"] += valid_group_count
            snapshot_base = cursors[clock].push(group, decision, clock)
            for candidate in CANDIDATE_IDS:
                state = states[candidate][clock]
                if state.state in {"FLAT", "MULTI_POSITION", "CENSORED"}:
                    snapshot = _state_ineligible_snapshot(decision, clock, state.state, snapshot_base.tick_count_60s)
                else:
                    snapshot = replace(snapshot_base, state=state.state)
                _increment_support(maps, candidate, clock, state.state, snapshot.support_reason)
                # Cursor/state construction validates each input once; avoid repeating
                # Decimal/schema checks for every candidate on every tick.
                decision_result = evaluate_candidate(state, snapshot, candidate, validate=False)
                _increment_outcome(maps, candidate, clock, state.state, decision_result.outcome)
                if decision_result.outcome != "action":
                    continue
                maps["action_counts"][candidate][clock][decision_result.action_kind] += 1
                maps["quantity_bands"][candidate][clock][
                    "other" if format(decision_result.quantity, "f") not in maps["quantity_bands"][candidate][clock] else format(decision_result.quantity, "f")
                ] += 1
                record = {
                    "candidate_id": candidate,
                    "clock_id": clock,
                    "epoch": state.epoch,
                    "decision_time_ns": int(decision.value),
                    "kind": decision_result.action_kind,
                    "side": decision_result.side,
                    "quantity_fixed8": format(decision_result.quantity, "f"),
                }
                action_digests[candidate][clock].add(record)
                oracle_matchers[candidate][clock].consume(decision_result)
                states[candidate][clock] = apply_decision(state, decision_result)

    for alias in sorted(tick_paths):
        ticks, stats = iter_ticks_decimal(
            tick_paths[alias],
            broad_start=server_to_utc(START_SERVER, "utc_plus_3") - pd.Timedelta(seconds=60),
            broad_end=server_to_utc(END_SERVER, "utc_plus_2") + pd.Timedelta(seconds=60),
            previous_ns=source_previous_ns,
            invalid_timestamp_callback=invalid_timestamp,
        )
        for tick in ticks:
            timestamp_ns = int(tick.time_utc.value)
            if pending_group_ns is None:
                pending_group_ns = timestamp_ns
            if timestamp_ns != pending_group_ns:
                process_group(pending)
                pending = []
                pending_group_ns = timestamp_ns
            pending.append(tick)
        source_previous_ns = stats["last_time_ns"]
        for clock in CLOCK_IDS:
            clock_stats[clock]["invalid_rows"] += stats["invalid_rows"]
            clock_stats[clock]["duplicate_timestamps"] += stats["duplicate_timestamps"]
            clock_stats[clock]["out_of_order"] += stats["out_of_order"]
            clock_stats[clock]["crossed_quotes"] += stats["crossed_quotes"]
            clock_stats[clock]["envelope_excluded_rows"] += stats["envelope_excluded_rows"]
    process_group(pending)

    action_digest_results = {candidate: {clock: action_digests[candidate][clock].hexdigest() for clock in CLOCK_IDS} for candidate in CANDIDATE_IDS}
    for candidate in CANDIDATE_IDS:
        for clock in CLOCK_IDS:
            maps["oracle_diagnostics"][candidate][clock] = oracle_matchers[candidate][clock].result()
    return clock_stats, {"maps": maps, "action_digests": action_digest_results}


def _require_ignored(path: Path) -> None:
    result = subprocess.run(["git", "check-ignore", "--no-index", "-q", str(path.relative_to(ROOT))], cwd=ROOT, check=False)
    if result.returncode != 0:
        raise ValueError("RH-003 output path is not ignored")


def run() -> dict[str, object]:
    report_paths = verify_manifest(REPORT_RUN_ID, REPORT_MANIFEST_SHA256, set(REPORT_ALIASES), sort_keys=True, check_objects=True)
    tick_paths = verify_manifest(TICK_RUN_ID, TICK_MANIFEST_SHA256, set(TICK_ALIASES), sort_keys=False, check_objects=True)
    positions, _position_stats = load_positions_retro(report_paths)
    clock_stats, replay = _run_replay(tick_paths, positions)
    maps = replay["maps"]
    population = {
        "start_server": "2025-11-01 00:00:00",
        "end_server_exclusive": "2026-07-31 00:00:00",
        "report_alias_count": len(REPORT_ALIASES),
        "tick_alias_count": len(TICK_ALIASES),
        "tick_clock_scenarios": list(CLOCK_IDS),
    }
    return aggregate_trigger_results(
        clocks=clock_stats,
        maps=maps,
        action_digests=replay["action_digests"],
        population=population,
    )


def main() -> int:
    try:
        result = run()
        _require_ignored(OUTPUT)
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT.write_text(json.dumps(result, ensure_ascii=True, separators=(",", ":")), encoding="utf-8")
        print(json.dumps({"case_id": result["case_id"], "aggregate_sha256": result["aggregate_sha256"]}, ensure_ascii=True, separators=(",", ":")))
        return 0
    except Exception:
        print("RETRO-HIST-003 analysis rejected", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
