"""T166: StandingsWidget — degraded = "STANDINGS STALE" banner.

The widget has an existing "No standings yet…" empty state
gated on ``_count === 0`` — but if telemetry stalls after
positions are cached the array stays populated and the list
keeps rendering frozen positions/gaps as if live. T166 adds
an explicit ``degraded`` boolean: when true the list hides
and the empty-state placeholder repurposes itself with
"STANDINGS STALE" headline so the user knows positions are
unreliable.

File-content QML pin (same shape as T163 LaptimeGraph; pattern
established T141 / T148 / T151 / T152 / T157-T165).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGET_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"
    / "StandingsWidget.qml"
)


@pytest.fixture(scope="module")
def widget_qml() -> str:
    return _WIDGET_PATH.read_text(encoding="utf-8")


def test_widget_declares_degraded_property(widget_qml: str) -> None:
    """``degraded`` is the contract — VM (or any caller) drives
    it; widget reacts."""
    assert re.search(
        r'property\s+bool\s+degraded\b', widget_qml,
    ), "StandingsWidget must declare `property bool degraded`"


def test_widget_degraded_defaults_to_false(widget_qml: str) -> None:
    """Default false so existing call sites that don't bind it
    keep the same behaviour."""
    assert re.search(
        r'property\s+bool\s+degraded\s*:\s*false\b', widget_qml,
    ), "degraded must default to `false`"


def test_widget_includes_standings_stale_text(widget_qml: str) -> None:
    """The repurposed empty-state shows the literal "STANDINGS
    STALE" headline when degraded — distinct from the existing
    "No standings yet…" so the user can tell "engine restarted"
    from "race hasn't started"."""
    assert re.search(
        r'"STANDINGS STALE"',
        widget_qml,
    ), "StandingsWidget must include the literal `STANDINGS STALE` text"


def test_list_hidden_when_degraded(widget_qml: str) -> None:
    """When degraded the list hides so frozen positions don't
    pass for live data. Tolerant: pin that the list visibility
    expression now accounts for degraded."""
    # Either `_count > 0 && !root.degraded` or equivalent
    assert re.search(
        r'visible\s*:\s*root\._count\s*>\s*0\s*&&\s*!\s*root\.degraded\b',
        widget_qml,
    ), (
        "List view must hide when root.degraded is true "
        "(visible: root._count > 0 && !root.degraded)"
    )


def test_placeholder_visible_when_degraded(widget_qml: str) -> None:
    """The empty-state placeholder shows when the list is empty
    OR when degraded. Tolerant: pin the visibility expression."""
    assert re.search(
        r'visible\s*:\s*root\._count\s*===\s*0\s*\|\|\s*root\.degraded\b',
        widget_qml,
    ), (
        "Empty-state placeholder must show when root.degraded "
        "is true (visible: root._count === 0 || root.degraded)"
    )
