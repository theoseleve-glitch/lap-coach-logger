"""T134: Preset versioning — every preset carries a ``version``
counter that increments on edits.

Distinct from T132/T133's ``schema_version`` envelope (the wire
format). This is a *content* version: same preset_id, different
versions = different layouts. Use cases:

- Detect when a user's local preset has drifted from the
  exported copy they shared with their league.
- Preserve edit history for the future ``preset history`` UI.
- Conflict resolution: if a sync system later compares
  versions across devices, the higher number wins.

T134 ships:

1. ``ModeOverlayPreset.version`` — defaults to ``1``.
2. ``to_dict`` / ``from_dict`` round-trip the version.
3. ``preset.bumped()`` — return a copy with version + 1.

Built-in presets keep version = 1 (no edits yet).
"""
from __future__ import annotations


# ---------------------------------------------------------------------------
# version field on the dataclass
# ---------------------------------------------------------------------------


def test_preset_has_a_version_field_defaulting_to_one() -> None:
    """Default version=1 means ""this is the first published
    iteration"". Built-in presets ship at this baseline."""
    from lap_coach_logger.core.modes.preset import ModeOverlayPreset

    preset = ModeOverlayPreset(preset_id="x", widgets=())

    assert preset.version == 1


def test_preset_version_is_settable_at_construction() -> None:
    """Imported presets carry their own version through the
    constructor."""
    from lap_coach_logger.core.modes.preset import ModeOverlayPreset

    preset = ModeOverlayPreset(preset_id="x", widgets=(), version=7)

    assert preset.version == 7


def test_preset_version_is_immutable() -> None:
    """Frozen dataclass means version can't be mutated post-
    construction. Bumping returns a new preset."""
    import pytest
    from dataclasses import FrozenInstanceError

    from lap_coach_logger.core.modes.preset import ModeOverlayPreset

    preset = ModeOverlayPreset(preset_id="x", widgets=())

    with pytest.raises(FrozenInstanceError):
        preset.version = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Serialisation round-trip
# ---------------------------------------------------------------------------


def test_to_dict_emits_version() -> None:
    from lap_coach_logger.core.modes.preset import ModeOverlayPreset

    preset = ModeOverlayPreset(preset_id="x", widgets=(), version=5)

    payload = preset.to_dict()

    assert payload["version"] == 5


def test_from_dict_reads_version() -> None:
    from lap_coach_logger.core.modes.preset import ModeOverlayPreset

    rehydrated = ModeOverlayPreset.from_dict(
        {"preset_id": "x", "widgets": [], "version": 12}
    )

    assert rehydrated.version == 12


def test_from_dict_defaults_version_to_one_when_missing() -> None:
    """Pre-T134 JSON files (or hand-edited payloads) lack the
    version key — they're assumed to be version 1, not rejected."""
    from lap_coach_logger.core.modes.preset import ModeOverlayPreset

    rehydrated = ModeOverlayPreset.from_dict(
        {"preset_id": "x", "widgets": []}  # no "version"
    )

    assert rehydrated.version == 1


def test_round_trip_through_to_dict_preserves_version() -> None:
    from lap_coach_logger.core.modes.preset import ModeOverlayPreset

    original = ModeOverlayPreset(preset_id="x", widgets=(), version=42)

    rehydrated = ModeOverlayPreset.from_dict(original.to_dict())

    assert rehydrated == original
    assert rehydrated.version == 42


# ---------------------------------------------------------------------------
# bumped() helper
# ---------------------------------------------------------------------------


def test_bumped_returns_new_preset_with_version_plus_one() -> None:
    """The canonical "user edited a preset" flow — bumped() is
    called after every save so the version monotonically
    increases as the user evolves their layout."""
    from lap_coach_logger.core.modes.preset import (
        ModeOverlayPreset,
        WidgetPlacement,
    )

    original = ModeOverlayPreset(
        preset_id="x",
        widgets=(WidgetPlacement("lap_delta", 0, 0, 0.1, 0.1),),
        version=3,
    )

    bumped = original.bumped()

    assert bumped.version == 4


def test_bumped_preserves_preset_id_and_widgets() -> None:
    """Only the version changes — the rest of the preset is
    identical so the user's edit doesn't lose layout state."""
    from lap_coach_logger.core.modes.preset import (
        ModeOverlayPreset,
        WidgetPlacement,
    )

    original = ModeOverlayPreset(
        preset_id="my-preset",
        widgets=(WidgetPlacement("fuel", 0.1, 0.1, 0.2, 0.1),),
        version=1,
    )

    bumped = original.bumped()

    assert bumped.preset_id == original.preset_id
    assert bumped.widgets == original.widgets


def test_bumped_does_not_mutate_original() -> None:
    """Frozen dataclass guarantees this, but pin it explicitly
    so a future refactor that drops ``frozen=True`` gets caught
    here too."""
    from lap_coach_logger.core.modes.preset import ModeOverlayPreset

    original = ModeOverlayPreset(preset_id="x", widgets=(), version=1)
    _ = original.bumped()

    assert original.version == 1


# ---------------------------------------------------------------------------
# Built-in presets ship at version 1
# ---------------------------------------------------------------------------


def test_all_built_in_presets_ship_at_version_one() -> None:
    """No hand-edits at first install ⇒ the four built-in
    presets baseline at version 1. A user importing one of them
    can compare against this baseline to detect drift."""
    from lap_coach_logger.core.modes.builtin_presets import _BUILTIN_PRESETS

    for preset in _BUILTIN_PRESETS.values():
        assert preset.version == 1, (
            f"built-in preset {preset.preset_id!r} version is "
            f"{preset.version}, expected 1"
        )


# ---------------------------------------------------------------------------
# Export / import path round-trips version too
# ---------------------------------------------------------------------------


def test_export_import_round_trip_preserves_version() -> None:
    """End-to-end: T132 → T133 must keep the version intact, or
    a user sharing v5 of their preset would silently land at v1
    on the receiver's machine."""
    from lap_coach_logger.core.modes.preset import (
        ModeOverlayPreset,
        WidgetPlacement,
    )
    from lap_coach_logger.core.modes.preset_io import (
        export_preset_to_json,
        import_preset_from_json,
    )

    original = ModeOverlayPreset(
        preset_id="shared",
        widgets=(WidgetPlacement("lap_delta", 0, 0, 0.1, 0.1),),
        version=8,
    )

    rehydrated = import_preset_from_json(export_preset_to_json(original))

    assert rehydrated.version == 8
    assert rehydrated == original
