"""T167: GapTimingWidget — degraded = both cells em-dash.

The widget already renders "—" via ``formatGap()`` when
``hasAhead`` / ``hasBehind`` is false. But that only fires when
the gap value itself is NaN or zero — if telemetry stalls
mid-session the cached numeric gaps stay in place and the
cells keep showing real-looking values. T167 adds an explicit
``degraded`` boolean: when true ``hasAhead`` and ``hasBehind``
both go false, re-using the existing em-dash path so both
cells flip to "—" simultaneously.

File-content QML pin (same shape as T164 SectorDelta).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGET_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"
    / "GapTimingWidget.qml"
)


@pytest.fixture(scope="module")
def widget_qml() -> str:
    return _WIDGET_PATH.read_text(encoding="utf-8")


def test_widget_declares_degraded_property(widget_qml: str) -> None:
    """``degraded`` is the contract — VM (or any caller) drives
    it; widget reacts."""
    assert re.search(
        r'property\s+bool\s+degraded\b', widget_qml,
    ), "GapTimingWidget must declare `property bool degraded`"


def test_widget_degraded_defaults_to_false(widget_qml: str) -> None:
    """Default false so existing call sites that don't bind it
    keep the same behaviour."""
    assert re.search(
        r'property\s+bool\s+degraded\s*:\s*false\b', widget_qml,
    ), "degraded must default to `false`"


def test_has_ahead_gates_on_degraded(widget_qml: str) -> None:
    """``hasAhead`` returns false when degraded — re-uses the
    formatGap em-dash path. Tolerant: any clause that gates on
    root.degraded inside the hasAhead binding is fine."""
    has_ahead_match = re.search(
        r'readonly\s+property\s+bool\s+hasAhead\s*:\s*([^\n]+)',
        widget_qml,
    )
    assert has_ahead_match is not None, "hasAhead binding must exist"
    assert re.search(
        r'!\s*root\.degraded\b|!\s*degraded\b',
        has_ahead_match.group(1),
    ), (
        "hasAhead must short-circuit on root.degraded so cell "
        "renders `—` when telemetry stalls"
    )


def test_has_behind_gates_on_degraded(widget_qml: str) -> None:
    """``hasBehind`` returns false when degraded — same logic."""
    has_behind_match = re.search(
        r'readonly\s+property\s+bool\s+hasBehind\s*:\s*([^\n]+)',
        widget_qml,
    )
    assert has_behind_match is not None, "hasBehind binding must exist"
    assert re.search(
        r'!\s*root\.degraded\b|!\s*degraded\b',
        has_behind_match.group(1),
    ), (
        "hasBehind must short-circuit on root.degraded so cell "
        "renders `—` when telemetry stalls"
    )
