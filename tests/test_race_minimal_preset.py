"""T122: ``race-minimal`` overlay preset definition.

Per spec: "8-10 core widgets (lap delta, fuel, tires, coach,
position, flags, sector color, gap)". The 8 listed are the
non-negotiable core — every short-format race needs:

- ``lap_delta``    — fastest indicator of where pace is being lost
- ``fuel``         — non-zero margin in T108 SprintMode means fuel still matters
- ``tires``        — temps + wear so the driver doesn't kill them on cold tires
- ``coach``        — T091's CoachingCardViewModel surface
- ``position``     — race position (overall + class)
- ``flags``        — yellows / blues / blacks
- ``sector_color`` — green/yellow/purple per-sector pace marker
- ``gap``          — gap to leader/ahead/behind

T122 ships the *definition* — preset_id matches
``SprintMode.overlay_preset_id`` ("race-minimal", T108) so
ModeEngine→bind_overlay_preset_to_mode_engine resolves it
without a translation layer.

Positions are normalised (0..1) defaults — sane fallback for
the first cold start. T126+ ships the user-customisation +
per-resolution scaling; T122 just pins the widget set + roughly
sensible layout.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Preset registration + id alignment with SprintMode
# ---------------------------------------------------------------------------


def test_race_minimal_preset_is_exposed_as_a_module_constant() -> None:
    """The preset is built once at import time so observers
    (overlay_binding lookup, tests) get a single shared frozen
    instance — matches how T107-T110 mode classes are exposed."""
    from lap_coach_logger.core.modes import builtin_presets

    assert hasattr(builtin_presets, "RACE_MINIMAL_PRESET")


def test_race_minimal_preset_id_matches_sprint_mode_target() -> None:
    """ModeEngine wires SprintMode.overlay_preset_id to the
    overlay system; the preset id has to match exactly or the
    runtime can't resolve a preset at switch time."""
    from lap_coach_logger.core.modes.builtin_presets import RACE_MINIMAL_PRESET
    from lap_coach_logger.core.modes.sprint import SprintMode

    assert RACE_MINIMAL_PRESET.preset_id == SprintMode.overlay_preset_id


# ---------------------------------------------------------------------------
# Widget set: the 8 listed in the spec, all present
# ---------------------------------------------------------------------------


_REQUIRED_WIDGETS = (
    "lap_delta",
    "fuel",
    "tires",
    "coach",
    "position",
    "flags",
    "sector_color",
    "gap",
)


@pytest.mark.parametrize("widget_id", _REQUIRED_WIDGETS)
def test_race_minimal_includes_required_widget(widget_id: str) -> None:
    """Pin each spec-listed widget individually so the failure
    message identifies *which* widget went missing if a refactor
    drops one. Catches a copy-paste mistake that would, say,
    omit the coaching surface from race mode."""
    from lap_coach_logger.core.modes.builtin_presets import RACE_MINIMAL_PRESET

    assert RACE_MINIMAL_PRESET.get_placement(widget_id) is not None


def test_race_minimal_widget_count_in_spec_range() -> None:
    """Spec says 8-10 widgets. Tighten lower bound to 8 (the
    listed core), upper to 10 (allows a small extension without
    triggering this test, but stops a refactor that quietly
    bloats race mode into Streamer territory)."""
    from lap_coach_logger.core.modes.builtin_presets import RACE_MINIMAL_PRESET

    count = len(RACE_MINIMAL_PRESET.widgets)
    assert 8 <= count <= 10, f"expected 8-10 widgets in race-minimal, got {count}"


# ---------------------------------------------------------------------------
# Positions are normalised — within [0, 1]
# ---------------------------------------------------------------------------


def test_every_widget_position_is_in_normalised_range() -> None:
    """Every (x, y) origin and (width, height) extent stays in
    [0, 1]. The runtime is allowed to interpret floats as either
    pixels or normalised, but the *defaults* T122 ships are
    normalised so they scale across resolutions."""
    from lap_coach_logger.core.modes.builtin_presets import RACE_MINIMAL_PRESET

    for w in RACE_MINIMAL_PRESET.widgets:
        assert 0.0 <= w.x <= 1.0, f"{w.widget_id} x={w.x} out of range"
        assert 0.0 <= w.y <= 1.0, f"{w.widget_id} y={w.y} out of range"
        assert 0.0 < w.width <= 1.0, f"{w.widget_id} width={w.width} out of range"
        assert 0.0 < w.height <= 1.0, f"{w.widget_id} height={w.height} out of range"
        assert w.x + w.width <= 1.0, f"{w.widget_id} extends past right edge"
        assert w.y + w.height <= 1.0, f"{w.widget_id} extends past bottom edge"


# ---------------------------------------------------------------------------
# Lookup helper: preset id → preset (or None)
# ---------------------------------------------------------------------------


def test_get_builtin_preset_returns_race_minimal_by_id() -> None:
    """Runtime lookup happens by id, not by importing constants.
    Wire the helper so observers can pass mode.overlay_preset_id
    straight in."""
    from lap_coach_logger.core.modes.builtin_presets import (
        RACE_MINIMAL_PRESET,
        get_builtin_preset,
    )

    assert get_builtin_preset("race-minimal") is RACE_MINIMAL_PRESET


def test_get_builtin_preset_returns_none_for_unknown_id() -> None:
    """Unknown id ⇒ None. Same defensive shape as
    ``WidgetPlacement`` lookup (T121) — caller decides how to
    handle it. Will let T123-T125 land their own presets without
    forcing T122 to know about them."""
    from lap_coach_logger.core.modes.builtin_presets import get_builtin_preset

    assert get_builtin_preset("not-a-real-preset") is None
