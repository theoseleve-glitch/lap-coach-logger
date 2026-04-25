"""T141: ``RaceStrategyWidget`` pit-armed visual feedback.

The QML rendering tests need a Qt visual context, which the
test runner doesn't have — so this file pins the *file content*
of the widget (and the OverlayWindow that hosts it) using
regex / substring checks. Every wiring the armed indicator
depends on must show up in the file:

- the widget declares a ``pitArmed`` property (QML side of the
  T141 contract — VM has to drive it)
- some visible element conditionally renders on ``pitArmed``
  (the indicator badge / colour change)
- ``OverlayWindow.qml`` passes the VM's ``pitArmed`` through to
  the widget — without that wire the widget always shows
  ``false`` and the visual feedback never fires

Regex (rather than exact substring) where the wiring includes
whitespace variability so a future formatting tweak doesn't
break the test for the wrong reason.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGET_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"
    / "RaceStrategyWidget.qml"
)
_OVERLAY_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "OverlayWindow.qml"
)


@pytest.fixture(scope="module")
def widget_qml() -> str:
    return _WIDGET_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def overlay_qml() -> str:
    return _OVERLAY_PATH.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Widget declares the pitArmed property
# ---------------------------------------------------------------------------


def test_widget_declares_pit_armed_property(widget_qml: str) -> None:
    """The widget must expose ``pitArmed`` as a bool property
    so the OverlayWindow can bind it to the VM. Without this,
    QML silently treats the binding as a no-op."""
    assert re.search(r"property\s+bool\s+pitArmed", widget_qml), (
        "RaceStrategyWidget must declare `property bool pitArmed`"
    )


def test_widget_pit_armed_defaults_to_false(widget_qml: str) -> None:
    """The default must be ``false`` — a true default would
    light up the indicator on every fresh launch before the
    VM has computed anything."""
    assert re.search(
        r"property\s+bool\s+pitArmed\s*:\s*false",
        widget_qml,
    ), "pitArmed must default to false"


# ---------------------------------------------------------------------------
# Widget renders an indicator that's visible only when armed
# ---------------------------------------------------------------------------


def test_widget_has_pit_armed_indicator(widget_qml: str) -> None:
    """An ``ARMED`` text label is the simplest, language-stable
    visual cue. Pin its presence so a future refactor doesn't
    silently drop the indicator."""
    assert "ARMED" in widget_qml, (
        "Widget must render an ARMED indicator"
    )


def test_widget_indicator_visibility_is_gated_on_pit_armed(
    widget_qml: str,
) -> None:
    """The indicator must be conditional on ``pitArmed`` —
    otherwise it would render permanently. Regex tolerant of
    minor formatting (visible: root.pitArmed / visible:
    pitArmed)."""
    assert re.search(r"visible\s*:\s*\w*\.?pitArmed", widget_qml), (
        "ARMED indicator must be visible-bound on pitArmed"
    )


# ---------------------------------------------------------------------------
# OverlayWindow wires VM.pitArmed through to the widget
# ---------------------------------------------------------------------------


def test_overlay_window_binds_widget_pit_armed_to_vm(
    overlay_qml: str,
) -> None:
    """The wire from ``overlayVM.pitArmed`` to
    ``widget.pitArmed`` is the seam that ties Python state to
    the QML indicator. Without this binding, the indicator
    never lights up regardless of VM state."""
    assert re.search(
        r"pitArmed\s*:\s*overlayVM\s*\?\s*overlayVM\.pitArmed",
        overlay_qml,
    ), (
        "OverlayWindow must bind widget.pitArmed to overlayVM.pitArmed "
        "with a null-safe overlayVM check"
    )
