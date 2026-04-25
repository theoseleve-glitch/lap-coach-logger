"""T180: Inno Setup install flow — custom dir, desktop
shortcut, start-menu entry.

The .iss script must wire three user-facing install affordances:

1. **Custom install dir** — the install dialog lets the user
   choose a destination folder. Requires ``DefaultDirName=``
   to be set and ``DisableDirPage`` to be either absent or
   ``no`` / ``auto`` (any value other than ``yes``).

2. **Desktop shortcut** — opt-in via the ``[Tasks]`` section
   with a ``desktopicon`` task, and an ``[Icons]`` entry
   tied to that task pointing at ``{autodesktop}``.

3. **Start-menu entry** — ``DefaultGroupName=`` set, plus an
   ``[Icons]`` entry under ``{group}`` so the app appears in
   Start Menu \\ <group> after install.

Source-content pin (consistent with T175-T179).
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


def _section_body(iss_text: str, section: str) -> str:
    """Extract a named section body (e.g. [Tasks])."""
    match = re.search(
        rf'\[{re.escape(section)}\]([\s\S]*?)(?=\n\[\w+\]|\Z)',
        iss_text,
    )
    assert match is not None, f".iss must have [{section}] section"
    return match.group(1)


# -- Custom install dir -------------------------------------------------


def test_iss_sets_default_dir_name(iss_text: str) -> None:
    """``DefaultDirName=`` is required for the custom-dir
    flow — without it Inno picks an opaque default."""
    setup = _setup_section(iss_text)
    assert re.search(
        r'^\s*DefaultDirName\s*=\s*\S+',
        setup,
        re.MULTILINE,
    ), "[Setup] must define DefaultDirName="


def test_iss_does_not_disable_dir_page(iss_text: str) -> None:
    """``DisableDirPage=yes`` would skip the dir-customization
    page. T180 explicitly wants the user to be able to choose."""
    setup = _setup_section(iss_text)
    match = re.search(
        r'^\s*DisableDirPage\s*=\s*(\w+)',
        setup,
        re.MULTILINE,
    )
    if match is not None:
        value = match.group(1).lower()
        assert value != "yes", (
            "DisableDirPage=yes would prevent the user from "
            "choosing a custom install directory — T180 requires "
            "either omitting the directive or setting it to "
            "`no`/`auto`"
        )


# -- Desktop shortcut ---------------------------------------------------


def test_iss_has_desktop_icon_task(iss_text: str) -> None:
    """``[Tasks]`` must include a ``desktopicon`` task so the
    user gets the opt-in checkbox for a desktop shortcut."""
    tasks_body = _section_body(iss_text, "Tasks")
    assert re.search(
        r'Name\s*:\s*"?desktopicon"?',
        tasks_body,
    ), (
        "[Tasks] must include `Name: \"desktopicon\"` so the "
        "user can opt into a desktop shortcut"
    )


def test_iss_has_desktop_shortcut_icon(iss_text: str) -> None:
    """``[Icons]`` must wire ``{autodesktop}`` to the
    ``desktopicon`` task so checking the box during install
    actually creates the shortcut."""
    icons_body = _section_body(iss_text, "Icons")
    # Match a line that has both `{autodesktop}` and references
    # the desktopicon task.
    found = False
    for line in icons_body.splitlines():
        if "{autodesktop}" in line and "desktopicon" in line:
            found = True
            break
    assert found, (
        "[Icons] must have an `{autodesktop}\\...` entry with "
        "`Tasks: desktopicon` so the desktop shortcut is "
        "actually created when the user opts in"
    )


# -- Start-menu entry ---------------------------------------------------


def test_iss_sets_default_group_name(iss_text: str) -> None:
    """``DefaultGroupName=`` names the Start Menu folder."""
    setup = _setup_section(iss_text)
    assert re.search(
        r'^\s*DefaultGroupName\s*=\s*\S+',
        setup,
        re.MULTILINE,
    ), "[Setup] must define DefaultGroupName= for the Start Menu folder"


def test_iss_has_start_menu_icon(iss_text: str) -> None:
    """``[Icons]`` must have a ``{group}\\...`` entry so the
    app appears in Start Menu \\ <DefaultGroupName>."""
    icons_body = _section_body(iss_text, "Icons")
    assert re.search(
        r'Name\s*:\s*"\{group\}\\\\',
        icons_body,
    ), (
        "[Icons] must have a `Name: \"{group}\\\\...\"` entry "
        "for the Start Menu shortcut"
    )
