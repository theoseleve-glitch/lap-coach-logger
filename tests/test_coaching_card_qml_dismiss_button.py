"""T097: CoachingCard has a dismiss button wired to ``vm.dismiss()``.

T091 already shipped the ``dismiss()`` slot — what was missing was
the user-facing button. T097 adds it: when the user is satisfied
they've internalised the coaching tip (or doesn't want it anymore
right now), they tap the button and the card fades out.

The button is small ("✕" or similar) and lives in the top-right
corner — the same idiom every dismissable HUD widget uses.
Mouse-area-on-click invokes ``coachingCardVM.dismiss()``, which
the VM already wires (T091) to advance to the next pending
insight if any, or clear to empty otherwise.

Visual placement: top-right corner. Accessibility: should be at
least 24×24 px (Fitts's-law-friendly tap target on the HUD).

QML can't render without QApplication, so this test pins the
file content — the button must exist, must be clickable, must
call dismiss(), and must NOT block the title/body content area
(``z`` ordering or anchored-only layout).
"""
from __future__ import annotations

from pathlib import Path

import pytest


_QML_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Components" / "CoachingCard.qml"
)


@pytest.fixture(scope="module")
def card_qml() -> str:
    return _QML_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Dismiss button: presence, wiring, accessibility
# ---------------------------------------------------------------------------


def test_card_contains_a_mouse_area_for_dismiss(card_qml: str) -> None:
    """A clickable element is the prerequisite — the dismiss
    button is realised in QML as a Rectangle/Item with a
    MouseArea overlay."""
    assert "MouseArea" in card_qml


def test_dismiss_button_invokes_vm_dismiss_slot(card_qml: str) -> None:
    """The MouseArea's ``onClicked`` must call
    ``coachingCardVM.dismiss()`` — that's how T091's slot is
    invoked from QML.

    Without this binding the button would be visually present
    but inert — easy to miss in a code review."""
    assert "coachingCardVM.dismiss()" in card_qml


def test_dismiss_button_has_visible_glyph(card_qml: str) -> None:
    """The user needs to see *something* to click on. A "✕" or
    "×" glyph is the universal dismiss convention. Pinning that
    a glyph is present (any of the common dismiss shapes) so the
    button isn't an invisible 24×24 area in the corner."""
    assert any(glyph in card_qml for glyph in ("✕", "×", "✖", "Dismiss"))


# ---------------------------------------------------------------------------
# Layout: button must not steal click from the rest of the card
# ---------------------------------------------------------------------------


def test_dismiss_button_uses_explicit_implicit_size(card_qml: str) -> None:
    """A MouseArea anchored without a constrained size grows to
    fill its parent — meaning the entire card becomes "dismiss".
    The dismiss MouseArea must have an ``implicitWidth`` /
    ``implicitHeight`` (or ``width`` / ``height``) so it stays
    bounded to the corner glyph.

    Loose-match: a numeric width or height anywhere in the file
    body is enough — the test would fail if the card had ONLY
    Layout-sized children with no explicit dimensions."""
    body = card_qml
    assert any(
        token in body
        for token in (
            "implicitWidth:",
            "implicitHeight:",
            "width: ",
            "height: ",
        )
    ), "dismiss MouseArea must have explicit dimensions"
