"""Main PySide6 desktop shell window and tray integration."""

from __future__ import annotations

import ctypes
import sys
from datetime import datetime

from PySide6.QtCore import QObject, Qt, Signal
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
from lap_coach_logger.ui.desktop.overlay import TelemetryOverlayWindow
from lap_coach_logger.ui.desktop.overlay_browser import OverlayWorkspaceShellCallbacks, build_overlay_browser_frontend
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
from lap_coach_logger.ui.desktop.workspaces import (
    DashboardPanel,
    HistoryPanel,
    LivePanel,
    LogsPanel,
    ReviewPanel,
    WorkspaceShellCallbacks,
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
        self._latest_snapshot: dict[str, object] = {}
        self._restore_emitter = _RestoreEmitter(self)
        self._restore_emitter.restore_requested.connect(self._restore)
        self._signal_server = InstanceSignalServer(
            lambda: self._restore_emitter.restore_requested.emit()
        )
        self._overlay = TelemetryOverlayWindow(service=service)
        self._overlay_browser = build_overlay_browser_frontend(
            parent=self,
            shell_callbacks=self._build_overlay_shell_callbacks(),
        )

        self.setWindowTitle(f"{APP_NAME}  v{__version__}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        icon_path = app_icon_path()
        if icon_path is not None and icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._build_ui()
        self._build_tray()
        self._wire_events()
        self._on_navigation_changed(self.nav.currentRow())
        self._overlay.visibility_changed.connect(self._sync_overlay_controls)
        self._apply_overlay_preferences()
        self._signal_server.start()

    def _build_workspace_shell_callbacks(self) -> WorkspaceShellCallbacks:
        return WorkspaceShellCallbacks(
            switch_page=self._switch_to_page,
            step_page=self._step_page,
            open_settings=self._open_settings,
            open_about=self._open_about,
            open_output=self._service.open_output_folder,
            open_logs=self._service.open_logs_folder,
            open_config=self._service.open_config_folder,
            resume_monitoring=self._service.start_monitoring,
            pause_monitoring=self._service.stop_monitoring,
        )

    def _build_overlay_shell_callbacks(self) -> OverlayWorkspaceShellCallbacks:
        return OverlayWorkspaceShellCallbacks(
            switch_page=self._switch_to_page,
            step_page=self._step_page,
            open_settings=self._open_settings,
            open_about=self._open_about,
            open_output=self._service.open_output_folder,
            open_logs=self._service.open_logs_folder,
            open_config=self._service.open_config_folder,
            resume_monitoring=self._service.start_monitoring,
            pause_monitoring=self._service.stop_monitoring,
        )

    def _build_ui(self) -> None:
        root = QWidget()
        self.setCentralWidget(root)

        wrap = QHBoxLayout(root)
        wrap.setContentsMargins(0, 0, 0, 0)
        wrap.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(192)
        self._shell_sidebar = sidebar
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(14, 18, 14, 14)
        sb_layout.setSpacing(10)

        brand_block = QFrame()
        brand_block.setObjectName("SidebarBrandBlock")
        brand_layout = QHBoxLayout(brand_block)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(10)

        mono_wrap = QFrame()
        mono_wrap.setObjectName("SidebarMonoWrap")
        mono_layout = QVBoxLayout(mono_wrap)
        mono_layout.setContentsMargins(0, 0, 0, 0)
        mono_layout.setSpacing(0)
        mono_svg = monogram_path()
        if mono_svg and mono_svg.exists():
            mono = QSvgWidget(str(mono_svg))
            mono.setFixedSize(34, 34)
            mono.setStyleSheet("background:transparent;")
            mono_layout.addWidget(mono, 0, Qt.AlignmentFlag.AlignCenter)
        brand_layout.addWidget(mono_wrap, 0, Qt.AlignmentFlag.AlignTop)

        brand_copy = QWidget()
        brand_copy_layout = QVBoxLayout(brand_copy)
        brand_copy_layout.setContentsMargins(0, 0, 0, 0)
        brand_copy_layout.setSpacing(2)

        title = QLabel("LAP COACH")
        title.setObjectName("AppTitle")
        subtitle = QLabel("Desktop telemetry")
        subtitle.setObjectName("AppSubtitle")
        brand_copy_layout.addWidget(title)
        brand_copy_layout.addWidget(subtitle)
        brand_layout.addWidget(brand_copy, 1)
        sb_layout.addWidget(brand_block)
        sb_layout.addSpacing(10)

        self.nav = QListWidget()
        self.nav.setObjectName("ShellNav")
        for name in ("DASHBOARD", "LIVE", "LOGS", "HISTORY", "OVERLAY"):
            self.nav.addItem(QListWidgetItem(name))
        self.nav.setCurrentRow(0)
        sb_layout.addWidget(self.nav, 1)

        utility = QFrame()
        utility.setObjectName("SidebarUtilityArea")
        utility_layout = QVBoxLayout(utility)
        utility_layout.setContentsMargins(0, 0, 0, 0)
        utility_layout.setSpacing(6)

        self.btn_settings = QPushButton("SETTINGS")
        self.btn_settings.setObjectName("SidebarUtilityButton")
        utility_layout.addWidget(self.btn_settings)

        self.btn_about = QPushButton("ABOUT")
        self.btn_about.setObjectName("SidebarUtilityButtonMuted")
        utility_layout.addWidget(self.btn_about)
        sb_layout.addWidget(utility)

        wrap.addWidget(sidebar)

        right = QFrame()
        right.setStyleSheet(f"background-color:{ASPHALT};")
        self._shell_content = right
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        topbar = QFrame()
        topbar.setObjectName("TopBar")
        self._shell_topbar = topbar
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(18, 12, 18, 12)
        topbar_layout.setSpacing(14)

        status_cluster = QFrame()
        status_cluster.setObjectName("TopBarStatusCluster")
        status_layout = QVBoxLayout(status_cluster)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(2)
        self.lbl_status = QLabel("IDLE")
        self.lbl_status.setObjectName("TopBarStatusLabel")
        self.lbl_state_detail = QLabel("Waiting for sim")
        self.lbl_state_detail.setObjectName("TopBarStatusDetail")
        status_layout.addWidget(self.lbl_status)
        status_layout.addWidget(self.lbl_state_detail)
        topbar_layout.addWidget(status_cluster)
        topbar_layout.addStretch(1)

        action_cluster = QFrame()
        action_cluster.setObjectName("TopBarActionCluster")
        action_layout = QHBoxLayout(action_cluster)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        self.btn_start = QPushButton("RESUME")
        self.btn_start.setObjectName("TopBarPrimaryAction")
        self.btn_stop = QPushButton("PAUSE")
        self.btn_stop.setObjectName("TopBarDangerAction")
        self.btn_overlay = QPushButton("OVERLAY")
        self.btn_overlay.setObjectName("TopBarUtilityAction")
        self.btn_open_output = QPushButton("OUTPUT")
        self.btn_open_output.setObjectName("TopBarUtilityAction")
        self.btn_open_logs = QPushButton("LOGS")
        self.btn_open_logs.setObjectName("TopBarUtilityAction")
        self.btn_open_config = QPushButton("CONFIG")
        self.btn_open_config.setObjectName("TopBarUtilityAction")
        action_layout.addWidget(self.btn_start)
        action_layout.addWidget(self.btn_stop)
        action_layout.addWidget(self.btn_overlay)
        action_layout.addWidget(self.btn_open_output)
        action_layout.addWidget(self.btn_open_logs)
        action_layout.addWidget(self.btn_open_config)
        topbar_layout.addWidget(action_cluster)

        right_layout.addWidget(topbar)

        self.stack = QStackedWidget()
        callbacks = self._build_workspace_shell_callbacks()
        self.dashboard = DashboardPanel(shell_callbacks=callbacks)
        self.live = LivePanel(shell_callbacks=callbacks)
        self.logs = LogsPanel(shell_callbacks=callbacks)
        self.history = HistoryPanel(shell_callbacks=callbacks)
        self.overlay_page = self._overlay_browser.page
        self.review = ReviewPanel(shell_callbacks=callbacks)
        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.live)
        self.stack.addWidget(self.logs)
        self.stack.addWidget(self.history)
        self.stack.addWidget(self.overlay_page)
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

        self.act_resume_monitoring = QAction("Resume Monitoring", self)
        self.act_resume_monitoring.triggered.connect(self._service.start_monitoring)
        menu.addAction(self.act_resume_monitoring)

        self.act_pause_monitoring = QAction("Pause Monitoring", self)
        self.act_pause_monitoring.triggered.connect(self._service.stop_monitoring)
        menu.addAction(self.act_pause_monitoring)

        self.act_toggle_overlay = QAction("Show Overlay", self)
        self.act_toggle_overlay.triggered.connect(self._toggle_overlay)
        menu.addAction(self.act_toggle_overlay)

        menu.addSeparator()
        act_exit = QAction("Exit", self)
        act_exit.triggered.connect(self._exit_requested)
        menu.addAction(act_exit)
        return menu

    def _wire_events(self) -> None:
        self.nav.currentRowChanged.connect(self._on_navigation_changed)
        self.btn_settings.clicked.connect(self._open_settings)
        self.btn_about.clicked.connect(self._open_about)
        self.btn_start.clicked.connect(self._service.start_monitoring)
        self.btn_stop.clicked.connect(self._service.stop_monitoring)
        self.btn_overlay.clicked.connect(self._toggle_overlay)
        self.btn_open_output.clicked.connect(self._service.open_output_folder)
        self.btn_open_logs.clicked.connect(self._service.open_logs_folder)
        self.btn_open_config.clicked.connect(self._service.open_config_folder)

        self.dashboard.start_monitoring_requested.connect(self._service.start_monitoring)
        self.dashboard.stop_monitoring_requested.connect(self._service.stop_monitoring)
        self.dashboard.toggle_overlay_requested.connect(self._toggle_overlay)
        self.dashboard.open_output_requested.connect(self._service.open_output_folder)
        self.dashboard.open_logs_requested.connect(self._service.open_logs_folder)
        self.dashboard.open_config_requested.connect(self._service.open_config_folder)
        self.dashboard.open_settings_requested.connect(self._open_settings)
        self.dashboard.refresh_setup_requested.connect(self._service.refresh_setup_tools)
        self.dashboard.favorite_setup_requested.connect(self._toggle_selected_setup_favorite)
        self.dashboard.install_setup_requested.connect(self._install_local_setup_file)
        self.dashboard.duplicate_setup_requested.connect(self._duplicate_selected_setup)
        self.dashboard.rollback_setup_requested.connect(self._service.rollback_setup_change)
        self.dashboard.save_setup_bundle_requested.connect(self._save_selected_setup_bundle)
        self.dashboard.refresh_operations_requested.connect(self._service.refresh_operations)
        self.dashboard.toggle_raw_requested.connect(self._service.toggle_active_raw_capture)
        self.dashboard.save_profile_requested.connect(self._save_operations_profile)
        self.dashboard.apply_profile_requested.connect(self._apply_operations_profile)
        self.dashboard.setup_diff_requested.connect(self._sync_dashboard_setup_diff)

        self.history.refresh_requested.connect(self._service.refresh_history)
        self.history.review_requested.connect(self._review_selected_history)
        self.history.open_requested.connect(self._open_selected_history)
        self.history.reprocess_requested.connect(self._reprocess_selected_history)
        self.history.toggle_ignored_requested.connect(self._toggle_selected_history_ignored)
        self.history.queue_sync_requested.connect(self._queue_selected_history_for_sync)
        self.history.export_requested.connect(self._export_selected_history_csv)
        self.history.copy_id_requested.connect(self._copy_selected_history_id)
        self.history.delete_requested.connect(self._delete_selected_history)

        self.review.open_folder_requested.connect(self._open_current_review_folder)
        self.review.queue_sync_requested.connect(self._queue_current_review_for_sync)
        self.review.reprocess_requested.connect(self._reprocess_current_review)
        self.review.toggle_ignored_requested.connect(self._toggle_current_review_ignored)
        self.review.delete_requested.connect(self._delete_current_review)
        self.review.return_requested.connect(self._return_to_history)

        self._service.snapshot_changed.connect(self._on_snapshot)
        self._service.history_changed.connect(self.history.update_sessions)
        self._service.review_changed.connect(self.review.update_review)
        self._service.review_requested.connect(self._show_review)
        self._service.log_event.connect(self.logs.append_event)
        self.logs.export_support_requested.connect(self._export_support_bundle)
        self._service.settings_saved.connect(self._toast)
        self._service.settings_saved.connect(self._apply_overlay_preferences)
        self._service.settings_failed.connect(self._show_error)
        self._service.action_message.connect(self._toast)
        self._service.action_failed.connect(self._show_error)

    def _on_navigation_changed(self, row: int) -> None:
        if row < 0:
            return
        self.stack.setCurrentIndex(row)
        self._apply_overlay_workspace_mode(row in {0, 1, 2, 3, 4})

    def _apply_overlay_workspace_mode(self, enabled: bool) -> None:
        self._shell_sidebar.setVisible(not enabled)
        self._shell_topbar.setVisible(not enabled)

    def _switch_to_page(self, page_id: str) -> None:
        mapping = {
            "dashboard": 0,
            "live": 1,
            "logs": 2,
            "history": 3,
            "overlay": 4,
        }
        target = mapping.get(str(page_id or "").lower())
        if target is None:
            return
        self.nav.setCurrentRow(target)

    def _step_page(self, delta: int) -> None:
        nav_count = self.nav.count()
        if nav_count <= 0:
            return
        current = self.nav.currentRow()
        if current < 0 or current >= nav_count:
            current = 0
        self.nav.setCurrentRow((current + int(delta)) % nav_count)

    def _on_snapshot(self, snap: dict) -> None:
        self._latest_snapshot = dict(snap)
        status = str(snap.get("status", "Idle"))
        color = STATUS_COLORS.get(status, STEEL)
        self.lbl_status.setText(status.upper())
        self.lbl_status.setStyleSheet(
            f"font-size:12px; font-weight:700; letter-spacing:2px;"
            f" font-family:'Consolas','Space Mono',monospace; color:{color};"
        )
        self.lbl_state_detail.setText(str(snap.get("status_detail") or "Ready"))

        monitoring_active = bool(snap.get("is_monitoring"))
        self.btn_start.setEnabled(not monitoring_active)
        self.btn_stop.setEnabled(monitoring_active)
        self.dashboard.btn_start.setEnabled(not monitoring_active)
        self.dashboard.btn_stop.setEnabled(monitoring_active)
        self.dashboard.btn_start.setText("RESUME MONITORING")
        self.dashboard.btn_stop.setText("PAUSE MONITORING")
        self.act_resume_monitoring.setEnabled(not monitoring_active)
        self.act_pause_monitoring.setEnabled(monitoring_active)
        self._sync_overlay_controls()

        self.dashboard.update_snapshot(snap)
        self.live.update_snapshot(snap)
        self.logs.update_context(snap)
        for page in (self.dashboard, self.live, self.logs, self.history, self.review):
            if hasattr(page, "set_shell_status"):
                page.set_shell_status(
                    status=status,
                    detail=str(snap.get("status_detail") or "Ready"),
                    monitoring_active=monitoring_active,
                )
        self._overlay_browser.controller.set_live_snapshot(snap)
        self.overlay_page.set_shell_status(
            status=status,
            detail=str(snap.get("status_detail") or "Ready"),
            monitoring_active=monitoring_active,
        )
        self._sync_overlay_page(snap)

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

    def _sync_dashboard_setup_diff(self) -> None:
        setup_a, setup_b = self.dashboard.selected_diff_pair()
        self._service.select_setup_diff(setup_a, setup_b)

    def _toggle_selected_setup_favorite(self) -> None:
        self._service.toggle_setup_favorite(self.dashboard.selected_setup_id())

    def _install_local_setup_file(self) -> None:
        source_path, _ = QFileDialog.getOpenFileName(
            self,
            "Install Local Setup File",
            "",
            "Setup Files (*.json *.ini *.svm *.sto);;All Files (*.*)",
        )
        if source_path:
            self._service.install_setup_from_file(source_path, self.dashboard.selected_setup_id())

    def _duplicate_selected_setup(self) -> None:
        self._service.duplicate_setup(
            self.dashboard.selected_setup_id(),
            self.dashboard.duplicate_setup_name(),
        )

    def _save_selected_setup_bundle(self) -> None:
        self._service.save_setup_with_last_session(self.dashboard.selected_setup_id())

    def _save_operations_profile(self) -> None:
        self._service.save_operations_profile(
            self.dashboard.operations_profile_name(),
            self.dashboard.operations_profile_scope(),
        )

    def _apply_operations_profile(self) -> None:
        self._service.apply_operations_profile(self.dashboard.selected_operations_profile_id())

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

    def _queue_selected_history_for_sync(self) -> None:
        path = self.history.selected_folder()
        if not path:
            return

        ok, message = self._service.queue_session_for_sync(path)
        if ok:
            self._toast(message)
        else:
            self._show_error(message, title="Sync Error")

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
        self._apply_overlay_workspace_mode(True)

    def _open_current_review_folder(self) -> None:
        path = self.review.current_path()
        if path:
            self._service.open_path(path)

    def _queue_current_review_for_sync(self) -> None:
        path = self.review.current_path()
        if not path:
            return

        ok, message = self._service.queue_session_for_sync(path)
        if ok:
            self._toast(message)
        else:
            self._show_error(message, title="Sync Error")

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

    def _show_error(self, message: str, *, title: str = APP_NAME) -> None:
        QMessageBox.critical(self, title, message)

    def _toggle_overlay(self) -> None:
        self._overlay.toggle_visible()

    def _apply_overlay_preferences(self, *_args) -> None:
        settings = self._service.settings_snapshot()
        self._overlay.sync_from_settings(settings)
        self._apply_window_pinning(settings)
        self._sync_overlay_controls()
        self._sync_overlay_page()

    def _apply_window_pinning(self, settings: dict) -> None:
        pin_mode = str(settings.get("overlay_pin_mode") or "overlay_on_top")
        flags = self.windowFlags()
        desired_on_top = pin_mode == "dashboard_on_top"
        if desired_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def _sync_overlay_controls(self, *_args) -> None:
        visible = self._overlay.isVisible()
        button_text = "HIDE OVERLAY" if visible else "OVERLAY"
        self.btn_overlay.setText(button_text)
        if hasattr(self.dashboard, "set_overlay_toggle_label"):
            self.dashboard.set_overlay_toggle_label(button_text)
        self.act_toggle_overlay.setText("Hide Overlay" if visible else "Show Overlay")
        self._sync_overlay_page()

    def _sync_overlay_page(self, snapshot: dict[str, object] | None = None) -> None:
        payload = snapshot or self._latest_snapshot or self._service.overlay_snapshot()
        self._overlay_browser.controller.set_live_snapshot(payload)

    def _on_tray_activated(self, reason) -> None:  # noqa: ANN001
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._restore()

    def _restore(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _exit_requested(self) -> None:
        self._allow_close = True
        self._overlay_browser.page.deleteLater()
        self._overlay.hide_overlay()
        self._overlay.close()
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
