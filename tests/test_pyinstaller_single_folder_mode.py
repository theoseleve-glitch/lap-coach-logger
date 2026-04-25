"""T177: PyInstaller spec produces a single-folder distribution.

PyInstaller has two distribution shapes:

* **single-file** (``--onefile``) — one ``.exe`` that extracts
  itself to a tempdir on every launch. Slower startup, harder
  to debug, occasional AV false-positives because of the
  self-extracting bootloader.

* **single-folder** — one folder named after the app containing
  the launcher ``.exe`` plus all dependencies as plain files.
  Faster cold-start, transparent for debugging, friendlier to
  Windows installers.

T177 pins single-folder mode for our release builds. The shape
is determined by two structural choices in the spec:

1. ``EXE(...)`` is constructed with ``exclude_binaries=True`` —
   the executable contains *only* the bootloader, not the
   bundled dependencies.
2. A ``COLLECT(...)`` call exists and bundles the binaries +
   datas into a named folder (``name="LapCoachLogger"``).

Source-content pin (consistent with T175 / T176 source pins).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_SPEC_PATH = Path(__file__).resolve().parents[1] / "lap_coach_logger.spec"


@pytest.fixture(scope="module")
def spec_text() -> str:
    return _SPEC_PATH.read_text(encoding="utf-8")


def test_exe_uses_exclude_binaries(spec_text: str) -> None:
    """``EXE(... exclude_binaries=True ...)`` is the
    single-folder mode signal — without it PyInstaller bundles
    binaries into the .exe and produces a self-extracting
    single-file distribution."""
    # Match the EXE() call body and look for exclude_binaries=True
    exe_match = re.search(
        r'EXE\s*\(([\s\S]*?)\)',
        spec_text,
    )
    assert exe_match is not None, "spec must construct EXE(...)"
    exe_body = exe_match.group(1)
    assert re.search(
        r'exclude_binaries\s*=\s*True',
        exe_body,
    ), (
        "EXE(...) must pass `exclude_binaries=True` for "
        "single-folder distribution mode"
    )


def test_spec_has_collect_call(spec_text: str) -> None:
    """``COLLECT(...)`` is the call that produces the
    distribution folder. Single-file mode omits it; the folder
    shape requires it."""
    assert re.search(
        r'\bCOLLECT\s*\(',
        spec_text,
    ), (
        "spec must call COLLECT(...) to produce a "
        "single-folder distribution"
    )


def test_collect_names_distribution_folder(spec_text: str) -> None:
    """The COLLECT call names the output folder. Without an
    explicit ``name=`` PyInstaller defaults to a less-friendly
    auto-generated name."""
    collect_match = re.search(
        r'COLLECT\s*\(([\s\S]*?)\)',
        spec_text,
    )
    assert collect_match is not None, "COLLECT(...) call must exist"
    collect_body = collect_match.group(1)
    name_match = re.search(
        r'name\s*=\s*[\'"]([^\'"]+)[\'"]',
        collect_body,
    )
    assert name_match is not None, (
        "COLLECT(...) must specify `name=\"...\"` for the "
        "distribution folder"
    )
    folder_name = name_match.group(1)
    assert folder_name == "LapCoachLogger", (
        f"COLLECT folder name should be 'LapCoachLogger', "
        f"got {folder_name!r}"
    )
