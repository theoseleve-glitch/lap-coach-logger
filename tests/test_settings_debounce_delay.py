"""T173: Settings persistence — debounce saves at 2s max.

The :class:`SaveScheduler` already implements debounce + coalesce
semantics (existing ``test_save_scheduler.py`` covers the
mechanics in detail). T173 sets the *production wiring* delay
to 2.0 seconds: at most one disk write per 2-second window for
the routine UI burst path.

Both production entry points construct their own scheduler:
``bootstrap.py`` (Qt desktop) and ``native_bridge/runtime.py``
(native bridge). Both must be at ≥2.0s so the debounce window
is consistent across runtimes.

Source-content pin so the test runs without Qt (matches the
file-content QML pin pattern used throughout this sprint).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_SRC_ROOT = Path(__file__).resolve().parents[1] / "src" / "lap_coach_logger"

_BOOTSTRAP_FILES = [
    _SRC_ROOT / "bootstrap.py",
    _SRC_ROOT / "native_bridge" / "runtime.py",
]


@pytest.mark.parametrize(
    "path", _BOOTSTRAP_FILES, ids=[p.name for p in _BOOTSTRAP_FILES],
)
def test_save_scheduler_uses_two_second_debounce(path: Path) -> None:
    """The SaveScheduler call site must request a debounce
    delay of at least 2.0 seconds. Tolerant: pin that the
    constructor call passes ``delay_s=2.0`` (or higher integer
    seconds) so future bumps don't break the test."""
    text = path.read_text(encoding="utf-8")

    # Find the SaveScheduler( construction and slice a window
    # after it. Lambda args inside the call would defeat a
    # balanced-paren regex; slice + bounded search is simpler.
    idx = text.find("SaveScheduler(")
    assert idx >= 0, f"{path.name} must construct SaveScheduler"
    ctor_args = text[idx : idx + 400]

    # Pin delay_s to 2.0 (or larger). Float or int both fine.
    delay_match = re.search(
        r'delay_s\s*=\s*(\d+(?:\.\d+)?)',
        ctor_args,
    )
    assert delay_match is not None, (
        f"{path.name} SaveScheduler must specify delay_s "
        "explicitly (don't rely on the library default)"
    )
    delay = float(delay_match.group(1))
    assert delay >= 2.0, (
        f"{path.name} SaveScheduler debounce delay is {delay}s; "
        f"T173 requires `delay_s >= 2.0` (save every 2s max)"
    )
