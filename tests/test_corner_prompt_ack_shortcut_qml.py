"""T153: QML shortcut wiring for corner-prompt acknowledgment.

The "wheel-compatible input" deliverable hinges on a single
QML ``Shortcut`` (or ``Action``) that calls
``overlayVM.acknowledgeCornerPrompt()`` on a key event. Any
input device that can be mapped to a keyboard key — wheel
buttons via Logitech G HUB / Fanatec / Simucube software,
gamepad buttons via Steam Input, regular keyboard — flows
through that one seam.

File-content QML pin (rendering tests need a Qt visual context
the test runner doesn't have, same pattern as T148/T151/T152).
We tolerate either a ``Shortcut`` or an ``Action`` element so
the implementation can pick whichever fits the surrounding
QML structure.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_OVERLAY_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "OverlayWindow.qml"
)


@pytest.fixture(scope="module")
def overlay_qml() -> str:
    return _OVERLAY_PATH.read_text(encoding="utf-8")


def test_overlay_window_declares_shortcut_or_action(overlay_qml: str) -> None:
    """The shortcut element exists in the OverlayWindow scope.
    Without it, no key event can reach the VM. Tolerant of
    either element type — either works for QML key handling."""
    assert re.search(
        r'\b(Shortcut|Action)\s*\{', overlay_qml,
    ), (
        "OverlayWindow must declare a Shortcut/Action element "
        "for the wheel-button acknowledgment"
    )


def test_overlay_window_shortcut_calls_acknowledge_corner_prompt(
    overlay_qml: str,
) -> None:
    """Pin the actual wiring: the shortcut calls the VM slot.
    Without this binding the key event has no effect on the
    prompt state. Null-safe overlayVM check matches T141 /
    T148 / T151 / T152 conventions."""
    assert re.search(
        r'overlayVM\s*&&\s*overlayVM\.acknowledgeCornerPrompt\s*\(\s*\)'
        r'|overlayVM\s*\?\.\s*acknowledgeCornerPrompt\s*\(\s*\)'
        r'|if\s*\(\s*overlayVM\s*\)\s*overlayVM\.acknowledgeCornerPrompt',
        overlay_qml,
    ), (
        "OverlayWindow shortcut handler must call "
        "overlayVM.acknowledgeCornerPrompt() with a null-safe "
        "overlayVM check"
    )
