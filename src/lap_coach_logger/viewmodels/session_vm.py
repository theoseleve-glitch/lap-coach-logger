"""SessionViewModel -- live telemetry state for the QML Live page and Dashboard hero.

Receives coordinator snapshots (dicts) and extracts telemetry data.
The bootstrap layer wires ``service.snapshot_changed.connect(session_vm.update_from_snapshot)``.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from statistics import mean, stdev

from PySide6.QtCore import Property, QObject, Signal, Slot

log = logging.getLogger(__name__)

_SPEED_HISTORY_MAX = 180


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_time(seconds: float) -> str:
    """Format lap time as ``M:SS.mmm``.  Returns ``'\u2014'`` for <= 0."""
    if seconds <= 0:
        return "\u2014"
    minutes, secs = divmod(seconds, 60)
    whole = int(secs)
    millis = round((secs - whole) * 1000)
    return f"{int(minutes)}:{whole:02d}.{millis:03d}"


def _format_delta(seconds: float) -> str:
    """Format delta vs best as ``+X.XXX`` / ``-X.XXX``.  Returns ``'BEST'`` for 0."""
    if seconds == 0.0:
        return "BEST"
    sign = "+" if seconds > 0 else "-"
    return f"{sign}{abs(seconds):.3f}"


# ---------------------------------------------------------------------------
# ViewModel
# ---------------------------------------------------------------------------

class SessionViewModel(QObject):
    """Exposes live session telemetry as flat, QML-bindable properties."""

    # -- change signals ----------------------------------------------------
    trackChanged = Signal()
    lapChanged = Signal()
    timesChanged = Signal()
    telemetryChanged = Signal()
    lapsChanged = Signal()

    # -- construction ------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()

        # Track / car / sim
        self._track: str = ""
        self._car: str = ""
        self._sim: str = ""

        # Current lap
        self._current_lap: int = 0

        # Lap timing
        self._last_lap_time: str = "\u2014"
        self._best_lap_time: str = "\u2014"
        self._best_lap_number: int = 0
        self._last_lap_delta: str = ""
        self._consistency_pct: float = 100.0
        self._consistency_sigma: str = ""

        # Live telemetry
        self._speed_kph: float = 0.0
        self._throttle_pct: float = 0.0
        self._brake_pct: float = 0.0

        # Lap list and speed history
        self._laps: list[dict] = []
        self._speed_history: deque[float] = deque(maxlen=_SPEED_HISTORY_MAX)

    # -- QML properties ----------------------------------------------------

    @Property(str, notify=trackChanged)
    def track(self) -> str:
        return self._track

    @Property(str, notify=trackChanged)
    def car(self) -> str:
        return self._car

    @Property(str, notify=trackChanged)
    def sim(self) -> str:
        return self._sim

    @Property(int, notify=lapChanged)
    def currentLap(self) -> int:  # noqa: N802
        return self._current_lap

    @Property(str, notify=timesChanged)
    def lastLapTime(self) -> str:  # noqa: N802
        return self._last_lap_time

    @Property(str, notify=timesChanged)
    def bestLapTime(self) -> str:  # noqa: N802
        return self._best_lap_time

    @Property(int, notify=timesChanged)
    def bestLapNumber(self) -> int:  # noqa: N802
        return self._best_lap_number

    @Property(str, notify=timesChanged)
    def lastLapDelta(self) -> str:  # noqa: N802
        return self._last_lap_delta

    @Property(float, notify=timesChanged)
    def consistencyPct(self) -> float:  # noqa: N802
        return self._consistency_pct

    @Property(str, notify=timesChanged)
    def consistencySigma(self) -> str:  # noqa: N802
        return self._consistency_sigma

    @Property(float, notify=telemetryChanged)
    def speedKph(self) -> float:  # noqa: N802
        return self._speed_kph

    @Property(float, notify=telemetryChanged)
    def throttlePct(self) -> float:  # noqa: N802
        return self._throttle_pct

    @Property(float, notify=telemetryChanged)
    def brakePct(self) -> float:  # noqa: N802
        return self._brake_pct

    @Property("QVariant", notify=lapsChanged)
    def laps(self) -> list[dict]:
        return self._laps

    @Property("QVariant", notify=lapsChanged)
    def speedHistory(self) -> deque[float]:  # noqa: N802
        return self._speed_history

    # -- public API --------------------------------------------------------

    def update_from_snapshot(self, snap: dict) -> None:
        """Read a coordinator snapshot dict and update all properties."""
        self._update_track_car_sim(snap)
        self._update_current_lap(snap)
        self._update_live_telemetry(snap)
        self._update_lap_times(snap)

    @Slot()
    def clear(self) -> None:
        """Reset all state to defaults."""
        self._track = ""
        self._car = ""
        self._sim = ""
        self._current_lap = 0
        self._last_lap_time = "\u2014"
        self._best_lap_time = "\u2014"
        self._best_lap_number = 0
        self._last_lap_delta = ""
        self._consistency_pct = 100.0
        self._consistency_sigma = ""
        self._speed_kph = 0.0
        self._throttle_pct = 0.0
        self._brake_pct = 0.0
        self._laps = []
        self._speed_history = deque(maxlen=_SPEED_HISTORY_MAX)

        self.trackChanged.emit()
        self.lapChanged.emit()
        self.timesChanged.emit()
        self.telemetryChanged.emit()
        self.lapsChanged.emit()

    # -- internal helpers --------------------------------------------------

    def _update_track_car_sim(self, snap: dict) -> None:
        new_track = snap.get("track") or ""
        new_car = snap.get("car") or ""
        new_sim = snap.get("sim") or ""

        changed = False
        if new_track != self._track:
            self._track = new_track
            changed = True
        if new_car != self._car:
            self._car = new_car
            changed = True
        if new_sim != self._sim:
            self._sim = new_sim
            changed = True

        if changed:
            self.trackChanged.emit()

    def _update_current_lap(self, snap: dict) -> None:
        new_lap = int(snap.get("current_lap", 0))
        if new_lap != self._current_lap:
            self._current_lap = new_lap
            self.lapChanged.emit()

    def _update_live_telemetry(self, snap: dict) -> None:
        live = snap.get("live") or {}
        self._speed_kph = float(live.get("speed_kph", 0.0))
        self._throttle_pct = float(live.get("throttle_pct", 0.0))
        self._brake_pct = float(live.get("brake_pct", 0.0))

        if self._speed_kph > 0.0:
            self._speed_history.append(self._speed_kph)

        self.telemetryChanged.emit()

    def _update_lap_times(self, snap: dict) -> None:
        raw_laps: list[dict] = snap.get("lap_times") or []
        if not raw_laps:
            # No change if empty and already empty
            if self._laps:
                self._laps = []
                self._last_lap_time = "\u2014"
                self._best_lap_time = "\u2014"
                self._best_lap_number = 0
                self._last_lap_delta = ""
                self._consistency_pct = 100.0
                self._consistency_sigma = ""
                self.timesChanged.emit()
                self.lapsChanged.emit()
            return

        # Find best valid lap
        valid_times = [
            lap for lap in raw_laps
            if lap.get("status") == "valid" and lap.get("time_s", 0) > 0
        ]

        best_time_s = min((l["time_s"] for l in valid_times), default=0.0)
        best_lap_num = 0
        if best_time_s > 0:
            for lap in valid_times:
                if lap["time_s"] == best_time_s:
                    best_lap_num = lap["lap"]
                    break

        # Build formatted laps list
        laps_out: list[dict] = []
        for lap in raw_laps:
            time_s = lap.get("time_s", 0.0)
            is_valid = lap.get("status") == "valid" and time_s > 0
            delta_s = (time_s - best_time_s) if (is_valid and best_time_s > 0) else 0.0
            laps_out.append({
                "lap": lap["lap"],
                "time": _format_time(time_s),
                "time_s": time_s,
                "delta": _format_delta(delta_s) if is_valid else "",
                "status": lap.get("status", ""),
                "is_best": lap["lap"] == best_lap_num and is_valid,
            })

        self._laps = laps_out
        self._best_lap_number = best_lap_num
        self._best_lap_time = _format_time(best_time_s)

        # Last lap info
        last = raw_laps[-1]
        last_time_s = last.get("time_s", 0.0)
        self._last_lap_time = _format_time(last_time_s)
        if last.get("status") == "valid" and last_time_s > 0 and best_time_s > 0:
            self._last_lap_delta = _format_delta(last_time_s - best_time_s)
        else:
            self._last_lap_delta = ""

        # Consistency
        self._compute_consistency(valid_times)

        self.timesChanged.emit()
        self.lapsChanged.emit()

    def _compute_consistency(self, valid_laps: list[dict]) -> None:
        times = [lap["time_s"] for lap in valid_laps if lap["time_s"] > 0]
        if len(times) < 2:
            self._consistency_pct = 100.0
            self._consistency_sigma = ""
            return

        m = mean(times)
        s = stdev(times)
        if m > 0:
            self._consistency_pct = round((1.0 - s / m) * 100.0, 1)
        else:
            self._consistency_pct = 100.0
        self._consistency_sigma = f"\u03c3 {s:.2f}s"
