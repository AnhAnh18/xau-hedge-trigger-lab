"""Fail on privacy-risk patterns in tracked project files.

Optionally add exact local terms, one per line, to
.local_secrets/blocked_terms.txt. That file is ignored by Git.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATTERNS = [
    r"[A-Za-z]:\\Users\\",
    r"/home/[^/]+/",
    r"(?<![A-Za-z0-9_])\d{9}(?![A-Za-z0-9_])",
]
EXCLUDED = {"scripts/check_privacy.py"}

def tracked_files() -> list[Path]:
    output = subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}", "ls-files"], cwd=ROOT, text=True)
    return [ROOT / item for item in output.splitlines() if item not in EXCLUDED]

def main() -> None:
    local_terms = ROOT / ".local_secrets" / "blocked_terms.txt"
    patterns = DEFAULT_PATTERNS + ([re.escape(x.strip()) for x in local_terms.read_text(encoding="utf-8").splitlines() if x.strip()] if local_terms.exists() else [])
    matcher = re.compile("|".join(patterns), re.I); findings = []
    for path in tracked_files():
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".parquet", ".zip"}: continue
        try: text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError: continue
        for number, line in enumerate(text.splitlines(), 1):
            if matcher.search(line): findings.append(f"{path.relative_to(ROOT)}:{number}")
    if findings:
        print("Privacy check failed:\n" + "\n".join(findings)); raise SystemExit(1)
    print("Privacy check passed.")

if __name__ == "__main__": main()
