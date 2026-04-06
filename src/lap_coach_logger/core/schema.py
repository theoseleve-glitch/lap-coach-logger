"""Normalised telemetry sample schema.

Every adapter maps its raw data into a ``TelemetrySample``.  Fields
that a particular sim cannot provide are left as ``None``.  The schema
is intentionally flat so it maps 1-to-1 to Parquet / CSV columns.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field, fields
from datetime import datetime, timezone
from typing import Any


TELEMETRY_SCHEMA_VERSION = "2.0.0"


@dataclass(slots=True)
class TelemetrySample:
    """One row of normalised telemetry."""

    # Timing / identity
    timestamp_utc: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    sim: str | None = None
    session_uid: str | None = None
    session_time_s: float | None = None

    # Lap / position on track
    lap_number: int | None = None
    lap_distance_m: float | None = None
    lap_dist_pct: float | None = None  # 0.0–1.0 normalised track position

    # Vehicle dynamics
    speed_kph: float | None = None
    throttle_pct: float | None = None
    brake_pct: float | None = None
    steering_deg: float | None = None
    clutch_pct: float | None = None
    gear: int | None = None
    rpm: float | None = None
    abs_level: float | None = None
    tc_level: float | None = None

    # World position
    world_pos_x: float | None = None
    world_pos_y: float | None = None
    world_pos_z: float | None = None

    # Orientation
    yaw_deg: float | None = None
    pitch: float | None = None
    roll: float | None = None

    # Forces
    long_accel_g: float | None = None
    lat_accel_g: float | None = None

    # Tyre temperatures (°C)
    tyre_temp_lf: float | None = None
    tyre_temp_rf: float | None = None
    tyre_temp_lr: float | None = None
    tyre_temp_rr: float | None = None

    # Fuel
    fuel_level: float | None = None   # litres remaining
    fuel_capacity: float | None = None  # tank capacity litres

    # Temperatures (°C)
    water_temp: float | None = None
    oil_temp: float | None = None
    track_temp_c: float | None = None
    air_temp_c: float | None = None

    # Status flags
    is_on_track: bool | None = None
    is_in_pits: bool | None = None

    # Context
    track_name: str | None = None
    car_name: str | None = None
    session_type: str | None = None

    # Raw source timestamp (sim-native)
    raw_source_timestamp: float | None = None

    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @classmethod
    def field_names(cls) -> list[str]:
        return [f.name for f in fields(cls)]
