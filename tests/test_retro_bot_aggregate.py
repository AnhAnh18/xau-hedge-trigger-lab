from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

from xau_trigger.retro_bot import (
    ReplayOutcome,
    RetroBotInputError,
    _canonical_digest,
    aggregate_outcomes,
    load_config,
    render_aggregate_markdown,
    validate_aggregate_payload,
)


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_retro_bot_replay_script",
    ROOT / "scripts" / "run_retro_bot_replay.py",
)
assert SPEC is not None and SPEC.loader is not None
REPLAY_CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPLAY_CLI)


def _registered_outcomes() -> tuple[ReplayOutcome, ...]:
    config = load_config()
    outputs = []
    statuses = (
        ("emitted", "buy", 30.0),
        ("right_censored_delay_not_reached", None, None),
        ("right_censored_no_valid_tick", None, None),
        ("excluded_clock_unresolved", None, None),
    )
    for clock in config.clocks:
        for policy, (status, side, lead) in zip(config.policies, statuses, strict=True):
            outputs.append(
                ReplayOutcome(
                    report_alias="report-001.html",
                    interval_id=1,
                    policy_id=policy.id,
                    clock_id=clock.id,
                    status=status,
                    action_side=side,
                    lead_seconds=lead,
                    valid_tick_count=1 if status == "emitted" else 0,
                )
            )
    return tuple(outputs)


def test_aggregate_is_complete_redacted_and_repeatable() -> None:
    config = load_config()
    kwargs = {
        "report_manifest_sha256": config.source_receipt["report_manifest_sha256"],
        "tick_manifest_sha256": config.source_receipt["tick_manifest_sha256"],
    }
    first = aggregate_outcomes(_registered_outcomes(), config, **kwargs)
    second = aggregate_outcomes(_registered_outcomes(), config, **kwargs)

    assert first == second
    assert len(first["policy_clock_rows"]) == 12
    assert all("report_alias" not in row and "interval_id" not in row for row in first["policy_clock_rows"])
    emitted = [row for row in first["policy_clock_rows"] if row["emitted_count"]]
    assert len(emitted) == 3
    assert all(row["lead_time_bands"]["0_to_under_60_seconds"] == 1 for row in emitted)
    rendered = render_aggregate_markdown(first, config)
    assert "no policy or clock is selected as a winner" in rendered


def test_aggregate_rejects_digest_tamper_and_raw_like_keys() -> None:
    config = load_config()
    payload = aggregate_outcomes(
        _registered_outcomes(),
        config,
        report_manifest_sha256=config.source_receipt["report_manifest_sha256"],
        tick_manifest_sha256=config.source_receipt["tick_manifest_sha256"],
    )
    tampered = copy.deepcopy(payload)
    tampered["policy_clock_rows"][0]["emitted_count"] = 2
    with pytest.raises(RetroBotInputError, match="self-digest mismatch"):
        validate_aggregate_payload(tampered, config)

    raw_like = copy.deepcopy(payload)
    raw_like["policy_clock_rows"][0]["price"] = 1
    raw_like["aggregate_sha256"] = _canonical_digest(raw_like, "aggregate_sha256")
    with pytest.raises(RetroBotInputError, match="row schema"):
        validate_aggregate_payload(raw_like, config)

    unknown = copy.deepcopy(payload)
    unknown["arbitrary_payload"] = {"opaque": "unreviewed"}
    unknown["aggregate_sha256"] = _canonical_digest(unknown, "aggregate_sha256")
    with pytest.raises(RetroBotInputError, match="root schema"):
        validate_aggregate_payload(unknown, config)


def test_aggregate_rejects_unknown_pairs_and_unequal_coverage() -> None:
    config = load_config()
    base = _registered_outcomes()
    unknown_pair = base + (
        ReplayOutcome("report-001.html", 99, "unregistered", "utc_plus_2", "emitted", "buy", 1.0, 1),
    )
    with pytest.raises(RetroBotInputError, match="unregistered policy/clock"):
        aggregate_outcomes(
            unknown_pair,
            config,
            report_manifest_sha256=config.source_receipt["report_manifest_sha256"],
            tick_manifest_sha256=config.source_receipt["tick_manifest_sha256"],
        )

    unequal = list(base)
    unequal.pop()
    with pytest.raises(RetroBotInputError, match="coverage set"):
        aggregate_outcomes(
            unequal,
            config,
            report_manifest_sha256=config.source_receipt["report_manifest_sha256"],
            tick_manifest_sha256=config.source_receipt["tick_manifest_sha256"],
        )


def test_aggregate_rejects_rehashed_boolean_counts() -> None:
    config = load_config()
    payload = aggregate_outcomes(
        _registered_outcomes(),
        config,
        report_manifest_sha256=config.source_receipt["report_manifest_sha256"],
        tick_manifest_sha256=config.source_receipt["tick_manifest_sha256"],
    )
    invalid = copy.deepcopy(payload)
    row = invalid["policy_clock_rows"][0]
    row["eligible_interval_count"] = True
    row["emitted_count"] = True
    row["direction_match_count"] = True
    row["lead_time_bands"]["0_to_under_60_seconds"] = True
    invalid["aggregate_sha256"] = _canonical_digest(invalid, "aggregate_sha256")

    with pytest.raises(RetroBotInputError, match="aggregate count is invalid"):
        validate_aggregate_payload(invalid, config)

    invalid_schema = copy.deepcopy(payload)
    invalid_schema["schema_version"] = True
    invalid_schema["aggregate_sha256"] = _canonical_digest(invalid_schema, "aggregate_sha256")
    with pytest.raises(RetroBotInputError, match="aggregate schema/case"):
        validate_aggregate_payload(invalid_schema, config)


def test_replay_cli_pins_output_to_registered_fresh_non_source_child(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    replay_root = tmp_path / "registered" / "replay_runs"
    output = replay_root / "run-001"
    report_run = tmp_path / "reports" / "run-001"
    tick_run = tmp_path / "ticks" / "run-001"
    monkeypatch.setattr(REPLAY_CLI, "REPLAY_RUN_ROOT", replay_root)

    REPLAY_CLI._require_registered_output_run(output, report_run, tick_run)

    with pytest.raises(RetroBotInputError, match="registered replay-run directory"):
        REPLAY_CLI._require_registered_output_run(tmp_path / "other" / "run-001", report_run, tick_run)
    with pytest.raises(RetroBotInputError, match="registered replay-run directory"):
        REPLAY_CLI._require_registered_output_run(output / "nested", report_run, tick_run)
    with pytest.raises(RetroBotInputError, match="overlaps a verified source"):
        REPLAY_CLI._require_registered_output_run(output, output, tick_run)
