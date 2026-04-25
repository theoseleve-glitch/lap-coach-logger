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


# ---------------------------------------------------------------------------
# T129 — "Show advanced" toggle gates Streamer + Advanced tiers
# ---------------------------------------------------------------------------
# Both tiers gate behind the same toggle (despite the spec calling it
# only "Streamer"): Advanced widgets clutter the picker for newcomers
# the same way Streamer widgets do, and the manager UI doesn't need a
# second sub-toggle. A user who unhides advanced gets both at once.
_HIDDEN_BY_DEFAULT_CATEGORIES: frozenset[str] = frozenset({"Streamer", "Advanced"})


def is_hidden_by_default(widget_id: str) -> bool:
    """True iff ``widget_id`` is gated behind the "Show advanced"
    toggle. Unknown widgets are treated as hidden — forces a
    catalogue update before a new widget surfaces in the UI
    (safer to under-show than over-show)."""
    category = _WIDGET_TO_CATEGORY.get(widget_id)
    if category is None:
        return True
    return category in _HIDDEN_BY_DEFAULT_CATEGORIES


def visible_widget_ids(*, show_advanced: bool) -> tuple[str, ...]:
    """Return every widget id the overlay manager should render
    given the current toggle state. ``show_advanced=False`` (the
    default) excludes Streamer + Advanced; ``True`` reveals
    everything in the catalogue."""
    if show_advanced:
        return tuple(_WIDGET_TO_CATEGORY.keys())
    return tuple(
        wid for wid in _WIDGET_TO_CATEGORY
        if not is_hidden_by_default(wid)
    )


# ---------------------------------------------------------------------------
# T130 — Widget search in the overlay manager
# ---------------------------------------------------------------------------


def _widget_label(widget_id: str) -> str:
    """Display label for ``widget_id`` — matches T127's preset
    label normalisation (snake/hyphen → spaces, title case)."""
    return widget_id.replace("_", " ").replace("-", " ").title()


def widget_matches_search(widget_id: str, query: str) -> bool:
    """Case-insensitive substring match against the widget id
    AND its display label. Empty / whitespace queries match
    everything (the no-filter case)."""
    needle = query.strip().lower()
    if not needle:
        return True
    haystack_id = widget_id.lower()
    haystack_label = _widget_label(widget_id).lower()
    return needle in haystack_id or needle in haystack_label


def search_widgets(query: str, *, show_advanced: bool) -> tuple[str, ...]:
    """Filter the visible widget set (per T129's toggle gate)
    down to ones matching ``query``. Empty query returns the
    full visible set."""
    return tuple(
        wid for wid in visible_widget_ids(show_advanced=show_advanced)
        if widget_matches_search(wid, query)
    )


# ---------------------------------------------------------------------------
# T131 — Per-widget thumbnail glyph + tier-keyed color role
# ---------------------------------------------------------------------------
# Glyphs stay in the BMP (≤ U+FFFF) so they render with the default
# Theme.Typography font — emoji require a font that isn't guaranteed
# on Windows headless / CI builds. The manager UI renders glyph in a
# Theme.Tokens-coloured rectangle, same trick the NavBar brand mark uses.
_WIDGET_GLYPHS: dict[str, str] = {
    # Race tier
    "lap_delta": "Δ",
    "fuel": "F",
    "tires": "○",
    "coach": "C",
    "position": "P",
    "flags": "⚑",
    "sector_color": "▮",
    "gap": "↔",
    # Practice tier
    "inputs": "I",
    "pedal_trace": "≈",
    # Endurance tier
    "stint_timer": "⏱",
    "tire_life": "T",
    "long_run_pace": "~",
    # Streamer tier
    "driver_name": "@",
    "session_clock": "⌚",
    "weather": "☀",
    "track_map": "M",
    # Advanced tier
    "g_g": "✚",
    "live_trace": "↯",
    "gear": "G",
    "speedometer": "S",
}

_GLYPH_FALLBACK = "•"


# Tier → Theme.Tokens role name. Five distinct colour roles so the
# tier badge stays glanceable across the manager UI.
_TIER_TO_COLOR_ROLE: dict[str, str] = {
    "Race": "pitOrange",
    "Practice": "acidGreen",
    "Endurance": "racingPurple",
    "Streamer": "chalk",
    "Advanced": "steel",
}

_COLOR_ROLE_FALLBACK = "steel"


def widget_thumbnail_glyph(widget_id: str) -> str:
    """One-grapheme glyph the manager UI renders as a thumbnail.
    Unknown widgets fall back to a placeholder so the picker
    never has to handle an empty cell."""
    return _WIDGET_GLYPHS.get(widget_id, _GLYPH_FALLBACK)


def widget_thumbnail_color_role(widget_id: str) -> str:
    """Theme.Tokens role for the widget's tier badge. Same role
    is returned for every widget in a tier — adding a future
    widget inherits the colour automatically."""
    category = _WIDGET_TO_CATEGORY.get(widget_id)
    if category is None:
        return _COLOR_ROLE_FALLBACK
    return _TIER_TO_COLOR_ROLE.get(category, _COLOR_ROLE_FALLBACK)


__all__ = [
    "WIDGET_CATEGORIES",
    "get_widget_category",
    "is_hidden_by_default",
    "search_widgets",
    "visible_widget_ids",
    "widget_matches_search",
    "widget_thumbnail_color_role",
    "widget_thumbnail_glyph",
    "widgets_in_category",
]
