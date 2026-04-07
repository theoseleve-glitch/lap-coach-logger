"""OverlayViewModel -- live HUD overlay bridge for QML.

Reads coordinator snapshots and exposes telemetry and context
properties for a floating overlay / HUD panel.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Property, QObject, Signal

log = logging.getLogger(__name__)


class OverlayViewModel(QObject):
    """Exposes live overlay HUD state as flat, QML-bindable properties."""

    # -- change signals --------------------------------------------------------
    timesChanged = Signal()
    inputsChanged = Signal()
    contextChanged = Signal()
    fuelChanged = Signal()

    # -- construction ----------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()

        # Telemetry inputs
        self._speed_kph: float = 0.0
        self._throttle_pct: float = 0.0
        self._brake_pct: float = 0.0
        self._steering_deg: float = 0.0
        self._lat_accel_g: float = 0.0
        self._long_accel_g: float = 0.0
        self._lap_progress: float = 0.0
        self._lap_dist_pct: float = 0.0

        # Lap timing
        self._last_time: str = ""
        self._best_time: str = ""
        self._last_delta: str = ""
        self._sector_states: list = []

        # Context
        self._lap_number: int = 0
        self._track: str = ""
        self._car: str = ""
        self._is_recording: bool = False
        self._elapsed: str = ""
        self._gear: int = 0
        self._rpm: int = 0

        # Fuel
        self._fuel_level: float = 0.0
        self._fuel_per_lap: float = 0.0
        self._fuel_laps_left: float = 0.0
        self._fuel_state: str = "SAFE"
        self._prev_fuel_level: float = 0.0
        self._lap_fuel_samples: list[float] = []

    # -- QML properties --------------------------------------------------------

    @Property(float, notify=inputsChanged)
    def speedKph(self) -> float:  # noqa: N802
        """Current speed in km/h."""
        return self._speed_kph

    @Property(float, notify=inputsChanged)
    def throttlePct(self) -> float:  # noqa: N802
        """Throttle position as a percentage (0-100)."""
        return self._throttle_pct

    @Property(float, notify=inputsChanged)
    def brakePct(self) -> float:  # noqa: N802
        """Brake position as a percentage (0-100)."""
        return self._brake_pct

    @Property(str, notify=timesChanged)
    def lastTime(self) -> str:  # noqa: N802
        """Formatted last lap time."""
        return self._last_time

    @Property(str, notify=timesChanged)
    def bestTime(self) -> str:  # noqa: N802
        """Formatted best lap time."""
        return self._best_time

    @Property(str, notify=timesChanged)
    def lastDelta(self) -> str:  # noqa: N802
        """Delta vs best as ``+X.XXX`` / ``-X.XXX``."""
        return self._last_delta

    @Property("QVariant", notify=timesChanged)
    def sectorStates(self) -> list:  # noqa: N802
        """Sector state list for sector indicator display."""
        return self._sector_states

    @Property(int, notify=contextChanged)
    def lapNumber(self) -> int:  # noqa: N802
        """Current lap number."""
        return self._lap_number

    @Property(str, notify=contextChanged)
    def track(self) -> str:
        """Track name (falls back to sim name)."""
        return self._track

    @Property(bool, notify=contextChanged)
    def isRecording(self) -> bool:  # noqa: N802
        """Whether the session is actively recording."""
        return self._is_recording

    @Property(str, notify=contextChanged)
    def elapsed(self) -> str:
        """Formatted elapsed session time."""
        return self._elapsed

    @Property(float, notify=inputsChanged)
    def steeringDeg(self) -> float:  # noqa: N802
        return self._steering_deg

    @Property(float, notify=inputsChanged)
    def latAccelG(self) -> float:  # noqa: N802
        return self._lat_accel_g

    @Property(float, notify=inputsChanged)
    def longAccelG(self) -> float:  # noqa: N802
        return self._long_accel_g

    @Property(int, notify=contextChanged)
    def gear(self) -> int:
        return self._gear

    @Property(int, notify=contextChanged)
    def rpm(self) -> int:
        return self._rpm

    @Property(str, notify=contextChanged)
    def car(self) -> str:
        return self._car

    @Property(float, notify=inputsChanged)
    def lapProgress(self) -> float:  # noqa: N802
        return self._lap_progress

    @Property(float, notify=inputsChanged)
    def lapDistPct(self) -> float:  # noqa: N802
        return self._lap_dist_pct

    @Property(float, notify=fuelChanged)
    def fuelLevel(self) -> float:  # noqa: N802
        return self._fuel_level

    @Property(float, notify=fuelChanged)
    def fuelPerLap(self) -> float:  # noqa: N802
        return self._fuel_per_lap

    @Property(float, notify=fuelChanged)
    def fuelLapsLeft(self) -> float:  # noqa: N802
        return self._fuel_laps_left

    @Property(str, notify=fuelChanged)
    def fuelState(self) -> str:  # noqa: N802
        return self._fuel_state

    # -- public API ------------------------------------------------------------

    def update_from_snapshot(self, snap: dict) -> None:
        """Read a coordinator snapshot and update all overlay properties."""
        live = snap.get("live") or {}

        # Telemetry inputs
        self._speed_kph = float(live.get("speed_kph", 0.0))
        self._throttle_pct = float(live.get("throttle_pct", 0.0))
        self._brake_pct = float(live.get("brake_pct", 0.0))
        self._steering_deg = float(live.get("steering_deg", 0.0))
        self._lat_accel_g = float(live.get("lat_accel_g", 0.0))
        self._long_accel_g = float(live.get("long_accel_g", 0.0))
        self._lap_dist_pct = float(live.get("lap_dist_pct") or 0.0)
        self._lap_progress = self._lap_dist_pct * 100.0
        self._lap_number = int(live.get("lap_number") or live.get("current_lap", 0))
        self._gear = int(live.get("gear", 0))
        self._rpm = int(live.get("rpm", 0))
        self.inputsChanged.emit()

        # Context
        self._track = str(live.get("track_name") or snap.get("track") or snap.get("sim") or "")
        self._car = str(live.get("car_name") or snap.get("car") or "")
        self._is_recording = str(snap.get("status", "")).lower() == "recording"
        self.contextChanged.emit()

        # Fuel calculation
        fuel = float(live.get("fuel_level", 0.0))
        if fuel > 0:
            # Track fuel consumption per lap
            if self._prev_fuel_level > 0 and fuel < self._prev_fuel_level:
                consumed = self._prev_fuel_level - fuel
                if 0.1 < consumed < 20:  # sanity check
                    self._lap_fuel_samples.append(consumed)
                    if len(self._lap_fuel_samples) > 10:
                        self._lap_fuel_samples.pop(0)
            self._prev_fuel_level = fuel
            self._fuel_level = fuel

            if self._lap_fuel_samples:
                avg = sum(self._lap_fuel_samples) / len(self._lap_fuel_samples)
                self._fuel_per_lap = round(avg, 2)
                self._fuel_laps_left = round(fuel / avg, 1) if avg > 0 else 0.0

                # Determine state
                laps_remaining = int(snap.get("total_laps", 0)) - self._lap_number
                if laps_remaining <= 0:
                    laps_remaining = 99
                if self._fuel_laps_left < 1.5:
                    self._fuel_state = "BOX"
                elif self._fuel_laps_left < laps_remaining * 0.85:
                    self._fuel_state = "SAVE"
                elif self._fuel_laps_left < laps_remaining * 1.05:
                    self._fuel_state = "TIGHT"
                else:
                    self._fuel_state = "SAFE"
            self.fuelChanged.emit()
