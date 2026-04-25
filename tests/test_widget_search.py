"""T130: Widget search in the overlay manager.

Per spec — "Widget search in overlay manager ⇒ works". The
manager UI has a search box; users type a fragment and the
widget list filters to matches.

T130 ships the *search predicate* + a filter helper. T130's
manager UI consumes it; the QML side just plumbs a TextInput's
content into the helper.

Search rules:
- Case-insensitive substring match.
- Matches widget_id ("lap_delta") AND its display label
  ("Lap Delta") so users can search either form.
- Empty / whitespace query returns the unfiltered set
  (visible_widget_ids per T129's toggle gate).
- Search respects the show_advanced toggle — searching with
  the toggle off can never reveal Advanced/Streamer widgets.

The display label is derived the same way as T127's preset
labels (id title-cased with "_" + "-" → space) so the user's
"input bars" search lands on ``inputs`` and "stint timer" lands
on ``stint_timer``.
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# Search predicate
# ---------------------------------------------------------------------------


def test_search_matches_widget_id_substring() -> None:
    from lap_coach_logger.core.modes.widget_catalog import widget_matches_search

    assert widget_matches_search("lap_delta", "lap") is True


def test_search_matches_label_substring() -> None:
    """Users typing "Lap Delta" expect the corresponding widget
    to surface — the search has to look at the human-readable
    label, not just the snake_case id."""
    from lap_coach_logger.core.modes.widget_catalog import widget_matches_search

    # "lap_delta" → label "Lap Delta" → "Lap " is a substring
    assert widget_matches_search("lap_delta", "Lap ") is True


def test_search_is_case_insensitive() -> None:
    from lap_coach_logger.core.modes.widget_catalog import widget_matches_search

    assert widget_matches_search("lap_delta", "LAP") is True
    assert widget_matches_search("lap_delta", "lap") is True
    assert widget_matches_search("lap_delta", "Lap") is True


def test_empty_query_matches_every_widget() -> None:
    """Empty query = no filter. Manager UI shows everything in
    the unfiltered tier-gated set when the search box is blank."""
    from lap_coach_logger.core.modes.widget_catalog import widget_matches_search

    assert widget_matches_search("lap_delta", "") is True
    assert widget_matches_search("any_widget", "   ") is True  # whitespace = empty


def test_non_matching_query_returns_false() -> None:
    from lap_coach_logger.core.modes.widget_catalog import widget_matches_search

    assert widget_matches_search("lap_delta", "xyzzy") is False


def test_search_handles_underscores_and_hyphens_as_spaces() -> None:
    """A user typing "stint timer" (with a space) should match
    ``stint_timer`` (underscored). The label normalisation in
    T127 already swaps "_"/"-" for spaces; the search has to
    honour it."""
    from lap_coach_logger.core.modes.widget_catalog import widget_matches_search

    assert widget_matches_search("stint_timer", "stint timer") is True


# ---------------------------------------------------------------------------
# Filter helper: search_widgets(query, *, show_advanced)
# ---------------------------------------------------------------------------


def test_search_widgets_returns_only_matching_widgets() -> None:
    from lap_coach_logger.core.modes.widget_catalog import search_widgets

    results = set(search_widgets("tire", show_advanced=False))

    # tires + tire_life both match
    assert "tires" in results
    assert "tire_life" in results
    # everything else excluded
    assert "lap_delta" not in results
    assert "fuel" not in results


def test_search_widgets_respects_show_advanced_off() -> None:
    """Searching with the toggle off must never surface
    Advanced or Streamer widgets, even if they match the query.
    "g" matches "gap" (Race), "g_g" (Advanced), "gear"
    (Advanced) — toggle-off filters g_g + gear out."""
    from lap_coach_logger.core.modes.widget_catalog import search_widgets

    results = set(search_widgets("g", show_advanced=False))

    assert "gap" in results          # Race tier — visible
    assert "g_g" not in results      # Advanced tier — hidden
    assert "gear" not in results     # Advanced tier — hidden


def test_search_widgets_with_advanced_on_returns_advanced_matches() -> None:
    from lap_coach_logger.core.modes.widget_catalog import search_widgets

    results = set(search_widgets("g", show_advanced=True))

    assert "gap" in results
    assert "g_g" in results
    assert "gear" in results


def test_empty_query_returns_full_visible_set() -> None:
    """Same set as ``visible_widget_ids`` — empty query is the
    no-filter case."""
    from lap_coach_logger.core.modes.widget_catalog import (
        search_widgets,
        visible_widget_ids,
    )

    assert set(search_widgets("", show_advanced=False)) == set(
        visible_widget_ids(show_advanced=False)
    )
    assert set(search_widgets("", show_advanced=True)) == set(
        visible_widget_ids(show_advanced=True)
    )


def test_search_returns_empty_for_no_match() -> None:
    from lap_coach_logger.core.modes.widget_catalog import search_widgets

    assert search_widgets("xyzzy", show_advanced=True) == ()
