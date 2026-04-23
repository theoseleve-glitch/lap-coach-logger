"""Stateful ghost delta computation from live samples."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from lap_coach_logger.core.ghost_reference import GhostReference
from lap_coach_logger.core.schema import TelemetrySample

log = logging.getLogger(__name__)


@dataclass(slots=True)
class GhostDelta:
    speed_delta_kph: float  # theoretical - actual (positive = you're slow)
    throttle_delta_pct: float  # theoretical - actual
    brake_delta_pct: float  # theoretical - actual
    steering_delta_deg: float  # theoretical - actual
    cumulative_delta_s: float  # time loss (positive = behind ghost)
    theoretical_speed_kph: float
    theoretical_throttle_pct: float
    theoretical_brake_pct: float
    theoretical_steering_deg: float


class GhostTracker:
    """Computes real-time ghost deltas from live TelemetrySample stream."""

    def __init__(self, reference: GhostReference):
        self._ref = reference
        self._cumulative_delta_s: float = 0.0
        self._prev_dist_pct: float | None = None
        self._prev_time_s: float | None = None
        self._prev_ghost_time: float | None = None

    def reset(self) -> None:
        self._cumulative_delta_s = 0.0
        self._prev_dist_pct = None
        self._prev_time_s = None
        self._prev_ghost_time = None

    @property
    def cumulative_delta_s(self) -> float:
        return self._cumulative_delta_s

    def update(self, sample: TelemetrySample) -> GhostDelta | None:
        if not self._ref.loaded:
            return None
        dist_pct = sample.lap_dist_pct
        if dist_pct is None or dist_pct < 0 or dist_pct > 1.0:
            return None

        ghost = self._ref.lookup(dist_pct)
        if ghost is None:
            return None

        # Accumulate time delta
        if (
            self._prev_dist_pct is not None
            and self._prev_time_s is not None
            and self._prev_ghost_time is not None
            and sample.session_time_s is not None
        ):
            dt_actual = sample.session_time_s - self._prev_time_s
            dt_ghost = ghost.cumulative_time_s - self._prev_ghost_time
            if dt_actual > 0 and dt_ghost > 0 and dt_actual < 5.0:
                self._cumulative_delta_s += dt_actual - dt_ghost

        # Detect lap reset: dist_pct drops backward by more than 10%
        # (catches full-lap wraparound, pit teleports, and session restarts
        # while ignoring normal GPS jitter which is typically < 0.1%)
        if (
            self._prev_dist_pct is not None
            and dist_pct < self._prev_dist_pct - 0.1
        ):
            self.reset()

        self._prev_dist_pct = dist_pct
        self._prev_time_s = sample.session_time_s
        self._prev_ghost_time = ghost.cumulative_time_s

        actual_speed = sample.speed_kph or 0.0
        actual_throttle = sample.throttle_pct or 0.0
        actual_brake = sample.brake_pct or 0.0
        actual_steering = sample.steering_deg or 0.0

        return GhostDelta(
            speed_delta_kph=ghost.speed_kph - actual_speed,
            throttle_delta_pct=ghost.throttle_pct - actual_throttle,
            brake_delta_pct=ghost.brake_pct - actual_brake,
            steering_delta_deg=ghost.steering_deg - actual_steering,
            cumulative_delta_s=self._cumulative_delta_s,
            theoretical_speed_kph=ghost.speed_kph,
            theoretical_throttle_pct=ghost.throttle_pct,
            theoretical_brake_pct=ghost.brake_pct,
            theoretical_steering_deg=ghost.steering_deg,
        )
