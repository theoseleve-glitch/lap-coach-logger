"""T121: Mode-driven overlay preset = list of widget ids + positions.

Block H (T121-T135) defines the four Mode-driven overlay presets
(race-minimal / practice / endurance / streamer). Before T122-T125
populate them, T121 ships the *data model*: a frozen dataclass
that just holds widget ids + positions, plus enough validation
to keep callers honest.

Distinct from :class:`overlays.models.OverlayPreset` (the
user-editable, slot/scope/filter-laden layout system) — this is
the *mode-driven* preset that the ``Mode.overlay_preset_id``
contract resolves at runtime. Different concerns, different
storage paths:

- ``overlays.models.OverlayPreset`` = user's saved layout, with
  filters and slot bindings. Lives in the per-user overlay store.
- ``core.modes.preset.ModeOverlayPreset`` (T121) = a Mode's
  static widget set, just ids + positions. Compiled into the
  desktop binary so Mode switches always have a target.

Position model: (x, y, width, height) as floats. T121 doesn't
prescribe units (normalised vs. pixels) — that's a runtime
concern; the model is dumb storage.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# WidgetPlacement: frozen dataclass holding one widget's position
# ---------------------------------------------------------------------------


def test_widget_placement_is_frozen() -> None:
    """Mode-driven presets must be immutable so the runtime
    can hash them, compare them, and share a single instance
    across consumers without defensive copies. Frozen
    dataclass is the cheapest path."""
    from dataclasses import FrozenInstanceError

    from lap_coach_logger.core.modes.preset import WidgetPlacement

    placement = WidgetPlacement(widget_id="lap_delta", x=0.05, y=0.05, width=0.20, height=0.10)

    with pytest.raises(FrozenInstanceError):
        placement.x = 0.15  # type: ignore[misc]


def test_widget_placement_holds_id_and_geometry() -> None:
    from lap_coach_logger.core.modes.preset import WidgetPlacement

    placement = WidgetPlacement(
        widget_id="fuel", x=0.10, y=0.20, width=0.15, height=0.08
    )

    assert placement.widget_id == "fuel"
    assert placement.x == 0.10
    assert placement.y == 0.20
    assert placement.width == 0.15
    assert placement.height == 0.08


# ---------------------------------------------------------------------------
# ModeOverlayPreset: frozen dataclass holding a list of placements
# ---------------------------------------------------------------------------


def test_preset_is_frozen() -> None:
    from dataclasses import FrozenInstanceError

    from lap_coach_logger.core.modes.preset import (
        ModeOverlayPreset,
        WidgetPlacement,
    )

    preset = ModeOverlayPreset(
        preset_id="race-minimal",
        widgets=(
            WidgetPlacement("lap_delta", 0.0, 0.0, 0.2, 0.1),
        ),
    )

    with pytest.raises(FrozenInstanceError):
        preset.preset_id = "endurance"  # type: ignore[misc]


def test_preset_widgets_is_a_tuple_for_immutability() -> None:
    """A list would let callers mutate after construction; a
    tuple keeps the preset truly immutable."""
    from lap_coach_logger.core.modes.preset import (
        ModeOverlayPreset,
        WidgetPlacement,
    )

    preset = ModeOverlayPreset(
        preset_id="race-minimal",
        widgets=(WidgetPlacement("lap_delta", 0.0, 0.0, 0.2, 0.1),),
    )

    assert isinstance(preset.widgets, tuple)


def test_empty_widgets_preset_is_valid() -> None:
    """A blank preset (no widgets) is a useful sentinel — e.g.,
    Review mode could surface an empty overlay set so the
    post-session UI isn't cluttered with live widgets that have
    nothing to render."""
    from lap_coach_logger.core.modes.preset import ModeOverlayPreset

    preset = ModeOverlayPreset(preset_id="blank", widgets=())

    assert preset.widgets == ()


# ---------------------------------------------------------------------------
# Duplicate widget ids are rejected (catches authoring mistakes)
# ---------------------------------------------------------------------------


def test_duplicate_widget_ids_raise_value_error() -> None:
    """Two placements with the same widget_id is almost always
    a copy-paste bug — the runtime would either render two
    instances or silently drop one. Fail fast at construction."""
    from lap_coach_logger.core.modes.preset import (
        ModeOverlayPreset,
        WidgetPlacement,
    )

    with pytest.raises(ValueError, match="duplicate widget"):
        ModeOverlayPreset(
            preset_id="bad",
            widgets=(
                WidgetPlacement("fuel", 0.0, 0.0, 0.1, 0.1),
                WidgetPlacement("fuel", 0.5, 0.5, 0.1, 0.1),
            ),
        )


# ---------------------------------------------------------------------------
# Round-trip serialisation (preset → dict → preset)
# ---------------------------------------------------------------------------


def test_to_dict_emits_preset_id_and_widget_list() -> None:
    """Persistence path needs the preset on a wire. Serialise
    to a flat JSON-friendly dict so future tooling (e.g., a
    'export your preset' UI) doesn't have to import dataclass
    machinery."""
    from lap_coach_logger.core.modes.preset import (
        ModeOverlayPreset,
        WidgetPlacement,
    )

    preset = ModeOverlayPreset(
        preset_id="race-minimal",
        widgets=(
            WidgetPlacement("lap_delta", 0.05, 0.05, 0.20, 0.10),
            WidgetPlacement("fuel", 0.05, 0.20, 0.20, 0.10),
        ),
    )

    payload = preset.to_dict()

    assert payload == {
        "preset_id": "race-minimal",
        "widgets": [
            {"widget_id": "lap_delta", "x": 0.05, "y": 0.05, "width": 0.20, "height": 0.10},
            {"widget_id": "fuel", "x": 0.05, "y": 0.20, "width": 0.20, "height": 0.10},
        ],
    }


def test_from_dict_reconstructs_an_equal_preset() -> None:
    """Round-trip: a serialised preset rehydrates into an equal
    object so the persistence path is loss-free."""
    from lap_coach_logger.core.modes.preset import (
        ModeOverlayPreset,
        WidgetPlacement,
    )

    original = ModeOverlayPreset(
        preset_id="endurance",
        widgets=(
            WidgetPlacement("stint_timer", 0.10, 0.10, 0.25, 0.12),
            WidgetPlacement("tire_life", 0.40, 0.10, 0.20, 0.10),
        ),
    )

    rehydrated = ModeOverlayPreset.from_dict(original.to_dict())

    assert rehydrated == original


def test_from_dict_handles_missing_widgets_key_as_empty() -> None:
    """A persisted blank preset (or a future minor schema where
    'widgets' is optional) must round-trip cleanly. Catches a
    refactor that would force every payload to include the key."""
    from lap_coach_logger.core.modes.preset import ModeOverlayPreset

    rehydrated = ModeOverlayPreset.from_dict({"preset_id": "blank"})

    assert rehydrated.preset_id == "blank"
    assert rehydrated.widgets == ()


# ---------------------------------------------------------------------------
# Lookup helper: find a placement by widget id
# ---------------------------------------------------------------------------


def test_get_placement_returns_the_matching_widget_placement() -> None:
    """Runtime callers (overlay renderer, tests) regularly need
    'where does widget X go?' The dataclass exposes that as a
    helper so callers don't have to write the loop."""
    from lap_coach_logger.core.modes.preset import (
        ModeOverlayPreset,
        WidgetPlacement,
    )

    fuel = WidgetPlacement("fuel", 0.10, 0.20, 0.15, 0.08)
    preset = ModeOverlayPreset(
        preset_id="race-minimal",
        widgets=(WidgetPlacement("lap_delta", 0.0, 0.0, 0.2, 0.1), fuel),
    )

    assert preset.get_placement("fuel") is fuel


def test_get_placement_returns_none_when_missing() -> None:
    """Looking up a widget that isn't in this preset returns
    None — caller decides how to handle it. Raising would
    couple every consumer to try/except for a perfectly
    legitimate query (e.g., 'does this preset have a tire_life
    widget?')."""
    from lap_coach_logger.core.modes.preset import (
        ModeOverlayPreset,
        WidgetPlacement,
    )

    preset = ModeOverlayPreset(
        preset_id="race-minimal",
        widgets=(WidgetPlacement("lap_delta", 0.0, 0.0, 0.2, 0.1),),
    )

    assert preset.get_placement("not_present") is None
