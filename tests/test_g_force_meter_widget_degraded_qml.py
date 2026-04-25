"""T162: GForceMeterWidget — degraded = "SENSOR STALE" banner.

The widget uses ``isFinite`` guards on each numeric input so
NaN / undefined gets coerced to 0.0 — meaning when telemetry
stalls the dot pegs at the center and the readout shows
``0.00 G``, visually identical to "stationary on grid".
T162 adds an explicit ``degraded`` boolean: when true an
overlay "SENSOR STALE" banner is shown over the canvas, and
the combined-G readout in the header flips to ``-- G``.

File-content QML pin (rendering tests need a Qt visual context
the test runner doesn't have, same pattern as T141 / T148 /
T151 / T152 / T157 / T158 / T159 / T160 / T161).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGET_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"
    / "GForceMeterWidget.qml"
)


@pytest.fixture(scope="module")
def widget_qml() -> str:
    return _WIDGET_PATH.read_text(encoding="utf-8")


def test_widget_declares_degraded_property(widget_qml: str) -> None:
    """``degraded`` is the contract — VM (or any caller) drives
    it; widget reacts."""
    assert re.search(
        r'property\s+bool\s+degraded\b', widget_qml,
    ), "GForceMeterWidget must declare `property bool degraded`"


def test_widget_degraded_defaults_to_false(widget_qml: str) -> None:
    """Default false so existing call sites that don't bind it
    keep the same behaviour."""
    assert re.search(
        r'property\s+bool\s+degraded\s*:\s*false\b', widget_qml,
    ), "degraded must default to `false`"


def test_widget_includes_sensor_stale_text(widget_qml: str) -> None:
    """The banner uses the literal "SENSOR STALE" string,
    consistent with T161's input-widget treatment."""
    assert re.search(
        r'"SENSOR STALE"',
        widget_qml,
    ), "GForceMeterWidget must include the literal banner text `SENSOR STALE`"


def test_widget_banner_visible_when_degraded(widget_qml: str) -> None:
    """The "SENSOR STALE" element shows when ``degraded`` is
    true. Tolerant: any element using ``visible: root.degraded``
    proves the wiring."""
    assert re.search(
        r'visible\s*:\s*root\.degraded\b',
        widget_qml,
    ), (
        "An element must toggle `visible: root.degraded` "
        "(the SENSOR STALE banner)"
    )


def test_combined_g_readout_grays_when_degraded(widget_qml: str) -> None:
    """The header combined-G text flips to ``-- G`` when
    degraded — overrides the toFixed(2) numeric so the user
    doesn't see ``0.00 G`` (which looks like real "stationary"
    data)."""
    assert re.search(
        r'root\.degraded\s*\?\s*"-- G"',
        widget_qml,
    ), (
        "Combined-G text must render `-- G` when "
        "root.degraded is true"
    )
