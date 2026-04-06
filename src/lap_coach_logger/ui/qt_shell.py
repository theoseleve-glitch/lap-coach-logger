"""Optional PySide6 desktop shell scaffold.

This module is intentionally isolated from the telemetry backend. It can be
adopted incrementally for a richer Windows shell while keeping current
recording/session logic unchanged.
"""

from __future__ import annotations

from typing import Callable


class QtShellNotAvailable(RuntimeError):
    """Raised when PySide6 is not installed but Qt shell was requested."""


class _ShellWindowProxy:
    """Namespace used to store Qt types when dependency is available."""

    MainWindow = None


def launch_qt_shell(
    *,
    on_open_settings: Callable[[], None],
    on_start_monitoring: Callable[[], None],
    on_stop_monitoring: Callable[[], None],
    on_exit: Callable[[], None],
) -> None:
    """Launch a minimal close-to-tray Qt shell.

    The function is kept as a small migration seam. Current app behavior still
    uses the existing tray implementation by default.
    """
    try:
        from PySide6 import QtCore, QtWidgets
        from PySide6.QtGui import QAction, QIcon
    except Exception as exc:  # pragma: no cover - optional dependency
        raise QtShellNotAvailable("PySide6 is not installed") from exc

    class _MainWindow(QtWidgets.QMainWindow):
        def closeEvent(self, event: QtCore.QEvent) -> None:  # type: ignore[override]
            self.hide()
            event.ignore()

    _ShellWindowProxy.MainWindow = _MainWindow

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)

    window = _ShellWindowProxy.MainWindow()
    window.setWindowTitle("Lap Coach Logger")
    window.resize(640, 420)

    tray = QtWidgets.QSystemTrayIcon(QIcon(), window)
    menu = QtWidgets.QMenu()

    act_show = QAction("Open", window)
    act_show.triggered.connect(window.showNormal)
    menu.addAction(act_show)

    act_settings = QAction("Settings", window)
    act_settings.triggered.connect(on_open_settings)
    menu.addAction(act_settings)

    act_start = QAction("Start Monitoring", window)
    act_start.triggered.connect(on_start_monitoring)
    menu.addAction(act_start)

    act_stop = QAction("Stop Monitoring", window)
    act_stop.triggered.connect(on_stop_monitoring)
    menu.addAction(act_stop)

    menu.addSeparator()
    act_exit = QAction("Exit", window)
    act_exit.triggered.connect(on_exit)
    menu.addAction(act_exit)

    tray.setContextMenu(menu)
    tray.setToolTip("Lap Coach Logger")
    tray.show()

    window.show()
    app.exec()
