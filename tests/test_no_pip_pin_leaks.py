"""Regression test: no pip-pin leak files at repo root (sprint T020).

Sprint T020 removed a stray ``=1.26`` file that had been created at
repo root by a shell-quoting slip on an earlier pip invocation
(``pip install numpy>=1.26`` without quotes redirects ``=1.26``).
This guard keeps such artefacts from creeping back in.
"""
from __future__ import annotations

import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LEGACY_FILE = REPO_ROOT / "=1.26"
LEAK_PATTERN = re.compile(r"^[=<>!]=?\d")


def test_legacy_pin_leak_file_is_gone() -> None:
    assert not LEGACY_FILE.exists(), (
        "=1.26 still on disk — T020 requires deletion"
    )


def test_no_other_pin_leak_files_at_repo_root() -> None:
    offenders = [
        p.name
        for p in REPO_ROOT.iterdir()
        if p.is_file() and LEAK_PATTERN.match(p.name)
    ]
    assert offenders == [], (
        f"pip-pin leak files at repo root: {offenders}. "
        "Looks like a shell-quoting slip on a pip install."
    )
