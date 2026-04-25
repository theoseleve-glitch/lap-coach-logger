"""T132: Export overlay preset as JSON.

Per spec — "Export preset JSON ⇒ works". A user with a curated
preset wants to share it (Discord, GitHub, leagues) — JSON
export is the lowest-friction format.

T132 ships two layers:

1. ``export_preset_to_json(preset)`` — returns a pretty-printed
   JSON string, ready for clipboard/share.
2. ``export_preset_to_path(preset, path)`` — writes the JSON to
   a file (atomic write through ``Path.write_text``).

Round-trip with T121's ``ModeOverlayPreset.from_dict`` /
``to_dict`` is the contract: export a preset, parse the result,
get an equal preset back. T133's import path consumes the same
JSON shape — they're symmetric.

JSON adds a ``schema_version`` envelope (start at ``1``) so a
future format change can fall back gracefully on import — same
move as the bundle schema. The preset payload sits under a
``preset`` key alongside the version stamp.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# export_preset_to_json: returns a JSON string
# ---------------------------------------------------------------------------


def _make_preset():
    from lap_coach_logger.core.modes.preset import (
        ModeOverlayPreset,
        WidgetPlacement,
    )

    return ModeOverlayPreset(
        preset_id="my-custom",
        widgets=(
            WidgetPlacement("lap_delta", x=0.10, y=0.10, width=0.20, height=0.10),
            WidgetPlacement("fuel", x=0.40, y=0.05, width=0.15, height=0.08),
        ),
    )


def test_export_to_json_returns_a_string() -> None:
    from lap_coach_logger.core.modes.preset_io import export_preset_to_json

    output = export_preset_to_json(_make_preset())

    assert isinstance(output, str)
    assert output  # non-empty


def test_exported_json_is_valid_json() -> None:
    """Output must round-trip through json.loads — catches a
    serialiser that emits Python repr (single quotes etc.)
    instead of JSON."""
    from lap_coach_logger.core.modes.preset_io import export_preset_to_json

    output = export_preset_to_json(_make_preset())

    parsed = json.loads(output)
    assert isinstance(parsed, dict)


def test_exported_json_carries_a_schema_version() -> None:
    """Versioned envelope so T133's import can fall back when
    a future format change ships."""
    from lap_coach_logger.core.modes.preset_io import export_preset_to_json

    parsed = json.loads(export_preset_to_json(_make_preset()))

    assert parsed["schema_version"] == 1


def test_exported_json_carries_the_preset_payload() -> None:
    """The preset payload sits under ``preset`` so version stamp
    + preset stay separable. Catches a refactor that flattens
    the envelope and breaks T133's importer."""
    from lap_coach_logger.core.modes.preset_io import export_preset_to_json

    parsed = json.loads(export_preset_to_json(_make_preset()))

    assert parsed["preset"]["preset_id"] == "my-custom"
    assert len(parsed["preset"]["widgets"]) == 2


def test_exported_json_round_trips_via_preset_from_dict() -> None:
    """End-to-end: export a preset, parse the JSON, re-construct
    via ModeOverlayPreset.from_dict — equal preset back. This
    is the headline T132/T133 symmetry contract."""
    from lap_coach_logger.core.modes.preset import ModeOverlayPreset
    from lap_coach_logger.core.modes.preset_io import export_preset_to_json

    original = _make_preset()
    parsed = json.loads(export_preset_to_json(original))
    rehydrated = ModeOverlayPreset.from_dict(parsed["preset"])

    assert rehydrated == original


# ---------------------------------------------------------------------------
# export_preset_to_path: writes to a file
# ---------------------------------------------------------------------------


def test_export_to_path_creates_a_file(tmp_path: Path) -> None:
    from lap_coach_logger.core.modes.preset_io import export_preset_to_path

    target = tmp_path / "exported.preset.json"
    export_preset_to_path(_make_preset(), target)

    assert target.exists()


def test_export_to_path_writes_the_same_bytes_as_export_to_json(
    tmp_path: Path,
) -> None:
    """File content must match the in-memory string export —
    they're the same canonical form."""
    from lap_coach_logger.core.modes.preset_io import (
        export_preset_to_json,
        export_preset_to_path,
    )

    preset = _make_preset()
    target = tmp_path / "exported.preset.json"
    export_preset_to_path(preset, target)

    assert target.read_text(encoding="utf-8") == export_preset_to_json(preset)


def test_export_to_path_creates_parent_directory(tmp_path: Path) -> None:
    """Writing to ``tmp/sub/dir/preset.json`` should create the
    intermediate directories — saves the caller from doing
    ``parent.mkdir(parents=True, exist_ok=True)`` every time."""
    from lap_coach_logger.core.modes.preset_io import export_preset_to_path

    target = tmp_path / "nested" / "deeply" / "preset.json"
    export_preset_to_path(_make_preset(), target)

    assert target.exists()


def test_export_uses_utf8_encoding(tmp_path: Path) -> None:
    """JSON spec is UTF-8; pin the encoding so a future
    Windows-default-encoding regression (``cp1252``) doesn't
    silently corrupt non-ASCII preset_ids in the future."""
    from lap_coach_logger.core.modes.preset_io import export_preset_to_path

    # Construct a preset with a non-ASCII char in preset_id to flush
    # encoding bugs (no production preset uses non-ASCII today, but
    # the file format must support it).
    from lap_coach_logger.core.modes.preset import (
        ModeOverlayPreset,
        WidgetPlacement,
    )
    preset = ModeOverlayPreset(
        preset_id="café",
        widgets=(WidgetPlacement("lap_delta", 0, 0, 0.1, 0.1),),
    )

    target = tmp_path / "p.json"
    export_preset_to_path(preset, target)

    parsed = json.loads(target.read_text(encoding="utf-8"))
    assert parsed["preset"]["preset_id"] == "café"
