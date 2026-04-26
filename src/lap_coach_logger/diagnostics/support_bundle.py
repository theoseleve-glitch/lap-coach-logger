"""Pure helpers for the diagnostic support bundle (T233).

Two helpers, both side-effect-free apart from filesystem reads:

  - :func:`redact_config` returns a dict copy of an
    ``AppConfig`` with secret-bearing fields replaced by the
    literal string ``"<redacted>"``. Other fields pass through
    unchanged. The function never mutates its input.
  - :func:`enumerate_sessions` walks an output directory and
    returns one record per session folder with enough metadata
    to triage without shipping the actual telemetry. Missing
    or malformed sessions are skipped (not raised).

The downstream ``export_support_bundle`` UI method can use these
to build the zip; tests can pin them in isolation without
spinning up the full desktop service.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from lap_coach_logger.config.models import AppConfig

_log = logging.getLogger(__name__)

_REDACTED = "<redacted>"


def redact_config(config: AppConfig) -> dict[str, Any]:
    """Return a dict copy of ``config`` with secret-bearing
    fields redacted.

    Currently redacts:
      - ``sync.device_token`` (account upload credential)

    Empty values are left untouched so support can distinguish
    "user had a token" from "user never set one"."""
    payload = config.to_dict()

    sync = payload.get("sync")
    if isinstance(sync, dict):
        token = sync.get("device_token")
        if isinstance(token, str) and token:
            sync["device_token"] = _REDACTED

    return payload


def enumerate_sessions(sessions_root: Path) -> list[dict[str, Any]]:
    """List session folders under ``sessions_root`` with
    triage-friendly metadata.

    Each entry includes:
      - ``folder``: the directory name (support's primary handle)
      - ``started_at_utc``, ``sample_count``, ``sim``, ``track``,
        ``session_uid`` (when present in the metadata.json)

    Folders without a ``metadata.json`` or with a corrupt one
    are skipped — a single bad session can't block the bundle.
    Returns an empty list when the root directory doesn't exist
    or isn't a directory.

    Results are sorted by folder name, which is alphabetical-
    equals-chronological because session folders are date-
    prefixed.
    """
    if not sessions_root.exists() or not sessions_root.is_dir():
        return []

    entries: list[dict[str, Any]] = []
    for child in sorted(sessions_root.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        meta_path = child / "metadata.json"
        if not meta_path.exists():
            continue
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            _log.debug(
                "support_bundle: skipping %s (unreadable metadata.json)",
                child.name,
            )
            continue
        if not isinstance(metadata, dict):
            continue
        entries.append(
            {
                "folder": child.name,
                "started_at_utc": metadata.get("started_at_utc"),
                "sample_count": metadata.get("sample_count"),
                "sim": metadata.get("sim"),
                "track": metadata.get("track"),
                "session_uid": metadata.get("session_uid"),
            }
        )
    return entries


__all__ = ["redact_config", "enumerate_sessions"]
