"""T159: TireLifeWidget — degraded = grayed.

The tire widget defaults to ``gripPct: 100, condition: "good"``,
so when telemetry stalls (paused session, lost connection) it
renders ``100%`` in acidGreen — visually identical to "fresh
tires, no wear". That's misleading. T159 adds an explicit
``degraded`` boolean: when true the widget forces the headline
grip readout and laps-remaining values to ``--`` placeholders
in steel colour, distinguishing "no tire data" from "tires are
fresh".

File-content QML pin (rendering tests need a Qt visual context
the test runner doesn't have, same pattern as T141 / T148 /
T151 / T152 / T157 / T158).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGET_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"
    / "TireLifeWidget.qml"
)


@pytest.fixture(scope="module")
def widget_qml() -> str:
    return _WIDGET_PATH.read_text(encoding="utf-8")


def test_widget_declares_degraded_property(widget_qml: str) -> None:
    """``degraded`` is the contract — VM (or any caller) drives
    it; widget reacts. Same shape as T157/T158."""
    assert re.search(
        r'property\s+bool\s+degraded\b', widget_qml,
    ), "TireLifeWidget must declare `property bool degraded`"


def test_widget_degraded_defaults_to_false(widget_qml: str) -> None:
    """Default false so existing call sites that don't bind
    ``degraded`` keep the same behaviour."""
    assert re.search(
        r'property\s+bool\s+degraded\s*:\s*false\b', widget_qml,
    ), "degraded must default to `false`"


def test_grip_pct_renders_placeholder_when_degraded(widget_qml: str) -> None:
    """The headline grip percentage flips to ``--`` when
    degraded — overrides the default 100% which would otherwise
    look like "fresh tires" in green."""
    assert re.search(
        r'root\.degraded\s*\?\s*"--"',
        widget_qml,
    ), (
        "Grip pct text must render `--` when "
        "root.degraded is true"
    )


def test_grip_pct_color_grays_out_when_degraded(widget_qml: str) -> None:
    """Grip pct colour goes neutral when degraded — overrides
    ``root.condColor`` (which would otherwise pick acidGreen
    for the default good condition)."""
    assert re.search(
        r'root\.degraded\s*\?\s*Theme\.Tokens\.steel',
        widget_qml,
    ), (
        "Grip pct colour must use Theme.Tokens.steel when "
        "root.degraded is true"
    )


def test_laps_remaining_renders_placeholder_when_degraded(widget_qml: str) -> None:
    """The laps-remaining readout (alongside stint count) needs
    to read as "no data" too, otherwise the headline says ``--``
    while ``99 laps left`` keeps showing — inconsistent UX.
    Tolerant: pin that ``root.degraded`` reaches the laps text
    via any ternary route."""
    assert re.search(
        r'root\.degraded\s*\?\s*"-- laps left"',
        widget_qml,
    ), (
        "Laps-remaining text must render `-- laps left` when "
        "root.degraded is true"
    )
