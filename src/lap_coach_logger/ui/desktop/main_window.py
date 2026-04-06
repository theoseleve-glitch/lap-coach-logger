"""Main PySide6 desktop shell window and tray integration."""

from __future__ import annotations

import ctypes
import sys
from datetime import datetime

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QCloseEvent, QIcon
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from lap_coach_logger import APP_NAME, __version__
from lap_coach_logger.app_identity import APP_ID, COMPANY_NAME
from lap_coach_logger.assets import app_icon_path, monogram_path, tray_icon_path
from lap_coach_logger.config.manager import ConfigManager
from lap_coach_logger.config.models import AppConfig
from lap_coach_logger.core.session_coordinator import SessionCoordinator
from lap_coach_logger.detection.process_watcher import ProcessWatcher
from lap_coach_logger.ui.desktop.about_dialog import AboutDialog
from lap_coach_logger.ui.desktop.panels import DashboardPanel, HistoryPanel, LivePanel, LogsPanel, ReviewPanel
from lap_coach_logger.ui.desktop.service import DesktopService
from lap_coach_logger.ui.desktop.settings_dialog import SettingsDialog
from lap_coach_logger.ui.desktop.theme import (
    APP_STYLESHEET,
    STATUS_COLORS,
    WINDOW_MIN_HEIGHT,
    WINDOW_MIN_WIDTH,
    ASPHALT,
    CONCRETE,
    STEEL,
    CHALK,
    PIT_ORANGE,
    ACID_GREEN,
)
from lap_coach_logger.utils.single_instance import InstanceSignalServer


def datetime_now_for_file() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


class _RestoreEmitter(QObject):
    restore_requested = Signal()


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        service: DesktopService,
        on_exit,
    ) -> None:  # noqa: ANN001
        super().__init__()
        self._service = service
        self._on_exit = on_exit
        self._allow_close = False
        self._restore_emitter = _RestoreEmitter(self)
        self._restore_emitter.restore_requested.connect(self._restore)
        self._signal_server = InstanceSignalServer(
            lambda: self._restore_emitter.restore_requested.emit()
        )

        self.setWindowTitle(f"{APP_NAME}  v{__version__}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        icon_path = app_icon_path()
        if icon_path is not None and icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._build_ui()
        self._build_tray()
        self._wire_events()
        self._signal_server.start()

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        wrap = QHBoxLayout(root)
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(16, 20, 16, 16)
        sb_layout.setSpacing(6)

        # Monogram
        mono_svg = monogram_path()
        if mono_svg and mono_svg.exists():
            mono = QSvgWidget(str(mono_svg))
            mono.setFixedSize(48, 48)
            mono.setStyleSheet("background:transparent;")
            sb_layout.addWidget(mono)
            sb_layout.addSpacing(6)

        title = QLabel("LAP")
        title.setObjectName("AppTitle")
        subtitle = QLabel("COACH")
        subtitle.setObjectName("AppSubtitle")
        sb_layout.addWidget(title)
        sb_layout.addWidget(subtitle)
        sb_layout.addSpacing(16)

        self.nav = QListWidget()
        for name in ("DASHBOARD", "LIVE", "LOGS", "HISTORY"):
            self.nav.addItem(QListWidgetItem(name))
        self.nav.setCurrentRow(0)
        sb_layout.addWidget(self.nav, 1)

        self.btn_settings = QPushButton("SETTINGS")
        self.btn_settings.setObjectName("PrimaryButton")
        sb_layout.addWidget(self.btn_settings)

        self.btn_about = QPushButton("ABOUT")
        sb_layout.addWidget(self.btn_about)

        wrap.addWidget(sidebar)

        right = QFrame()
        right.setStyleSheet(f"background-color:{ASPHALT};")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(16, 10, 16, 10)
        topbar_layout.setSpacing(10)

        self.lbl_status = QLabel("IDLE")
        self.lbl_status.setStyleSheet(
            f"font-size:13px; font-weight:700; letter-spacing:2px;"
            f" font-family:'Consolas','Space Mono',monospace; color:{STEEL};"
        )
        self.lbl_state_detail = QLabel("Waiting for sim")
        self.lbl_state_detail.setStyleSheet(f"color:{STEEL}; font-size:12px;")
        topbar_layout.addWidget(self.lbl_status)
        topbar_layout.addWidget(self.lbl_state_detail)
        topbar_layout.addStretch(1)

        self.btn_start = QPushButton("START")
        self.btn_start.setObjectName("PrimaryButton")
        self.btn_stop = QPushButton("STOP")
        self.btn_stop.setObjectName("DangerButton")
        self.btn_open_output = QPushButton("OUTPUT")
        self.btn_open_logs = QPushButton("LOGS")
        self.btn_open_config = QPushButton("CONFIG")
        topbar_layout.addWidget(self.btn_start)
        topbar_layout.addWidget(self.btn_stop)
        topbar_layout.addWidget(self.btn_open_output)
        topbar_layout.addWidget(self.btn_open_logs)
        topbar_layout.addWidget(self.btn_open_config)

        right_layout.addWidget(topbar)

        self.stack = QStackedWidget()
        self.dashboard = DashboardPanel()
        self.live = LivePanel()
        self.logs = LogsPanel()
        self.history = HistoryPanel()
        self.review = ReviewPanel()
        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.live)
        self.stack.addWidget(self.logs)
        self.stack.addWidget(self.history)
        self.stack.addWidget(self.review)
        right_layout.addWidget(self.stack, 1)

        wrap.addWidget(right, 1)

    def _build_tray(self) -> None:
        icon_path = tray_icon_path()
        icon = QIcon(str(icon_path)) if icon_path is not None and icon_path.exists() else self.windowIcon()
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip(APP_NAME)

        menu = self.tray.contextMenu() or self._create_tray_menu()
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _create_tray_menu(self):
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        act_show = QAction("Show", self)
        act_show.triggered.connect(self._restore)
        menu.addAction(act_show)

        act_output = QAction("Open Output Folder", self)
        act_output.triggered.connect(self._service.open_output_folder)
        menu.addAction(act_output)

        act_logs = QAction("Open Logs Folder", self)
        act_logs.triggered.connect(self._service.open_logs_folder)
        menu.addAction(act_logs)

        act_config = QAction("Open Config Folder", self)
        act_config.triggered.connect(self._service.open_config_folder)
        menu.addAction(act_config)

        act_start = QAction("Start Monitoring", self)
        act_start.triggered.connect(self._service.start_monitoring)
        menu.addAction(act_start)

        act_stop = QAction("Stop Monitoring", self)
        act_stop.triggered.connect(self._service.stop_monitoring)
        menu.addAction(act_stop)

        menu.addSeparator()
        act_exit = QAction("Exit", self)
        act_exit.triggered.connect(self._exit_requested)
        menu.addAction(act_exit)
        return menu

    def _wire_events(self) -> None:
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.btn_settings.clicked.connect(self._open_settings)
        self.btn_about.clicked.connect(self._open_about)
        self.btn_start.clicked.connect(self._service.start_monitoring)
        self.btn_stop.clicked.connect(self._service.stop_monitoring)
        self.btn_open_output.clicked.connect(self._service.open_output_folder)
        self.btn_open_logs.clicked.connect(self._service.open_logs_folder)
        self.btn_open_config.clicked.connect(self._service.open_config_folder)

        self.dashboard.btn_start.clicked.connect(self._service.start_monitoring)
        self.dashboard.btn_stop.clicked.connect(self._service.stop_monitoring)
        self.dashboard.btn_output.clicked.connect(self._service.open_output_folder)
        self.dashboard.btn_logs.clicked.connect(self._service.open_logs_folder)
        self.dashboard.btn_config.clicked.connect(self._service.open_config_folder)
        self.dashboard.btn_settings.clicked.connect(self._open_settings)

        self.history.btn_refresh.clicked.connect(self._service.refresh_history)
        self.history.btn_review.clicked.connect(self._review_selected_history)
        self.history.btn_open.clicked.connect(self._open_selected_history)
        self.history.btn_reprocess.clicked.connect(self._reprocess_selected_history)
        self.history.btn_marked.clicked.connect(self._toggle_selected_history_ignored)
        self.history.btn_export.clicked.connect(self._export_selected_history_csv)
        self.history.btn_copy_id.clicked.connect(self._copy_selected_history_id)
        self.history.btn_delete.clicked.connect(self._delete_selected_history)

        self.review.btn_open_folder.clicked.connect(self._open_current_review_folder)
        self.review.btn_reprocess.clicked.connect(self._reprocess_current_review)
        self.review.btn_ignore.clicked.connect(self._toggle_current_review_ignored)
        self.review.btn_delete.clicked.connect(self._delete_current_review)
        self.review.btn_return.clicked.connect(self._return_to_history)

        self._service.snapshot_changed.connect(self._on_snapshot)
        self._service.history_changed.connect(self.history.update_sessions)
        self._service.review_changed.connect(self.review.update_review)
        self._service.review_requested.connect(self._show_review)
        self._service.log_event.connect(self.logs.append_event)
        self.logs.export_support_requested.connect(self._export_support_bundle)
        self._service.settings_saved.connect(self._toast)
        self._service.settings_failed.connect(self._show_error)

    def _on_snapshot(self, snap: dict) -> None:
        status = str(snap.get("status", "Idle"))
        color = STATUS_COLORS.get(status, STEEL)
        self.lbl_status.setText(status.upper())
        self.lbl_status.setStyleSheet(
            f"font-size:13px; font-weight:700; letter-spacing:2px;"
            f" font-family:'Consolas','Space Mono',monospace; color:{color};"
        )
        self.lbl_state_detail.setText(str(snap.get("status_detail") or "Ready"))
        self.lbl_state_detail.setText(str(snap.get("status_detail") or "Ready"))

        self.dashboard.update_snapshot(snap)
        self.live.update_snapshot(snap)
        self.logs.update_context(snap)

    def _export_support_bundle(self, current_session_only: bool) -> None:
        default_name = datetime_now_for_file()
        export_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Support Bundle",
            f"lap_coach_support_{default_name}.zip",
            "ZIP Files (*.zip)",
        )
        if not export_path:
            return
        ok, message = self._service.export_support_bundle(
            export_path,
            current_session_only=current_session_only,
        )
        if ok:
            self._toast("Support bundle exported")
        else:
            self._show_error(f"Support bundle export failed: {message}")

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self._service.settings_snapshot(), self)
        if dlg.exec():
            self._service.save_settings(dlg.values())

    def _open_about(self) -> None:
        dlg = AboutDialog(install_path=str(sys.executable), parent=self)
        dlg.exec()

    def _open_selected_history(self) -> None:
        path = self.history.selected_folder()
        if path:
            self._service.open_path(path)

    def _reprocess_selected_history(self) -> None:
        path = self.history.selected_folder()
        if not path:
            return
        answer = QMessageBox.question(
            self,
            "Reprocess Session",
            "Reprocess this session (lap classification, quality validation)? This will update the saved data.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.reprocess_review(path, navigate=False)
            self._toast("Session reprocessed")
        except Exception as exc:
            self._show_error(f"Reprocess failed: {exc}")

    def _toggle_selected_history_ignored(self) -> None:
        path = self.history.selected_folder()
        if not path:
            return
        session = None
        for s in self.history._sessions:
            if s.get("folder") == path:
                session = s
                break
        if not session:
            return
        
        is_ignored = session.get("review_status") == "ignored"
        new_status = "ready" if is_ignored else "ignored"
        try:
            self._service.mark_review_ignored(path, ignored=not is_ignored)
            self._toast(f"Session marked as {new_status}")
        except Exception as exc:
            self._show_error(f"Failed to update status: {exc}")

    def _export_selected_history_csv(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        path = self.history.selected_folder()
        if not path:
            return
        
        session_name = self.history.selected_session_name() or "session"
        filename = f"{session_name}_telemetry.csv"
        
        export_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Session Telemetry",
            filename,
            "CSV Files (*.csv);;All Files (*.*)",
        )
        
        if not export_path:
            return
        
        try:
            if self._service.export_session_csv(path, export_path):
                self._toast(f"Exported to {export_path}")
            else:
                self._show_error("Failed to export CSV")
        except Exception as exc:
            self._show_error(f"Export failed: {exc}")

    def _copy_selected_history_id(self) -> None:
        session_id = self.history.selected_session_id()
        if not session_id:
            return
        
        from PySide6.QtGui import QClipboard
        clipboard = QApplication.clipboard()
        clipboard.setText(session_id, QClipboard.Mode.Clipboard)
        self._toast(f"Session ID copied: {session_id[:8]}...")

    def _delete_selected_history(self) -> None:
        path = self.history.selected_folder()
        if not path:
            return
        
        session_name = self.history.selected_session_name() or "session"
        answer = QMessageBox.question(
            self,
            "Delete Session",
            f"Delete '{session_name}' and all saved data? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        
        try:
            self._service.delete_review_session(path)
            self._toast("Session deleted")
        except Exception as exc:
            self._show_error(f"Delete failed: {exc}")

    def _review_selected_history(self) -> None:
        path = self.history.selected_folder()
        if path:
            try:
                self._service.open_review(path, navigate=True)
            except Exception as exc:
                self._show_error(str(exc))

    def _show_review(self, review: dict) -> None:
        self.review.update_review(review)
        self.stack.setCurrentWidget(self.review)

    def _open_current_review_folder(self) -> None:
        path = self.review.current_path()
        if path:
            self._service.open_path(path)

    def _reprocess_current_review(self) -> None:
        path = self.review.current_path()
        if not path:
            return
        try:
            self._service.reprocess_review(path, navigate=True)
            self._toast("Session reprocessed")
        except Exception as exc:
            self._show_error(str(exc))

    def _toggle_current_review_ignored(self) -> None:
        path = self.review.current_path()
        if not path:
            return
        ignored = self.review.btn_ignore.text() == "MARK IGNORED"
        try:
            self._service.mark_review_ignored(path, ignored=ignored)
            self._toast("Session ignored" if ignored else "Session restored")
        except Exception as exc:
            self._show_error(str(exc))

    def _delete_current_review(self) -> None:
        path = self.review.current_path()
        if not path:
            return
        answer = QMessageBox.question(
            self,
            "Delete Local Copy",
            "Delete this saved session bundle from disk? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self._service.delete_review_session(path)
            self._return_to_history()
            self._toast("Session deleted")
        except Exception as exc:
            self._show_error(str(exc))

    def _return_to_history(self) -> None:
        self.nav.setCurrentRow(3)
        self.stack.setCurrentWidget(self.history)

    def _toast(self, message: str) -> None:
        self.statusBar().showMessage(message, 4000)

    def _show_error(self, message: str) -> None:
        QMessageBox.critical(self, "Settings Error", message)

    def _on_tray_activated(self, reason) -> None:  # noqa: ANN001
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._restore()

    def _restore(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _exit_requested(self) -> None:
        self._allow_close = True
        self._on_exit()
        QApplication.quit()
        self.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._allow_close:
            self.tray.hide()
            self._signal_server.stop()
            event.accept()
            return
        self.hide()
        self.tray.showMessage(APP_NAME, "Running in tray. Use the tray icon to reopen or exit.")
        event.ignore()


def run_desktop_shell(
    *,
    config: AppConfig,
    config_manager: ConfigManager,
    coordinator: SessionCoordinator,
    watcher: ProcessWatcher,
    on_exit,
) -> None:  # noqa: ANN001
    # Ensure proper taskbar grouping and app identity in Windows shell.
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(COMPANY_NAME)
    app.setApplicationVersion(__version__)
    app.setStyleSheet(APP_STYLESHEET)

    service = DesktopService(
        config=config,
        config_manager=config_manager,
        coordinator=coordinator,
        watcher=watcher,
    )
    service.start()

    window = MainWindow(service=service, on_exit=on_exit)
    window.show()

    app.exec()
    service.stop()
