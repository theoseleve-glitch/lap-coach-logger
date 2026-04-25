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

from lap_coach_logger.core.modes.preset import ModeOverlayPreset


_SCHEMA_VERSION = 1


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


__all__ = ["export_preset_to_json", "export_preset_to_path"]
