"""Simple tire degradation model for overlay display.

Tracks average tire temperatures per lap and estimates remaining
tire life as a percentage. Not a physics sim — just a heuristic
based on temperature history and lap count.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TireState:
    """Current tire state for overlay display."""
    lap_count: int = 0
    avg_temp_lf: float = 0.0
    avg_temp_rf: float = 0.0
    avg_temp_lr: float = 0.0
    avg_temp_rr: float = 0.0
    grip_pct: float = 100.0       # estimated grip remaining (0-100)
    wear_rate: float = 0.0        # grip loss per lap
    laps_remaining: int = 99      # estimated laps until grip drops below threshold
    compound: str = "unknown"     # soft/medium/hard/wet
    condition: str = "good"       # good/worn/critical

    def to_dict(self) -> dict:
        return {
            "lap_count": self.lap_count,
            "avg_temp_lf": round(self.avg_temp_lf, 1),
            "avg_temp_rf": round(self.avg_temp_rf, 1),
            "avg_temp_lr": round(self.avg_temp_lr, 1),
            "avg_temp_rr": round(self.avg_temp_rr, 1),
            "grip_pct": round(self.grip_pct, 1),
            "wear_rate": round(self.wear_rate, 2),
            "laps_remaining": self.laps_remaining,
            "compound": self.compound,
            "condition": self.condition,
        }


class TireDegradationTracker:
    """Tracks tire degradation across a stint."""

    GRIP_THRESHOLD = 40.0  # below this = critical
    OPTIMAL_TEMP_RANGE = (75.0, 100.0)  # Celsius

    def __init__(self) -> None:
        self._state = TireState()
        self._lap_temps: list[tuple[float, float, float, float]] = []
        self._last_lap: int = 0

    @property
    def state(self) -> TireState:
        return self._state

    def push_sample(self, temps: tuple[float, float, float, float], lap_number: int) -> None:
        """Push a tire temperature sample (LF, RF, LR, RR)."""
        if lap_number != self._last_lap and lap_number > 0:
            if self._last_lap > 0:
                self._finalize_lap()
            self._last_lap = lap_number
            self._current_temps: list[tuple[float, float, float, float]] = []

        if not hasattr(self, "_current_temps"):
            self._current_temps = []
        self._current_temps.append(temps)

    def _finalize_lap(self) -> None:
        if not hasattr(self, "_current_temps") or not self._current_temps:
            return

        n = len(self._current_temps)
        avg = tuple(sum(t[i] for t in self._current_temps) / n for i in range(4))
        self._lap_temps.append(avg)
        self._state.lap_count = len(self._lap_temps)
        self._state.avg_temp_lf = avg[0]
        self._state.avg_temp_rf = avg[1]
        self._state.avg_temp_lr = avg[2]
        self._state.avg_temp_rr = avg[3]

        # Estimate grip from temperature and lap count
        avg_all = sum(avg) / 4
        temp_penalty = 0.0
        if avg_all < self.OPTIMAL_TEMP_RANGE[0]:
            temp_penalty = (self.OPTIMAL_TEMP_RANGE[0] - avg_all) * 0.3
        elif avg_all > self.OPTIMAL_TEMP_RANGE[1]:
            temp_penalty = (avg_all - self.OPTIMAL_TEMP_RANGE[1]) * 0.5

        # Base degradation: ~2% per lap + temperature penalty
        base_wear = 2.0 + temp_penalty * 0.1
        self._state.wear_rate = base_wear
        self._state.grip_pct = max(0.0, 100.0 - self._state.lap_count * base_wear)
        self._state.laps_remaining = max(0, int((self._state.grip_pct - self.GRIP_THRESHOLD) / max(0.1, base_wear)))

        if self._state.grip_pct > 70:
            self._state.condition = "good"
        elif self._state.grip_pct > self.GRIP_THRESHOLD:
            self._state.condition = "worn"
        else:
            self._state.condition = "critical"

    def reset(self) -> None:
        self._state = TireState()
        self._lap_temps.clear()
        self._last_lap = 0
        if hasattr(self, "_current_temps"):
            self._current_temps.clear()
