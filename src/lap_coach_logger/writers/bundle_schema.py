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

# Shared v2 contract. Sprint T022 replaces the local ``SessionManifest``
# dataclass with this Pydantic model so the desktop bundle pipeline
# writes to the same shape every other consumer reads. The legacy
# dataclass is retained as ``LegacySessionManifest`` for transitional
# code paths until the T025-T034 SessionFinalizer rewrite adopts the
# new shape throughout.
from lap_schemas.v1 import SessionManifest  # noqa: F401

BUNDLE_SCHEMA_VERSION = "1.0.0"


# ------------------------------------------------------------------
# Lap record
# ------------------------------------------------------------------

@dataclass
class LapRecord:
    """Timing and metadata for a single lap."""
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
# Session manifest  (== session.json top-level)
# ------------------------------------------------------------------

@dataclass
class LegacySessionManifest:
    """Transitional v1-bundle manifest (pre-T022 shape).

    Superseded by ``lap_schemas.v1.SessionManifest`` (re-exported here
    as ``SessionManifest``). Retained until the SessionFinalizer
    rewrite in T025-T034 adopts the shared shape throughout.
    """
    session_id: str
    schema_version: str = BUNDLE_SCHEMA_VERSION
    telemetry_schema_version: str = ""
    logger_version: str = ""
    adapter: str | None = None

    # Sim
    sim_name: str | None = None

    # Timestamps
    started_at_utc: str = ""
    ended_at_utc: str = ""
    timezone_offset: str | None = None

    # Session
    session_type: str | None = None
    track_name: str | None = None
    car_name: str | None = None

    # Driver
    driver_name: str | None = None

    # Recording stats
    sample_count: int = 0
    dropped_sample_count: int = 0
    sample_rate_hz: float | None = None
    duration_s: float = 0.0
    data_quality_score: float = 0.0

    # Environment
    track_temp_c: float | None = None
    air_temp_c: float | None = None

    # Lap summary
    total_laps: int = 0
    valid_laps: int = 0
    clean_laps: int = 0
    best_lap_time_s: float | None = None
    best_clean_lap_time_s: float | None = None
    representative_lap_number: int | None = None
    representative_lap_time_s: float | None = None

    # Review workflow
    review_status: str = "ready"
    review_updated_at_utc: str | None = None

    # Sync workflow (offline-first; remote upload may be disabled)
    sync_status: str = "not_queued"
    sync_attempt_count: int = 0
    last_sync_attempt_at: str | None = None
    last_sync_error: str | None = None
    bundle_hash: str | None = None
    remote_id: str | None = None

    # Validation output
    quality_classification: str = "needs_review"
    quality_score: float = 0.0
    quality_report_file: str = "quality_report.json"

    # Files
    telemetry_file: str = "telemetry.csv"
    telemetry_format: str = "csv"
    telemetry_sha256: str | None = None

    # Source metadata
    source_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


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
