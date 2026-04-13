"""Mode state management for the hero workflow."""
from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot

from lap_coach_logger.core.mode_detector import MODES, suggest_mode


class ModeViewModel(QObject):

    modeChanged = Signal()
    bannerChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._active_mode = "sprint"
        self._banner_visible = False
        self._session_type = ""
        self._race_duration_s = 0.0

    @Property(str, notify=modeChanged)
    def activeMode(self) -> str:
        return self._active_mode

    @Property(bool, notify=bannerChanged)
    def bannerVisible(self) -> bool:
        return self._banner_visible

    @Property(str, notify=modeChanged)
    def sessionType(self) -> str:
        return self._session_type

    @Slot(str)
    def setMode(self, mode: str) -> None:
        if mode in MODES:
            self._active_mode = mode
            self.modeChanged.emit()

    @Slot()
    def dismissBanner(self) -> None:
        self._banner_visible = False
        self.bannerChanged.emit()

    def onSessionDetected(self, session_type: str, race_duration_s: float, is_timed: bool) -> None:
        self._session_type = session_type
        self._race_duration_s = race_duration_s
        self._active_mode = suggest_mode(session_type, race_duration_s, is_timed)
        self._banner_visible = True
        self.modeChanged.emit()
        self.bannerChanged.emit()
