"""T131: Widget preview thumbnail in the overlay manager.

Per spec — "Widget preview thumbnail in manager ⇒ visible".
Each widget needs a visual hint the manager UI can render as a
thumbnail next to its label, so users browsing the picker get a
quick sense of what the widget shows without dragging it onto
the screen.

T131 ships the *data layer*: a per-widget glyph (BMP Unicode —
no emoji-font dependency, renders identically on every platform)
plus a tier-based color cue. The manager UI renders both as a
colored monogram badge — same trick the NavBar uses for the
brand mark, no PNG/SVG assets required.

Two layers under test:

1. ``widget_thumbnail_glyph(widget_id)`` — returns a single
   glyph per widget. Unknown widgets fall back to "•" so the
   manager UI never has to handle an empty cell.

2. ``widget_thumbnail_color_role(widget_id)`` — returns the
   Theme.Tokens role name (e.g., ``"pitOrange"``) keyed off
   the widget's category tier. Rooting the color in the tier
   means a future widget added to a category inherits the right
   colour automatically.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Glyph: every catalogued widget has a non-empty single-grapheme glyph
# ---------------------------------------------------------------------------


def test_glyph_helper_exists() -> None:
    from lap_coach_logger.core.modes.widget_catalog import (  # noqa: F401
        widget_thumbnail_glyph,
    )


def test_every_catalogued_widget_has_a_glyph() -> None:
    """Walk the live catalogue; each widget id must produce a
    non-empty glyph. Catches a refactor that adds a widget to
    the catalogue but forgets to map a glyph."""
    from lap_coach_logger.core.modes.widget_catalog import (
        _WIDGET_TO_CATEGORY,
        widget_thumbnail_glyph,
    )

    for wid in _WIDGET_TO_CATEGORY:
        glyph = widget_thumbnail_glyph(wid)
        assert glyph, f"empty glyph for widget {wid!r}"


def test_unknown_widget_returns_placeholder_glyph() -> None:
    """Unknown widget = fallback glyph. Manager UI never has to
    handle an empty cell."""
    from lap_coach_logger.core.modes.widget_catalog import (
        widget_thumbnail_glyph,
    )

    assert widget_thumbnail_glyph("not-a-real-widget") == "•"


# ---------------------------------------------------------------------------
# Glyphs are BMP-Unicode (no emoji-font dependency)
# ---------------------------------------------------------------------------


def test_glyphs_stay_in_basic_multilingual_plane() -> None:
    """Emoji code points (U+1F300+) require an emoji font that
    isn't guaranteed on Windows headless / CI builds. Restrict
    to the BMP (≤ U+FFFF) so glyphs render reliably with the
    default Theme.Typography font."""
    from lap_coach_logger.core.modes.widget_catalog import (
        _WIDGET_TO_CATEGORY,
        widget_thumbnail_glyph,
    )

    for wid in _WIDGET_TO_CATEGORY:
        glyph = widget_thumbnail_glyph(wid)
        for ch in glyph:
            assert ord(ch) <= 0xFFFF, (
                f"widget {wid!r} glyph {glyph!r} contains "
                f"non-BMP code point U+{ord(ch):04X}"
            )


# ---------------------------------------------------------------------------
# Color role keyed off the widget's tier (categories share a colour)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "widget_id",
    ["lap_delta", "fuel", "tires", "coach"],
)
def test_race_tier_widgets_share_a_color_role(widget_id: str) -> None:
    """Race-tier widgets all return the same color role —
    the tier defines the badge colour, so a future Race widget
    inherits it without per-widget bookkeeping."""
    from lap_coach_logger.core.modes.widget_catalog import (
        widget_thumbnail_color_role,
    )

    assert widget_thumbnail_color_role(widget_id) == widget_thumbnail_color_role("lap_delta")


def test_different_tiers_use_distinct_color_roles() -> None:
    """Tier colours must be visibly distinct — the whole point
    of the tier badge is glanceability. Pin all 5 tier colours
    pairwise-different."""
    from lap_coach_logger.core.modes.widget_catalog import (
        widget_thumbnail_color_role,
    )

    sample_per_tier = {
        "Race": "lap_delta",
        "Practice": "inputs",
        "Endurance": "stint_timer",
        "Streamer": "driver_name",
        "Advanced": "g_g",
    }
    roles = {
        tier: widget_thumbnail_color_role(wid)
        for tier, wid in sample_per_tier.items()
    }

    # All 5 must be distinct
    assert len(set(roles.values())) == 5, (
        f"colour-role collision across tiers: {roles}"
    )


def test_unknown_widget_color_role_is_a_safe_default() -> None:
    """Unknown widget falls back to a neutral role so the
    manager UI doesn't raise. Pin to a non-empty string —
    callers will pass it through to Theme.Tokens lookup."""
    from lap_coach_logger.core.modes.widget_catalog import (
        widget_thumbnail_color_role,
    )

    role = widget_thumbnail_color_role("not-a-real-widget")
    assert isinstance(role, str)
    assert role  # non-empty


# ---------------------------------------------------------------------------
# Specific glyph picks (sanity-check a few)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "widget_id, expected_glyph",
    [
        ("lap_delta", "Δ"),       # delta symbol
        ("position", "P"),         # P for position
        ("gear", "G"),             # G for gear
        ("track_map", "M"),        # M for map
    ],
)
def test_glyph_choice_is_descriptive(widget_id: str, expected_glyph: str) -> None:
    """Pin a few specific glyph choices so a refactor that
    swaps every glyph to the same character (or wildly mis-maps
    them) gets caught. These four are the most semantically
    obvious mappings — drift on these is almost certainly a bug."""
    from lap_coach_logger.core.modes.widget_catalog import (
        widget_thumbnail_glyph,
    )

    assert widget_thumbnail_glyph(widget_id) == expected_glyph
