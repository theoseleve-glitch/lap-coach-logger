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

    # -- construction ----------------------------------------------------------

    def __init__(self) -> None:
        super().__init__()

        # Telemetry inputs
        self._speed_kph: float = 0.0
        self._throttle_pct: float = 0.0
        self._brake_pct: float = 0.0

        # Lap timing
        self._last_time: str = ""
        self._best_time: str = ""
        self._last_delta: str = ""
        self._sector_states: list = []

        # Context
        self._lap_number: int = 0
        self._track: str = ""
        self._is_recording: bool = False
        self._elapsed: str = ""

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

    # -- public API ------------------------------------------------------------

    def update_from_snapshot(self, snap: dict) -> None:
        """Read a coordinator snapshot and update all overlay properties."""
        live = snap.get("live") or {}

        # Telemetry inputs
        self._speed_kph = float(live.get("speed_kph", 0.0))
        self._throttle_pct = float(live.get("throttle_pct", 0.0))
        self._brake_pct = float(live.get("brake_pct", 0.0))
        self._lap_number = int(live.get("current_lap", 0))
        self.inputsChanged.emit()

        # Context
        self._track = snap.get("track") or snap.get("sim") or ""
        self._is_recording = snap.get("status") == "Recording"
        self.contextChanged.emit()
