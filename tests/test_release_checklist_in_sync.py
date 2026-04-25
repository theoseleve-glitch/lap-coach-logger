"""T184: ``RELEASE_CHECKLIST.md`` versioned and in-sync with code.

The static release checklist at the repo root is the recurring
runbook a release manager follows for every version: build the
exe, sign the installer, smoke-test on a clean Windows VM,
verify the About dialog version, validate an iRacing capture,
etc.

If the checklist drifts from the code (version mismatch,
referenced build script renamed, dropped pytest command), the
release manager runs the wrong contract and silent ship-bugs
follow.

T184 pins three drift-prevention properties:

1. The file exists at the canonical repo-root location.
2. It contains the current ``app_identity.VERSION`` literal.
3. It references the core build/test toolchain by exact name:
   ``build.bat``, ``build_installer.bat``, ``pytest``,
   ``requirements.txt``, ``assets\\icon.ico``.

Source-content cross-file pin (consistent with T175-T183).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_CHECKLIST_PATH = _REPO / "RELEASE_CHECKLIST.md"
_APP_IDENTITY_PATH = (
    _REPO / "src" / "lap_coach_logger" / "app_identity.py"
)


@pytest.fixture(scope="module")
def checklist_text() -> str:
    assert _CHECKLIST_PATH.is_file(), (
        f"RELEASE_CHECKLIST.md must exist at the repo root, "
        f"got: {_CHECKLIST_PATH}"
    )
    return _CHECKLIST_PATH.read_text(encoding="utf-8")


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


# -- Existence + version pin -------------------------------------------


def test_release_checklist_exists() -> None:
    """The static release checklist must live at the repo
    root so release managers find it without having to know
    the docs/ layout."""
    assert _CHECKLIST_PATH.is_file(), (
        f"RELEASE_CHECKLIST.md must exist at "
        f"{_CHECKLIST_PATH}; T184 requires it tracked at the "
        f"repo root"
    )


def test_release_checklist_mentions_current_version(
    checklist_text: str, app_identity_version: str,
) -> None:
    """Whatever ``app_identity.VERSION`` reports, the checklist
    must mention the same literal — typically in the
    "About dialog version" verification step. Drift here means
    the release manager either confirms the wrong version or
    realizes the docs are stale at install time."""
    assert app_identity_version in checklist_text, (
        f"RELEASE_CHECKLIST.md does not mention the current "
        f"version {app_identity_version!r}. Update the file to "
        f"match `app_identity.VERSION` (search for old version "
        f"strings and bump them)."
    )


# -- Toolchain references ---------------------------------------------


@pytest.mark.parametrize(
    "marker,reason",
    [
        (
            "build.bat",
            "must reference the production build script "
            "`build.bat` so the release manager knows how to "
            "produce the dist/ folder",
        ),
        (
            "build_installer.bat",
            "must reference the installer build script "
            "`build_installer.bat` so the release manager knows "
            "how to produce the .exe installer",
        ),
        (
            "pytest",
            "must reference `pytest` so the release manager "
            "knows the test gate is `pytest` (not `unittest` or "
            "some custom runner)",
        ),
        (
            "requirements.txt",
            "must reference `requirements.txt` so the release "
            "manager knows where dependencies are pinned",
        ),
    ],
)
def test_release_checklist_references_toolchain(
    checklist_text: str, marker: str, reason: str,
) -> None:
    """Each core toolchain artifact must be named explicitly so
    the runbook stays valid even if a future contributor
    renames a script. Renaming `build.bat` → `package.bat`
    without updating the checklist breaks the whole release
    flow."""
    assert marker in checklist_text, (
        f"RELEASE_CHECKLIST.md {reason}; missing marker: "
        f"{marker!r}"
    )


def test_release_checklist_references_app_icon(
    checklist_text: str,
) -> None:
    """The app icon path must be mentioned because installer
    branding depends on it; the checklist's pre-build step is
    where this is verified."""
    # Tolerant: accept either `assets\icon.ico` or
    # `assets/icon.ico` (markdown rendering of Windows path
    # could go either way).
    has_icon_ref = (
        "assets\\icon.ico" in checklist_text
        or "assets/icon.ico" in checklist_text
    )
    assert has_icon_ref, (
        "RELEASE_CHECKLIST.md must reference `assets\\icon.ico` "
        "(or `assets/icon.ico`) — the installer branding fails "
        "silently if this asset is missing, so the runbook must "
        "verify it"
    )


# -- Format pin --------------------------------------------------------


def test_release_checklist_has_h1_title(checklist_text: str) -> None:
    """The file must start with a markdown H1 — `# Release Checklist`
    or similar — so it renders correctly in GitHub's file
    preview."""
    first_nonblank = next(
        (line for line in checklist_text.splitlines() if line.strip()),
        "",
    )
    assert first_nonblank.startswith("# "), (
        f"RELEASE_CHECKLIST.md must start with a markdown H1 "
        f"heading; got first non-blank line: {first_nonblank!r}"
    )
