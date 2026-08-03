"""Verify the locked RETRO-BOT-004 source boundary without printing raw data."""
from __future__ import annotations

import argparse
from pathlib import Path

from xau_trigger.retro_bot_004 import load_population_config, verify_rb008_sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify RETRO-BOT-004 manifests")
    parser.add_argument("--reports-run", type=Path, required=True)
    parser.add_argument("--ticks-run", type=Path, required=True)
    parser.add_argument("--quarantine-root", type=Path, required=True)
    args = parser.parse_args()
    config = load_population_config()
    verify_rb008_sources(args.reports_run, args.ticks_run, args.quarantine_root, config)
    print("RETRO-BOT-004 source verification passed; raw rows were not retained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
