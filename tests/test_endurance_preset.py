"""T124: ``endurance`` overlay preset definition.

Per spec: "10 widgets (adds stint timer, tire life, long-run pace)".
Endurance racing focuses on stint management, tire wear, and
consistent long-run pace — distinct from sprint's last-three-lap
intensity. The 3 spec additions reflect that:

- ``stint_timer``    — elapsed time in current stint (driver-swap planning)
- ``tire_life``      — predicted laps remaining on the current set
- ``long_run_pace``  — rolling average pace over the last N laps
                       (vs. lap_delta which is per-lap)

Total = 10 widgets. With T122's race-minimal at 8, the math is
``8 - 1 + 3 = 10`` — endurance drops one race-minimal widget that
isn't useful for endurance focus. The drop choice: ``sector_color``,
since drivers tracking long-run pace care about *stint* averages
not sector-by-sector marginal differences.

preset_id matches EnduranceMode.overlay_preset_id ("endurance",
T109) so ModeEngine→bind_overlay_preset_to_mode_engine resolves
it without a translation layer.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Module export + Mode contract alignment
# ---------------------------------------------------------------------------


def test_endurance_preset_is_exposed_as_module_constant() -> None:
    from lap_coach_logger.core.modes import builtin_presets

    assert hasattr(builtin_presets, "ENDURANCE_PRESET")


def test_endurance_preset_id_matches_endurance_mode_target() -> None:
    """EnduranceMode.overlay_preset_id is ``"endurance"`` (T109).
    The preset has to declare the same id or the runtime can't
    resolve it at switch time."""
    from lap_coach_logger.core.modes.builtin_presets import ENDURANCE_PRESET
    from lap_coach_logger.core.modes.endurance import EnduranceMode

    assert ENDURANCE_PRESET.preset_id == EnduranceMode.overlay_preset_id


# ---------------------------------------------------------------------------
# Endurance-specific widget set: the 3 spec additions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "widget_id",
    ["stint_timer", "tire_life", "long_run_pace"],
)
def test_endurance_includes_stint_focused_widget(widget_id: str) -> None:
    """The 3 spec-listed additions are non-negotiable. Pin
    each individually so a refactor that drops one fails loudly
    with the offending widget id."""
    from lap_coach_logger.core.modes.builtin_presets import ENDURANCE_PRESET

    assert ENDURANCE_PRESET.get_placement(widget_id) is not None


# ---------------------------------------------------------------------------
# Race-minimal core mostly inherited (with sector_color dropped)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "widget_id",
    [
        "lap_delta",  # per-lap pace still relevant
        "tires",      # heat (pairs with tire_life for wear)
        "coach",      # coaching surface (T109: minimal verbosity)
        "flags",      # FCY / safety car critical in endurance
        "fuel",       # endurance is THE fuel-strategy mode
        "position",   # class position matters for cohort racing
        "gap",        # gap to ahead/behind in long stints
    ],
)
def test_endurance_inherits_race_minimal_core_widget(widget_id: str) -> None:
    """Inherits 7 of 8 race-minimal widgets at the same positions
    so a Sprint↔Endurance mid-session switch doesn't shuffle
    the driver's screen for the widgets that stay (matches T123's
    inheritance approach)."""
    from lap_coach_logger.core.modes.builtin_presets import ENDURANCE_PRESET

    assert ENDURANCE_PRESET.get_placement(widget_id) is not None


def test_endurance_drops_sector_color_in_favour_of_stint_focus() -> None:
    """sector_color is the one race-minimal widget endurance
    drops — drivers tracking long-run pace care about stint
    averages, not sector-by-sector marginal differences. This
    test pins the deliberate omission so a future regression
    that "fixes" the missing widget ends up shipping 11 widgets
    against the spec's 10."""
    from lap_coach_logger.core.modes.builtin_presets import ENDURANCE_PRESET

    assert ENDURANCE_PRESET.get_placement("sector_color") is None


# ---------------------------------------------------------------------------
# Total count = 10 (per spec)
# ---------------------------------------------------------------------------


def test_endurance_widget_count_is_ten() -> None:
    """Spec says ""10 widgets"". A creep to 11 means we re-added
    sector_color or another widget; a drop to 9 means we lost
    one of the 3 spec additions or 7 inherited widgets. Pin
    the count exactly."""
    from lap_coach_logger.core.modes.builtin_presets import ENDURANCE_PRESET

    assert len(ENDURANCE_PRESET.widgets) == 10


# ---------------------------------------------------------------------------
# Positions stay in normalised range
# ---------------------------------------------------------------------------


def test_every_endurance_widget_position_is_in_normalised_range() -> None:
    from lap_coach_logger.core.modes.builtin_presets import ENDURANCE_PRESET

    for w in ENDURANCE_PRESET.widgets:
        assert 0.0 <= w.x <= 1.0, f"{w.widget_id} x={w.x} out of range"
        assert 0.0 <= w.y <= 1.0, f"{w.widget_id} y={w.y} out of range"
        assert 0.0 < w.width <= 1.0, f"{w.widget_id} width={w.width} out of range"
        assert 0.0 < w.height <= 1.0, f"{w.widget_id} height={w.height} out of range"
        assert w.x + w.width <= 1.0, f"{w.widget_id} extends past right edge"
        assert w.y + w.height <= 1.0, f"{w.widget_id} extends past bottom edge"


# ---------------------------------------------------------------------------
# Lookup helper picks up the new preset
# ---------------------------------------------------------------------------


def test_get_builtin_preset_returns_endurance_by_id() -> None:
    from lap_coach_logger.core.modes.builtin_presets import (
        ENDURANCE_PRESET,
        get_builtin_preset,
    )

    assert get_builtin_preset("endurance") is ENDURANCE_PRESET


def test_lookup_still_returns_earlier_presets_after_endurance_added() -> None:
    """Regression check: T122 + T123 lookups still work after
    T124 extends the registry. Catches a refactor that
    accidentally drops earlier presets."""
    from lap_coach_logger.core.modes.builtin_presets import (
        PRACTICE_PRESET,
        RACE_MINIMAL_PRESET,
        get_builtin_preset,
    )

    assert get_builtin_preset("race-minimal") is RACE_MINIMAL_PRESET
    assert get_builtin_preset("practice") is PRACTICE_PRESET
