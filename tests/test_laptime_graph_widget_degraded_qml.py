"""T163: LaptimeGraphWidget — degraded = "TRACE STALE" placeholder.

The widget has an existing "NO DATA" placeholder gated by
``hasData`` — but that only fires when ``lapTimes.length === 0``.
If the sim disconnects mid-session the array keeps holding the
last recorded laps and the chart freezes on stale bars,
visually identical to live data. T163 adds an explicit
``degraded`` boolean: when true the chart hides and the
placeholder shows with "TRACE STALE" headline (re-using the
empty-state UX furniture but with a semantically distinct
message).

File-content QML pin (rendering tests need a Qt visual context
the test runner doesn't have, same pattern as T141 / T148 /
T151 / T152 / T157 / T158 / T159 / T160 / T161 / T162).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGET_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"
    / "LaptimeGraphWidget.qml"
)


@pytest.fixture(scope="module")
def widget_qml() -> str:
    return _WIDGET_PATH.read_text(encoding="utf-8")


def test_widget_declares_degraded_property(widget_qml: str) -> None:
    """``degraded`` is the contract — VM (or any caller) drives
    it; widget reacts."""
    assert re.search(
        r'property\s+bool\s+degraded\b', widget_qml,
    ), "LaptimeGraphWidget must declare `property bool degraded`"


def test_widget_degraded_defaults_to_false(widget_qml: str) -> None:
    """Default false so existing call sites that don't bind it
    keep the same behaviour."""
    assert re.search(
        r'property\s+bool\s+degraded\s*:\s*false\b', widget_qml,
    ), "degraded must default to `false`"


def test_widget_includes_trace_stale_text(widget_qml: str) -> None:
    """The placeholder uses the literal "TRACE STALE" headline
    when degraded — distinct from "NO DATA" so the user can
    tell "engine restarted" from "haven't completed a lap yet"."""
    assert re.search(
        r'"TRACE STALE"',
        widget_qml,
    ), "LaptimeGraphWidget must include the literal `TRACE STALE` headline"


def test_canvas_hidden_when_degraded(widget_qml: str) -> None:
    """When degraded the chart canvas hides so the user sees the
    placeholder instead of frozen bars. Tolerant: pin that the
    canvas visibility expression now accounts for degraded."""
    # Either `hasData && !root.degraded` or equivalent
    assert re.search(
        r'visible\s*:\s*root\.hasData\s*&&\s*!\s*root\.degraded\b',
        widget_qml,
    ), (
        "Chart canvas must hide when root.degraded is true "
        "(visible: root.hasData && !root.degraded)"
    )


def test_placeholder_visible_when_degraded(widget_qml: str) -> None:
    """The empty-state placeholder shows when there's no data
    OR when degraded. Tolerant: pin that the placeholder
    visibility expression includes ``root.degraded``."""
    assert re.search(
        r'visible\s*:\s*!\s*root\.hasData\s*\|\|\s*root\.degraded\b',
        widget_qml,
    ), (
        "Empty-state placeholder must show when root.degraded "
        "is true (visible: !root.hasData || root.degraded)"
    )
