"""Write privacy-safe result notes for RETRO-004..006 from aggregate outputs."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    for number in range(4, 7):
        case_id = f"RETRO-{number:03d}"
        aggregate = json.loads((ROOT / "reports" / "private" / case_id.lower() / f"{case_id.lower()}-aggregate.json").read_text(encoding="utf-8"))
        recorded_digest = aggregate.pop("aggregate_sha256", None)
        canonical = json.dumps(aggregate, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        if recorded_digest is None or hashlib.sha256(canonical.encode("utf-8")).hexdigest() != recorded_digest:
            raise ValueError(f"{case_id} aggregate digest mismatch")
        if aggregate.get("schema_version") != 1 or aggregate.get("m5_firewall") != "not_an_M5_input; no fitting, evaluation, threshold change, or gate decision":
            raise ValueError(f"{case_id} aggregate schema/firewall mismatch")
        if not aggregate["target"]["transition_reconstructed"] or aggregate["target"]["continuation_opposite_rehedge_inside_interval"] != 0:
            raise ValueError(f"{case_id} observed transition fields do not match result contract")
        if not aggregate["order_comment_indicator"]["window_all_blank"]:
            raise ValueError(f"{case_id} window comment indicator does not match result contract")
        if aggregate["clock"]["status"] != "ambiguous_multiple_supported_mappings":
            raise ValueError(f"{case_id} clock status does not match result contract")
        aggregate["aggregate_sha256"] = recorded_digest
        target = aggregate["target"]
        clock = aggregate["clock"]
        comments = aggregate["order_comment_indicator"]
        text = f"""# {case_id} Result: Historical One-Leg Case

Status: descriptive result; independent review pending.

## Provenance

Report manifest digest: `{aggregate['report_manifest_sha256']}`.
Tick manifest digest: `{aggregate['tick_manifest_sha256']}`.
Aggregate result digest: `{aggregate['aggregate_sha256']}`.
The source objects remain quarantine-only and are not M5 inputs.

## Observed

- The preselected `{target['server_date']}` `{target['side']}` one-leg interval
  is uniquely reconstructed for `{target['duration_seconds']}` seconds, with
  the registered opposite-side re-hedge transition at its boundary.
- No continuation opposite-side re-hedge occurs inside the selected interval.
- The selected window contains `{comments['window_order_count']}` order rows and
  their comments are blank; no journal was authorized or inspected.
- Both registered clock candidates support the report-boundary alignment, so
  the clock status is `{clock['status']}` rather than a unique mapping.

## Interpretation

- **Observed:** this preselected case shows a finite one-leg interval followed
  by the registered opposite-side re-hedge, with no continuation opposite-side
  re-hedge before the interval ends.
- **Compatible:** this sequence is compatible with a state-dependent rotation
  that waits before re-hedging; it does not establish why it waits.
- **Unresolved:** because UTC+2 and UTC+3 both support the tick boundaries, the
  adverse-excursion band is not accepted as a single result. The trigger,
  manual intervention, profitability, ownership, and historical broker clock
  remain unresolved.

No journal, cache, screenshot, M1 object, XLSX/PNG companion, or additional
source was inspected. This is descriptive RETRO evidence only and does not
modify, fit, evaluate, or gate any M5 artifact.
"""
        (ROOT / "docs" / "observational_cases" / f"{case_id}-result.md").write_text(text, encoding="utf-8")
    print(json.dumps({"results_written": [f"RETRO-{number:03d}" for number in range(4, 7)]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
