"""T169: TireLifeWidget — degraded covers condition badge,
grip bar, and tire temps.

T159 added the ``degraded`` property and overrode the headline
grip% / laps-left / stint readouts. T169 finishes the widget
by extending the override to:

1. The condition badge (which still showed "GOOD" in acidGreen
   when degraded — defeating T159's purpose).
2. The grip bar fill (still rendered as a full green bar when
   degraded if gripPct stayed at its default 100).
3. The four tire temperature cells (which only flipped to
   "--" when ``temp > 0`` was false — frozen values kept
   showing).

File-content QML pin (same shape as T159 but covering the
remaining elements). Reuses the existing ``degraded``
property added in T159 — no new contract.
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


def test_condition_badge_text_grays_when_degraded(widget_qml: str) -> None:
    """The condition badge label flips to "--" when degraded —
    overrides condition.toUpperCase() so we don't read "GOOD"
    in green for stale tires."""
    assert re.search(
        r'root\.degraded\s*\?\s*"--"\s*:\s*root\.condition\.toUpperCase\(\)',
        widget_qml,
    ), (
        "Condition badge text must render `--` when "
        "root.degraded is true"
    )


def test_condition_badge_color_grays_when_degraded(widget_qml: str) -> None:
    """The condition badge color flips to steel when degraded.
    Anchored to a window after the ``condLabel`` id so we don't
    match T159's grip% color ternary by accident."""
    # Find the line index of `id: condLabel` and slice the next
    # ~10 lines — the color line lives within that window.
    idx = widget_qml.find("id: condLabel")
    assert idx >= 0, "condLabel Text element must exist"
    window = widget_qml[idx : idx + 600]
    assert re.search(
        r'color\s*:\s*root\.degraded\s*\?\s*Theme\.Tokens\.steel\s*:\s*root\.condColor',
        window,
    ), (
        "Condition badge color must use Theme.Tokens.steel "
        "when root.degraded is true"
    )


def test_grip_bar_fill_grays_when_degraded(widget_qml: str) -> None:
    """The grip bar fill width goes to 0 when degraded, so we
    don't render a "100% green" bar over stale data. Tolerant:
    pin that the inner Rectangle's width expression accounts
    for root.degraded."""
    # The fill width is `parent.width * Math.max(0, Math.min(1, root.gripPct / 100))`
    # We want it gated on degraded → render nothing when degraded.
    assert re.search(
        r'width\s*:\s*root\.degraded\s*\?\s*0',
        widget_qml,
    ), (
        "Grip bar fill width must be 0 when root.degraded is true"
    )


def test_tire_temps_render_placeholder_when_degraded(widget_qml: str) -> None:
    """Tire temp cells render "--" when degraded, even if
    cached temp values are still > 0. Tolerant: pin that the
    temp text expression accounts for root.degraded."""
    # Existing: `text: modelData.temp > 0 ? Math.round(modelData.temp) + "°" : "--"`
    # We want: `text: root.degraded ? "--" : (existing)`
    assert re.search(
        r'root\.degraded\s*\?\s*"--"\s*:\s*\(?\s*modelData\.temp',
        widget_qml,
    ), (
        "Tire temp text must render `--` when "
        "root.degraded is true"
    )
