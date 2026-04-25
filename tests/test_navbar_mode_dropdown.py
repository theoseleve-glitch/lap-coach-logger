"""T116: Mode switch dropdown in the main toolbar.

The NavBar already shows a read-only ``modeVM.activeMode`` badge
(post-T106 mode work). T116 turns that into a *clickable*
dropdown so the user can switch modes without leaving the
toolbar — Sprint ↔ Endurance ↔ Coaching ↔ Data are all one
click away.

Wires to the existing ``ModeViewModel``: clicking a menu item
calls ``modeVM.setMode(<mode_id>)``. The VM already handles
the no-op case (clicking the active mode does nothing) and
the analytics ``mode_switched`` event (T063), so T116 is purely
the UI layer — no new VM behaviour.

QML rendering needs a QApplication, so this test pins the file
content. Every wiring the dropdown depends on must appear in
the file: the Menu definition, one MenuItem per mode, the
``setMode`` call, and a click target that opens the menu.
"""
from __future__ import annotations

from pathlib import Path

import pytest

_QML_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Components" / "NavBar.qml"
)


@pytest.fixture(scope="module")
def navbar_qml() -> str:
    return _QML_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# File presence + import for Controls
# ---------------------------------------------------------------------------


def test_navbar_qml_file_exists() -> None:
    assert _QML_PATH.exists()


def test_navbar_imports_qtquick_controls(navbar_qml: str) -> None:
    """``Menu`` / ``MenuItem`` live in ``QtQuick.Controls``. Without
    the import the dropdown silently turns into a plain object and
    nothing fires on click."""
    assert "import QtQuick.Controls" in navbar_qml


# ---------------------------------------------------------------------------
# Dropdown menu lists every mode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mode_id",
    ["sprint", "endurance", "coaching", "data"],
)
def test_dropdown_has_menu_item_for_each_mode(navbar_qml: str, mode_id: str) -> None:
    """Each mode in MODES (core/mode_detector.py) must be reachable
    from the dropdown — otherwise users can land in modes (e.g.
    via auto-detect) they can't manually switch out of. Pin the
    setMode call so a refactor that renames the VM slot fails
    here loudly instead of silently breaking the dropdown."""
    expected = f'modeVM.setMode("{mode_id}")'
    assert expected in navbar_qml, (
        f"NavBar.qml must wire MenuItem onTriggered to {expected!r}"
    )


# ---------------------------------------------------------------------------
# Click target opens the menu
# ---------------------------------------------------------------------------


def test_dropdown_has_a_menu_block(navbar_qml: str) -> None:
    """The Menu has to be defined as a QML object — without the
    ``Menu {`` block, the four MenuItems are just floating
    declarations that never bind to a popup."""
    assert "Menu {" in navbar_qml


def test_dropdown_trigger_opens_menu_on_click(navbar_qml: str) -> None:
    """A user must be able to OPEN the dropdown — i.e. some
    MouseArea has to call ``.open()`` on the menu. Without this
    the menu is unreachable from the UI even if all four items
    are wired. The exact id can vary (modeMenu / modeDropdown /
    etc.) so we accept any ``.open()`` invocation against an
    object whose name contains 'mode' (case-insensitive)."""
    import re
    pattern = re.compile(r"\b\w*[Mm]ode\w*\.open\(\)")
    assert pattern.search(navbar_qml), (
        "NavBar.qml must call <modeMenu>.open() somewhere "
        "(MouseArea click handler) to open the dropdown"
    )
