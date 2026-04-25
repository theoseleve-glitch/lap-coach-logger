"""T178: Inno Setup script consistent with PyInstaller spec.

The Inno Setup script (``installer/LapCoachLogger.iss``) wraps
the PyInstaller distribution folder produced by
``lap_coach_logger.spec`` (via ``COLLECT(name=...)``). If a
refactor renames the executable or the dist folder in the spec
but the .iss script keeps the old name, the installer points
at a missing path — silent ship-failure.

T178 pins these consistency properties:

1. The .iss ``AppExeName`` matches the PyInstaller EXE
   ``name=`` plus ``.exe``.
2. The .iss ``DistDir`` ends with the same folder name as
   PyInstaller's COLLECT ``name=``.
3. The .iss has the required sections: ``[Setup]``, ``[Files]``,
   ``[Icons]``, ``[Run]``.

Source-content cross-file pin (consistent with T175-T177).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_SPEC_PATH = _REPO / "lap_coach_logger.spec"
_ISS_PATH = _REPO / "installer" / "LapCoachLogger.iss"


@pytest.fixture(scope="module")
def spec_text() -> str:
    return _SPEC_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def iss_text() -> str:
    return _ISS_PATH.read_text(encoding="utf-8")


def _spec_exe_name(spec_text: str) -> str:
    """Extract `name=` from the EXE() call."""
    exe_match = re.search(r'EXE\s*\(([\s\S]*?)\)', spec_text)
    assert exe_match is not None, "spec must construct EXE(...)"
    name_match = re.search(
        r'name\s*=\s*[\'"]([^\'"]+)[\'"]',
        exe_match.group(1),
    )
    assert name_match is not None, "EXE must specify name="
    return name_match.group(1)


def _spec_collect_name(spec_text: str) -> str:
    """Extract `name=` from the COLLECT() call."""
    collect_match = re.search(r'COLLECT\s*\(([\s\S]*?)\)', spec_text)
    assert collect_match is not None, "spec must call COLLECT(...)"
    name_match = re.search(
        r'name\s*=\s*[\'"]([^\'"]+)[\'"]',
        collect_match.group(1),
    )
    assert name_match is not None, "COLLECT must specify name="
    return name_match.group(1)


def _iss_define(iss_text: str, name: str) -> str:
    """Extract `#define <name> "..."` value, or empty string."""
    match = re.search(
        rf'#define\s+{re.escape(name)}\s+"([^"]+)"',
        iss_text,
    )
    return match.group(1) if match else ""


def test_iss_app_exe_name_matches_spec_exe(
    spec_text: str, iss_text: str,
) -> None:
    """``AppExeName`` in the .iss must match PyInstaller's EXE
    ``name=`` plus a ``.exe`` extension."""
    spec_exe = _spec_exe_name(spec_text)
    iss_exe = _iss_define(iss_text, "AppExeName")
    assert iss_exe, ".iss must #define AppExeName"
    expected = spec_exe + ".exe"
    assert iss_exe == expected, (
        f"AppExeName in .iss ({iss_exe!r}) does not match "
        f"PyInstaller EXE name ({expected!r}). One of the "
        f"files was updated without updating the other."
    )


def test_iss_dist_dir_matches_spec_collect_folder(
    spec_text: str, iss_text: str,
) -> None:
    """``DistDir`` in the .iss must reference the PyInstaller
    COLLECT folder. Tolerant: pin that the .iss DistDir ENDS
    with the COLLECT name (path prefix can vary across
    workspaces)."""
    collect_name = _spec_collect_name(spec_text)
    iss_dist = _iss_define(iss_text, "DistDir")
    assert iss_dist, ".iss must #define DistDir"
    # Normalize Windows-style backslashes — Inno uses `\\` in
    # quoted strings to escape the backslash.
    iss_dist_normalized = iss_dist.replace("\\\\", "/").replace("\\", "/")
    assert iss_dist_normalized.endswith("/" + collect_name) or (
        iss_dist_normalized == collect_name
    ), (
        f"DistDir in .iss ({iss_dist!r}) does not reference "
        f"PyInstaller COLLECT folder ({collect_name!r})."
    )


def test_iss_has_required_sections(iss_text: str) -> None:
    """An Inno script needs at minimum ``[Setup]``,
    ``[Files]``, ``[Icons]``, ``[Run]`` for a windowed app."""
    for section in ("[Setup]", "[Files]", "[Icons]", "[Run]"):
        assert section in iss_text, (
            f".iss missing required section: {section}"
        )


def test_iss_files_section_uses_dist_dir(iss_text: str) -> None:
    """The ``[Files]`` section must source from ``{#DistDir}`` —
    otherwise the installer doesn't know where to read the
    PyInstaller output from."""
    files_match = re.search(
        r'\[Files\][\s\S]*?(?=\[\w+\]|$)',
        iss_text,
    )
    assert files_match is not None, ".iss must have [Files] section body"
    assert "{#DistDir}" in files_match.group(0), (
        "[Files] section must reference {#DistDir} so the "
        "installer reads from the PyInstaller output folder"
    )
