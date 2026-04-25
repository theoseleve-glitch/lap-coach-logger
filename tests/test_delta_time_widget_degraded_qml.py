"""T157: DeltaTimeWidget — degraded = grayed with "—".

The lap-delta widget defaults to ``delta: 0.0`` so when
telemetry stalls (paused session, lost connection) it renders
``+0.000`` in steel colour — visually identical to "I just
ran exactly on best lap". That's misleading. T157 adds an
explicit ``degraded`` boolean: when true the widget shows
``—`` in steel for both the delta value and the lap time,
distinguishing "no data" from "perfect lap pace".

File-content QML pin (rendering tests need a Qt visual context
the test runner doesn't have, same pattern as T141 / T148 /
T151 / T152). The audit doc T156 calls this out as the first
of the Block I follow-ups.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGET_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"
    / "DeltaTimeWidget.qml"
)


@pytest.fixture(scope="module")
def widget_qml() -> str:
    return _WIDGET_PATH.read_text(encoding="utf-8")


def test_widget_declares_degraded_property(widget_qml: str) -> None:
    """``degraded`` is the contract: VM (or any caller) drives
    it; the widget reacts. Without the property declaration
    QML can't even bind to it."""
    assert re.search(
        r'property\s+bool\s+degraded\b', widget_qml,
    ), "DeltaTimeWidget must declare `property bool degraded`"


def test_widget_degraded_defaults_to_false(widget_qml: str) -> None:
    """Default false so existing call sites that don't bind
    ``degraded`` keep the same behaviour. Symmetric to T148's
    ``guidance: ""`` default — opt-in, not opt-out."""
    assert re.search(
        r'property\s+bool\s+degraded\s*:\s*false\b', widget_qml,
    ), "degraded must default to `false`"


def test_delta_text_renders_em_dash_when_degraded(widget_qml: str) -> None:
    """The headline delta value flips to ``—`` (em-dash with
    `.———` decimals) when degraded. Same placeholder string
    the existing :func:`formatDelta` returns for NaN inputs,
    so the visual treatment is consistent with the existing
    NaN path."""
    # Tolerant: the implementation can either use the existing
    # "—.———" placeholder string directly, or call formatDelta
    # with NaN. Either reaches the same rendered text.
    assert re.search(
        r'root\.degraded\s*\?\s*"—\.———"|'
        r'root\.degraded\s*\?\s*formatDelta\s*\(\s*NaN\s*\)',
        widget_qml,
    ), (
        "Delta text must render `—.———` (or formatDelta(NaN)) "
        "when root.degraded is true"
    )


def test_delta_color_grays_out_when_degraded(widget_qml: str) -> None:
    """Colour signal goes neutral when degraded — the existing
    deltaColor() returns acidGreen/safetyRed/steel based on
    sign, so we override with steel (the neutral colour) to
    mute the gain/loss visual when there's no real data."""
    assert re.search(
        r'root\.degraded\s*\?\s*Theme\.Tokens\.steel',
        widget_qml,
    ), (
        "Delta colour must use Theme.Tokens.steel when "
        "root.degraded is true (neutral / grayed out)"
    )


def test_lap_time_renders_em_dash_when_degraded(widget_qml: str) -> None:
    """The lap-time field already has a ``"—:——.———"``
    placeholder for falsy strings; pin that ``root.degraded``
    forces it too. Without this the lap time keeps showing
    the last frozen value while the delta says no-data —
    inconsistent UX."""
    assert re.search(
        r'root\.degraded\s*\?\s*"—:——\.———"',
        widget_qml,
    ), (
        "Lap time text must render `—:——.———` when "
        "root.degraded is true"
    )
