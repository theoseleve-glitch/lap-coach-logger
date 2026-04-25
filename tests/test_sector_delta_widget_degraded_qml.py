"""T164: SectorDeltaWidget — degraded = all sectors em-dash.

The widget already renders ``—`` in chalk for individual
sectors with missing data (via ``deltaFor()`` returning null).
But when the whole telemetry pipeline stalls, all 3 cells
freeze on their last numeric values — visually identical to
"live data". T164 adds an explicit ``degraded`` boolean: when
true ``deltaFor()`` returns null for every sector, re-using the
existing null path so all 3 cells flip to "—" simultaneously.

File-content QML pin (rendering tests need a Qt visual context
the test runner doesn't have, same pattern as T141 / T148 /
T151 / T152 / T157 / T158 / T159 / T160 / T161 / T162 / T163).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGET_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"
    / "SectorDeltaWidget.qml"
)


@pytest.fixture(scope="module")
def widget_qml() -> str:
    return _WIDGET_PATH.read_text(encoding="utf-8")


def test_widget_declares_degraded_property(widget_qml: str) -> None:
    """``degraded`` is the contract — VM (or any caller) drives
    it; widget reacts."""
    assert re.search(
        r'property\s+bool\s+degraded\b', widget_qml,
    ), "SectorDeltaWidget must declare `property bool degraded`"


def test_widget_degraded_defaults_to_false(widget_qml: str) -> None:
    """Default false so existing call sites that don't bind it
    keep the same behaviour."""
    assert re.search(
        r'property\s+bool\s+degraded\s*:\s*false\b', widget_qml,
    ), "degraded must default to `false`"


def test_delta_for_returns_null_when_degraded(widget_qml: str) -> None:
    """``deltaFor()`` short-circuits to null when degraded — the
    existing null path renders "—" in muted chalk for each
    cell. Tolerant: any branch in deltaFor that gates on
    root.degraded and returns null is fine."""
    # Match the deltaFor function body and check it gates on degraded
    fn_match = re.search(
        r'function\s+deltaFor\s*\([^)]*\)\s*\{([\s\S]*?)\}',
        widget_qml,
    )
    assert fn_match is not None, "deltaFor function must exist"
    body = fn_match.group(1)
    assert re.search(
        r'root\.degraded|this\.degraded|\bdegraded\b',
        body,
    ), (
        "deltaFor() must gate on root.degraded so all sectors "
        "render `—` when telemetry stalls"
    )
    # And return null in that branch
    assert re.search(
        r'(if\s*\(\s*(root\.)?degraded\s*\)\s*return\s+null|'
        r'(root\.)?degraded\s*\?\s*null)',
        body,
    ), (
        "deltaFor() must return null when root.degraded is true"
    )
