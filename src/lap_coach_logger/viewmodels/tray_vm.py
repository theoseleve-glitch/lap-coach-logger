"""System tray integration for QML application."""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from lap_coach_logger import APP_NAME
from lap_coach_logger.assets import tray_icon_path

log = logging.getLogger(__name__)


class TrayViewModel(QObject):
    """Manages the system tray icon and menu for QML."""

    showRequested = Signal()
    exitRequested = Signal()
    overlayToggleRequested = Signal()

    def __init__(self, app_icon: QIcon, parent: QObject | None = None) -> None:
        super().__init__(parent)
        icon_path = tray_icon_path()
        icon = QIcon(str(icon_path)) if icon_path and icon_path.exists() else app_icon

        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip(APP_NAME)
        self._tray.activated.connect(self._on_activated)

        menu = QMenu()
        act_show = QAction("Show", self)
        act_show.triggered.connect(self.showRequested)
        menu.addAction(act_show)

        act_overlay = QAction("Toggle Overlay", self)
        act_overlay.triggered.connect(self.overlayToggleRequested)
        menu.addAction(act_overlay)

        menu.addSeparator()
        act_exit = QAction("Exit", self)
        act_exit.triggered.connect(self.exitRequested)
        menu.addAction(act_exit)

        self._tray.setContextMenu(menu)

    @Slot()
    def show(self) -> None:
        self._tray.show()

    @Slot()
    def hide(self) -> None:
        self._tray.hide()

    @Slot(str)
    def showMessage(self, message: str) -> None:
        self._tray.showMessage(APP_NAME, message)

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.showRequested.emit()
