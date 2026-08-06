"""stdin-only RB-020 reconstruction stages."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from xau_trigger.retro_bot import RetroBotInputError
from xau_trigger.retro_bot_020 import parse_autonomous, parse_oracle, replay_autonomous, replay_decisions, replay_rh003_candidate, oracle_diagnostic, validate_source, verify_aggregate, walk_forward, paper_account
from xau_trigger.retro_bot_012 import load_json_no_duplicates

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("validate-source", "replay-autonomous", "replay-rh003", "replay-oracle-diagnostic", "walk-forward", "paper-account", "verify-aggregate"))
    args = parser.parse_args(argv)
    try:
        doc = load_json_no_duplicates(sys.stdin)
        if args.stage == "validate-source": out = validate_source(doc)
        elif args.stage == "replay-autonomous": out = replay_autonomous(parse_autonomous(doc))
        elif args.stage == "replay-rh003": out = replay_rh003_candidate(parse_autonomous(doc))
        elif args.stage == "replay-oracle-diagnostic":
            oracle = parse_oracle({"observed_events": doc["observed_events"]})
            decisions = replay_decisions(parse_autonomous(doc["autonomous"])) if "autonomous" in doc else ()
            out = oracle_diagnostic(oracle, decisions)
        elif args.stage in {"walk-forward", "paper-account"}:
            # These stages intentionally expose only the causal aggregate; no
            # observed labels or accounting values can affect policy output.
            if args.stage == "walk-forward":
                folds = doc.get("fold_inputs")
                aliases = doc.get("fold_aliases")
                if not isinstance(folds, dict) or not isinstance(aliases, dict):
                    raise RetroBotInputError("RB-020 CLI fold inputs are required")
                if not isinstance(doc.get("holdout_receipt"), dict):
                    raise RetroBotInputError("RB-020 CLI holdout receipt is required")
                parsed_folds = {name: parse_autonomous(folds[name]) for name in ("development", "validation", "holdout")}
                consumed = doc.get("consumed_nonces", [])
                if not isinstance(consumed, list) or any(not isinstance(x, str) for x in consumed):
                    raise RetroBotInputError("RB-020 CLI nonce ledger is invalid")
                out = walk_forward(parsed_folds["development"], fold_inputs=parsed_folds, fold_aliases=aliases, holdout_receipt=doc["holdout_receipt"], used_nonces=set(consumed))
            else:
                lifecycle = doc.get("lifecycle")
                autonomous_doc = {key: value for key, value in doc.items() if key != "lifecycle"}
                out = paper_account(parse_autonomous(autonomous_doc), lifecycle=lifecycle)
        else: verify_aggregate(doc); out = {"stage": "verify-aggregate", "verified": True}
        sys.stdout.write(json.dumps(out, ensure_ascii=True, separators=(",", ":")) + "\n")
        return 0
    except (RetroBotInputError, TypeError, ValueError, KeyError, json.JSONDecodeError):
        sys.stderr.write("RB-020 input rejected\n")
        return 2
if __name__ == "__main__": raise SystemExit(main())
