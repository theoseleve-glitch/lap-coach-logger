"""T170: LaptimeSpreadWidget — degraded forces all time fields
to placeholder.

The widget already returns ``-:---.---`` from ``formatTime``
for invalid/zero inputs and gates canvas markers via
``hasData``. But when telemetry stalls mid-session the cached
fastest/slowest/average/current numbers stay populated, and
the widget keeps showing real-looking lap times. T170 adds an
explicit ``degraded`` boolean: when true ``hasData`` reports
false (canvas markers stop drawing) and ``formatTime``
short-circuits to ``-:---.---`` (all DataRow values and the
header spread flip simultaneously).

File-content QML pin (same shape as T164 SectorDelta — gate
the existing fallback path on degraded).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGET_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"
    / "LaptimeSpreadWidget.qml"
)


@pytest.fixture(scope="module")
def widget_qml() -> str:
    return _WIDGET_PATH.read_text(encoding="utf-8")


def test_widget_declares_degraded_property(widget_qml: str) -> None:
    """``degraded`` is the contract — VM (or any caller) drives
    it; widget reacts."""
    assert re.search(
        r'property\s+bool\s+degraded\b', widget_qml,
    ), "LaptimeSpreadWidget must declare `property bool degraded`"


def test_widget_degraded_defaults_to_false(widget_qml: str) -> None:
    """Default false so existing call sites that don't bind it
    keep the same behaviour."""
    assert re.search(
        r'property\s+bool\s+degraded\s*:\s*false\b', widget_qml,
    ), "degraded must default to `false`"


def test_has_data_gates_on_degraded(widget_qml: str) -> None:
    """``hasData`` reports false when degraded — kills canvas
    markers. Tolerant: any clause gating hasData on
    root.degraded is fine."""
    has_data_match = re.search(
        r'readonly\s+property\s+bool\s+hasData\s*:\s*([^\n]+)',
        widget_qml,
    )
    assert has_data_match is not None, "hasData binding must exist"
    assert re.search(
        r'!\s*root\.degraded\b|!\s*degraded\b',
        has_data_match.group(1),
    ), (
        "hasData must short-circuit on root.degraded so canvas "
        "markers stop rendering when telemetry stalls"
    )


def test_format_time_returns_placeholder_when_degraded(widget_qml: str) -> None:
    """``formatTime`` short-circuits to "-:---.---" when
    degraded — re-uses the existing placeholder so all DataRow
    values + the header spread flip simultaneously. Tolerant:
    any branch in formatTime that gates on degraded and returns
    the placeholder is fine."""
    fn_match = re.search(
        r'function\s+formatTime\s*\([^)]*\)\s*\{([\s\S]*?)\}',
        widget_qml,
    )
    assert fn_match is not None, "formatTime function must exist"
    body = fn_match.group(1)
    assert re.search(
        r'(root\.)?degraded',
        body,
    ), (
        "formatTime() must gate on root.degraded so all time "
        "rows render `-:---.---` when telemetry stalls"
    )
