from pathlib import Path
from dataclasses import replace

import pandas as pd
import pytest

from xau_trigger.retro_bot import EligibleInterval, load_config
from xau_trigger.retro_bot_002 import (
    aggregate_paper_outcomes,
    paper_backtest_interval,
    paper_backtest_intervals,
    validate_paper_aggregate,
)


def _interval(state: str = "ONE_BUY") -> EligibleInterval:
    return EligibleInterval("synthetic.html", 1, state, pd.Timestamp("2026-01-01 02:00:00"), pd.Timestamp("2026-01-01 02:10:00"), 600)


def _ticks(path: Path, rows: str) -> Path:
    path.write_text("time_utc,bid,ask\n" + rows, encoding="utf-8")
    return path


def test_action_and_mark_use_conservative_bid_ask_sides(tmp_path: Path) -> None:
    config = load_config()
    clock = next(item for item in config.clocks if item.id == "utc_plus_2")
    policy = next(item for item in config.policies if item.id == "wait_300_seconds")
    ticks = _ticks(tmp_path / "ticks.csv", "2026-01-01T00:05:00Z,10,12\n2026-01-01T00:10:00Z,13,15\n")
    sell = paper_backtest_interval(_interval("ONE_BUY"), policy, clock, config, [ticks])
    buy = paper_backtest_interval(_interval("ONE_SELL"), policy, clock, config, [ticks])
    assert sell.status == buy.status == "emitted_marked"
    assert sell.net_return == pytest.approx(-5.0)
    assert buy.net_return == pytest.approx(1.0)


def test_no_lookahead_and_censoring(tmp_path: Path) -> None:
    config = load_config()
    clock = next(item for item in config.clocks if item.id == "utc_plus_2")
    policy = next(item for item in config.policies if item.id == "wait_300_seconds")
    before_anchor = _ticks(tmp_path / "before.csv", "2026-01-01T00:05:00Z,10,12\n")
    assert paper_backtest_interval(_interval(), policy, clock, config, [before_anchor]).status == "emitted_mark_censored"
    after_only = _ticks(tmp_path / "after.csv", "2026-01-01T00:10:00Z,13,15\n")
    assert paper_backtest_interval(_interval(), policy, clock, config, [after_only]).status == "right_censored_no_valid_tick"


def test_single_interval_honors_requested_policy_and_clock(tmp_path: Path) -> None:
    config = load_config()
    clock = next(item for item in config.clocks if item.id == "utc_plus_3")
    policy = next(item for item in config.policies if item.id == "wait_900_seconds")
    ticks = _ticks(tmp_path / "ticks.csv", "2026-01-01T00:05:00Z,10,12\n")
    outcome = paper_backtest_interval(_interval(), policy, clock, config, [ticks])
    assert (outcome.policy_id, outcome.clock_id) == ("wait_900_seconds", "utc_plus_3")
    assert outcome.status == "right_censored_delay_not_reached"


def test_aggregate_reconciles_and_rejects_tamper() -> None:
    config = load_config()
    outcomes = paper_backtest_intervals((), config, [])
    payload = aggregate_paper_outcomes(outcomes, config, report_manifest_sha256=config.source_receipt["report_manifest_sha256"], tick_manifest_sha256=config.source_receipt["tick_manifest_sha256"])
    validate_paper_aggregate(payload, config)
    tampered = dict(payload)
    tampered["policy_clock_rows"] = list(payload["policy_clock_rows"])
    tampered["policy_clock_rows"][0] = dict(tampered["policy_clock_rows"][0])
    tampered["policy_clock_rows"][0]["eligible_interval_count"] = 1
    with pytest.raises(Exception, match="digest"):
        validate_paper_aggregate(tampered, config)


def test_privacy_validator_rejects_raw_like_fields() -> None:
    config = load_config()
    payload = aggregate_paper_outcomes((), config, report_manifest_sha256=config.source_receipt["report_manifest_sha256"], tick_manifest_sha256=config.source_receipt["tick_manifest_sha256"])
    payload["raw_price"] = 1
    with pytest.raises(Exception):
        validate_paper_aggregate(payload, config)


def test_schema_validator_rejects_boolean_integer_tamper() -> None:
    config = load_config()
    payload = aggregate_paper_outcomes((), config, report_manifest_sha256=config.source_receipt["report_manifest_sha256"], tick_manifest_sha256=config.source_receipt["tick_manifest_sha256"])
    payload["schema_version"] = True
    from xau_trigger.retro_bot import _canonical_digest

    payload["aggregate_sha256"] = _canonical_digest(payload, "aggregate_sha256")
    with pytest.raises(Exception):
        validate_paper_aggregate(payload, config)


def test_library_rejects_mutated_config() -> None:
    config = load_config()
    mutated = replace(config, case_id="not-locked")
    with pytest.raises(Exception, match="config is not locked"):
        paper_backtest_intervals((), mutated, [])
    with pytest.raises(Exception, match="config is not locked"):
        aggregate_paper_outcomes((), mutated, report_manifest_sha256="x", tick_manifest_sha256="y")
