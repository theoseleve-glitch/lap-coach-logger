from __future__ import annotations

from PySide6.QtWidgets import QApplication

from lap_coach_logger.ui.desktop.workspaces import DashboardPanel, HistoryPanel, LivePanel, LogsPanel, ReviewPanel
from lap_coach_logger.ui.desktop.workspaces.common import WorkspaceShellCallbacks


def test_workspace_pages_construct_with_shared_shell() -> None:
    """Verify all workspace panels can be constructed and have correct names."""
    app = _app()
    callbacks = WorkspaceShellCallbacks()
    pages = [
        DashboardPanel(shell_callbacks=callbacks),
        LivePanel(shell_callbacks=callbacks),
        LogsPanel(shell_callbacks=callbacks),
        HistoryPanel(shell_callbacks=callbacks),
        ReviewPanel(shell_callbacks=callbacks),
    ]
    app.processEvents()

    assert pages[0].objectName() == "DashboardWorkspacePage"
    assert pages[1].objectName() == "LiveWorkspacePage"
    assert pages[2].objectName() == "LogsWorkspacePage"
    assert pages[3].objectName() == "HistoryWorkspacePage"
    assert pages[4].objectName() == "ReviewWorkspacePage"
    for page in pages:
        page.deleteLater()


def test_dashboard_workspace_builds_and_emits_signals() -> None:
    """Verify dashboard can build its widget tree and emit signals."""
    app = _app()
    events: list[str] = []

    dashboard = DashboardPanel(shell_callbacks=WorkspaceShellCallbacks())
    dashboard._build()

    dashboard.start_monitoring_requested.connect(lambda: events.append("start"))
    dashboard.toggle_overlay_requested.connect(lambda: events.append("overlay"))

    dashboard.btn_start.click()
    dashboard.btn_overlay.click()
    app.processEvents()

    assert "start" in events
    assert "overlay" in events
    dashboard.deleteLater()


def _app() -> QApplication:
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app
