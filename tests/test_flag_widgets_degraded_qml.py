"""T165: Flag widgets — degraded = "TELEMETRY STALE" banner.

Both ``FlagsWidget`` and ``DigiflagWidget`` default to the
"none/CLEAR" state with the same green/steel treatment as a
real "ALL CLEAR" flag. When the sim disconnects the widget
keeps showing the last received flag (or "CLEAR" if no flag
ever arrived), and the user has no way to tell "track is
clear" from "connection dead". T165 adds a ``degraded``
boolean + overlay "TELEMETRY STALE" banner so the user knows
the flag display is unreliable.

File-content QML pin (rendering tests need a Qt visual context
the test runner doesn't have, same pattern as T141 / T148 /
T151 / T152 / T157 / T158 / T159 / T160 / T161 / T162 / T163 /
T164). Parameterized over both widgets since they share an
identical contract per the audit.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGETS_DIR = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"
)

_FLAGS_WIDGET = _WIDGETS_DIR / "FlagsWidget.qml"
_DIGIFLAG_WIDGET = _WIDGETS_DIR / "DigiflagWidget.qml"


@pytest.fixture(
    params=[_FLAGS_WIDGET, _DIGIFLAG_WIDGET],
    ids=["FlagsWidget", "DigiflagWidget"],
)
def widget_qml(request: pytest.FixtureRequest) -> str:
    path: Path = request.param
    return path.read_text(encoding="utf-8")


def test_widget_declares_degraded_property(widget_qml: str) -> None:
    """``degraded`` is the contract — VM (or any caller) drives
    it; widget reacts."""
    assert re.search(
        r'property\s+bool\s+degraded\b', widget_qml,
    ), "Flag widget must declare `property bool degraded`"


def test_widget_degraded_defaults_to_false(widget_qml: str) -> None:
    """Default false so existing call sites that don't bind it
    keep the same behaviour."""
    assert re.search(
        r'property\s+bool\s+degraded\s*:\s*false\b', widget_qml,
    ), "degraded must default to `false`"


def test_widget_includes_telemetry_stale_text(widget_qml: str) -> None:
    """The banner uses the literal "TELEMETRY STALE" string —
    semantically distinct from the input-widget "SENSOR STALE"
    (here the data source is the sim's flag stream, not a
    sensor)."""
    assert re.search(
        r'"TELEMETRY STALE"',
        widget_qml,
    ), "Flag widget must include the literal banner text `TELEMETRY STALE`"


def test_widget_banner_visible_when_degraded(widget_qml: str) -> None:
    """The "TELEMETRY STALE" element shows when ``degraded`` is
    true. Tolerant: any element using ``visible: root.degraded``
    proves the wiring."""
    assert re.search(
        r'visible\s*:\s*root\.degraded\b',
        widget_qml,
    ), (
        "An element must toggle `visible: root.degraded` "
        "(the TELEMETRY STALE banner)"
    )
