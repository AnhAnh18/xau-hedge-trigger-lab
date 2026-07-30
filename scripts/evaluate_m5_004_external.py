from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_trigger.m5_004_external_intake import (
    canonical_json_sha256,
    load_external_contract,
    load_input_aliases,
    validate_fallback_authorization,
)
from xau_trigger.m5_004_frozen_evaluator import (
    acquire_evaluation_guard,
    build_frozen_external_predictions,
    consume_evaluation,
    deterministic_evaluation_id,
    local_frame_hashes,
    summarize_frozen_external,
    verify_frozen_package,
    verify_infrastructure_manifest,
    verify_intake_and_acceptance,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate the frozen M5-004 package exactly once."
    )
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--intake", type=Path, required=True)
    parser.add_argument("--acceptance", type=Path, required=True)
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
    parser.add_argument("--local-dir", type=Path)
    parser.add_argument("--guard-dir", type=Path)
    parser.add_argument("--fallback-authorization", type=Path)
    parser.add_argument("--resume-identical", action="store_true")
    parser.add_argument("--allow-synthetic-fixture", action="store_true")
    return parser.parse_args()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _render_markdown(report: dict) -> str:
    headline = report["widths"]["1000"]
    decision = headline["headline_decision"]
    metric = headline["comparisons"][
        "C_age_price_cause_minus_A_age_cause"
    ]
    lines = [
        "# M5-004 Frozen External Evaluation",
        "",
        f"- Block: `{report['block_id']}`",
        f"- Verdict: `{decision['verdict']}`",
        f"- C-A pooled mean: `{metric['mean']:.9f}`",
        f"- One-sided 95% lower bound: `{metric['familywise_one_sided_low']:.9f}`",
        f"- Positive daily means: `{decision['positive_daily_means']}/5`",
        "",
        "The 500 ms analysis is non-gating. This result does not establish",
        "profitability, causality, an occurrence trigger, or a tradeable edge.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    args = _arguments()
    contract = load_external_contract(args.contract)
    inputs = load_input_aliases(args.inputs, contract)
    intake = json.loads(args.intake.read_text(encoding="utf-8"))
    acceptance = json.loads(args.acceptance.read_text(encoding="utf-8"))
    infrastructure = json.loads(
        args.infrastructure.read_text(encoding="utf-8")
    )
    verify_infrastructure_manifest(ROOT, infrastructure)
    manifest, _ = verify_frozen_package(ROOT, contract)
    if inputs["data_origin"] == "synthetic_fixture" and not args.allow_synthetic_fixture:
        raise SystemExit("Synthetic fixture cannot run as real external data")
    verify_intake_and_acceptance(
        contract,
        inputs,
        intake,
        acceptance,
        infrastructure["infrastructure_manifest_sha256"],
    )
    if inputs["block_id"] == "fallback":
        if not args.fallback_authorization:
            raise SystemExit("Fallback requires reviewed authorization")
        authorization = json.loads(
            args.fallback_authorization.read_text(encoding="utf-8")
        )
        primary_failure_path = Path(
            authorization["primary_failure_record_path"]
        )
        primary_failure = json.loads(
            primary_failure_path.read_text(encoding="utf-8")
        )
        validate_fallback_authorization(
            authorization,
            primary_failure,
            infrastructure["infrastructure_manifest_sha256"],
        )

    evaluation_id = deterministic_evaluation_id(
        acceptance,
        manifest["frozen_manifest_sha256"],
        infrastructure["infrastructure_manifest_sha256"],
    )
    guard_payload = {
        "schema_version": 1,
        "evaluation_id": evaluation_id,
        "block_id": inputs["block_id"],
        "acceptance_id": acceptance["record_id"],
        "input_set_sha256": acceptance["input_set_sha256"],
        "frozen_manifest_sha256": manifest["frozen_manifest_sha256"],
        "infrastructure_manifest_sha256": infrastructure[
            "infrastructure_manifest_sha256"
        ],
        "status": "started",
    }
    guard_dir = args.guard_dir or (
        ROOT / "data" / "interim" / "m5_004_external" / "evaluation_guard"
    )
    # No cause label is derived before this exclusive lock succeeds.
    acquire_evaluation_guard(
        guard_dir, guard_payload, resume=args.resume_identical
    )

    frames, accounting = build_frozen_external_predictions(
        contract, inputs, intake, manifest
    )
    report = summarize_frozen_external(
        contract,
        intake,
        acceptance,
        frames["unlock_cause_predictions"],
        accounting,
        manifest["frozen_manifest_sha256"],
        infrastructure["infrastructure_manifest_sha256"],
    )
    local_hashes = local_frame_hashes(frames)
    report["local_output_hashes"] = local_hashes
    report.pop("deterministic_report_sha256")
    report["deterministic_report_sha256"] = canonical_json_sha256(report)

    local_dir = args.local_dir or (
        ROOT / "data" / "interim" / "m5_004_external" / inputs["block_id"]
    )
    local_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        frame.to_parquet(local_dir / f"{name}.parquet", index=False)
    output = args.output_dir or ROOT / "reports" / "phase_05"
    prefix = f"m5_004_{inputs['block_id']}_external_evaluation"
    json_path = output / f"{prefix}.json"
    markdown_path = output / f"{prefix}.md"
    _write_json(json_path, report)
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    result_hashes = {
        "report_deterministic_sha256": report[
            "deterministic_report_sha256"
        ],
        "report_raw_file_sha256": __import__("hashlib").sha256(
            json_path.read_bytes()
        ).hexdigest(),
        "markdown_raw_file_sha256": __import__("hashlib").sha256(
            markdown_path.read_bytes()
        ).hexdigest(),
    }
    receipt = consume_evaluation(guard_dir, guard_payload, result_hashes)
    _write_json(output / f"{prefix}_consumed.json", receipt)
    print(
        json.dumps(
            {
                "evaluation_id": evaluation_id,
                "verdict": report["widths"]["1000"]["headline_decision"][
                    "verdict"
                ],
                "report_sha256": report["deterministic_report_sha256"],
                "status": "consumed",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
