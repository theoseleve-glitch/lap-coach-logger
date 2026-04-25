"""T122-T125: Built-in :class:`ModeOverlayPreset` instances.

Each Mode (T107-T110 — Practice / Sprint / Endurance / Review)
points at one of these via its ``overlay_preset_id`` attribute.
T122 ships the first instance (race-minimal); T123-T125 will
add Practice, Endurance, and Streamer variants.

Positions are normalised to ``0..1`` so the same preset works
across monitor resolutions — the renderer multiplies by the
target window size at draw time. T126+ will ship per-resolution
overrides + user customisation; T122 just pins the *default*
layout.

Lookup is by id (matches how ``Mode.overlay_preset_id`` resolves
at runtime); ``get_builtin_preset(<id>)`` returns ``None`` for
unknown ids so T123-T125 can land their own presets without
forcing this module to know about them upfront.
"""

from __future__ import annotations

from lap_coach_logger.core.modes.preset import (
    ModeOverlayPreset,
    WidgetPlacement,
)


# ---------------------------------------------------------------------------
# T122 — Race-minimal preset (SprintMode target)
# ---------------------------------------------------------------------------
# 8 core widgets per spec — sized + positioned so the racing line
# stays visible (no centre-screen widgets except the lap_delta
# strip + coaching card on the very edges of the canvas).
RACE_MINIMAL_PRESET: ModeOverlayPreset = ModeOverlayPreset(
    preset_id="race-minimal",
    widgets=(
        # Top-left cluster: tires + position (eyes flick here on straights)
        WidgetPlacement("tires", x=0.02, y=0.02, width=0.18, height=0.14),
        WidgetPlacement("position", x=0.02, y=0.18, width=0.10, height=0.06),
        # Top-centre: flags banner (yellows / blues / blacks)
        WidgetPlacement("flags", x=0.45, y=0.02, width=0.10, height=0.05),
        # Top-centre prominent: lap_delta (the headline pace number)
        WidgetPlacement("lap_delta", x=0.30, y=0.10, width=0.40, height=0.12),
        # Sector colour strip — under lap_delta, same horizontal span
        WidgetPlacement("sector_color", x=0.30, y=0.24, width=0.40, height=0.04),
        # Top-right cluster: fuel + gap (race-management view)
        WidgetPlacement("fuel", x=0.80, y=0.02, width=0.18, height=0.10),
        WidgetPlacement("gap", x=0.80, y=0.14, width=0.18, height=0.08),
        # Bottom: coaching card across the full width
        WidgetPlacement("coach", x=0.10, y=0.85, width=0.80, height=0.10),
    ),
)


_BUILTIN_PRESETS: dict[str, ModeOverlayPreset] = {
    p.preset_id: p
    for p in (RACE_MINIMAL_PRESET,)
}


def get_builtin_preset(preset_id: str) -> ModeOverlayPreset | None:
    """Look up a built-in preset by id. Returns ``None`` for
    unknown ids so callers (overlay binding, tests) can tell
    'no such preset' apart from 'preset exists but empty'."""
    return _BUILTIN_PRESETS.get(preset_id)


__all__ = ["RACE_MINIMAL_PRESET", "get_builtin_preset"]
