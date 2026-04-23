"""Load and lookup pre-computed theoretical ghost traces."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)


@dataclass(slots=True)
class GhostPoint:
    distance_pct: float
    speed_kph: float
    throttle_pct: float
    brake_pct: float
    steering_deg: float
    cumulative_time_s: float


class GhostReference:
    """Distance-indexed theoretical trace for O(1) lookup via np.interp."""

    def __init__(self, trace_path: Path | None = None):
        self._loaded = False
        self._track_name = ""
        self._car_name = ""
        self._lap_time_s = 0.0
        self._dist_pct: np.ndarray = np.array([])
        self._speed: np.ndarray = np.array([])
        self._throttle: np.ndarray = np.array([])
        self._brake: np.ndarray = np.array([])
        self._steering: np.ndarray = np.array([])
        self._cum_time: np.ndarray = np.array([])
        if trace_path is not None:
            self.load(trace_path)

    def load(self, path: Path) -> bool:
        """Load theoretical_ghost.json. Returns True on success."""
        try:
            with open(path) as f:
                data = json.load(f)
            self._track_name = data.get("track_name", "")
            self._car_name = data.get("car_name", "")
            self._lap_time_s = float(data.get("theoretical_lap_time_s", 0))
            self._dist_pct = np.array(data["distance_pct"], dtype=float)
            self._speed = np.array(data["speed_kph"], dtype=float)
            self._throttle = np.array(data["throttle_pct"], dtype=float)
            self._brake = np.array(data["brake_pct"], dtype=float)
            self._steering = np.array(data["steering_deg"], dtype=float)
            # Compute cumulative time: dt = ds / v
            ds = np.diff(self._dist_pct, prepend=0.0)
            v_mps = np.maximum(self._speed / 3.6, 1.0)
            # cumulative_time = integral(ds_pct / (speed * some_factor))
            # Linearly space time from 0 to lap_time based on distance
            # weighted by inverse speed.
            dt = ds / v_mps
            dt_sum = dt.sum()
            if dt_sum > 0:
                self._cum_time = np.cumsum(dt) / dt_sum * self._lap_time_s
            else:
                self._cum_time = np.linspace(
                    0, self._lap_time_s, len(self._dist_pct)
                )
            self._loaded = len(self._dist_pct) >= 10
            log.info(
                "Ghost loaded: %s / %s, %.3fs, %d points",
                self._track_name,
                self._car_name,
                self._lap_time_s,
                len(self._dist_pct),
            )
            return self._loaded
        except Exception as exc:
            log.warning("Failed to load ghost trace from %s: %s", path, exc)
            self._loaded = False
            return False

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def track_name(self) -> str:
        return self._track_name

    @property
    def car_name(self) -> str:
        return self._car_name

    @property
    def theoretical_lap_time_s(self) -> float:
        return self._lap_time_s

    def lookup(self, lap_dist_pct: float) -> GhostPoint | None:
        """Interpolate theoretical values at given track position (0.0-1.0)."""
        if not self._loaded or lap_dist_pct < 0 or lap_dist_pct > 1.0:
            return None
        return GhostPoint(
            distance_pct=lap_dist_pct,
            speed_kph=float(
                np.interp(lap_dist_pct, self._dist_pct, self._speed)
            ),
            throttle_pct=float(
                np.interp(lap_dist_pct, self._dist_pct, self._throttle)
            ),
            brake_pct=float(
                np.interp(lap_dist_pct, self._dist_pct, self._brake)
            ),
            steering_deg=float(
                np.interp(lap_dist_pct, self._dist_pct, self._steering)
            ),
            cumulative_time_s=float(
                np.interp(lap_dist_pct, self._dist_pct, self._cum_time)
            ),
        )

    @classmethod
    def find_latest(
        cls, output_dir: Path, track_name: str, car_name: str
    ) -> GhostReference | None:
        """Search for most recent theoretical_ghost.json matching track+car."""
        candidates = sorted(
            output_dir.glob("**/theoretical_ghost.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for path in candidates:
            ref = cls(path)
            if ref.loaded and ref.track_name == track_name and ref.car_name == car_name:
                return ref
        return None
