"""T151: Driver-decision-prompt label in the strategy widget.

File-content QML pin — same pattern as T148's strategyGuidance
and T141's pitArmed indicator. The widget declares a property
bound to the VM, renders the prompt conditionally, and the
OverlayWindow wires the binding through.

QML rendering tests need a Qt visual context the test runner
doesn't have, so this file regex-matches the widget source
instead.
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


def test_widget_declares_decision_prompt_property(widget_qml: str) -> None:
    """Widget exposes ``decisionPrompt`` as the QML side of the
    T151 contract — VM has to drive it."""
    assert re.search(
        r'property\s+string\s+decisionPrompt\b', widget_qml,
    ), "RaceStrategyWidget must declare `property string decisionPrompt`"


def test_widget_decision_prompt_defaults_to_empty_string(widget_qml: str) -> None:
    """Default empty so the prompt is hidden until VM populates
    it. Symmetric to T148's guidance default."""
    assert re.search(
        r'property\s+string\s+decisionPrompt\s*:\s*""',
        widget_qml,
    ), "decisionPrompt must default to empty string"


def test_widget_renders_decision_prompt_text(widget_qml: str) -> None:
    """Widget displays ``root.decisionPrompt`` somewhere —
    without the binding the value would never reach a Text
    element."""
    assert re.search(
        r'\btext\s*:\s*root\.decisionPrompt\b', widget_qml,
    ), "Widget must render root.decisionPrompt as visible text"


def test_widget_decision_prompt_visibility_is_gated_on_truthy(
    widget_qml: str,
) -> None:
    """Empty string ⇒ no visible label. Same tolerance as T148:
    ``visible: root.decisionPrompt`` (truthy), ``!== ""``, or
    ``length > 0`` all match."""
    assert re.search(
        r'visible\s*:\s*root\.decisionPrompt', widget_qml,
    ), "Decision-prompt label visibility must be gated on root.decisionPrompt"


def test_overlay_window_binds_widget_decision_prompt_to_vm(
    overlay_qml: str,
) -> None:
    """OverlayWindow wires ``overlayVM.decisionPrompt`` →
    widget. Without this the property is always default and
    no prompt ever shows."""
    assert re.search(
        r'decisionPrompt\s*:\s*overlayVM\s*\?\s*overlayVM\.decisionPrompt',
        overlay_qml,
    ), (
        "OverlayWindow must bind widget.decisionPrompt to "
        "overlayVM.decisionPrompt with null-safe overlayVM check"
    )
