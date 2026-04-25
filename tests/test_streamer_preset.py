"""T125: ``streamer`` overlay preset definition.

Per spec: "separate from above, 15 widgets". Unlike T122-T124
(which back the four built-in modes Practice / Sprint / Endurance
/ Review), the streamer preset is *not* tied to a Mode — it's
opt-in for content creators broadcasting their session and
favours a viewer-friendly layout over driver ergonomics.

15 widgets covering both telemetry and broadcast context:

Driver telemetry (visual interest for viewers):
- ``lap_delta``     — pace headline
- ``position``      — race position
- ``gap``           — gap to ahead/behind
- ``fuel``          — fuel level
- ``tires``         — tire temps
- ``flags``         — yellows / blues / blacks
- ``coach``         — coaching tip currently shown to driver
                      (viewers find this engaging)
- ``sector_color``  — sector pace marker
- ``inputs``        — steering / throttle / brake bars
                      (visually engaging during onboard streams)
- ``speedometer``   — current speed (driver-facing dashboards
                      already show this; streamer preset re-adds
                      it because OBS overlay viewers don't see
                      the in-game HUD)
- ``gear``          — current gear

Broadcast context (no driver value, viewer-only):
- ``driver_name``   — driver / team identity for stream branding
- ``session_clock`` — race clock for context
- ``track_map``     — minimap of position on track
- ``weather``       — track / air temp + precipitation

15 widgets total. preset_id="streamer" — *no Mode points to it*,
which T125 pins explicitly (catches a future regression that
silently ties Streamer to one of the existing modes).
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Module export + Mode independence
# ---------------------------------------------------------------------------


def test_streamer_preset_is_exposed_as_module_constant() -> None:
    from lap_coach_logger.core.modes import builtin_presets

    assert hasattr(builtin_presets, "STREAMER_PRESET")


def test_streamer_preset_id_is_streamer() -> None:
    from lap_coach_logger.core.modes.builtin_presets import STREAMER_PRESET

    assert STREAMER_PRESET.preset_id == "streamer"


def test_no_built_in_mode_targets_streamer_preset() -> None:
    """Per spec — Streamer is "separate from above" (the four
    Mode-driven presets). No built-in Mode (Practice / Sprint /
    Endurance / Review) should declare ``streamer`` as its
    overlay_preset_id; if any do, the spec line is violated.
    Pin it so a future regression that wires SprintMode →
    streamer doesn't slip through silently."""
    from lap_coach_logger.core.modes.engine import ModeEngine

    engine = ModeEngine()
    for mode in engine.available_modes:
        assert mode.overlay_preset_id != "streamer", (
            f"{type(mode).__name__} unexpectedly targets the streamer preset"
        )


# ---------------------------------------------------------------------------
# Streamer-specific widget set
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "widget_id",
    [
        # Driver-telemetry visible-to-viewer set
        "lap_delta",
        "position",
        "gap",
        "fuel",
        "tires",
        "flags",
        "coach",
        "sector_color",
        "inputs",
        "speedometer",
        "gear",
        # Broadcast-only widgets (no driver value)
        "driver_name",
        "session_clock",
        "track_map",
        "weather",
    ],
)
def test_streamer_includes_widget(widget_id: str) -> None:
    """Pin every spec'd widget individually — failure message
    points straight at the missing widget if a refactor drops
    one. Catches a copy-paste mistake that would, say, ship
    Streamer with no driver_name (breaking stream branding)."""
    from lap_coach_logger.core.modes.builtin_presets import STREAMER_PRESET

    assert STREAMER_PRESET.get_placement(widget_id) is not None


# ---------------------------------------------------------------------------
# Total count = 15 (per spec)
# ---------------------------------------------------------------------------


def test_streamer_widget_count_is_fifteen() -> None:
    """Spec says exactly 15. A creep upward bloats the broadcast
    overlay; a drop means we're missing a documented widget.
    Pin the count exactly."""
    from lap_coach_logger.core.modes.builtin_presets import STREAMER_PRESET

    assert len(STREAMER_PRESET.widgets) == 15


# ---------------------------------------------------------------------------
# Positions stay in normalised range
# ---------------------------------------------------------------------------


def test_every_streamer_widget_position_is_in_normalised_range() -> None:
    from lap_coach_logger.core.modes.builtin_presets import STREAMER_PRESET

    for w in STREAMER_PRESET.widgets:
        assert 0.0 <= w.x <= 1.0, f"{w.widget_id} x={w.x} out of range"
        assert 0.0 <= w.y <= 1.0, f"{w.widget_id} y={w.y} out of range"
        assert 0.0 < w.width <= 1.0, f"{w.widget_id} width={w.width} out of range"
        assert 0.0 < w.height <= 1.0, f"{w.widget_id} height={w.height} out of range"
        assert w.x + w.width <= 1.0, f"{w.widget_id} extends past right edge"
        assert w.y + w.height <= 1.0, f"{w.widget_id} extends past bottom edge"


# ---------------------------------------------------------------------------
# Lookup helper picks up the new preset
# ---------------------------------------------------------------------------


def test_get_builtin_preset_returns_streamer_by_id() -> None:
    from lap_coach_logger.core.modes.builtin_presets import (
        STREAMER_PRESET,
        get_builtin_preset,
    )

    assert get_builtin_preset("streamer") is STREAMER_PRESET


def test_lookup_still_returns_earlier_presets_after_streamer_added() -> None:
    """Regression check — T122-T124 lookups still work after
    T125 extends the registry."""
    from lap_coach_logger.core.modes.builtin_presets import (
        ENDURANCE_PRESET,
        PRACTICE_PRESET,
        RACE_MINIMAL_PRESET,
        get_builtin_preset,
    )

    assert get_builtin_preset("race-minimal") is RACE_MINIMAL_PRESET
    assert get_builtin_preset("practice") is PRACTICE_PRESET
    assert get_builtin_preset("endurance") is ENDURANCE_PRESET
