"""Telemetry snapshot validator.

Normalizes raw telemetry snapshots so downstream consumers never
encounter KeyError or surprise None values. Missing fields become
explicit MetricState.UNAVAILABLE entries.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from lap_coach_logger.core.metric_state import MetricState


# Expected top-level snapshot payload keys from DesktopService.snapshot_changed
_TOP_LEVEL_KEYS = frozenset({
    "raw_state", "live", "session_state", "status_detail",
    "is_monitoring", "detected_sim", "sample_rate_hz_est",
    "sample_rate_hz_config", "update_hz_est", "data_staleness_s",
    "stream_status", "stream_flags", "completed_session",
    "adapter_health", "sim_detection_status",
    "sync_queue_depth", "sync_feature_enabled",
})

# Telemetry channels expected in the "live" sub-dict
_TELEMETRY_KEYS = frozenset({
    "timestamp_utc", "sim", "session_uid", "session_time_s",
    "lap_number", "lap_distance_m", "lap_dist_pct",
    "speed_kph", "throttle_pct", "brake_pct", "steering_deg",
    "clutch_pct", "gear", "rpm",
    "world_pos_x", "world_pos_y", "world_pos_z",
    "yaw_deg", "pitch", "roll",
    "long_accel_g", "lat_accel_g",
    "tyre_temp_lf", "tyre_temp_rf", "tyre_temp_lr", "tyre_temp_rr",
    "brake_temp_lf", "brake_temp_rf", "brake_temp_lr", "brake_temp_rr",
    "position", "num_cars", "track_length_m",
    "fuel_level", "fuel_capacity",
    "water_temp", "oil_temp", "track_temp_c", "air_temp_c",
    "is_on_track", "is_in_pits",
    "track_name", "car_name", "session_type",
})


@dataclass(frozen=True)
class ValidatedSnapshot:
    """Normalized snapshot with explicit state per field."""
    raw: dict[str, Any]
    states: dict[str, MetricState]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def state_of(self, key: str) -> MetricState:
        return self.states.get(key, MetricState.UNAVAILABLE)

    def is_available(self, key: str) -> bool:
        return self.states.get(key) == MetricState.AVAILABLE


def validate_snapshot(payload: Any) -> ValidatedSnapshot | None:
    """Validate and normalize a snapshot payload.

    Returns None if payload is not a dict (defensive for Qt signal
    dispatch edge cases where payload may be something unexpected).
    """
    if not isinstance(payload, dict):
        return None

    raw = dict(payload)  # defensive copy
    states: dict[str, MetricState] = {}

    # Classify top-level payload keys
    for key in _TOP_LEVEL_KEYS:
        value = raw.get(key)
        states[key] = MetricState.AVAILABLE if value is not None else MetricState.UNAVAILABLE

    return ValidatedSnapshot(raw=raw, states=states)


def validate_live(live: Any) -> ValidatedSnapshot | None:
    """Validate and normalize the 'live' telemetry sub-dict."""
    if not isinstance(live, dict):
        return None

    raw = dict(live)
    states: dict[str, MetricState] = {}

    for key in _TELEMETRY_KEYS:
        value = raw.get(key)
        states[key] = MetricState.AVAILABLE if value is not None else MetricState.UNAVAILABLE

    return ValidatedSnapshot(raw=raw, states=states)


def safe_get(snap: Any, key: str, default: Any = None) -> Any:
    """Hot-path safe accessor -- never raises.

    Works with any mapping-like object or returns default on anything else.
    """
    if snap is None:
        return default
    if isinstance(snap, ValidatedSnapshot):
        return snap.get(key, default)
    if isinstance(snap, dict):
        return snap.get(key, default)
    # Last resort: try generic getitem with try/except
    try:
        return snap[key] if key in snap else default
    except (TypeError, KeyError):
        return default


def missing_keys(snap: Any, required: set[str] | frozenset[str]) -> list[str]:
    """Return which required keys are missing from a snapshot."""
    if not isinstance(snap, (dict, ValidatedSnapshot)):
        return sorted(required)
    raw = snap.raw if isinstance(snap, ValidatedSnapshot) else snap
    return sorted(k for k in required if raw.get(k) is None)
