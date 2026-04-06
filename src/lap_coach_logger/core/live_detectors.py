"""Live coaching detectors for overlay pop-ups.

Each detector is a small class with a check() method called every sample.
Returns a CoachingNote if the condition is detected, None otherwise.

Usage:
    manager = DetectorManager(config)
    manager.set_best_lap_reference(best_lap_points)

    for sample in live_stream:
        notes = manager.check(sample)
        for note in notes:
            overlay.show_popup(note)
"""
from __future__ import annotations

import logging
import math
from typing import Any

from lap_coach_logger.core.detector_models import (
    CoachingNote,
    DetectorConfig,
    DetectorType,
)
from lap_coach_logger.core.schema import TelemetrySample

log = logging.getLogger(__name__)


class _BaseDetector:
    """Base class for all detectors."""

    def __init__(self, config: DetectorConfig) -> None:
        self.config = config
        self._last_fire_pct: float = -1.0

    def _cooldown_ok(self, dist_pct: float) -> bool:
        if dist_pct - self._last_fire_pct < self.config.cooldown_dist_pct:
            return False
        return True

    def _fire(self, dist_pct: float) -> None:
        self._last_fire_pct = dist_pct


class OversteerDetector(_BaseDetector):
    """Detect oversteer: yaw rate deviates from expected (speed * curvature proxy).

    Uses: speed, lat_accel (as proxy for curvature), yaw_deg change.
    Trigger: |actual_yaw_rate - expected_yaw_rate| > threshold at speed > min.
    """

    def __init__(self, config: DetectorConfig) -> None:
        super().__init__(config)
        self._prev_yaw: float | None = None
        self._prev_time: float | None = None

    def check(self, sample: TelemetrySample) -> CoachingNote | None:
        yaw = sample.yaw_deg
        t = sample.session_time_s
        speed = sample.speed_kph
        lat_g = sample.lat_accel_g
        dist_pct = sample.lap_dist_pct

        if yaw is None or t is None or speed is None or lat_g is None or dist_pct is None:
            self._prev_yaw = yaw
            self._prev_time = t
            return None

        if self._prev_yaw is None or self._prev_time is None:
            self._prev_yaw = yaw
            self._prev_time = t
            return None

        dt = t - self._prev_time
        if dt <= 0:
            self._prev_yaw = yaw
            self._prev_time = t
            return None

        actual_yaw_rate = abs(yaw - self._prev_yaw) / dt  # deg/s
        self._prev_yaw = yaw
        self._prev_time = t

        if speed < self.config.oversteer_min_speed_kph:
            return None

        # Expected yaw rate from lateral acceleration: lat_g * 9.81 / (speed_m_s)
        # converted to deg/s via * (180/pi)
        speed_ms = speed / 3.6
        if speed_ms < 1.0:
            return None
        expected_yaw_rate = abs(lat_g * 9.81 / speed_ms) * (180.0 / math.pi)

        deviation = actual_yaw_rate - expected_yaw_rate
        if deviation > self.config.oversteer_yaw_rate_threshold_dps:
            if not self._cooldown_ok(dist_pct):
                return None
            self._fire(dist_pct)
            return CoachingNote(
                detector=DetectorType.OVERSTEER,
                message="Oversteer — earlier throttle?",
                severity="warning",
                lap_dist_pct=dist_pct,
                value=round(deviation, 1),
            )
        return None


class UndersteerDetector(_BaseDetector):
    """Detect understeer: steering angle increasing but lat_g plateaus or drops.

    Uses window of last ~5 samples. If steering increased by > threshold
    but lat_g didn't increase (or decreased), fire.
    """

    WINDOW = 5

    def __init__(self, config: DetectorConfig) -> None:
        super().__init__(config)
        self._history: list[tuple[float, float, float]] = []  # (dist_pct, steering, lat_g)

    def check(self, sample: TelemetrySample) -> CoachingNote | None:
        steering = sample.steering_deg
        lat_g = sample.lat_accel_g
        speed = sample.speed_kph
        dist_pct = sample.lap_dist_pct

        if steering is None or lat_g is None or speed is None or dist_pct is None:
            return None
        if speed < self.config.understeer_min_speed_kph:
            return None

        self._history.append((dist_pct, abs(steering), abs(lat_g)))
        if len(self._history) > self.WINDOW:
            self._history.pop(0)
        if len(self._history) < self.WINDOW:
            return None

        steer_first = self._history[0][1]
        steer_last = self._history[-1][1]
        lat_g_first = self._history[0][2]
        lat_g_last = self._history[-1][2]

        steer_delta = steer_last - steer_first
        lat_g_delta = lat_g_last - lat_g_first

        if (
            steer_delta >= self.config.understeer_steering_increase_deg
            and lat_g_delta <= -self.config.understeer_lat_g_drop_threshold
        ):
            if not self._cooldown_ok(dist_pct):
                return None
            self._fire(dist_pct)
            return CoachingNote(
                detector=DetectorType.UNDERSTEER,
                message="Understeer — less speed in",
                severity="warning",
                lap_dist_pct=dist_pct,
                value=round(lat_g_delta, 2),
            )
        return None


class BrakePointDetector(_BaseDetector):
    """Detect early/late braking vs best lap reference.

    Compares the distance at which brake > threshold to the reference brake point.
    """

    def __init__(self, config: DetectorConfig) -> None:
        super().__init__(config)
        self._ref_brake_points: dict[int, float] = {}  # corner_id -> brake_dist_m
        self._current_braking: bool = False
        self._brake_start_dist: float | None = None

    def set_reference(self, brake_points: dict[int, float]) -> None:
        """Set reference brake points from best lap. Keys are corner IDs, values are brake distances."""
        self._ref_brake_points = dict(brake_points)

    def check(self, sample: TelemetrySample) -> CoachingNote | None:
        brake = sample.brake_pct
        dist_m = sample.lap_distance_m
        dist_pct = sample.lap_dist_pct

        if brake is None or dist_m is None or dist_pct is None:
            return None

        was_braking = self._current_braking
        now_braking = brake >= self.config.brake_threshold_pct

        if now_braking and not was_braking:
            # Brake onset detected
            self._current_braking = True
            self._brake_start_dist = dist_m

            # Find the closest reference brake point
            best_corner_id: int | None = None
            best_delta: float | None = None
            for corner_id, ref_dist in self._ref_brake_points.items():
                delta = dist_m - ref_dist
                if best_delta is None or abs(delta) < abs(best_delta):
                    best_delta = delta
                    best_corner_id = corner_id

            if best_delta is not None and best_corner_id is not None:
                margin = self.config.brake_point_margin_m
                if best_delta > margin:
                    if not self._cooldown_ok(dist_pct):
                        return None
                    self._fire(dist_pct)
                    return CoachingNote(
                        detector=DetectorType.LATE_BRAKE,
                        message=f"Braked late — {best_delta:.0f}m past ref",
                        severity="warning",
                        lap_dist_pct=dist_pct,
                        value=round(best_delta, 1),
                    )
                elif best_delta < -margin:
                    if not self._cooldown_ok(dist_pct):
                        return None
                    self._fire(dist_pct)
                    return CoachingNote(
                        detector=DetectorType.EARLY_BRAKE,
                        message=f"Braked early — {abs(best_delta):.0f}m before ref",
                        severity="info",
                        lap_dist_pct=dist_pct,
                        value=round(best_delta, 1),
                    )
        elif not now_braking:
            self._current_braking = False
            self._brake_start_dist = None

        return None


class ApexSpeedDetector(_BaseDetector):
    """Detect low apex speed vs best lap reference.

    At each corner's apex distance, compare current speed to best lap apex speed.
    """

    def __init__(self, config: DetectorConfig) -> None:
        super().__init__(config)
        self._ref_apex: dict[float, float] = {}  # apex_dist_pct -> speed_kph
        self._apex_tolerance: float = 0.005  # match within 0.5% of track

    def set_reference(self, apex_speeds: dict[float, float]) -> None:
        self._ref_apex = dict(apex_speeds)

    def check(self, sample: TelemetrySample) -> CoachingNote | None:
        speed = sample.speed_kph
        dist_pct = sample.lap_dist_pct

        if speed is None or dist_pct is None:
            return None

        for apex_pct, ref_speed in self._ref_apex.items():
            if abs(dist_pct - apex_pct) <= self._apex_tolerance:
                delta = ref_speed - speed
                if delta > self.config.apex_speed_margin_kph:
                    if not self._cooldown_ok(dist_pct):
                        return None
                    self._fire(dist_pct)
                    return CoachingNote(
                        detector=DetectorType.LOW_APEX_SPEED,
                        message=f"Apex +{delta:.0f} km/h possible",
                        severity="info",
                        lap_dist_pct=dist_pct,
                        value=round(delta, 1),
                    )
        return None


class DetectorManager:
    """Manages all detectors and dispatches samples to each."""

    def __init__(self, config: DetectorConfig | None = None) -> None:
        self.config = config or DetectorConfig()
        self.oversteer = OversteerDetector(self.config)
        self.understeer = UndersteerDetector(self.config)
        self.brake_point = BrakePointDetector(self.config)
        self.apex_speed = ApexSpeedDetector(self.config)
        self._detectors: list[_BaseDetector] = [
            self.oversteer,
            self.understeer,
            self.brake_point,
            self.apex_speed,
        ]

    def set_best_lap_reference(
        self,
        brake_points: dict[int, float],
        apex_speeds: dict[float, float],
    ) -> None:
        self.brake_point.set_reference(brake_points)
        self.apex_speed.set_reference(apex_speeds)

    def check(self, sample: TelemetrySample) -> list[CoachingNote]:
        notes: list[CoachingNote] = []
        for detector in self._detectors:
            note = detector.check(sample)
            if note is not None:
                notes.append(note)
        return notes

    def reset(self) -> None:
        for d in self._detectors:
            d._last_fire_pct = -1.0
