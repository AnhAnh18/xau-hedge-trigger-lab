from __future__ import annotations

import pytest
from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_live_evidence_001 import FROZEN_GATE_DIGEST, digest
from xau_trigger.retro_live_evidence_003 import evaluate_fidelity, seal_holdout_block, verify_fidelity_aggregate, verify_holdout_block, verify_holdout_result


def _row(index: int) -> dict:
    return {"comparison_id": f"x-{index}", "categories":["normal_hedge"], "buy_actions":1,"sell_actions":1,"observed_actions":2,"state_match": True, "direction_match": True, "ordering_match": True, "timing_delta_seconds": 2, "lot_observed_quantity": "0.30000000", "lot_predicted_quantity": "0.30000000", "duplicate_actions": 0, "eligible": True, "censored": False, "future_read": False, "illegal_transition": False,"negative_lots":0,"same_tick_double_actions":0,"conservation_failures":0}


def test_fidelity_is_redacted_and_deterministic() -> None:
    first = evaluate_fidelity([_row(1), _row(2)])
    assert first == evaluate_fidelity([_row(1), _row(2)])
    assert first["synthetic_only"] is True and first["metrics"]["state_parity"] == 1.0 and first["actionful_sufficient"] is False
    assert verify_fidelity_aggregate(first)


def test_fidelity_rejects_censor_and_tamper_shapes() -> None:
    bad = _row(1); bad["eligible"] = False; bad["censored"] = True
    with pytest.raises(RetroBotInputError): evaluate_fidelity([bad])
    with pytest.raises(RetroBotInputError): evaluate_fidelity([_row(1)], synthetic_only=1)
    malformed = evaluate_fidelity([_row(1)]); malformed["comparison_count"] = 0; malformed["aggregate_sha256"] = digest({key: malformed[key] for key in malformed if key != "aggregate_sha256"})
    with pytest.raises(RetroBotInputError): verify_fidelity_aggregate(malformed)
    invalid_category = _row(2); invalid_category["categories"] = ["made_up"]
    with pytest.raises(RetroBotInputError): evaluate_fidelity([invalid_category])


def test_holdout_receipt_is_one_shot_and_bound() -> None:
    receipt = seal_holdout_block(gate_digest=FROZEN_GATE_DIGEST, source_digest="a" * 64, input_digest=digest({"x": 1}), nonce="holdout-1234")
    used: set[str] = set()
    assert verify_holdout_block(receipt, used_nonces=used)
    with pytest.raises(RetroBotInputError): verify_holdout_block(receipt, used_nonces=used)


def test_synthetic_holdout_evaluation_is_sealed_and_robustness_aware() -> None:
    folds = [evaluate_fidelity([_row(index)]) for index in (1, 2, 3)]
    receipt = seal_holdout_block(gate_digest=FROZEN_GATE_DIGEST, source_digest="a" * 64, input_digest=folds[2]["input_digest"], nonce="holdout-5678")
    result = __import__("xau_trigger.retro_live_evidence_003", fromlist=["evaluate_holdout"]).evaluate_holdout(development=folds[0], validation=folds[1], holdout=folds[2], receipt=receipt, used_nonces=set(), robustness_results=[True, True, False], trusted_source_receipt_digest="a" * 64, fold_bounds=[[0, 1], [1, 2], [2, 3]])
    assert result["holdout_consumed"] is True and result["status"] == "hold"
    assert verify_holdout_result(result)


def test_holdout_requires_trusted_source_and_fold_order() -> None:
    folds = [evaluate_fidelity([_row(index)]) for index in (1, 2, 3)]
    receipt = seal_holdout_block(gate_digest=FROZEN_GATE_DIGEST, source_digest="a" * 64, input_digest=folds[2]["input_digest"], nonce="holdout-9012")
    with pytest.raises(RetroBotInputError):
        __import__("xau_trigger.retro_live_evidence_003", fromlist=["evaluate_holdout"]).evaluate_holdout(development=folds[0], validation=folds[1], holdout=folds[2], receipt=receipt, used_nonces=set(), robustness_results=[True], trusted_source_receipt_digest="b" * 64, fold_bounds=[[0, 1], [1, 2], [2, 3]])
