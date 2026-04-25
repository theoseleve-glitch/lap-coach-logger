"""T168: SessionTimerWidget — degraded = grayed elapsed time.

The widget displays a hero elapsed-time readout that freezes
silently when telemetry stalls — visually identical whether
the session is paused or the connection died. T168 adds an
explicit ``degraded`` boolean: when true the elapsed text
flips to ``—:——:——`` in steel colour, distinguishing "no
session data" from "session is paused at exactly 0:00:00".

File-content QML pin (same shape as T157 DeltaTime).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGET_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"
    / "SessionTimerWidget.qml"
)


@pytest.fixture(scope="module")
def widget_qml() -> str:
    return _WIDGET_PATH.read_text(encoding="utf-8")


def test_widget_declares_degraded_property(widget_qml: str) -> None:
    """``degraded`` is the contract — VM (or any caller) drives
    it; widget reacts."""
    assert re.search(
        r'property\s+bool\s+degraded\b', widget_qml,
    ), "SessionTimerWidget must declare `property bool degraded`"


def test_widget_degraded_defaults_to_false(widget_qml: str) -> None:
    """Default false so existing call sites that don't bind it
    keep the same behaviour."""
    assert re.search(
        r'property\s+bool\s+degraded\s*:\s*false\b', widget_qml,
    ), "degraded must default to `false`"


def test_elapsed_renders_placeholder_when_degraded(widget_qml: str) -> None:
    """The headline elapsed time flips to ``—:——:——`` when
    degraded — distinguishes "no data" from "0:00:00 paused"."""
    assert re.search(
        r'root\.degraded\s*\?\s*"—:——:——"',
        widget_qml,
    ), (
        "Elapsed text must render `—:——:——` when "
        "root.degraded is true"
    )


def test_elapsed_color_grays_when_degraded(widget_qml: str) -> None:
    """The hero elapsed colour goes steel (neutral) when
    degraded — overrides the chalk default."""
    assert re.search(
        r'root\.degraded\s*\?\s*Theme\.Tokens\.steel',
        widget_qml,
    ), (
        "Elapsed colour must use Theme.Tokens.steel when "
        "root.degraded is true"
    )
