"""T161: Input widgets — degraded = "SENSOR STALE" banner.

Both ``InputsWidget`` and ``InputTelemetryWidget`` currently
have zero degraded indication (audit T156 classified both as
"NONE"). When the sim quits or telemetry pauses they render
pedal bars at 0% — visually indistinguishable from "no driver
input" — with no signal that the data is stale rather than
truly zero. T161 adds a ``degraded`` bool + overlay banner
saying "SENSOR STALE" so the user knows the input pipeline is
dead, not the driver's foot.

File-content QML pin (rendering tests need a Qt visual context
the test runner doesn't have, same pattern as T141 / T148 /
T151 / T152 / T157 / T158 / T159 / T160). Parameterized over
both target widgets since they share an identical contract per
the audit.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGETS_DIR = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"
)

_INPUTS_WIDGET = _WIDGETS_DIR / "InputsWidget.qml"
_INPUT_TELEMETRY_WIDGET = _WIDGETS_DIR / "InputTelemetryWidget.qml"


@pytest.fixture(
    params=[_INPUTS_WIDGET, _INPUT_TELEMETRY_WIDGET],
    ids=["InputsWidget", "InputTelemetryWidget"],
)
def widget_qml(request: pytest.FixtureRequest) -> str:
    path: Path = request.param
    return path.read_text(encoding="utf-8")


def test_widget_declares_degraded_property(widget_qml: str) -> None:
    """``degraded`` is the contract — VM (or any caller) drives
    it; widget reacts. Same shape as T157-T160."""
    assert re.search(
        r'property\s+bool\s+degraded\b', widget_qml,
    ), "Input widget must declare `property bool degraded`"


def test_widget_degraded_defaults_to_false(widget_qml: str) -> None:
    """Default false so existing call sites that don't bind it
    keep the same behaviour. Opt-in, not opt-out."""
    assert re.search(
        r'property\s+bool\s+degraded\s*:\s*false\b', widget_qml,
    ), "degraded must default to `false`"


def test_widget_includes_sensor_stale_text(widget_qml: str) -> None:
    """The banner uses the literal string "SENSOR STALE"
    (uppercase like other monospace meta-labels in these
    widgets)."""
    assert re.search(
        r'"SENSOR STALE"',
        widget_qml,
    ), "Input widget must include the literal banner text `SENSOR STALE`"


def test_widget_banner_visible_when_degraded(widget_qml: str) -> None:
    """The "SENSOR STALE" element is visible when ``degraded``
    is true. Tolerant: any element using
    ``visible: root.degraded`` proves the wiring."""
    assert re.search(
        r'visible\s*:\s*root\.degraded\b',
        widget_qml,
    ), (
        "An element must toggle `visible: root.degraded` "
        "(the SENSOR STALE banner)"
    )
