"""T194: Privacy notice is packaged and shown to the user
during install.

Inno Setup's ``InfoBeforeFile=`` directive in ``[Setup]`` adds
a wizard page that displays an informational document
*before* installation begins. Right semantic for a privacy
notice — the user reads what data the app will (and will not)
collect *before* committing to install.

T194 mirrors T193's ``LicenseFile=`` shape:
1. Directive present.
2. Referenced file resolves to an existing path.
3. File is non-empty.
4. Content sanity-checks as a privacy notice.

Source-content cross-file pin (consistent with T175-T193).
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


def _info_before_directive(setup: str) -> str | None:
    """Return the ``InfoBeforeFile=`` value (path) or None."""
    match = re.search(
        r'^\s*InfoBeforeFile\s*=\s*(\S.*?)\s*$',
        setup,
        re.MULTILINE,
    )
    return match.group(1) if match else None


def _resolve(path_value: str) -> Path:
    """Strip quotes, decode Inno's `\\\\` to `\\`, then resolve
    relative to the .iss directory."""
    cleaned = path_value.strip().strip('"').replace("\\\\", "\\")
    return (_ISS_PATH.parent / cleaned).resolve()


# -- directive present -------------------------------------------------


def test_iss_declares_info_before_file(iss_text: str) -> None:
    """The .iss must have ``InfoBeforeFile=`` so the installer
    shows the privacy notice before the install starts.
    Without it the user never sees the privacy commitment
    before clicking Install — a trust failure for a
    privacy-forward app."""
    setup = _setup_section(iss_text)
    value = _info_before_directive(setup)
    assert value, (
        "[Setup] must declare `InfoBeforeFile=<path>` to show "
        "the privacy notice on a wizard page before install"
    )


# -- referenced file exists -------------------------------------------


def test_info_before_file_path_resolves(iss_text: str) -> None:
    """The InfoBeforeFile path must resolve to an actual file
    relative to the .iss directory. A broken reference fails
    iscc compilation — pin it at test time."""
    setup = _setup_section(iss_text)
    value = _info_before_directive(setup)
    assert value, "precondition: InfoBeforeFile= must be present"

    resolved = _resolve(value)
    assert resolved.is_file(), (
        f"InfoBeforeFile= references a non-existent path: "
        f"{value!r} (resolved to {resolved}). The file must "
        f"exist relative to {_ISS_PATH.parent}."
    )


def test_info_before_file_is_non_empty(iss_text: str) -> None:
    """Empty privacy file → wizard shows a blank "important
    information" page. Worse than no notice at all because
    the empty page implies nothing-to-disclose."""
    setup = _setup_section(iss_text)
    value = _info_before_directive(setup)
    resolved = _resolve(value)
    assert resolved.is_file(), "precondition"

    contents = resolved.read_bytes()
    assert len(contents) > 100, (
        f"privacy file appears empty / nearly-empty "
        f"({len(contents)} bytes); check {resolved}"
    )


# -- content sanity ---------------------------------------------------


def test_info_before_file_looks_like_privacy_notice(
    iss_text: str,
) -> None:
    """Sanity: the referenced file's content contains the
    word 'Privacy' or 'privacy' — catches the "wrong file
    pointed to" failure where someone aimed `InfoBeforeFile=`
    at README or CHANGELOG by mistake."""
    setup = _setup_section(iss_text)
    value = _info_before_directive(setup)
    resolved = _resolve(value)

    text = resolved.read_text(encoding="utf-8", errors="replace")
    assert "Privacy" in text or "privacy" in text, (
        f"file pointed to by InfoBeforeFile= ({resolved}) "
        f"doesn't contain the word 'Privacy' — likely points "
        f"at the wrong file"
    )


def test_info_before_file_distinct_from_license_file(
    iss_text: str,
) -> None:
    """Privacy and License are different documents — they
    must not point at the same file. T193's LicenseFile= and
    T194's InfoBeforeFile= must reference distinct paths so
    users see both notices."""
    setup = _setup_section(iss_text)
    info_before = _info_before_directive(setup)
    license_match = re.search(
        r'^\s*LicenseFile\s*=\s*(\S.*?)\s*$',
        setup,
        re.MULTILINE,
    )
    license_value = license_match.group(1) if license_match else None
    assert info_before, "precondition"
    assert license_value, (
        "T193's LicenseFile= must already be declared "
        "(precondition for the privacy/license distinction)"
    )

    privacy_resolved = _resolve(info_before)
    license_resolved = _resolve(license_value)
    assert privacy_resolved != license_resolved, (
        f"InfoBeforeFile= ({privacy_resolved}) and LicenseFile= "
        f"({license_resolved}) must reference different files; "
        f"they cover different topics (privacy vs license)"
    )
