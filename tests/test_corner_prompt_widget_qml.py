"""T152: corner-prompt label in the strategy widget.

File-content QML pin — same pattern as T148/T151. The widget
declares a property bound to the VM, renders the prompt
conditionally, and the OverlayWindow wires the binding through.

Unlike T148/T151's badges, the corner prompt is a longer
sentence ("losing 0.3s at T1 — brake earlier"). The widget
renders it as plain text (not a coloured pill), positioned to
not crowd the existing header chips.
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


def test_widget_declares_corner_prompt_property(widget_qml: str) -> None:
    """Widget exposes ``cornerPrompt`` — the VM has to drive it."""
    assert re.search(
        r'property\s+string\s+cornerPrompt\b', widget_qml,
    ), "RaceStrategyWidget must declare `property string cornerPrompt`"


def test_widget_corner_prompt_defaults_to_empty_string(widget_qml: str) -> None:
    """Default empty so the line is hidden until VM populates
    it. Same default as T148/T151."""
    assert re.search(
        r'property\s+string\s+cornerPrompt\s*:\s*""',
        widget_qml,
    ), "cornerPrompt must default to empty string"


def test_widget_renders_corner_prompt_text(widget_qml: str) -> None:
    """Widget displays ``root.cornerPrompt`` somewhere — the
    binding must reach a Text element."""
    assert re.search(
        r'\btext\s*:\s*root\.cornerPrompt\b', widget_qml,
    ), "Widget must render root.cornerPrompt as visible text"


def test_widget_corner_prompt_visibility_is_gated_on_truthy(
    widget_qml: str,
) -> None:
    """Empty string ⇒ no visible text element. Same tolerant
    pattern as T148/T151: ``visible: root.cornerPrompt`` (truthy),
    ``!== ""``, or ``length > 0`` all match."""
    assert re.search(
        r'visible\s*:\s*root\.cornerPrompt', widget_qml,
    ), "Corner-prompt visibility must be gated on root.cornerPrompt"


def test_overlay_window_binds_widget_corner_prompt_to_vm(
    overlay_qml: str,
) -> None:
    """OverlayWindow wires ``overlayVM.cornerPrompt`` → widget.
    Without this the property is always default and no prompt
    ever shows."""
    assert re.search(
        r'cornerPrompt\s*:\s*overlayVM\s*\?\s*overlayVM\.cornerPrompt',
        overlay_qml,
    ), (
        "OverlayWindow must bind widget.cornerPrompt to "
        "overlayVM.cornerPrompt with null-safe overlayVM check"
    )
