from __future__ import annotations

import pandas as pd
import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_004 import (
    CASE_ID,
    CENSOR_CLASSES,
    WindowRecord,
    build_population_aggregate,
    classify_window,
    fold_for_report,
    load_population_config,
    map_clock_boundary,
    validate_aggregate,
)


def _record(alias: str, day: str, side: str, unit: str, **kwargs: object) -> WindowRecord:
    start = pd.Timestamp(day)
    return WindowRecord(alias, start, start + pd.Timedelta(seconds=60), side, unit, **kwargs)


def _supported_records() -> tuple[WindowRecord, ...]:
    return (
        _record("report-001.html", "2025-11-02", "ONE_BUY", "u1"),
        _record("report-001.html", "2025-11-03", "ONE_SELL", "u2"),
        _record("report-001.html", "2025-11-04", "ONE_BUY", "u3"),
        _record("report-001.html", "2025-11-05", "ONE_SELL", "u4"),
        _record("report-006.html", "2026-04-02", "ONE_BUY", "u5"),
        _record("report-006.html", "2026-04-03", "ONE_SELL", "u6"),
        _record("report-006.html", "2026-04-04", "ONE_BUY", "u7"),
        _record("report-006.html", "2026-04-05", "ONE_SELL", "u8"),
        _record("report-008.html", "2026-06-02", "ONE_BUY", "u9"),
        _record("report-008.html", "2026-06-03", "ONE_SELL", "u10"),
        _record("report-008.html", "2026-06-04", "ONE_BUY", "u11"),
        _record("report-008.html", "2026-06-05", "ONE_SELL", "u12"),
    )


def test_rb008_config_is_self_hashed_and_temporally_pinned() -> None:
    config = load_population_config()
    assert config.config_sha256 == "26fec4baa2b8e2680cc17afaad299bbbb00afba32810865ac60bf28eb2e49ebf"
    assert tuple(item.alias for item in config.report_ranges) == tuple(f"report-{i:03d}.html" for i in range(1, 10))
    assert tuple(item.id for item in config.bootstrap_scenarios) == ("left_censored", "fixed_warmup_seed")
    assert config.bootstrap_scenarios[1].seed_state == "HEDGED"


def test_fold_assignment_is_unique_and_chronological() -> None:
    config = load_population_config()
    assert fold_for_report("report-001.html", config).id == "development"
    assert fold_for_report("report-006.html", config).id == "validation"
    assert fold_for_report("report-008.html", config).id == "holdout"
    with pytest.raises(RetroBotInputError):
        fold_for_report("report-999.html", config)


def test_censor_precedence_is_single_class_and_fail_closed() -> None:
    config = load_population_config()
    record = _record(
        "report-001.html", "2025-11-02", "ONE_BUY", "u1",
        clock_status="ambiguous", invalid_transition=True, has_terminal=False, has_valid_tick=False,
    )
    fold, status = classify_window(record, "fixed_warmup_seed", config)
    assert fold == "development"
    assert status == "clock_unresolved"
    left_fold, left_status = classify_window(record, "left_censored", config)
    assert left_fold == "development"
    assert left_status == "clock_unresolved"
    assert CENSOR_CLASSES[0] == "clock_unresolved"


def test_cross_fold_continuation_cannot_become_valid() -> None:
    config = load_population_config()
    record = _record("report-005.html", "2026-03-31 23:59:30", "ONE_BUY", "u1")
    record = WindowRecord(
        record.report_alias, record.start_server, pd.Timestamp("2026-04-01 00:00:30"),
        record.side, record.independent_unit,
    )
    _, status = classify_window(record, "fixed_warmup_seed", config)
    assert status == "cross_fold_continuation"


def test_report_alias_ownership_and_invalid_side_fail_closed() -> None:
    config = load_population_config()
    wrong_month = _record("report-001.html", "2026-06-02", "ONE_BUY", "u1")
    _, wrong_status = classify_window(wrong_month, "fixed_warmup_seed", config)
    assert wrong_status == "invalid_transition"
    invalid_side = _record("report-001.html", "2025-11-02", "UNKNOWN", "u1")
    _, invalid_status = classify_window(invalid_side, "left_censored", config)
    assert invalid_status == "invalid_transition"


def test_dst_boundary_mapping_is_explicit() -> None:
    assert map_clock_boundary("eu_dst_2025_2026", "2026-03-29 03:30:00").status == "nonexistent"
    assert map_clock_boundary("eu_dst_2025_2026", "2026-03-29 04:30:00").status == "unique"


def test_left_censored_and_fixed_seed_rows_are_reported_side_by_side() -> None:
    config = load_population_config()
    payload = build_population_aggregate(_supported_records(), config)
    assert payload["case_id"] == CASE_ID
    assert len(payload["policy_clock_rows"]) == 18
    left = [row for row in payload["policy_clock_rows"] if row["bootstrap"] == "left_censored"]
    fixed = [row for row in payload["policy_clock_rows"] if row["bootstrap"] == "fixed_warmup_seed"]
    assert all(row["support_status"] == "insufficient_population" for row in left)
    assert all(row["support_status"] == "sufficient" for row in fixed)
    assert all(row["valid_windows"] == 0 for row in left)
    assert all(row["valid_windows"] == 4 for row in fixed)
    validate_aggregate(payload, config)


def test_aggregate_digest_is_deterministic_and_rejects_tampering() -> None:
    config = load_population_config()
    first = build_population_aggregate(_supported_records(), config)
    second = build_population_aggregate(_supported_records(), config)
    assert first == second
    tampered = dict(first)
    tampered["aggregate_sha256"] = "0" * 64
    with pytest.raises(RetroBotInputError):
        validate_aggregate(tampered, config)


def test_aggregate_rejects_duplicate_clock_rows_and_negative_counts() -> None:
    config = load_population_config()
    payload = build_population_aggregate(_supported_records(), config)
    duplicate = dict(payload)
    duplicate["policy_clock_rows"] = list(payload["policy_clock_rows"])
    duplicate["policy_clock_rows"][1] = dict(duplicate["policy_clock_rows"][0])
    duplicate["aggregate_sha256"] = "TO_BE_FILLED"
    from xau_trigger.retro_bot_004 import _canonical_digest
    duplicate["aggregate_sha256"] = _canonical_digest(duplicate, "aggregate_sha256")
    with pytest.raises(RetroBotInputError):
        validate_aggregate(duplicate, config)
    negative = dict(payload)
    negative["policy_clock_rows"] = [dict(row) for row in payload["policy_clock_rows"]]
    negative["policy_clock_rows"][0]["total_windows"] = -1
    negative["aggregate_sha256"] = _canonical_digest(negative, "aggregate_sha256")
    with pytest.raises(RetroBotInputError):
        validate_aggregate(negative, config)


def test_aggregate_rejects_later_overlapping_window_without_sorting() -> None:
    config = load_population_config()
    records = (
        WindowRecord("report-001.html", pd.Timestamp("2025-11-02"), pd.Timestamp("2025-11-02 01:00:00"), "ONE_BUY", "u1"),
        WindowRecord("report-001.html", pd.Timestamp("2025-11-02 00:30:00"), pd.Timestamp("2025-11-02 01:30:00"), "ONE_SELL", "u2"),
    )
    payload = build_population_aggregate(records, config)
    development = [
        row for row in payload["policy_clock_rows"]
        if row["fold"] == "development" and row["bootstrap"] == "fixed_warmup_seed"
    ]
    assert all(row["valid_windows"] == 1 for row in development)
    assert all(row["censor_counts"]["invalid_transition"] == 1 for row in development)
