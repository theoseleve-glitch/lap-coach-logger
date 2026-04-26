"""T193: License is packaged and shown to the user during install.

Inno Setup's ``LicenseFile=`` directive in ``[Setup]`` produces
the standard "I accept the agreement" wizard page. Without the
directive the installer skips the license page entirely —
T193's "visible in installer" requires the directive to be
present, the referenced file to exist relative to the .iss,
and the file content to be a real license.

Source-content cross-file pin (consistent with T175-T184).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


_ISS_PATH = (
    Path(__file__).resolve().parents[1]
    / "installer" / "LapCoachLogger.iss"
)


@pytest.fixture(scope="module")
def iss_text() -> str:
    return _ISS_PATH.read_text(encoding="utf-8")


def _setup_section(iss_text: str) -> str:
    match = re.search(
        r'\[Setup\]([\s\S]*?)(?=\n\[\w+\]|\Z)',
        iss_text,
    )
    assert match is not None, ".iss must have a [Setup] section"
    return match.group(1)


def _license_file_directive(setup: str) -> str | None:
    """Return the ``LicenseFile=`` value (path) or None."""
    match = re.search(
        r'^\s*LicenseFile\s*=\s*(\S.*?)\s*$',
        setup,
        re.MULTILINE,
    )
    return match.group(1) if match else None


# -- directive present -------------------------------------------------


def test_iss_declares_license_file(iss_text: str) -> None:
    """The .iss must have a ``LicenseFile=`` directive in
    ``[Setup]`` — without it the installer skips the license
    page and the user never sees the agreement."""
    setup = _setup_section(iss_text)
    value = _license_file_directive(setup)
    assert value, (
        "[Setup] must declare `LicenseFile=<path>` so the "
        "installer shows the license agreement page during "
        "install"
    )


# -- referenced file exists -------------------------------------------


def test_license_file_path_resolves(iss_text: str) -> None:
    """The path in ``LicenseFile=`` must resolve to an actual
    file (relative to the .iss directory). A broken reference
    fails iscc compilation — pin it at test time so we catch
    it before the build pipeline does."""
    setup = _setup_section(iss_text)
    value = _license_file_directive(setup)
    assert value, "precondition: LicenseFile= must be present"

    # Strip surrounding quotes if any, and Inno's ``\\``
    # backslash-escapes that survive in raw .iss text.
    cleaned = value.strip().strip('"').replace("\\\\", "\\")
    license_path = (_ISS_PATH.parent / cleaned).resolve()

    assert license_path.is_file(), (
        f"LicenseFile= references a non-existent path: "
        f"{cleaned!r} (resolved to {license_path}). The "
        f"file must exist relative to {_ISS_PATH.parent}."
    )


def test_license_file_is_non_empty(iss_text: str) -> None:
    """Empty license file → the wizard shows a blank
    agreement page. That's worse than no license at all."""
    setup = _setup_section(iss_text)
    value = _license_file_directive(setup)
    assert value, "precondition"
    cleaned = value.strip().strip('"').replace("\\\\", "\\")
    license_path = (_ISS_PATH.parent / cleaned).resolve()
    assert license_path.is_file(), "precondition"

    contents = license_path.read_bytes()
    assert len(contents) > 100, (
        f"license file appears empty / nearly-empty "
        f"({len(contents)} bytes); check {license_path}"
    )


# -- license content sanity ------------------------------------------


def test_license_file_looks_like_a_license(iss_text: str) -> None:
    """Sanity: the referenced file's content contains the word
    'License' (case-insensitive) — catches the "wrong file
    pointed to" failure where someone aimed `LicenseFile=` at
    `README.md` by mistake."""
    setup = _setup_section(iss_text)
    value = _license_file_directive(setup)
    cleaned = value.strip().strip('"').replace("\\\\", "\\")
    license_path = (_ISS_PATH.parent / cleaned).resolve()

    text = license_path.read_text(encoding="utf-8", errors="replace")
    assert "License" in text or "license" in text, (
        f"file pointed to by LicenseFile= ({license_path}) "
        f"doesn't contain the word 'License' — likely points "
        f"at the wrong file"
    )
