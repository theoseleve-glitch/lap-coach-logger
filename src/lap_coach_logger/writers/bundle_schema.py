"""Session bundle schema definitions.

Defines the structured data models used to produce session bundles:
  session.json   — manifest + metadata
  laps.json      — per-lap timing records
  events.json    — lifecycle events log
  channels.json  — telemetry channel definitions
  telemetry.csv / .parquet — sample data
"""

from __future__ import annotations

import dataclasses
import hashlib
from dataclasses import dataclass, field
from typing import Any

# Shared v2 contract. Sprint T022/T023 replaced the local
# ``SessionManifest`` and ``LapRecord`` dataclasses with these Pydantic
# models so the desktop bundle pipeline writes the same shape every
# other consumer reads. Sprint T039 removed the legacy
# ``LegacySessionManifest`` dataclass once the SessionFinalizer (T025–T034)
# started emitting v2 manifest.json directly. ``LegacyLapRecord`` stays
# until lap_analysis / session_coordinator migrate to the shared shape.
from lap_schemas.v1 import LapRecord, SessionManifest  # noqa: F401

BUNDLE_SCHEMA_VERSION = "1.0.0"


# ------------------------------------------------------------------
# Lap record
# ------------------------------------------------------------------

@dataclass
class LegacyLapRecord:
    """Transitional v1-bundle lap record (pre-T023 shape).

    Superseded by ``lap_schemas.v1.LapRecord`` (re-exported here as
    ``LapRecord``). Retained until the SessionFinalizer rewrite in
    T025-T034 adopts the shared tuple-based sector splits.
    """
    lap_number: int
    start_session_time_s: float
    end_session_time_s: float | None = None
    lap_time_s: float | None = None
    out_lap: bool = False
    in_lap: bool = False
    invalid: bool = False
    classification: str = "unknown"
    has_complete_telemetry: bool = False
    valid_for_analysis: bool = False
    suspected_offtrack: bool = False
    suspected_spin_or_reset: bool = False
    pit_entry_or_exit_detected: bool = False
    lap_time_valid: bool = False
    likely_flying_lap: bool = False
    clean_lap: bool = False
    sample_count: int = 0
    max_speed_kph: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# ------------------------------------------------------------------
# Session event
# ------------------------------------------------------------------

@dataclass
class SessionEvent:
    """A timestamped lifecycle event."""
    event: str
    timestamp_utc: str
    detail: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"event": self.event, "timestamp_utc": self.timestamp_utc}
        if self.detail:
            d["detail"] = self.detail
        return d


# ------------------------------------------------------------------
# Channel definition
# ------------------------------------------------------------------

@dataclass
class ChannelDef:
    """Metadata for one telemetry channel/column."""
    canonical_name: str
    dtype: str                   # "float64", "int32", "string", "bool"
    units: str | None = None
    missing_allowed: bool = True
    description: str | None = None
    source_names: dict[str, str | None] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


# ------------------------------------------------------------------
# Session manifest
# ------------------------------------------------------------------
# The v1-bundle ``LegacySessionManifest`` dataclass has been removed
# (sprint T039). ``SessionManifest`` is now the shared
# ``lap_schemas.v1.SessionManifest`` re-export only — Bundle v2 is
# the single source of truth. See T025–T034 for the finalizer path
# that writes the new manifest.json.


# ------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------

def compute_file_sha256(path: Any) -> str:
    """Compute hex SHA-256 of a file.  *path* is a ``Path``-like object."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()
