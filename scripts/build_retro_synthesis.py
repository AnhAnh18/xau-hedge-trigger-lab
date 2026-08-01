"""Build the aggregate-only RETRO cross-case synthesis."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGGREGATE_ROOT = ROOT / "reports" / "private"
OUTPUT = AGGREGATE_ROOT / "retro-synthesis" / "retro-synthesis-aggregate.json"
CASE_IDS = ["RETRO-001", "RETRO-002", "RETRO-003", "RETRO-004", "RETRO-005", "RETRO-006"]
REQUIRED_FIELDS = {
    "RETRO-001": {"case", "manual_intervention", "source_validation", "m5_firewall"},
    "RETRO-002": {"source_agreement", "source_metrics", "source_validation", "m5_firewall"},
    "RETRO-003": {"selection_rule", "selected_cases", "source_validation", "m5_firewall", "raw_rows_printed"},
    "RETRO-004": {"target", "clock", "order_comment_indicator", "source_validation", "m5_firewall", "raw_rows_printed"},
    "RETRO-005": {"target", "clock", "order_comment_indicator", "source_validation", "m5_firewall", "raw_rows_printed"},
    "RETRO-006": {"target", "clock", "order_comment_indicator", "source_validation", "m5_firewall", "raw_rows_printed"},
}


def require_ignored(path: Path) -> None:
    result = subprocess.run(
        ["git", "check-ignore", "--no-index", "-q", str(path.relative_to(ROOT))],
        cwd=ROOT,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("RETRO synthesis output is not ignored")


def load_aggregate(case_id: str) -> tuple[dict, str]:
    path = AGGREGATE_ROOT / case_id.lower() / f"{case_id.lower()}-aggregate.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    recorded = data.pop("aggregate_sha256")
    canonical = json.dumps(data, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    actual = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    if actual != recorded:
        raise ValueError(f"Aggregate digest mismatch: {case_id}")
    if data.get("schema_version") != 1 or data.get("case_id") != case_id:
        raise ValueError(f"Aggregate schema or case ID mismatch: {case_id}")
    if not REQUIRED_FIELDS[case_id].issubset(data):
        raise ValueError(f"Aggregate required fields missing: {case_id}")
    if not isinstance(data["m5_firewall"], str) or not data["m5_firewall"].startswith("not_an_M5_input;"):
        raise ValueError(f"Aggregate M5 firewall mismatch: {case_id}")
    if case_id in {"RETRO-003", "RETRO-004", "RETRO-005", "RETRO-006"} and data["raw_rows_printed"] is not False:
        raise ValueError(f"Aggregate raw-output safeguard mismatch: {case_id}")
    data["aggregate_sha256"] = recorded
    return data, recorded


def main() -> int:
    require_ignored(OUTPUT)
    aggregates = {}
    digests = {}
    for case_id in CASE_IDS:
        aggregates[case_id], digests[case_id] = load_aggregate(case_id)
    selected = [aggregates[cid] for cid in ("RETRO-004", "RETRO-005", "RETRO-006")]
    repeated_no_continuation = all(item["target"]["continuation_opposite_rehedge_inside_interval"] == 0 for item in selected)
    synthesis = {
        "schema_version": 1,
        "case_id": "RETRO-SYNTH",
        "input_case_ids": CASE_IDS,
        "input_aggregate_sha256": digests,
        "selection_inventory_digest": aggregates["RETRO-003"]["aggregate_sha256"],
        "observed": {
            "preselected_new_cases": 3,
            "new_case_transition_reconstruction_count": sum(int(item["target"]["transition_reconstructed"]) for item in selected),
            "new_case_no_continuation_count": sum(int(item["target"]["continuation_opposite_rehedge_inside_interval"] == 0) for item in selected),
            "all_new_cases_clock_ambiguous": all(item["clock"]["status"] == "ambiguous_multiple_supported_mappings" for item in selected),
            "all_new_case_window_comments_blank": all(item["order_comment_indicator"]["window_all_blank"] for item in selected),
            "retrospective_selection_rule": aggregates["RETRO-003"]["selection_rule"],
        },
        "compatible": {
            "repeated_wait_then_rehedge_pattern": repeated_no_continuation,
            "state_dependent_rotation_compatibility": True,
            "clock_basis_as_source_explanation": True,
        },
        "unresolved": [
            "historical broker-authoritative timestamp basis",
            "exact price excursion for the three new cases because both registered clock candidates are supported",
            "bot trigger condition",
            "manual intervention",
            "profitability, ownership, and tradeable edge",
        ],
        "m5_firewall": "not_an_M5_input; no fitting, evaluation, threshold change, model selection, or gate decision",
        "raw_rows_printed": False,
    }
    canonical = json.dumps(synthesis, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    synthesis["aggregate_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(synthesis, ensure_ascii=True, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    result = f"""# RETRO-SYNTH Result: 2025-11 to 2026-07

Status: descriptive synthesis; independent review pending.

Synthesis aggregate digest: `{synthesis['aggregate_sha256']}`.
The six input aggregates remain quarantine-derived RETRO evidence and are not
M5 inputs.

## Observed

- Three preselected historical cases were reconstructed with the registered
  one-leg to opposite-side re-hedge transition.
- All three had no continuation opposite-side re-hedge inside the selected
  interval.
- All three support both UTC+2 and UTC+3 at the report boundaries, so the
  historical clock basis remains ambiguous.
- The selected-window order comments are blank in all three cases; no journal
  was inspected.

## Interpretation

- **Observed:** the wait-then-re-hedge sequence repeats in the three cases
  selected without price-based cherry-picking.
- **Compatible:** the repeated sequence is compatible with a state-dependent
  rotation and with a clock/data explanation for apparent price discrepancies.
- **Unresolved:** the trigger, manual intervention, broker clock, exact price
  excursions, profitability, ownership, and tradeable edge remain unknown.

RETRO-SYNTH is descriptive only. It does not fit, evaluate, select, or gate
any M5 artifact.
"""
    (ROOT / "docs" / "observational_cases" / "RETRO-SYNTH-2025-11_to_2026-07-result.md").write_text(result, encoding="utf-8")
    print(json.dumps({"case_id": "RETRO-SYNTH", "aggregate_sha256": synthesis["aggregate_sha256"], "input_count": len(CASE_IDS)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
