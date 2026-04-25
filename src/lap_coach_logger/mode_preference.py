"""T117: Persistence for the user's chosen mode.

File-backed JSON store mirroring :class:`AccountRegistry` (T053):
the file lives under ``config_dir()`` in production, but the
constructor takes an explicit ``state_path`` so tests can keep
it hermetic. Corrupt / unreadable / wrong-shape payloads are
treated as cold start — losing the prefs file is a UX hiccup,
not a crash.

Persistence shape::

    {"mode": "endurance"}

Validation lives in the *caller* (ModeViewModel). The store is
deliberately schema-agnostic so it doesn't have to grow a
hard-coded MODES table — that would couple this module to
``core/mode_detector`` and force this file to evolve every time
a mode is added.
"""

from __future__ import annotations

import json
from pathlib import Path


class ModePreferenceStore:
    """File-backed mode-id store. Tiny — just ``load()`` and ``save(mode)``."""

    def __init__(self, *, state_path: Path) -> None:
        self._state_path = state_path

    def load(self) -> str | None:
        """Return the persisted mode id or ``None`` for cold start."""
        if not self._state_path.exists():
            return None
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            return None
        if not isinstance(payload, dict):
            return None
        mode = payload.get("mode")
        if not isinstance(mode, str) or not mode:
            return None
        return mode

    def save(self, mode: str) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps({"mode": mode}, indent=2), encoding="utf-8"
        )


__all__ = ["ModePreferenceStore"]
