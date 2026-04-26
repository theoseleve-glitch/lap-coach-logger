"""T199: README.md covers end-user onboarding — install link,
pair phone, first session.

The current README focuses on contributor concerns (build from
source, package the installer). T199 adds end-user onboarding
sections so a new user landing on the GitHub page knows how to
get the app installed, pair their phone (T190's wizard step),
and capture their first telemetry session.

Pin the sections by topic-keyword in a markdown heading rather
than exact phrasing — the documentation can evolve as long as
the topics stay covered.

Source-content drift-prevention pin (consistent with T184 /
T198's shape).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


_README_PATH = (
    Path(__file__).resolve().parents[1] / "README.md"
)
_APP_IDENTITY_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "app_identity.py"
)


@pytest.fixture(scope="module")
def readme_text() -> str:
    assert _README_PATH.is_file(), (
        f"README.md must exist at the repo root: {_README_PATH}"
    )
    return _README_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def app_identity_version() -> str:
    text = _APP_IDENTITY_PATH.read_text(encoding="utf-8")
    match = re.search(
        r'^\s*VERSION\s*=\s*[\'"]([^\'"]+)[\'"]',
        text,
        re.MULTILINE,
    )
    assert match is not None
    return match.group(1)


def _markdown_headings(text: str) -> list[str]:
    """Return all markdown headings (any level) as a list."""
    return [
        line.strip()
        for line in text.splitlines()
        if line.lstrip().startswith("#")
    ]


# -- structure pins ---------------------------------------------------


def test_readme_starts_with_h1(readme_text: str) -> None:
    """GitHub renders the H1 as the project page title."""
    first_nonblank = next(
        (line for line in readme_text.splitlines() if line.strip()),
        "",
    )
    assert first_nonblank.startswith("# "), (
        f"README.md must start with H1; first non-blank line: "
        f"{first_nonblank!r}"
    )


def test_readme_mentions_current_version(
    readme_text: str, app_identity_version: str,
) -> None:
    """Drift-prevention: bumping ``app_identity.VERSION`` must
    force a README update too."""
    assert app_identity_version in readme_text, (
        f"README.md does not mention the current version "
        f"{app_identity_version!r}. Update the README's "
        f"version reference to match `app_identity.VERSION`."
    )


# -- T199 onboarding sections -----------------------------------------


@pytest.mark.parametrize(
    "topic_keyword,description",
    [
        ("Install", "install link / installer download section"),
        ("Pair", "pair phone section (links to onboarding wizard)"),
        ("First", "first session / first lap walkthrough"),
    ],
)
def test_readme_has_onboarding_heading(
    readme_text: str, topic_keyword: str, description: str,
) -> None:
    """Each onboarding topic must have a markdown heading
    containing the keyword. Tolerant: doesn't lock the exact
    phrasing — `## Install`, `## Installation`, `### Install
    From Release`, etc. all qualify.

    The README evolves; what matters is the topic is covered."""
    headings = _markdown_headings(readme_text)
    matching = [
        h for h in headings
        if topic_keyword.lower() in h.lower()
    ]
    assert matching, (
        f"README.md must have a markdown heading containing "
        f"{topic_keyword!r} (for the {description}). Current "
        f"headings: {headings}"
    )


def test_readme_install_section_references_installer(
    readme_text: str,
) -> None:
    """The install section must reference the installer
    artifact (``LapCoachLogger-Setup`` or similar) so the
    user knows what to download."""
    # Match any heading that is the install section, then
    # check the body references the installer.
    install_section_match = re.search(
        r'^#+\s+[^\n]*\bInstall\w*[^\n]*\n([\s\S]*?)(?=^#+\s|\Z)',
        readme_text,
        re.MULTILINE | re.IGNORECASE,
    )
    assert install_section_match is not None, (
        "README.md must have an Install section (precondition "
        "from test_readme_has_onboarding_heading)"
    )
    section_body = install_section_match.group(1)
    has_installer_ref = (
        "LapCoachLogger-Setup" in section_body
        or "installer" in section_body.lower()
        or "release" in section_body.lower()
    )
    assert has_installer_ref, (
        "Install section must reference the installer "
        "artifact (e.g. `LapCoachLogger-Setup-X.Y.Z.exe`) or "
        "a release/download link so users know what to "
        "actually download"
    )


def test_readme_pair_section_references_wizard_or_phone(
    readme_text: str,
) -> None:
    """The Pair section must mention either the onboarding
    wizard (where the QR appears) or the phone — otherwise
    the section is decoupled from T190's actual wiring."""
    pair_match = re.search(
        r'^#+\s+[^\n]*\bPair\w*[^\n]*\n([\s\S]*?)(?=^#+\s|\Z)',
        readme_text,
        re.MULTILINE | re.IGNORECASE,
    )
    assert pair_match is not None, "precondition"
    body = pair_match.group(1).lower()
    assert "phone" in body or "wizard" in body or "qr" in body, (
        "Pair section must reference 'phone', 'wizard', or "
        "'QR' — otherwise it's not connected to T190's "
        "pairing flow"
    )


def test_readme_first_section_walks_user_through_session(
    readme_text: str,
) -> None:
    """The First section must mention sessions / sims / a
    sim-specific keyword — otherwise it's not actually a
    first-session walkthrough."""
    first_match = re.search(
        r'^#+\s+[^\n]*\bFirst\w*[^\n]*\n([\s\S]*?)(?=^#+\s|\Z)',
        readme_text,
        re.MULTILINE | re.IGNORECASE,
    )
    assert first_match is not None, "precondition"
    body = first_match.group(1).lower()
    has_session_keyword = (
        "session" in body
        or "sim" in body
        or "lap" in body
        or "drive" in body
        or "iracing" in body
        or "acc" in body
    )
    assert has_session_keyword, (
        "First section must mention session / sim / lap / "
        "drive / a sim name — otherwise it's not a real "
        "first-session walkthrough"
    )
