"""T128: Widget categorisation — every widget tagged with one tier.

Per spec, the five tiers are:

- **Race**      — race-minimal core (T122 8 widgets)
- **Practice**  — technique-tuning additions
- **Endurance** — stint-management additions
- **Streamer**  — broadcast-only widgets
- **Advanced** — power-user telemetry hidden behind the
                 T129 "Show advanced" toggle

Categories follow widget *introduction*, not preset membership:
``lap_delta`` is tagged Race even though it appears in Practice
and Endurance presets too — the introduction tier identifies
which mode the widget primarily serves.

The split between Practice and Advanced (within the T123
preset additions) is deliberate: ``inputs`` and ``pedal_trace``
are everyday practice tools; ``g_g`` and ``live_trace`` are
power-user views best discovered via the advanced toggle.
"""

from __future__ import annotations


WIDGET_CATEGORIES: tuple[str, ...] = (
    "Race",
    "Practice",
    "Endurance",
    "Streamer",
    "Advanced",
)


_WIDGET_TO_CATEGORY: dict[str, str] = {
    # Race — race-minimal core (T122)
    "lap_delta": "Race",
    "fuel": "Race",
    "tires": "Race",
    "coach": "Race",
    "position": "Race",
    "flags": "Race",
    "sector_color": "Race",
    "gap": "Race",
    # Practice — technique snapshot/history
    "inputs": "Practice",
    "pedal_trace": "Practice",
    # Endurance — stint management
    "stint_timer": "Endurance",
    "tire_life": "Endurance",
    "long_run_pace": "Endurance",
    # Streamer — broadcast-only context
    "driver_name": "Streamer",
    "session_clock": "Streamer",
    "weather": "Streamer",
    "track_map": "Streamer",
    # Advanced — power-user telemetry
    "g_g": "Advanced",
    "live_trace": "Advanced",
    "gear": "Advanced",
    "speedometer": "Advanced",
}


def get_widget_category(widget_id: str) -> str | None:
    """Return the tier for ``widget_id`` or ``None`` if unknown.

    Defensive shape matches ``get_builtin_preset`` / ``get_placement``
    — callers decide how to handle missing widgets rather than
    being forced into try/except."""
    return _WIDGET_TO_CATEGORY.get(widget_id)


def widgets_in_category(category: str) -> tuple[str, ...]:
    """Reverse lookup: every widget id tagged with ``category``.
    Returns an empty tuple for unknown categories."""
    return tuple(
        wid for wid, cat in _WIDGET_TO_CATEGORY.items() if cat == category
    )


__all__ = [
    "WIDGET_CATEGORIES",
    "get_widget_category",
    "widgets_in_category",
]
