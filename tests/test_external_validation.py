from __future__ import annotations

import pytest

from xau_trigger.external_validation import (
    apply_external_acquisition_amendment,
    canonical_json_sha256,
    external_endpoint_verdict,
)


def _metric(mean: float, family_low: float, ci_high: float) -> dict:
    return {
        "mean": mean,
        "familywise_one_sided_low": family_low,
        "ci95_high": ci_high,
    }


@pytest.mark.parametrize(
    ("metric", "sessions", "expected"),
    [
        (_metric(0.2, 0.01, 0.4), [0.1, -0.1, 0.2], "supported"),
        (_metric(0.2, 0.01, 0.4), [0.1, -0.1, -0.2], "mixed/inconclusive"),
        (_metric(0.2, -0.01, 0.4), [0.1, 0.2, 0.3], "weak/inconclusive"),
        (_metric(-0.2, -0.4, 0.0), [-0.1, -0.2, -0.3], "rejected"),
        (_metric(-0.01, -0.1, 0.2), [-0.1, 0.1, -0.1], "inconclusive"),
    ],
)
def test_external_endpoint_verdict_contract(
    metric: dict,
    sessions: list[float],
    expected: str,
) -> None:
    assert external_endpoint_verdict(metric, sessions)["verdict"] == expected


def test_external_endpoint_verdict_requires_all_three_sessions() -> None:
    with pytest.raises(ValueError, match="exactly three"):
        external_endpoint_verdict(_metric(0.1, 0.01, 0.2), [0.1, 0.2])


def test_acquisition_amendment_rehashes_the_amended_payload() -> None:
    validation = {
        "sessions": ["2026-07-27", "2026-07-28", "2026-07-29"],
        "status": "FAIL",
        "ticks": {
            "status": "FAIL",
            "files": [{"status": "PASS"}],
            "sessions": [
                {
                    "date": "2026-07-27",
                    "status": "FAIL",
                    "has_no_intraday_coverage_gap": False,
                    "coverage_gaps": [
                        {
                            "start": "2026-07-27T18:08:35.303000",
                            "end": "2026-07-27T18:10:21.660000",
                            "duration_seconds": 106.357,
                            "classification": "unknown",
                        }
                    ],
                },
                {
                    "date": "2026-07-28",
                    "status": "PASS",
                    "coverage_gaps": [],
                },
                {
                    "date": "2026-07-29",
                    "status": "PASS",
                    "coverage_gaps": [],
                },
            ],
        },
        "trade_reports": {"status": "PASS"},
        "deterministic_validation_sha256": "raw-hash",
    }
    amendment = {
        "amendment_id": "test-amendment",
        "external_decision_contract": {
            "registered_sessions": [
                "2026-07-27",
                "2026-07-28",
                "2026-07-29",
            ]
        },
        "replicated_source_quote_gap": {
            "session": "2026-07-27",
            "start": "2026-07-27T18:08:35.303000",
            "end": "2026-07-27T18:10:21.660000",
            "duration_seconds": 106.357,
            "classification": "replicated_source_quote_gap",
            "risk_support_policy": "exclude",
            "event_policy": "retain",
        },
    }

    amended = apply_external_acquisition_amendment(validation, amendment)
    amended_hash = amended.pop("deterministic_amended_validation_sha256")

    assert amended["raw_deterministic_validation_sha256"] == "raw-hash"
    assert amended["status"] == "PASS_WITH_REPLICATED_SOURCE_QUOTE_GAP"
    assert amended_hash == canonical_json_sha256(amended)
