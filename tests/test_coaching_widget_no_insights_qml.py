"""T160: CoachingWidget — "insights not available" banner.

The coaching card is currently visible-only — when the
coaching engine has nothing to surface (no recent insight,
no significant loss, fresh session) the widget simply hides
itself via opacity. From the user's perspective that's
indistinguishable from "the overlay is broken / coaching
isn't working". T160 adds an explicit empty-state banner
that says "INSIGHTS NOT AVAILABLE" so the affordance is
visible.

File-content QML pin (rendering tests need a Qt visual context
the test runner doesn't have, same pattern as T141 / T148 /
T151 / T152 / T157 / T158 / T159).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGET_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"
    / "CoachingWidget.qml"
)


@pytest.fixture(scope="module")
def widget_qml() -> str:
    return _WIDGET_PATH.read_text(encoding="utf-8")


def test_widget_declares_no_insights_property(widget_qml: str) -> None:
    """``noInsightsAvailable`` is the empty-state contract — VM
    drives it; widget reacts. Domain-specific name so callers
    distinguish "no insights yet" from generic "stale telemetry"
    used by other widgets' ``degraded``."""
    assert re.search(
        r'property\s+bool\s+noInsightsAvailable\b', widget_qml,
    ), "CoachingWidget must declare `property bool noInsightsAvailable`"


def test_widget_no_insights_defaults_to_false(widget_qml: str) -> None:
    """Default false so existing call sites that don't bind it
    keep the same behaviour. Opt-in, not opt-out."""
    assert re.search(
        r'property\s+bool\s+noInsightsAvailable\s*:\s*false\b', widget_qml,
    ), "noInsightsAvailable must default to `false`"


def test_widget_renders_banner_text_when_no_insights(widget_qml: str) -> None:
    """The empty-state banner uses the literal string
    "INSIGHTS NOT AVAILABLE" (uppercase like the other
    monospace meta-labels in this widget)."""
    assert re.search(
        r'"INSIGHTS NOT AVAILABLE"',
        widget_qml,
    ), "CoachingWidget must include the literal banner text `INSIGHTS NOT AVAILABLE`"


def test_widget_banner_visible_when_no_insights(widget_qml: str) -> None:
    """The banner element is shown when ``noInsightsAvailable``
    is true. Tolerant: the implementation can use ``visible:
    root.noInsightsAvailable`` directly or the inverse pattern
    on the existing content."""
    # Either the banner Text has `visible: root.noInsightsAvailable`
    # or the existing headline has `visible: !root.noInsightsAvailable`
    assert re.search(
        r'visible\s*:\s*root\.noInsightsAvailable\b|'
        r'visible\s*:\s*!\s*root\.noInsightsAvailable\b',
        widget_qml,
    ), (
        "Banner / headline must toggle visibility via "
        "root.noInsightsAvailable"
    )
