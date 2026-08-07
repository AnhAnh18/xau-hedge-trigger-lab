from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_live_evidence_001 import FROZEN_GATE_DIGEST, digest
from xau_trigger.retro_live_evidence_003 import evaluate_fidelity, evaluate_holdout, seal_holdout_block
from xau_trigger.retro_live_evidence_004_ledger import (
    GENESIS_DIGEST,
    append_ledger_entry,
    context_digest,
    genesis_digest,
    verify_ledger,
)


ROOT = Path(__file__).parents[1]
SOURCE = "a" * 64
FOLDS = [digest(["development", "validation", "holdout"]), digest([[0, 1], [1, 2], [2, 3]])]


def _row(index: int) -> dict[str, object]:
    return {"comparison_id": f"x-{index}", "categories": ["normal_hedge"], "buy_actions": 1, "sell_actions": 1, "observed_actions": 2, "state_match": True, "direction_match": True, "ordering_match": True, "timing_delta_seconds": 2, "lot_observed_quantity": "0.30000000", "lot_predicted_quantity": "0.30000000", "duplicate_actions": 0, "eligible": True, "censored": False, "future_read": False, "illegal_transition": False, "negative_lots": 0, "same_tick_double_actions": 0, "conservation_failures": 0}


def _materials(nonce: str = "holdout-1234", seed: int = 0) -> tuple[dict, dict, dict[str, str], str]:
    folds = [evaluate_fidelity([_row(index + seed)]) for index in (1, 2, 3)]
    receipt = seal_holdout_block(gate_digest=FROZEN_GATE_DIGEST, source_digest=SOURCE, input_digest=folds[2]["input_digest"], nonce=nonce, fold_order_digest=FOLDS[0], fold_bounds_digest=FOLDS[1])
    proof = evaluate_holdout(development=folds[0], validation=folds[1], holdout=folds[2], receipt=receipt, used_nonces=set(), robustness_results=[True, False], trusted_source_receipt_digest=SOURCE, fold_bounds=[[0, 1], [1, 2], [2, 3]], trusted_fold_order_digest=FOLDS[0], trusted_fold_bounds_digest=FOLDS[1])
    return receipt, proof, {"source_digest": SOURCE, "fold_order_digest": FOLDS[0], "fold_bounds_digest": FOLDS[1]}, folds[2]["input_digest"]


def _empty(context: dict[str, str]) -> dict:
    return {"schema_version": 1, "case_id": "RETRO-LIVE-EVIDENCE-004", "context_digest": context_digest(**context), "genesis_digest": GENESIS_DIGEST, "entries": [], "head_digest": GENESIS_DIGEST}


def test_genesis_and_two_independent_runs_are_deterministic() -> None:
    assert genesis_digest() == GENESIS_DIGEST
    receipt, proof, context, input_digest = _materials()
    assert context_digest(**context) == "ccf9c006edf4eb8d8a93c858c1aa45379a86d8a33c7ee657d487ffd7f38784fa"
    ledger = _empty(context)
    first = append_ledger_entry(ledger=ledger, expected_head_digest=GENESIS_DIGEST, receipt=receipt, evaluation_proof=proof, evaluation_succeeded=True, input_digest=input_digest, trusted_input_digests=[input_digest], **context)
    second = append_ledger_entry(ledger=ledger, expected_head_digest=GENESIS_DIGEST, receipt=receipt, evaluation_proof=proof, evaluation_succeeded=True, input_digest=input_digest, trusted_input_digests=[input_digest], **context)
    assert first == second
    assert verify_ledger(ledger=first, expected_head_digest=first["head_digest"], trusted_input_digests=[input_digest], **context)


def test_ledger_supports_two_distinct_holdout_entries() -> None:
    receipt_one, proof_one, context, input_one = _materials()
    receipt_two, proof_two, context_two, input_two = _materials(nonce="holdout-5678", seed=10)
    assert context_two == context
    first = append_ledger_entry(ledger=_empty(context), expected_head_digest=GENESIS_DIGEST, receipt=receipt_one, evaluation_proof=proof_one, evaluation_succeeded=True, input_digest=input_one, trusted_input_digests=[input_one], **context)
    second = append_ledger_entry(ledger=first, expected_head_digest=first["head_digest"], receipt=receipt_two, evaluation_proof=proof_two, evaluation_succeeded=True, input_digest=input_two, trusted_input_digests=[input_one, input_two], **context)
    assert len(second["entries"]) == 2
    assert verify_ledger(ledger=second, expected_head_digest=second["head_digest"], trusted_input_digests=[input_one, input_two], **context)


def test_idempotent_retry_and_new_nonce_reuse_rules() -> None:
    receipt, proof, context, input_digest = _materials()
    ledger = _empty(context)
    first = append_ledger_entry(ledger=ledger, expected_head_digest=GENESIS_DIGEST, receipt=receipt, evaluation_proof=proof, evaluation_succeeded=True, input_digest=input_digest, trusted_input_digests=[input_digest], **context)
    assert append_ledger_entry(ledger=first, expected_head_digest=first["head_digest"], receipt=receipt, evaluation_proof=proof, evaluation_succeeded=True, input_digest=input_digest, trusted_input_digests=[input_digest], **context) == first
    changed = copy.deepcopy(receipt); changed["nonce"] = "holdout-5678"; changed["receipt_sha256"] = digest({key: changed[key] for key in changed if key != "receipt_sha256"})
    changed_proof = copy.deepcopy(proof); changed_proof["receipt_sha256"] = changed["receipt_sha256"]; changed_proof["aggregate_sha256"] = digest({key: changed_proof[key] for key in changed_proof if key != "aggregate_sha256"})
    with pytest.raises(RetroBotInputError): append_ledger_entry(ledger=first, expected_head_digest=first["head_digest"], receipt=changed, evaluation_proof=changed_proof, evaluation_succeeded=True, input_digest=input_digest, trusted_input_digests=[input_digest], **context)


@pytest.mark.parametrize("mutation", ["delete", "reorder", "rewrite", "proof"])
def test_external_head_and_chain_tampering_are_rejected(mutation: str) -> None:
    receipt, proof, context, input_digest = _materials()
    ledger = append_ledger_entry(ledger=_empty(context), expected_head_digest=GENESIS_DIGEST, receipt=receipt, evaluation_proof=proof, evaluation_succeeded=True, input_digest=input_digest, trusted_input_digests=[input_digest], **context)
    bad = copy.deepcopy(ledger)
    if mutation == "delete":
        bad["entries"] = []
        bad["head_digest"] = GENESIS_DIGEST
    elif mutation == "reorder":
        bad["entries"] = [copy.deepcopy(ledger["entries"][0]), copy.deepcopy(ledger["entries"][0])]
    elif mutation == "rewrite":
        bad["head_digest"] = "b" * 64
    else:
        bad["entries"][0]["evaluation_proof"]["status"] = "descriptive-only"
    with pytest.raises(RetroBotInputError): verify_ledger(ledger=bad, expected_head_digest=ledger["head_digest"], trusted_input_digests=[input_digest], **context)


def test_context_head_and_failed_append_do_not_mutate() -> None:
    receipt, proof, context, input_digest = _materials()
    ledger = _empty(context)
    before = copy.deepcopy(ledger)
    with pytest.raises(RetroBotInputError): append_ledger_entry(ledger=ledger, expected_head_digest="b" * 64, receipt=receipt, evaluation_proof=proof, evaluation_succeeded=True, input_digest=input_digest, trusted_input_digests=[input_digest], **context)
    assert ledger == before
    with pytest.raises(RetroBotInputError): verify_ledger(ledger=ledger, expected_head_digest=GENESIS_DIGEST, trusted_input_digests=[input_digest], source_digest="b" * 64, fold_order_digest=context["fold_order_digest"], fold_bounds_digest=context["fold_bounds_digest"])


@pytest.mark.parametrize("nonce", ["password-123", "private-123", "raw-data1", "m5-abcdef", "live-1234"])
def test_nonce_firewall_rejects_sensitive_terms(nonce: str) -> None:
    receipt, proof, context, input_digest = _materials(nonce="holdout-1234")
    receipt["nonce"] = nonce
    receipt["receipt_sha256"] = digest({key: receipt[key] for key in receipt if key != "receipt_sha256"})
    proof["receipt_sha256"] = receipt["receipt_sha256"]
    proof["aggregate_sha256"] = digest({key: proof[key] for key in proof if key != "aggregate_sha256"})
    with pytest.raises(RetroBotInputError): append_ledger_entry(ledger=_empty(context), expected_head_digest=GENESIS_DIGEST, receipt=receipt, evaluation_proof=proof, evaluation_succeeded=True, input_digest=input_digest, trusted_input_digests=[input_digest], **context)


def test_nonce_length_is_enforced_before_entry_sealing() -> None:
    receipt, proof, context, input_digest = _materials()
    receipt["nonce"] = "n" * 81
    receipt["receipt_sha256"] = digest({key: receipt[key] for key in receipt if key != "receipt_sha256"})
    proof["receipt_sha256"] = receipt["receipt_sha256"]
    proof["aggregate_sha256"] = digest({key: proof[key] for key in proof if key != "aggregate_sha256"})
    with pytest.raises(RetroBotInputError): append_ledger_entry(ledger=_empty(context), expected_head_digest=GENESIS_DIGEST, receipt=receipt, evaluation_proof=proof, evaluation_succeeded=True, input_digest=input_digest, trusted_input_digests=[input_digest], **context)


def test_schema_versions_require_real_integers() -> None:
    receipt, proof, context, input_digest = _materials()
    proof["schema_version"] = True
    proof["aggregate_sha256"] = digest({key: proof[key] for key in proof if key != "aggregate_sha256"})
    with pytest.raises(RetroBotInputError): append_ledger_entry(ledger=_empty(context), expected_head_digest=GENESIS_DIGEST, receipt=receipt, evaluation_proof=proof, evaluation_succeeded=True, input_digest=input_digest, trusted_input_digests=[input_digest], **context)
    ledger = _empty(context); ledger["schema_version"] = True
    with pytest.raises(RetroBotInputError): verify_ledger(ledger=ledger, expected_head_digest=GENESIS_DIGEST, trusted_input_digests=[input_digest], **context)


def test_sequence_type_and_evaluation_success_marker_are_strict() -> None:
    receipt, proof, context, input_digest = _materials()
    with pytest.raises(RetroBotInputError): append_ledger_entry(ledger=_empty(context), expected_head_digest=GENESIS_DIGEST, receipt=receipt, evaluation_proof=proof, evaluation_succeeded=False, input_digest=input_digest, trusted_input_digests=[input_digest], **context)
    ledger = append_ledger_entry(ledger=_empty(context), expected_head_digest=GENESIS_DIGEST, receipt=receipt, evaluation_proof=proof, evaluation_succeeded=True, input_digest=input_digest, trusted_input_digests=[input_digest], **context)
    bad = copy.deepcopy(ledger)
    bad["entries"][0]["sequence"] = 1.0
    with pytest.raises(RetroBotInputError): verify_ledger(ledger=bad, expected_head_digest=ledger["head_digest"], trusted_input_digests=[input_digest], **context)


def test_cli_is_stdin_only_and_strict() -> None:
    receipt, proof, context, input_digest = _materials()
    document = {"operation": "append", "ledger": _empty(context), "expected_head_digest": GENESIS_DIGEST, "trusted_context": context, "trusted_input_digests": [input_digest], "trusted_input_digest": input_digest, "receipt": receipt, "evaluation_proof": proof, "evaluation_succeeded": True}
    script = ROOT / "scripts" / "run_retro_live_evidence_004.py"
    run = subprocess.run([sys.executable, str(script)], input=json.dumps(document), text=True, capture_output=True, check=False)
    assert run.returncode == 0
    output = json.loads(run.stdout)
    assert output["head_digest"] != GENESIS_DIGEST
    bad = dict(document); bad["unknown"] = True
    rejected = subprocess.run([sys.executable, str(script)], input=json.dumps(bad), text=True, capture_output=True, check=False)
    assert rejected.returncode == 2
