from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.m5_004_external_intake import (
    canonical_json_sha256,
    canonical_text_sha256,
    load_external_contract,
)


RUNTIME_FILES = (
    "data/m5_004_external_intake_contract.json",
    "src/xau_trigger/m5_004_external_intake.py",
    "src/xau_trigger/m5_004_frozen_evaluator.py",
    "scripts/intake_m5_004_external.py",
    "scripts/evaluate_m5_004_external.py",
    "scripts/freeze_m5_004_external_infrastructure.py",
    "src/xau_trigger/unlock_cause.py",
    "reports/phase_05/m5_004_external_infrastructure.md",
)

PROTECTED_FILES = (
    "reports/phase_02/state_reconstruction_report.json",
    "reports/phase_03/event_tick_alignment_report.json",
    "reports/phase_04/trigger_dataset_report.json",
    "reports/phase_05/m5_002_state_age_pilot.json",
    "reports/phase_05/m5_003_frozen_model_manifest.json",
    "reports/phase_05/m5_003_price_increment_report.json",
    "reports/phase_05/m5_003_external_validation_report.json",
    "reports/phase_05/m5_004_frozen_model_manifest.json",
    "reports/phase_05/m5_004_unlock_cause_report.json",
    ".local_ai/M5_004_PREREGISTRATION.md",
    ".local_ai/M5_004_PROVENANCE_AMENDMENT.md",
    "data/m5_004_preregistration.json",
    "data/m5_004_provenance_amendment.json",
)


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    contract_path = ROOT / "data" / "m5_004_external_intake_contract.json"
    contract = load_external_contract(contract_path)
    missing = [
        relative
        for relative in (*RUNTIME_FILES, *PROTECTED_FILES)
        if not (ROOT / relative).is_file()
    ]
    if missing:
        raise SystemExit(f"Cannot freeze missing infrastructure files: {missing}")
    payload = {
        "schema_version": 1,
        "milestone": "M5-004-external-infrastructure",
        "status": "external_infrastructure_ready_data_unseen",
        "base_commit": contract["frozen_package"]["base_commit"],
        "contract_id": contract["contract_id"],
        "contract_canonical_sha256": canonical_json_sha256(contract),
        "contract_raw_file_sha256": _file_sha256(contract_path),
        "runtime_canonical_text_sha256": {
            relative: canonical_text_sha256(ROOT / relative)
            for relative in RUNTIME_FILES
        },
        "protected_canonical_text_sha256": {
            relative: canonical_text_sha256(ROOT / relative)
            for relative in PROTECTED_FILES
        },
        "registered_blocks": contract["blocks"],
        "frozen_package": contract["frozen_package"],
        "bootstrap": {
            "draws": contract["evaluation"]["bootstrap_draws"],
            "seed": contract["evaluation"]["bootstrap_seed"],
            "cluster_key": contract["evaluation"]["cluster_key"],
        },
        "external_data_seen": False,
        "external_evaluation_consumed": False,
        "m6_started": False,
    }
    payload["infrastructure_manifest_sha256"] = canonical_json_sha256(payload)
    output = (
        ROOT
        / "reports"
        / "phase_05"
        / "m5_004_external_infrastructure_manifest.json"
    )
    output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(payload["infrastructure_manifest_sha256"])


if __name__ == "__main__":
    main()
