from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from xau_trigger.retro_bot import (
    EligibleInterval,
    Policy,
    RetroBotInputError,
    eligible_intervals,
    lead_time_band,
    load_config,
    replay_rehedge_policy,
    replay_rehedge_policies,
    replay_rehedge_intervals,
)


def _interval_frame(start: str, end: str, state: str = "ONE_BUY") -> tuple[pd.DataFrame, pd.DataFrame]:
    start_time = pd.Timestamp(start)
    end_time = pd.Timestamp(end)
    before = "UNLOCK_TO_BUY" if state == "ONE_BUY" else "UNLOCK_TO_SELL"
    after = "REHEDGE_SELL" if state == "ONE_BUY" else "REHEDGE_BUY"
    events = pd.DataFrame(
        {
            "event_time": [start_time, end_time],
            "ordering_quality": ["deterministic", "deterministic"],
            "behavior_type": [before, after],
        }
    )
    intervals = pd.DataFrame(
        {
            "interval_id": [7],
            "start_time": [start_time],
            "end_time": [end_time],
            "duration_seconds": [(end_time - start_time).total_seconds()],
            "state": [state],
            "preceding_event_type": [before],
            "following_event_type": [after],
        }
    )
    return events, intervals


def test_eligible_intervals_allow_cross_midnight_and_reject_registered_exceptions() -> None:
    config = load_config()
    events, intervals = _interval_frame("2026-03-03 23:55:00", "2026-03-04 00:10:00")
    lifecycle = pd.DataFrame({"symbol": ["XAUUSD"]})

    accepted = eligible_intervals("report-005.html", lifecycle, events, intervals, pd.DataFrame(), pd.DataFrame(), config)
    assert len(accepted) == 1
    assert accepted[0].action_side == "sell"
    assert accepted[0].duration_seconds == 900

    state_exception = pd.DataFrame({"event_time": [pd.Timestamp("2026-03-04 00:00:00")]})
    assert not eligible_intervals("report-005.html", lifecycle, events, intervals, pd.DataFrame(), state_exception, config)
    assert not eligible_intervals("report-005.html", lifecycle, events, intervals, pd.DataFrame({"exception_type": ["x"]}), pd.DataFrame(), config)
    with_non_xau = pd.DataFrame({"symbol": ["XAUUSD", "EURUSD"]})
    with pytest.raises(RetroBotInputError, match="non-XAUUSD"):
        eligible_intervals("report-005.html", with_non_xau, events, intervals, pd.DataFrame(), pd.DataFrame(), config)

    mismatched_duration = intervals.copy()
    mismatched_duration.loc[0, "duration_seconds"] = 300
    assert not eligible_intervals("report-005.html", lifecycle, events, mismatched_duration, pd.DataFrame(), pd.DataFrame(), config)

    mismatched_event = events.copy()
    mismatched_event.loc[0, "behavior_type"] = "UNLOCK_TO_SELL"
    assert not eligible_intervals("report-005.html", lifecycle, mismatched_event, intervals, pd.DataFrame(), pd.DataFrame(), config)


def test_replay_rehedge_policy_uses_first_tick_after_delay_and_censors(tmp_path: Path) -> None:
    config = load_config()
    clock = next(clock for clock in config.clocks if clock.id == "utc_plus_2")
    wait_300 = next(policy for policy in config.policies if policy.id == "wait_300_seconds")
    wait_3600 = next(policy for policy in config.policies if policy.id == "wait_3600_seconds")
    interval = EligibleInterval(
        report_alias="report-001.html",
        interval_id=1,
        state="ONE_BUY",
        unlock_time_server=pd.Timestamp("2026-01-01 02:00:00"),
        observed_rehedge_time_server=pd.Timestamp("2026-01-01 02:10:00"),
        duration_seconds=600,
    )
    ticks = tmp_path / "ticks.csv"
    ticks.write_text(
        "time_utc,bid,ask\n"
        "2026-01-01T00:04:59Z,1,2\n"
        "2026-01-01T00:05:00Z,1,2\n"
        "2026-01-01T00:10:00Z,1,2\n",
        encoding="utf-8",
    )

    emitted = replay_rehedge_policy(interval, wait_300, clock, config, [ticks])
    assert emitted.status == "emitted"
    assert emitted.action_side == "sell"
    assert emitted.lead_seconds == 300.0
    assert emitted.valid_tick_count == 1
    assert lead_time_band(emitted.lead_seconds, config) == "300_to_under_900_seconds"

    censored = replay_rehedge_policy(interval, wait_3600, clock, config, [ticks])
    assert censored.status == "right_censored_delay_not_reached"
    assert censored.action_side is None

    with pytest.raises(RetroBotInputError, match="locked RETRO-BOT policies"):
        replay_rehedge_policy(interval, Policy("unregistered", 1), clock, config, [ticks])


def test_replay_rehedge_policy_excludes_dst_unresolved_interval(tmp_path: Path) -> None:
    config = load_config()
    clock = next(clock for clock in config.clocks if clock.id == "eu_dst_2025_2026")
    policy = next(policy for policy in config.policies if policy.id == "first_available_tick")
    interval = EligibleInterval(
        report_alias="report-005.html",
        interval_id=9,
        state="ONE_SELL",
        unlock_time_server=pd.Timestamp("2026-03-29 03:30:00"),
        observed_rehedge_time_server=pd.Timestamp("2026-03-29 03:50:00"),
        duration_seconds=1200,
    )

    outcome = replay_rehedge_policy(interval, policy, clock, config, [tmp_path / "not-opened.csv"])
    assert outcome.status == "excluded_clock_unresolved"
    assert outcome.action_side is None


def test_dst_target_unresolved_excludes_every_policy_for_the_interval(tmp_path: Path) -> None:
    config = load_config()
    clock = next(clock for clock in config.clocks if clock.id == "eu_dst_2025_2026")
    interval = EligibleInterval(
        report_alias="report-005.html",
        interval_id=10,
        state="ONE_BUY",
        unlock_time_server=pd.Timestamp("2026-03-29 02:50:00"),
        observed_rehedge_time_server=pd.Timestamp("2026-03-29 04:20:00"),
        duration_seconds=5400,
    )
    ticks = tmp_path / "ticks.csv"
    ticks.write_text(
        "time_utc,bid,ask\n2026-03-29T00:00:00Z,1,2\n",
        encoding="utf-8",
    )

    outcomes = replay_rehedge_policies(interval, config.policies, clock, config, [ticks])
    assert len(outcomes) == len(config.policies)
    assert {outcome.status for outcome in outcomes} == {"excluded_clock_unresolved"}

    batched = replay_rehedge_intervals((interval,), config, [ticks])
    dst_outcomes = [outcome for outcome in batched if outcome.clock_id == clock.id]
    assert {outcome.status for outcome in dst_outcomes} == {"excluded_clock_unresolved"}


def test_batched_replay_matches_single_interval_replay(tmp_path: Path) -> None:
    config = load_config()
    clock = next(clock for clock in config.clocks if clock.id == "utc_plus_2")
    interval_a = EligibleInterval(
        report_alias="report-001.html",
        interval_id=1,
        state="ONE_BUY",
        unlock_time_server=pd.Timestamp("2026-01-01 02:00:00"),
        observed_rehedge_time_server=pd.Timestamp("2026-01-01 02:10:00"),
        duration_seconds=600,
    )
    interval_b = EligibleInterval(
        report_alias="report-001.html",
        interval_id=2,
        state="ONE_SELL",
        unlock_time_server=pd.Timestamp("2026-01-02 02:00:00"),
        observed_rehedge_time_server=pd.Timestamp("2026-01-02 02:20:00"),
        duration_seconds=1200,
    )
    ticks = tmp_path / "ticks.csv"
    ticks.write_text(
        "time_utc,bid,ask\n"
        "2026-01-01T00:05:00Z,1,2\n"
        "2026-01-02T00:10:00Z,1,2\n",
        encoding="utf-8",
    )
    single = tuple(
        replay_rehedge_policies(interval, config.policies, clock, config, [ticks])
        for interval in (interval_a, interval_b)
    )
    batched = replay_rehedge_intervals((interval_a, interval_b), config, [ticks])
    expected = tuple(outcome for group in single for outcome in group if outcome.clock_id == clock.id)
    actual = tuple(outcome for outcome in batched if outcome.clock_id == clock.id)
    assert actual == expected
