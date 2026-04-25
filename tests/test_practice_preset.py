"""T123: ``practice`` overlay preset definition.

Per spec: "12 widgets (adds inputs, g-g, live trace)". The base
race-minimal layout (T122) covers the universal core (lap_delta,
tires, coach, flags, sector_color, etc.); Practice mode adds
the technique-focused widgets a driver leans on when learning
a track or working a setup:

- ``inputs``       — steering / throttle / brake bars (snapshot)
- ``g_g``          — lateral × longitudinal G dot (smoothness)
- ``live_trace``   — live track map / racing line trace
- ``pedal_trace``  — continuous brake + throttle trace history
                     (technique tuning beyond the snapshot bars)

12 widgets total = T122's 8 race-minimal core + 4 practice-only.
preset_id matches PracticeMode.overlay_preset_id ("practice",
T107) so ModeEngine→bind_overlay_preset_to_mode_engine resolves
it without a translation layer.

Position model (normalised 0..1) mirrors T122 so the renderer
can interpret both presets identically.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Module export + Mode contract alignment
# ---------------------------------------------------------------------------


def test_practice_preset_is_exposed_as_module_constant() -> None:
    from lap_coach_logger.core.modes import builtin_presets

    assert hasattr(builtin_presets, "PRACTICE_PRESET")


def test_practice_preset_id_matches_practice_mode_target() -> None:
    """PracticeMode.overlay_preset_id is ``"practice"`` (T107).
    The preset has to declare the same id or the runtime can't
    resolve it at switch time."""
    from lap_coach_logger.core.modes.builtin_presets import PRACTICE_PRESET
    from lap_coach_logger.core.modes.practice import PracticeMode

    assert PRACTICE_PRESET.preset_id == PracticeMode.overlay_preset_id


# ---------------------------------------------------------------------------
# Practice-specific widget set: the 3 spec additions + 1 implicit
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "widget_id",
    ["inputs", "g_g", "live_trace", "pedal_trace"],
)
def test_practice_includes_technique_focused_widget(widget_id: str) -> None:
    """Spec lists inputs, g_g, live_trace as the headline
    additions; pedal_trace is the 4th to reach the spec total
    of 12 widgets — distinct from inputs (which is a snapshot)
    in that it carries history. Pin each individually so a
    refactor that drops one fails loudly with the offending
    widget id in the failure message."""
    from lap_coach_logger.core.modes.builtin_presets import PRACTICE_PRESET

    assert PRACTICE_PRESET.get_placement(widget_id) is not None


# ---------------------------------------------------------------------------
# Race-minimal core stays present
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "widget_id",
    [
        "lap_delta",      # pace
        "tires",          # heat
        "coach",          # instruction (the whole point of practice)
        "flags",          # yellows
        "sector_color",   # sector pace
        "fuel",           # still relevant in long stints
        "position",       # context for traffic in busy iRacing test sessions
        "gap",            # rough reference to other cars
    ],
)
def test_practice_inherits_race_minimal_core_widget(widget_id: str) -> None:
    """Practice extends — not replaces — the race-minimal core.
    A driver shouldn't lose lap_delta or coach when switching
    to Practice mode. Pin each individually so the failure
    message identifies what went missing."""
    from lap_coach_logger.core.modes.builtin_presets import PRACTICE_PRESET

    assert PRACTICE_PRESET.get_placement(widget_id) is not None


# ---------------------------------------------------------------------------
# Total count = 12 (per spec)
# ---------------------------------------------------------------------------


def test_practice_widget_count_is_twelve() -> None:
    """Spec says ""12 widgets"". A creep to 13 is a regression
    (overlay starts looking cluttered); a drop to 11 means
    we've lost a documented widget. Pin the count exactly."""
    from lap_coach_logger.core.modes.builtin_presets import PRACTICE_PRESET

    assert len(PRACTICE_PRESET.widgets) == 12


# ---------------------------------------------------------------------------
# Positions stay in normalised range
# ---------------------------------------------------------------------------


def test_every_practice_widget_position_is_in_normalised_range() -> None:
    """Same invariant as T122 — defaults must round-trip across
    monitor resolutions."""
    from lap_coach_logger.core.modes.builtin_presets import PRACTICE_PRESET

    for w in PRACTICE_PRESET.widgets:
        assert 0.0 <= w.x <= 1.0, f"{w.widget_id} x={w.x} out of range"
        assert 0.0 <= w.y <= 1.0, f"{w.widget_id} y={w.y} out of range"
        assert 0.0 < w.width <= 1.0, f"{w.widget_id} width={w.width} out of range"
        assert 0.0 < w.height <= 1.0, f"{w.widget_id} height={w.height} out of range"
        assert w.x + w.width <= 1.0, f"{w.widget_id} extends past right edge"
        assert w.y + w.height <= 1.0, f"{w.widget_id} extends past bottom edge"


# ---------------------------------------------------------------------------
# Lookup helper picks up the new preset
# ---------------------------------------------------------------------------


def test_get_builtin_preset_returns_practice_by_id() -> None:
    from lap_coach_logger.core.modes.builtin_presets import (
        PRACTICE_PRESET,
        get_builtin_preset,
    )

    assert get_builtin_preset("practice") is PRACTICE_PRESET


def test_lookup_still_returns_race_minimal_after_practice_added() -> None:
    """Regression check: T122's lookup still works after T123
    extends the registry. Catches a refactor that swaps the
    ``_BUILTIN_PRESETS`` dict for a single-preset structure."""
    from lap_coach_logger.core.modes.builtin_presets import (
        RACE_MINIMAL_PRESET,
        get_builtin_preset,
    )

    assert get_builtin_preset("race-minimal") is RACE_MINIMAL_PRESET
