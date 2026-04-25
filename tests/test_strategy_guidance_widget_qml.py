"""T148: Strategy guidance label in the overlay widget.

File-content QML pin — same pattern as T141's pit-armed
indicator: the widget declares a property bound to the VM,
renders the label conditionally, and the OverlayWindow wires
the binding through.
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


def test_widget_declares_strategy_guidance_property(widget_qml: str) -> None:
    """Widget exposes ``guidance`` (or similarly-named string
    property) as the QML side of the T148 contract — VM has
    to drive it."""
    assert re.search(
        r'property\s+string\s+guidance\b', widget_qml,
    ), "RaceStrategyWidget must declare `property string guidance`"


def test_widget_guidance_defaults_to_empty_string(widget_qml: str) -> None:
    """Default empty so the label is hidden until VM populates
    it. Symmetric to T141's pitArmed default false."""
    assert re.search(
        r'property\s+string\s+guidance\s*:\s*""',
        widget_qml,
    ), "guidance must default to empty string"


def test_widget_renders_guidance_text(widget_qml: str) -> None:
    """Widget displays ``root.guidance`` somewhere — without
    the binding the value would never reach a Text element."""
    assert re.search(
        r'\btext\s*:\s*root\.guidance\b', widget_qml,
    ), "Widget must render root.guidance as visible text"


def test_widget_guidance_visibility_is_gated_on_truthy(widget_qml: str) -> None:
    """Empty string ⇒ no visible label (avoids an awkward
    blank pill in the header). Visibility binding can be
    `visible: root.guidance !== ""`, `length > 0`, or just
    `root.guidance` (truthy). Tolerant pattern."""
    assert re.search(
        r'visible\s*:\s*root\.guidance', widget_qml,
    ), "Guidance label visibility must be gated on root.guidance"


def test_overlay_window_binds_widget_guidance_to_vm(overlay_qml: str) -> None:
    """OverlayWindow wires ``overlayVM.strategyGuidance`` →
    widget. Without this the property is always default and
    no label ever shows."""
    assert re.search(
        r'guidance\s*:\s*overlayVM\s*\?\s*overlayVM\.strategyGuidance',
        overlay_qml,
    ), (
        "OverlayWindow must bind widget.guidance to "
        "overlayVM.strategyGuidance with null-safe overlayVM check"
    )
