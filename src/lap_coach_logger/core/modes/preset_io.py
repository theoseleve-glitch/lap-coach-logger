"""T132 / T133: Preset JSON export / import.

T132 ships export; T133 ships import. They're symmetric — JSON
shape exported by T132 round-trips through T133 to an equal
:class:`ModeOverlayPreset`.

Wire format (envelope + payload):

    {
      "schema_version": 1,
      "preset": {
        "preset_id": "...",
        "widgets": [...]
      }
    }

The version stamp lets T133 fall back gracefully on a future
format change (same move as the bundle schema). Keeping
preset payload + version separable means a future migration
can transform the payload without rewriting the envelope.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lap_coach_logger.core.modes.preset import ModeOverlayPreset


_SCHEMA_VERSION = 1


class PresetImportError(ValueError):
    """Raised when a JSON payload can't be parsed as a preset.

    ValueError-derived so existing ``except ValueError`` paths
    still trip; the typed subclass lets new code distinguish
    preset-import failures from generic parse errors."""


def export_preset_to_json(preset: ModeOverlayPreset) -> str:
    """Return the preset as a JSON string — pretty-printed for
    human readability when shared via clipboard / GitHub gist /
    Discord."""
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "preset": preset.to_dict(),
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def export_preset_to_path(preset: ModeOverlayPreset, path: Path) -> None:
    """Write the preset JSON to ``path``. Creates parent
    directories automatically — saves callers a
    ``parent.mkdir(parents=True, exist_ok=True)`` every time.
    UTF-8 encoded so non-ASCII preset_ids survive the round-trip."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(export_preset_to_json(preset), encoding="utf-8")


def import_preset_from_json(text: str) -> ModeOverlayPreset:
    """Parse ``text`` as a preset JSON envelope and return the
    rehydrated :class:`ModeOverlayPreset`.

    Raises :class:`PresetImportError` (a ``ValueError`` subclass)
    on any malformed input — invalid JSON, missing/unknown
    schema_version, missing preset payload, or downstream
    validation errors from ``ModeOverlayPreset.__post_init__``
    (e.g., duplicate widget ids)."""
    try:
        parsed: Any = json.loads(text)
    except json.JSONDecodeError as exc:
        raise PresetImportError(f"invalid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise PresetImportError(
            f"expected a JSON object at the top level, got {type(parsed).__name__}"
        )

    version = parsed.get("schema_version")
    if version != _SCHEMA_VERSION:
        raise PresetImportError(
            f"unsupported schema_version {version!r} "
            f"(expected {_SCHEMA_VERSION})"
        )

    preset_payload = parsed.get("preset")
    if not isinstance(preset_payload, dict):
        raise PresetImportError(
            "missing or malformed `preset` payload in import envelope"
        )

    try:
        return ModeOverlayPreset.from_dict(preset_payload)
    except (KeyError, ValueError, TypeError) as exc:
        raise PresetImportError(f"preset validation failed: {exc}") from exc


def import_preset_from_path(path: Path) -> ModeOverlayPreset:
    """Read ``path`` as UTF-8 and parse via
    :func:`import_preset_from_json`. ``PresetImportError`` if
    the file is missing or unreadable."""
    try:
        text = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError) as exc:
        raise PresetImportError(f"can't read preset file {path}: {exc}") from exc
    return import_preset_from_json(text)


__all__ = [
    "PresetImportError",
    "export_preset_to_json",
    "export_preset_to_path",
    "import_preset_from_json",
    "import_preset_from_path",
]
