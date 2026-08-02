from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest

from xau_trigger.retro_bot import EligibleInterval, RetroBotInputError, _canonical_digest, load_config
from xau_trigger.retro_bot_003 import (
    SequentialOutcome,
    wrap_paper_outcomes,
    aggregate_sequential_outcomes,
    sequential_paper_outcomes,
    validate_sequential_aggregate,
)


def _interval(start: str, end: str) -> EligibleInterval:
    return EligibleInterval("synthetic.html", 1, "ONE_BUY", pd.Timestamp(start), pd.Timestamp(end), 60)


def _ticks(path: Path) -> Path:
    path.write_text("time_utc,bid,ask\n2026-01-01T00:05:00Z,10,12\n2026-01-01T00:10:00Z,13,15\n", encoding="utf-8")
    return path


def test_sequential_wrapper_preserves_order_and_marks_overlap(tmp_path: Path) -> None:
    config = load_config()
    intervals = (_interval("2026-01-01 02:00", "2026-01-01 02:10"), _interval("2026-01-01 02:05", "2026-01-01 02:15"))
    outcomes = sequential_paper_outcomes(intervals, config, [_ticks(tmp_path / "ticks.csv")])
    assert outcomes[0].status != "excluded_overlap"
    assert outcomes[12].status == "excluded_overlap"  # second cycle, first clock/policy


def test_invalid_order_is_excluded_without_sorting(tmp_path: Path) -> None:
    config = load_config()
    intervals = (_interval("2026-01-01 02:10", "2026-01-01 02:20"), _interval("2026-01-01 02:00", "2026-01-01 02:05"))
    outcomes = sequential_paper_outcomes(intervals, config, [_ticks(tmp_path / "ticks.csv")])
    assert outcomes[12].status == "excluded_invalid_order"


def test_aggregate_counts_reconcile_and_is_redacted() -> None:
    config = load_config()
    outcomes = []
    for clock in config.clocks:
        for policy in config.policies:
            outcomes.extend(
                [
                    SequentialOutcome(0, policy.id, clock.id, "emitted_marked", "buy", 2.0),
                    SequentialOutcome(1, policy.id, clock.id, "excluded_overlap", None, None),
                    SequentialOutcome(2, policy.id, clock.id, "excluded_invalid_order", None, None),
                ]
            )
    payload = aggregate_sequential_outcomes(outcomes, config, report_manifest_sha256=config.source_receipt["report_manifest_sha256"], tick_manifest_sha256=config.source_receipt["tick_manifest_sha256"])
    assert payload == aggregate_sequential_outcomes(outcomes, config, report_manifest_sha256=config.source_receipt["report_manifest_sha256"], tick_manifest_sha256=config.source_receipt["tick_manifest_sha256"])
    row = payload["policy_clock_rows"][0]
    assert row["total_cycle_count"] == 3
    assert row["eligible_cycle_count"] == 1 and row["action_count"] == row["marked_count"] == 1
    assert row["overlap_count"] == row["invalid_order_count"] == 1
    assert "cycle_index" not in payload and "timestamp" not in payload
    validate_sequential_aggregate(payload, config)


def test_aggregate_rejects_duplicate_or_tampered_rows() -> None:
    config = load_config()
    payload = aggregate_sequential_outcomes((), config, report_manifest_sha256=config.source_receipt["report_manifest_sha256"], tick_manifest_sha256=config.source_receipt["tick_manifest_sha256"])
    tampered = dict(payload)
    tampered["policy_clock_rows"] = list(payload["policy_clock_rows"])
    tampered["policy_clock_rows"][0] = dict(tampered["policy_clock_rows"][0])
    tampered["policy_clock_rows"][0]["total_cycle_count"] = 1
    with pytest.raises(RetroBotInputError, match="digest"):
        validate_sequential_aggregate(tampered, config)
    invalid = dict(payload)
    invalid["schema_version"] = True
    invalid["aggregate_sha256"] = _canonical_digest(invalid, "aggregate_sha256")
    with pytest.raises(RetroBotInputError):
        validate_sequential_aggregate(invalid, config)


def test_wrapper_rejects_mutated_config(tmp_path: Path) -> None:
    config = load_config()
    with pytest.raises(RetroBotInputError, match="config is not locked"):
        sequential_paper_outcomes((), replace(config, case_id="mutated"), [_ticks(tmp_path / "ticks.csv")])


def test_wrapper_rejects_mismatched_rb006_identity() -> None:
    config = load_config()
    interval = _interval("2026-01-01 02:00", "2026-01-01 02:10")
    base = tuple(
        SequentialOutcome(0, policy.id, clock.id, "right_censored_no_valid_tick", None, None)
        for clock in config.clocks
        for policy in config.policies
    )
    from xau_trigger.retro_bot_002 import PaperOutcome

    wrong = tuple(PaperOutcome("wrong", "wrong", "right_censored_no_valid_tick", None, None) for _ in base)
    with pytest.raises(RetroBotInputError, match="identity"):
        wrap_paper_outcomes(wrong, (interval,), config)


def test_wrapper_rejects_non_numeric_marked_return() -> None:
    config = load_config()
    interval = _interval("2026-01-01 02:00", "2026-01-01 02:10")
    from xau_trigger.retro_bot_002 import PaperOutcome

    malformed = tuple(
        PaperOutcome(policy.id, clock.id, "emitted_marked", "buy", "not-a-number")
        for clock in config.clocks
        for policy in config.policies
    )
    with pytest.raises(RetroBotInputError, match="marked outcome"):
        wrap_paper_outcomes(malformed, (interval,), config)


def test_aggregate_rejects_non_contiguous_cycle_indexes() -> None:
    config = load_config()
    outcomes = []
    for clock in config.clocks:
        for policy in config.policies:
            outcomes.extend([
                SequentialOutcome(0, policy.id, clock.id, "excluded_overlap", None, None),
                SequentialOutcome(2, policy.id, clock.id, "excluded_overlap", None, None),
            ])
    with pytest.raises(RetroBotInputError, match="coverage/order"):
        aggregate_sequential_outcomes(outcomes, config, report_manifest_sha256=config.source_receipt["report_manifest_sha256"], tick_manifest_sha256=config.source_receipt["tick_manifest_sha256"])


def test_aggregate_rejects_nonfinite_marked_return() -> None:
    config = load_config()
    outcomes = [
        SequentialOutcome(0, policy.id, clock.id, "emitted_marked", "buy", float("nan"))
        for clock in config.clocks
        for policy in config.policies
    ]
    with pytest.raises(RetroBotInputError, match="marked sequential outcome"):
        aggregate_sequential_outcomes(outcomes, config, report_manifest_sha256=config.source_receipt["report_manifest_sha256"], tick_manifest_sha256=config.source_receipt["tick_manifest_sha256"])
