"""iRacing full-capture orchestration.

Manages:
  - Raw telemetry buffer (all IRSDK vars, flattened)
  - Session-info snapshot
  - Static reference catalog loading and bundling
  - Observed sample-rate tracking
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_CATALOG_FILES = {
    "live_var_schema": "iracing_live_var_schema.json",
    "session_leaf_paths": "iracing_session_leaf_paths.json",
    "localserver_track_fields": "iracing_localserver_track_fields.json",
    "localserver_arq_messages": "iracing_localserver_arq_messages.json",
    "sim_param_names": "iracing_sim_param_names.json",
}


class IRacingRawCapture:
    """Collects raw iRacing data alongside the normalized stream."""

    def __init__(self) -> None:
        self._raw_buffer: list[dict[str, Any]] = []
        self._session_info_snapshot: dict[str, Any] | None = None
        self._catalogs: dict[str, Any] | None = None
        self._raw_column_names: list[str] | None = None
        # Observed rate tracking
        self._first_sample_time: float | None = None
        self._sample_count: int = 0

    @property
    def raw_buffer(self) -> list[dict[str, Any]]:
        return self._raw_buffer

    @property
    def raw_sample_count(self) -> int:
        return len(self._raw_buffer)

    @property
    def session_info_snapshot(self) -> dict[str, Any] | None:
        return self._session_info_snapshot

    @property
    def catalogs(self) -> dict[str, Any] | None:
        return self._catalogs

    @property
    def observed_sample_rate_hz(self) -> float | None:
        if self._sample_count < 2 or self._first_sample_time is None:
            return None
        elapsed = time.monotonic() - self._first_sample_time
        if elapsed <= 0:
            return None
        return round(self._sample_count / elapsed, 2)

    def reset(self) -> None:
        self._raw_buffer.clear()
        self._session_info_snapshot = None
        self._raw_column_names = None
        self._first_sample_time = None
        self._sample_count = 0

    def append_raw_sample(self, row: dict[str, Any]) -> None:
        """Append a flattened raw sample dict to the buffer."""
        # Track column superset for consistent output
        if self._raw_column_names is None:
            self._raw_column_names = sorted(row.keys())
        self._raw_buffer.append(row)
        self._sample_count += 1
        if self._first_sample_time is None:
            self._first_sample_time = time.monotonic()

    def set_session_info_snapshot(self, snapshot: dict[str, Any]) -> None:
        self._session_info_snapshot = snapshot

    def get_raw_column_names(self) -> list[str]:
        """Return the union of all column names seen, sorted."""
        if not self._raw_buffer:
            return self._raw_column_names or []
        # Build union of all keys across all rows (handles dynamic var appearance)
        all_keys: set[str] = set()
        for row in self._raw_buffer:
            all_keys.update(row.keys())
        return sorted(all_keys)

    # -- catalog loading ---------------------------------------------------

    def load_catalogs(
        self,
        live_var_schema_path: str = "",
        session_leaf_paths_path: str = "",
        localserver_track_fields_path: str = "",
        localserver_arq_messages_path: str = "",
        sim_param_names_path: str = "",
    ) -> None:
        """Load the recovered static catalogs from disk."""
        catalogs: dict[str, Any] = {}

        catalogs["localserver_track_fields"] = _load_catalog(
            localserver_track_fields_path,
            _CATALOG_FILES["localserver_track_fields"],
        )
        catalogs["localserver_arq_messages"] = _load_catalog(
            localserver_arq_messages_path,
            _CATALOG_FILES["localserver_arq_messages"],
        )
        catalogs["sim_param_names"] = _load_catalog(
            sim_param_names_path,
            _CATALOG_FILES["sim_param_names"],
        )

        # Add counts and source paths
        for key in ("localserver_track_fields", "localserver_arq_messages", "sim_param_names"):
            data = catalogs[key]
            if isinstance(data.get("data"), list):
                data["count"] = len(data["data"])

        self._catalogs = catalogs


def _load_catalog(explicit_path: str, default_filename: str) -> dict[str, Any]:
    """Load a JSON catalog file, returning metadata dict.

    If no explicit path is configured, the catalog is skipped (returns empty).
    """
    if not explicit_path:
        return {"source_path": None, "data": None, "count": 0}
    path = Path(explicit_path)
    result: dict[str, Any] = {"source_path": str(path), "data": None, "count": 0}

    if not path.exists():
        log.info("Catalog file not found: %s", path)
        return result

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        result["data"] = data
        if isinstance(data, list):
            result["count"] = len(data)
        return result
    except Exception:
        log.warning("Failed to load catalog: %s", path, exc_info=True)
        return result
