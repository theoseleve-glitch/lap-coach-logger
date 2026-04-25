"""T128: Widget categorisation — every widget tagged with one tier.

Per spec: ""Race"", ""Practice"", ""Endurance"", ""Streamer"", ""Advanced""
— five tiers. Every widget the presets reference (T122-T125)
gets exactly one category, used by:

- The overlay manager (T130 search) to filter by tier.
- T129's "Show advanced" toggle (Streamer / Advanced are
  hidden by default).
- Future onboarding flows that ramp users from Race → Practice
  → Endurance complexity.

Categories follow widget *introduction*, not preset membership:
``lap_delta`` is tagged Race even though it appears in Practice
and Endurance presets too — the introduction tier identifies
which mode the widget primarily serves.

Tier breakdown:
- **Race** — race-minimal core (T122 8 widgets)
- **Practice** — technique-tuning additions (T123)
- **Endurance** — stint-management additions (T124)
- **Streamer** — broadcast-only widgets (driver_name,
  session_clock, weather, track_map)
- **Advanced** — power-user telemetry that doesn't fit
  cleanly above (g_g, live_trace, gear, speedometer)
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Catalogue exists + categories are exactly the spec-listed five
# ---------------------------------------------------------------------------


def test_widget_catalogue_module_exists() -> None:
    from lap_coach_logger.core.modes import widget_catalog  # noqa: F401


def test_categories_are_exactly_the_spec_five() -> None:
    """Pin the category constants — adding a sixth without updating
    the spec would silently bypass the tier system. Catches a
    refactor that introduces a stray ""Misc"" category."""
    from lap_coach_logger.core.modes.widget_catalog import WIDGET_CATEGORIES

    assert set(WIDGET_CATEGORIES) == {
        "Race", "Practice", "Endurance", "Streamer", "Advanced"
    }


# ---------------------------------------------------------------------------
# Per-widget category assignments (introduction-tier model)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "widget_id",
    [
        "lap_delta", "fuel", "tires", "coach", "position",
        "flags", "sector_color", "gap",
    ],
)
def test_race_minimal_widgets_tagged_race(widget_id: str) -> None:
    """Race-minimal core widgets (T122) anchor the Race tier."""
    from lap_coach_logger.core.modes.widget_catalog import (
        get_widget_category,
    )

    assert get_widget_category(widget_id) == "Race"


@pytest.mark.parametrize(
    "widget_id",
    ["inputs", "pedal_trace"],
)
def test_practice_additions_tagged_practice(widget_id: str) -> None:
    """Technique-tuning widgets introduced in Practice (T123) —
    inputs (snapshot bars) and pedal_trace (history). g_g and
    live_trace, also added in Practice, are tagged Advanced
    instead because they're power-user views; the spec leaves
    that interpretive (T128 just requires *a* tier per widget)."""
    from lap_coach_logger.core.modes.widget_catalog import (
        get_widget_category,
    )

    assert get_widget_category(widget_id) == "Practice"


@pytest.mark.parametrize(
    "widget_id",
    ["stint_timer", "tire_life", "long_run_pace"],
)
def test_endurance_additions_tagged_endurance(widget_id: str) -> None:
    """Stint-management widgets introduced in Endurance (T124)."""
    from lap_coach_logger.core.modes.widget_catalog import (
        get_widget_category,
    )

    assert get_widget_category(widget_id) == "Endurance"


@pytest.mark.parametrize(
    "widget_id",
    ["driver_name", "session_clock", "weather", "track_map"],
)
def test_streamer_only_widgets_tagged_streamer(widget_id: str) -> None:
    """Broadcast-only widgets introduced exclusively in Streamer
    (T125). Note: gear / speedometer also appear in Streamer
    but are tagged Advanced — they're power-user telemetry that
    happens to be visually engaging in broadcasts."""
    from lap_coach_logger.core.modes.widget_catalog import (
        get_widget_category,
    )

    assert get_widget_category(widget_id) == "Streamer"


@pytest.mark.parametrize(
    "widget_id",
    ["g_g", "live_trace", "gear", "speedometer"],
)
def test_advanced_widgets_tagged_advanced(widget_id: str) -> None:
    """Power-user telemetry — visually rich but not central to
    any one mode. Hidden behind T129's ""Show advanced"" toggle."""
    from lap_coach_logger.core.modes.widget_catalog import (
        get_widget_category,
    )

    assert get_widget_category(widget_id) == "Advanced"


# ---------------------------------------------------------------------------
# Coverage: every widget referenced by any built-in preset is tagged
# ---------------------------------------------------------------------------


def test_every_preset_widget_has_a_category() -> None:
    """Cross-check: walk all 4 built-in presets, collect every
    widget_id, confirm each one has a non-None category. Catches
    a refactor where T122-T125 add a new widget but T128's
    catalogue isn't updated."""
    from lap_coach_logger.core.modes.builtin_presets import _BUILTIN_PRESETS
    from lap_coach_logger.core.modes.widget_catalog import (
        get_widget_category,
    )

    seen: set[str] = set()
    for preset in _BUILTIN_PRESETS.values():
        for placement in preset.widgets:
            seen.add(placement.widget_id)

    missing = [wid for wid in seen if get_widget_category(wid) is None]
    assert not missing, f"untagged widgets: {missing}"


# ---------------------------------------------------------------------------
# Lookup helper: unknown widget returns None (no exception)
# ---------------------------------------------------------------------------


def test_get_widget_category_returns_none_for_unknown_widget() -> None:
    """Same defensive shape as get_builtin_preset / get_placement —
    callers decide how to handle an unknown widget rather than
    being forced into try/except."""
    from lap_coach_logger.core.modes.widget_catalog import (
        get_widget_category,
    )

    assert get_widget_category("not-a-widget") is None


# ---------------------------------------------------------------------------
# Reverse helper: list every widget in a given tier
# ---------------------------------------------------------------------------


def test_widgets_in_category_returns_all_race_tier_widgets() -> None:
    """T130's search and T129's tier-filter need to enumerate
    widgets *by* category. Reverse helper avoids repeating the
    full filter loop in every consumer."""
    from lap_coach_logger.core.modes.widget_catalog import (
        widgets_in_category,
    )

    assert set(widgets_in_category("Race")) == {
        "lap_delta", "fuel", "tires", "coach", "position",
        "flags", "sector_color", "gap",
    }


def test_widgets_in_category_returns_empty_for_unknown_tier() -> None:
    from lap_coach_logger.core.modes.widget_catalog import (
        widgets_in_category,
    )

    assert widgets_in_category("NotATier") == ()
