"""T158: FuelWidget — degraded = grayed.

The fuel widget already returns ``-- L`` / ``--.-`` placeholder
strings when ``remaining`` / ``lapsLeft`` / ``fuelPerLap`` are
``NaN`` or undefined — but the colour bindings still go through
``stateColor`` (acidGreen / pitOrange / safetyRed) so a stale
fuel reading at 0 still renders in the SAFE green colour. T158
adds an explicit ``degraded`` boolean: when true the widget
forces all the data-bearing text to ``-- L`` / ``--.-`` *and*
flips colour to steel, distinguishing "no fuel data" from
"car has 0 L of fuel".

File-content QML pin (rendering tests need a Qt visual context
the test runner doesn't have, same pattern as T141 / T148 /
T151 / T152 / T157).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_WIDGET_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "lap_coach_logger" / "qml" / "Overlay" / "widgets"
    / "FuelWidget.qml"
)


@pytest.fixture(scope="module")
def widget_qml() -> str:
    return _WIDGET_PATH.read_text(encoding="utf-8")


def test_widget_declares_degraded_property(widget_qml: str) -> None:
    """``degraded`` is the contract — VM (or any caller)
    drives it; widget reacts. Same shape as T157 added to
    DeltaTimeWidget."""
    assert re.search(
        r'property\s+bool\s+degraded\b', widget_qml,
    ), "FuelWidget must declare `property bool degraded`"


def test_widget_degraded_defaults_to_false(widget_qml: str) -> None:
    """Default false so existing call sites that don't bind
    ``degraded`` keep the same behaviour."""
    assert re.search(
        r'property\s+bool\s+degraded\s*:\s*false\b', widget_qml,
    ), "degraded must default to `false`"


def test_laps_left_renders_placeholder_when_degraded(widget_qml: str) -> None:
    """The headline LAPS LEFT readout flips to ``--.-`` when
    degraded — same placeholder string the existing NaN guard
    already returns. Caller having stalled telemetry should see
    "no data" not "0.0 laps left in green"."""
    assert re.search(
        r'root\.degraded\s*\?\s*"--\.-"',
        widget_qml,
    ), (
        "LAPS LEFT text must render `--.-` when "
        "root.degraded is true"
    )


def test_laps_left_colour_grays_out_when_degraded(widget_qml: str) -> None:
    """LAPS LEFT colour goes neutral when degraded — overrides
    ``root.stateColor`` (which would otherwise pick acidGreen
    for the default SAFE state)."""
    assert re.search(
        r'root\.degraded\s*\?\s*Theme\.Tokens\.steel',
        widget_qml,
    ), (
        "LAPS LEFT colour must use Theme.Tokens.steel when "
        "root.degraded is true"
    )


def test_remaining_data_row_grays_value_when_degraded(widget_qml: str) -> None:
    """The REMAINING and FUEL/LAP rows also need to read as
    "no data". Tolerant: pinning that the DataRow ``value``
    binding for "REMAINING" or the ``valueColor`` for any
    DataRow respects ``root.degraded``. Easiest implementation
    is a single ternary on each DataRow's value/valueColor."""
    assert re.search(
        r'root\.degraded\s*\?\s*"-- L"',
        widget_qml,
    ), (
        "REMAINING / FUEL/LAP DataRow value must render `-- L` "
        "when root.degraded is true"
    )
