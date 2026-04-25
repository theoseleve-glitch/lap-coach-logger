"""T182: Version string sourced from a single canonical place.

Three places in the repo carry a version string and they must
agree, otherwise installer artifacts get labeled with one
version while runtime code reports another:

1. ``pyproject.toml`` ``[project] version`` — the canonical
   source per Python packaging standards (PEP 621).
2. ``src/lap_coach_logger/app_identity.py`` ``VERSION`` —
   the runtime constant; ``__version__`` is sourced from this.
3. ``installer/LapCoachLogger.iss`` ``#define AppVersion``
   fallback — used by ``iscc`` if the build pipeline does not
   pass ``/DAppVersion=...``. ``build_installer.bat`` always
   passes the override, but a developer running ``iscc``
   directly would otherwise produce a stale-versioned
   installer.

The compile-time bridge is ``build_installer.bat``:

   for /f %%I in ('python -c "from lap_coach_logger.app_identity import VERSION; print(VERSION)"') do set APP_VERSION=%%I
   ISCC /DAppVersion=%APP_VERSION% ...

Pin the three constraints so a version bump in one place
forces an update in the others (or fails CI).

Source-content pin (consistent with T175-T181).
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_PYPROJECT_PATH = _REPO / "pyproject.toml"
_APP_IDENTITY_PATH = _REPO / "src" / "lap_coach_logger" / "app_identity.py"
_ISS_PATH = _REPO / "installer" / "LapCoachLogger.iss"
_BUILD_BAT_PATH = _REPO / "build_installer.bat"


@pytest.fixture(scope="module")
def pyproject_version() -> str:
    with _PYPROJECT_PATH.open("rb") as fh:
        data = tomllib.load(fh)
    return data["project"]["version"]


@pytest.fixture(scope="module")
def app_identity_version() -> str:
    text = _APP_IDENTITY_PATH.read_text(encoding="utf-8")
    match = re.search(
        r'^\s*VERSION\s*=\s*[\'"]([^\'"]+)[\'"]',
        text,
        re.MULTILINE,
    )
    assert match is not None, (
        "app_identity.py must define VERSION = \"...\""
    )
    return match.group(1)


@pytest.fixture(scope="module")
def iss_appversion_fallback() -> str:
    text = _ISS_PATH.read_text(encoding="utf-8")
    # Match the fallback `#define AppVersion "X.Y.Z"` inside
    # an `#ifndef AppVersion` block.
    match = re.search(
        r'#ifndef\s+AppVersion[\s\S]*?'
        r'#define\s+AppVersion\s+"([^"]+)"',
        text,
    )
    assert match is not None, (
        ".iss must have an `#ifndef AppVersion / #define AppVersion \"...\"` "
        "fallback so a direct `iscc` invocation still produces "
        "a versioned installer"
    )
    return match.group(1)


# -- Cross-file version consistency ------------------------------------


def test_app_identity_version_matches_pyproject(
    pyproject_version: str, app_identity_version: str,
) -> None:
    """``app_identity.VERSION`` (runtime constant) must match
    ``pyproject.toml`` ``[project] version`` (canonical source).
    Drift here means the in-app "About" dialog reports one
    version while pip metadata reports another."""
    assert app_identity_version == pyproject_version, (
        f"Version drift: pyproject.toml says "
        f"{pyproject_version!r} but app_identity.VERSION is "
        f"{app_identity_version!r}. Update one to match the "
        f"other (pyproject.toml is canonical)."
    )


def test_iss_appversion_fallback_matches_pyproject(
    pyproject_version: str, iss_appversion_fallback: str,
) -> None:
    """The .iss ``#define AppVersion`` fallback must match
    ``pyproject.toml`` ``version``. Without this pin, running
    ``iscc LapCoachLogger.iss`` directly (without the
    ``build_installer.bat`` ``/DAppVersion=`` override) produces
    an installer labeled with the stale fallback version."""
    assert iss_appversion_fallback == pyproject_version, (
        f"Version drift: pyproject.toml says "
        f"{pyproject_version!r} but installer/LapCoachLogger.iss "
        f"`#define AppVersion` fallback is "
        f"{iss_appversion_fallback!r}. Update the .iss fallback "
        f"to match — this is what `iscc` uses if "
        f"`build_installer.bat` is bypassed."
    )


# -- Compile-time bridge -----------------------------------------------


def test_build_bat_reads_version_from_app_identity() -> None:
    """``build_installer.bat`` must source the version from
    ``app_identity.VERSION`` so the installer label stays
    consistent with the runtime ``__version__``.

    Tolerant: match a Python invocation that imports VERSION
    from ``lap_coach_logger.app_identity``."""
    text = _BUILD_BAT_PATH.read_text(encoding="utf-8")
    assert re.search(
        r'from\s+lap_coach_logger\.app_identity\s+import\s+VERSION',
        text,
    ), (
        "build_installer.bat must read the version from "
        "`from lap_coach_logger.app_identity import VERSION` so "
        "the installer label stays consistent with runtime."
    )
    # And it must pass that version to iscc via /DAppVersion=
    assert re.search(
        r'/DAppVersion\s*=\s*%APP_VERSION%',
        text,
    ), (
        "build_installer.bat must pass /DAppVersion=%APP_VERSION% "
        "to ISCC so the .iss fallback is overridden with the "
        "live app_identity.VERSION value."
    )
