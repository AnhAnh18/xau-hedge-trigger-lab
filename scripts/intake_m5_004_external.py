from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.m5_004_external_intake import (
    build_blind_intake,
    build_structural_record,
    load_external_contract,
    load_input_aliases,
    verify_blind_infrastructure,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run information-firewalled M5-004 structural intake."
    )
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument(
        "--contract",
        type=Path,
        default=ROOT / "data" / "m5_004_external_intake_contract.json",
    )
    parser.add_argument(
        "--infrastructure",
        type=Path,
        default=(
            ROOT
            / "reports"
            / "phase_05"
            / "m5_004_external_infrastructure_manifest.json"
        ),
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--allow-synthetic-fixture",
        action="store_true",
        help="Required for tests; synthetic artifacts cannot be used as real intake.",
    )
    return parser.parse_args()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _render_markdown(intake: dict) -> str:
    lines = [
        "# M5-004 Blind External Intake",
        "",
        f"- Block: `{intake['block_id']}`",
        f"- Structural status: `{intake['structural_status']}`",
        f"- Information firewall: `{intake['information_firewall']['status']}`",
        f"- Failure codes: `{', '.join(intake['failure_codes']) or 'none'}`",
        f"- Input-set hash: `{intake['input_set_sha256']}`",
        f"- Intake hash: `{intake['deterministic_intake_sha256']}`",
        "",
        "No unlock direction, feature, prediction, coefficient, likelihood,",
        "financial amount, or model-performance field is published here.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    args = _arguments()
    contract = load_external_contract(args.contract)
    inputs = load_input_aliases(args.inputs, contract)
    if (
        inputs["data_origin"] == "synthetic_fixture"
        and not args.allow_synthetic_fixture
    ):
        raise SystemExit("Synthetic fixture requires explicit fixture mode")
    infrastructure = json.loads(
        args.infrastructure.read_text(encoding="utf-8")
    )
    verify_blind_infrastructure(ROOT, infrastructure)
    infrastructure_hash = infrastructure["infrastructure_manifest_sha256"]
    if (
        infrastructure["external_data_seen"] is not False
        or infrastructure["external_evaluation_consumed"] is not False
    ):
        raise SystemExit("Pre-data infrastructure manifest state changed")

    intake, _ = build_blind_intake(contract, inputs)
    structural = build_structural_record(intake, infrastructure_hash)
    output = args.output_dir or ROOT / "reports" / "phase_05"
    prefix = f"m5_004_{inputs['block_id']}"
    intake_path = output / f"{prefix}_blind_intake.json"
    structural_name = (
        f"{prefix}_structural_acceptance.json"
        if structural["accepted"]
        else f"{prefix}_structural_failure.json"
    )
    _write_json(intake_path, intake)
    _write_json(output / structural_name, structural)
    (output / f"{prefix}_blind_intake.md").write_text(
        _render_markdown(intake), encoding="utf-8"
    )
    # The console is intentionally limited to the same structural firewall.
    print(
        json.dumps(
            {
                "block_id": intake["block_id"],
                "structural_status": intake["structural_status"],
                "failure_codes": intake["failure_codes"],
                "deterministic_intake_sha256": intake[
                    "deterministic_intake_sha256"
                ],
                "record_id": structural["record_id"],
            },
            sort_keys=True,
        )
    )
    raise SystemExit(0 if structural["accepted"] else 2)


if __name__ == "__main__":
    main()
