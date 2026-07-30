from __future__ import annotations

import importlib.util
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_privacy_script",
    ROOT / "scripts" / "check_privacy.py",
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

MATCHER = re.compile("|".join(MODULE.DEFAULT_PATTERNS), re.I)


def test_nine_digit_account_like_token_is_blocked() -> None:
    account_like = "account=" + "123" * 3
    assert MATCHER.search(account_like)


def test_sha256_starting_with_nine_digits_is_not_an_account_match() -> None:
    assert not MATCHER.search(
        "955874623e6d84be62a8382dda4a8ffd55e49dc0f888d9dc63a98e9b5c48cf7f"
    )
