from __future__ import annotations

import pytest

# The main_window module was removed when the app migrated to QML.
# These tests are retained for reference but skip until the module is restored.
pytest.skip(
    "main_window module removed during QML migration",
    allow_module_level=True,
)

from PySide6.QtCore import QObject, Signal  # noqa: E402
from PySide6.QtGui import QAction  # noqa: E402
from PySide6.QtWidgets import QApplication, QComboBox, QPushButton, QWidget  # noqa: E402

from lap_coach_logger.ui.desktop import main_window as main_window_module  # noqa: E402


class _StubDashboard(QWidget):
    start_monitoring_requested = Signal()
    stop_monitoring_requested = Signal()
    toggle_overlay_requested = Signal()
    open_output_requested = Signal()
    open_logs_requested = Signal()
    open_config_requested = Signal()
    open_settings_requested = Signal()
    refresh_setup_requested = Signal()
    favorite_setup_requested = Signal()
    install_setup_requested = Signal()
    duplicate_setup_requested = Signal()
    rollback_setup_requested = Signal()
    save_setup_bundle_requested = Signal()
    refresh_operations_requested = Signal()
    toggle_raw_requested = Signal()
    save_profile_requested = Signal()
    apply_profile_requested = Signal()
    setup_diff_requested = Signal()

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__()
        self.btn_start = QPushButton()
        self.btn_stop = QPushButton()

    def update_snapshot(self, _snap) -> None:  # noqa: ANN001
        pass

    def set_shell_status(self, *, status: str, detail: str, monitoring_active: bool) -> None:
        _ = (status, detail, monitoring_active)

    def set_overlay_toggle_label(self, _label: str) -> None:
        pass

    def selected_diff_pair(self):
        return (None, None)

    def selected_setup_id(self):
        return None

    def duplicate_setup_name(self) -> str:
        return ""

    def operations_profile_name(self) -> str:
        return ""

    def operations_profile_scope(self) -> str:
        return ""

    def selected_operations_profile_id(self):
        return None


class _StubLive(QWidget):
    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__()

    def update_snapshot(self, _snap) -> None:  # noqa: ANN001
        pass

    def set_shell_status(self, *, status: str, detail: str, monitoring_active: bool) -> None:
        _ = (status, detail, monitoring_active)


class _StubLogs(QWidget):
    export_support_requested = Signal(bool)

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__()

    def append_event(self, _event) -> None:  # noqa: ANN001
        pass

    def update_context(self, _snap) -> None:  # noqa: ANN001
        pass

    def set_shell_status(self, *, status: str, detail: str, monitoring_active: bool) -> None:
        _ = (status, detail, monitoring_active)


class _StubHistory(QWidget):
    refresh_requested = Signal()
    review_requested = Signal()
    open_requested = Signal()
    reprocess_requested = Signal()
    toggle_ignored_requested = Signal()
    queue_sync_requested = Signal()
    export_requested = Signal()
    copy_id_requested = Signal()
    delete_requested = Signal()

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__()

    def update_sessions(self, _sessions) -> None:  # noqa: ANN001
        pass

    def set_shell_status(self, *, status: str, detail: str, monitoring_active: bool) -> None:
        _ = (status, detail, monitoring_active)

    def selected_folder(self):
        return None

    def selected_session_name(self):
        return None

    def selected_session_id(self):
        return None


class _StubReview(QWidget):
    open_folder_requested = Signal()
    queue_sync_requested = Signal()
    reprocess_requested = Signal()
    toggle_ignored_requested = Signal()
    delete_requested = Signal()
    return_requested = Signal()

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__()
        self.btn_ignore = QPushButton("MARK IGNORED")

    def update_review(self, _review) -> None:  # noqa: ANN001
        pass

    def set_shell_status(self, *, status: str, detail: str, monitoring_active: bool) -> None:
        _ = (status, detail, monitoring_active)

    def current_path(self):
        return None


class _StubOverlayWindow(QWidget):
    visibility_changed = Signal(bool)

    def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
        super().__init__()

    def sync_from_settings(self, _settings) -> None:  # noqa: ANN001
        pass

    def toggle_visible(self) -> None:
        self.visibility_changed.emit(not self.isVisible())

    def hide_overlay(self) -> None:
        self.hide()
        self.visibility_changed.emit(False)


class _DummySignalServer:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


class _DummyTray:
    def hide(self) -> None:
        pass

    def showMessage(self, *_args, **_kwargs) -> None:  # noqa: ANN002, ANN003
        pass


class _StubService(QObject):
    snapshot_changed = Signal(dict)
    history_changed = Signal(list)
    review_changed = Signal(dict)
    review_requested = Signal(dict)
    log_event = Signal(dict)
    settings_saved = Signal(str)
    settings_failed = Signal(str)
    action_message = Signal(str)
    action_failed = Signal(str)

    def settings_snapshot(self) -> dict[str, object]:
        return {
            "overlay_enabled": False,
            "overlay_pin_mode": "overlay_on_top",
        }

    def overlay_snapshot(self) -> dict[str, object]:
        return {}

    def __getattr__(self, _name: str):
        return lambda *args, **kwargs: None


def test_main_window_switches_into_overlay_workspace_mode(monkeypatch) -> None:
    app = _app()

    monkeypatch.setattr(main_window_module, "DashboardPanel", _StubDashboard)
    monkeypatch.setattr(main_window_module, "LivePanel", _StubLive)
    monkeypatch.setattr(main_window_module, "LogsPanel", _StubLogs)
    monkeypatch.setattr(main_window_module, "HistoryPanel", _StubHistory)
    monkeypatch.setattr(main_window_module, "ReviewPanel", _StubReview)
    monkeypatch.setattr(main_window_module, "TelemetryOverlayWindow", _StubOverlayWindow)
    monkeypatch.setattr(main_window_module, "InstanceSignalServer", _DummySignalServer)

    def _fake_build_tray(self) -> None:
        self.tray = _DummyTray()
        self.act_resume_monitoring = QAction(self)
        self.act_pause_monitoring = QAction(self)
        self.act_toggle_overlay = QAction(self)

    monkeypatch.setattr(main_window_module.MainWindow, "_build_tray", _fake_build_tray)

    window = main_window_module.MainWindow(service=_StubService(), on_exit=lambda: None)
    window.show()
    app.processEvents()

    assert window._shell_sidebar.isHidden() is True
    assert window._shell_topbar.isHidden() is True

    window.nav.setCurrentRow(4)
    app.processEvents()

    assert window._shell_sidebar.isHidden() is True
    assert window._shell_topbar.isHidden() is True

    window.nav.setCurrentRow(3)
    app.processEvents()

    assert window._shell_sidebar.isHidden() is True
    assert window._shell_topbar.isHidden() is True

    window._show_review({"session_status": "ready"})
    app.processEvents()

    assert window.stack.currentWidget() is window.review
    assert window._shell_sidebar.isHidden() is True
    assert window._shell_topbar.isHidden() is True

    window.close()


def _app() -> QApplication:
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app
