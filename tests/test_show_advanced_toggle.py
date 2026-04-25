"""T129: Streamer + Advanced widgets hidden behind "Show advanced".

Per spec — "Streamer widgets grouped behind 'Show advanced' toggle
⇒ hidden by default". The overlay manager (T130) renders the
widget catalogue (T128) filtered by visibility: by default users
see Race / Practice / Endurance widgets only; flipping the
"Show advanced" toggle reveals the Streamer + Advanced tiers.

Two tiers gate behind the toggle (despite the spec calling it
just "Streamer"):
- **Streamer**  — broadcast-only widgets (driver_name etc.) —
                  noise for non-streamers
- **Advanced**  — power-user telemetry (g_g, live_trace, gear,
                  speedometer) — clutters the picker for
                  newcomers

T129 ships the *visibility predicate* + a filter helper.
T130's overlay manager UI consumes them. Bootstrap stores the
toggle state in settings under "show_advanced_widgets" (default
False) — production wiring lands in T130 since that's where the
manager UI is built; T129's deliverable is the pure data layer.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Visibility predicate: is_hidden_by_default(widget_id)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "widget_id",
    [
        # Streamer tier — broadcast context
        "driver_name", "session_clock", "weather", "track_map",
        # Advanced tier — power-user telemetry
        "g_g", "live_trace", "gear", "speedometer",
    ],
)
def test_streamer_and_advanced_widgets_hidden_by_default(widget_id: str) -> None:
    """Both tiers gate behind the toggle. A user landing in the
    overlay manager for the first time should NOT see g_g or
    weather — they should pick from the obvious Race / Practice
    / Endurance widgets first."""
    from lap_coach_logger.core.modes.widget_catalog import (
        is_hidden_by_default,
    )

    assert is_hidden_by_default(widget_id) is True


@pytest.mark.parametrize(
    "widget_id",
    [
        # Race tier — always visible
        "lap_delta", "fuel", "tires", "coach", "position",
        "flags", "sector_color", "gap",
        # Practice tier — always visible
        "inputs", "pedal_trace",
        # Endurance tier — always visible
        "stint_timer", "tire_life", "long_run_pace",
    ],
)
def test_race_practice_endurance_widgets_visible_by_default(widget_id: str) -> None:
    """Race / Practice / Endurance widgets stay visible without
    the toggle — they're the everyday driver-mode widgets that
    new users discover first."""
    from lap_coach_logger.core.modes.widget_catalog import (
        is_hidden_by_default,
    )

    assert is_hidden_by_default(widget_id) is False


def test_unknown_widget_is_hidden_by_default() -> None:
    """Defensive: a widget not in the catalogue is treated as
    hidden — safer to under-show than over-show, and forces a
    catalogue update before the new widget surfaces in the UI."""
    from lap_coach_logger.core.modes.widget_catalog import (
        is_hidden_by_default,
    )

    assert is_hidden_by_default("not-a-real-widget") is True


# ---------------------------------------------------------------------------
# Filter helper: visible_widget_ids(*, show_advanced)
# ---------------------------------------------------------------------------


def test_default_visibility_excludes_streamer_and_advanced() -> None:
    """The filter helper is the canonical way the manager UI
    will read the visibility decision. Default toggle = False
    excludes both Streamer and Advanced."""
    from lap_coach_logger.core.modes.widget_catalog import (
        visible_widget_ids,
    )

    visible = set(visible_widget_ids(show_advanced=False))

    # Streamer-only widgets must NOT be in the default view
    assert "driver_name" not in visible
    assert "session_clock" not in visible
    assert "weather" not in visible
    assert "track_map" not in visible
    # Advanced widgets must NOT be in the default view
    assert "g_g" not in visible
    assert "live_trace" not in visible
    assert "gear" not in visible
    assert "speedometer" not in visible


def test_default_visibility_includes_race_practice_endurance() -> None:
    """Race / Practice / Endurance widgets must all be in the
    default view (catches a regression that over-filters)."""
    from lap_coach_logger.core.modes.widget_catalog import (
        visible_widget_ids,
    )

    visible = set(visible_widget_ids(show_advanced=False))

    assert {
        "lap_delta", "fuel", "tires", "coach", "position",
        "flags", "sector_color", "gap",
        "inputs", "pedal_trace",
        "stint_timer", "tire_life", "long_run_pace",
    }.issubset(visible)


def test_show_advanced_true_returns_every_tagged_widget() -> None:
    """Toggle on ⇒ everything in the catalogue is visible."""
    from lap_coach_logger.core.modes.widget_catalog import (
        _WIDGET_TO_CATEGORY,
        visible_widget_ids,
    )

    visible = set(visible_widget_ids(show_advanced=True))

    assert visible == set(_WIDGET_TO_CATEGORY.keys())
