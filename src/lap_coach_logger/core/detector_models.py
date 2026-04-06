"""Data models for live coaching detectors."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DetectorType(Enum):
    OVERSTEER = "oversteer"
    UNDERSTEER = "understeer"
    LATE_BRAKE = "late_brake"
    EARLY_BRAKE = "early_brake"
    LOW_APEX_SPEED = "low_apex_speed"


@dataclass(slots=True)
class CoachingNote:
    """A single coaching pop-up to show on the overlay."""

    detector: DetectorType
    message: str
    severity: str = "info"  # "info" | "warning"
    lap_dist_pct: float = 0.0
    value: float = 0.0  # detector-specific metric (e.g., delta meters, delta kph)


@dataclass
class DetectorConfig:
    """Thresholds for all detectors."""

    # Oversteer: yaw rate deviation threshold (deg/s)
    oversteer_yaw_rate_threshold_dps: float = 15.0
    oversteer_min_speed_kph: float = 40.0
    # Understeer: lat_g drop while steering increases
    understeer_lat_g_drop_threshold: float = 0.15
    understeer_steering_increase_deg: float = 5.0
    understeer_min_speed_kph: float = 30.0
    # Brake point: distance margin (meters)
    brake_point_margin_m: float = 10.0
    brake_threshold_pct: float = 0.1  # minimum brake to count as "braking"
    # Apex speed: margin (km/h)
    apex_speed_margin_kph: float = 3.0
    # Cooldown: minimum distance between same-type notes (pct)
    cooldown_dist_pct: float = 0.05
