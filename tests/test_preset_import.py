"""T133: Import overlay preset from JSON.

Symmetric to T132's export. Takes a JSON string (or file path)
shaped per the T132 envelope::

    {"schema_version": 1, "preset": {...}}

Returns a :class:`ModeOverlayPreset` if the payload is valid;
raises ``PresetImportError`` (a ``ValueError`` subclass) with
a clear message otherwise. Bad inputs we have to reject:

- Missing / wrong schema_version (future formats fall back here)
- Missing ``preset`` key
- Missing required preset fields (preset_id, widgets)
- Duplicate widget ids (T121 catches this in __post_init__)
- Out-of-range positions (delegated to caller validation —
  T133 doesn't second-guess the renderer's geometry)

Round-trip with T132 is the headline contract: export then
import yields an equal preset.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Round-trip with T132's export
# ---------------------------------------------------------------------------


def _make_preset():
    from lap_coach_logger.core.modes.preset import (
        ModeOverlayPreset,
        WidgetPlacement,
    )

    return ModeOverlayPreset(
        preset_id="my-shared",
        widgets=(
            WidgetPlacement("lap_delta", x=0.10, y=0.10, width=0.20, height=0.10),
            WidgetPlacement("fuel", x=0.40, y=0.05, width=0.15, height=0.08),
        ),
    )


def test_import_roundtrips_through_export() -> None:
    """T132 → T133 yields an equal preset. This is the headline
    symmetry contract — it's why T132's envelope and T133's
    parser have to agree on every field."""
    from lap_coach_logger.core.modes.preset_io import (
        export_preset_to_json,
        import_preset_from_json,
    )

    original = _make_preset()
    rehydrated = import_preset_from_json(export_preset_to_json(original))

    assert rehydrated == original


# ---------------------------------------------------------------------------
# Schema version gate
# ---------------------------------------------------------------------------


def test_missing_schema_version_raises() -> None:
    """A JSON without the version stamp is either malformed or
    a pre-T132 file (which never existed). Reject with a clear
    message rather than guessing."""
    from lap_coach_logger.core.modes.preset_io import (
        PresetImportError,
        import_preset_from_json,
    )

    payload = json.dumps({"preset": {"preset_id": "x", "widgets": []}})

    with pytest.raises(PresetImportError, match="schema_version"):
        import_preset_from_json(payload)


def test_unknown_schema_version_raises() -> None:
    """Future format = newer desktop wrote it. Refuse gracefully
    rather than risk mis-parsing a partially-recognised payload."""
    from lap_coach_logger.core.modes.preset_io import (
        PresetImportError,
        import_preset_from_json,
    )

    payload = json.dumps({
        "schema_version": 99,
        "preset": {"preset_id": "x", "widgets": []},
    })

    with pytest.raises(PresetImportError, match="schema_version"):
        import_preset_from_json(payload)


# ---------------------------------------------------------------------------
# Payload structure
# ---------------------------------------------------------------------------


def test_missing_preset_key_raises() -> None:
    from lap_coach_logger.core.modes.preset_io import (
        PresetImportError,
        import_preset_from_json,
    )

    payload = json.dumps({"schema_version": 1})  # no "preset"

    with pytest.raises(PresetImportError, match="preset"):
        import_preset_from_json(payload)


def test_invalid_json_raises() -> None:
    """A truncated / hand-edited file is the most likely failure
    mode in production — caller probably copied half a JSON
    blob into Discord. Surface a clean error, don't crash with
    json.JSONDecodeError leaking through."""
    from lap_coach_logger.core.modes.preset_io import (
        PresetImportError,
        import_preset_from_json,
    )

    with pytest.raises(PresetImportError):
        import_preset_from_json("{ this is not valid")


def test_top_level_non_dict_raises() -> None:
    """A JSON list / string at the top level is not a preset.
    Catches a pasted widget array fragment that happens to
    parse but isn't a preset envelope."""
    from lap_coach_logger.core.modes.preset_io import (
        PresetImportError,
        import_preset_from_json,
    )

    with pytest.raises(PresetImportError):
        import_preset_from_json(json.dumps(["not", "a", "preset"]))


# ---------------------------------------------------------------------------
# Path helper
# ---------------------------------------------------------------------------


def test_import_from_path_round_trips_an_exported_file(tmp_path: Path) -> None:
    """End-to-end via filesystem: T132 writes a file, T133 reads
    it back to an equal preset. This is the canonical "user
    shared a .preset.json" flow."""
    from lap_coach_logger.core.modes.preset_io import (
        export_preset_to_path,
        import_preset_from_path,
    )

    target = tmp_path / "shared.preset.json"
    original = _make_preset()
    export_preset_to_path(original, target)

    assert import_preset_from_path(target) == original


def test_import_from_missing_path_raises() -> None:
    from lap_coach_logger.core.modes.preset_io import (
        PresetImportError,
        import_preset_from_path,
    )

    with pytest.raises(PresetImportError):
        import_preset_from_path(Path("does-not-exist.preset.json"))


# ---------------------------------------------------------------------------
# Preset-validation errors propagate
# ---------------------------------------------------------------------------


def test_duplicate_widget_ids_raise_via_preset_validation() -> None:
    """T121's ModeOverlayPreset.__post_init__ rejects duplicate
    widget_ids. T133 must let that exception propagate (wrapped
    as PresetImportError) so the user sees a clear "this preset
    is malformed" message rather than a stack trace through the
    importer."""
    from lap_coach_logger.core.modes.preset_io import (
        PresetImportError,
        import_preset_from_json,
    )

    payload = json.dumps({
        "schema_version": 1,
        "preset": {
            "preset_id": "bad",
            "widgets": [
                {"widget_id": "fuel", "x": 0, "y": 0, "width": 0.1, "height": 0.1},
                {"widget_id": "fuel", "x": 0.5, "y": 0.5, "width": 0.1, "height": 0.1},
            ],
        },
    })

    with pytest.raises(PresetImportError, match="duplicate"):
        import_preset_from_json(payload)
