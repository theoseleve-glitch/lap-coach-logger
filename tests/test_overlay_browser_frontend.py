from __future__ import annotations

from PySide6.QtWidgets import QApplication, QCheckBox, QDoubleSpinBox, QPushButton, QSplitter, QTabBar, QToolButton, QWidget

from lap_coach_logger.overlays import (
    OverlayBrowserSettingFieldView,
    OverlayBrowserSettingsSectionView,
    OverlayStateStore,
)
from lap_coach_logger.ui.desktop.overlay_browser import (
    OverlaySettingsFormRenderer,
    OverlayWorkspaceShellCallbacks,
    build_overlay_browser_frontend,
)


def test_overlay_browser_frontend_builds_from_shared_backend(tmp_path) -> None:
    app = _app()
    store = OverlayStateStore(tmp_path / "overlay-browser.db")
    frontend = build_overlay_browser_frontend(store=store)
    app.processEvents()

    state = frontend.controller.page_state
    assert state is not None
    assert len(state.overlays) >= 10
    assert state.selected_overlay is not None
    assert frontend.controller.preview_model().title == state.selected_overlay.display_name

    frontend.page.deleteLater()


def test_overlay_browser_preview_uses_telemetry_preview_bindings(tmp_path) -> None:
    app = _app()
    store = OverlayStateStore(tmp_path / "overlay-preview.db")
    frontend = build_overlay_browser_frontend(store=store)

    frontend.controller.select_overlay("track_map")
    app.processEvents()
    preview = frontend.controller.preview_model()

    assert preview.overlay_id == "track_map"
    assert preview.health_status == "preview"
    assert any(stat.label == "Health" for stat in preview.stats)

    frontend.page.deleteLater()


def test_overlay_browser_preview_uses_live_snapshot_when_available(tmp_path) -> None:
    app = _app()
    store = OverlayStateStore(tmp_path / "overlay-live-preview.db")
    frontend = build_overlay_browser_frontend(store=store)

    frontend.controller.select_overlay("track_map")
    frontend.controller.set_live_snapshot(
        {
            "status": "Recording",
            "sim": "ACC",
            "data_staleness_s": 0.1,
            "live": {
                "timestamp_utc": "2026-04-01T10:00:00+00:00",
                "world_pos_x": 125.2,
                "world_pos_y": -81.4,
                "lap_dist_pct": 0.52,
                "current_sector_index": 2,
                "speed_kph": 184.6,
                "track_name": "Spa",
            },
        }
    )
    app.processEvents()
    preview = frontend.controller.preview_model()

    assert preview.overlay_id == "track_map"
    assert preview.health_status == "healthy"
    assert any(stat.label == "Health" and stat.value == "HEALTHY" for stat in preview.stats)

    frontend.page.deleteLater()


def test_overlay_browser_can_install_a_free_overlay_into_selected_layout(tmp_path) -> None:
    app = _app()
    store = OverlayStateStore(tmp_path / "overlay-install.db")
    frontend = build_overlay_browser_frontend(store=store)

    frontend.controller.select_overlay("race_control")
    state = frontend.controller.page_state
    assert state is not None
    if state.selected_overlay is not None and state.selected_overlay.installed:
        frontend.controller.run_overlay_action("uninstall", overlay_id="race_control")

    frontend.controller.run_overlay_action("install", overlay_id="race_control")
    app.processEvents()
    state = frontend.controller.page_state

    assert state is not None
    assert state.selected_overlay is not None
    assert state.selected_overlay.overlay_id == "race_control"
    assert state.selected_overlay.installed is True

    frontend.page.deleteLater()


def test_overlay_browser_workspace_exposes_immersive_shell(tmp_path) -> None:
    app = _app()
    store = OverlayStateStore(tmp_path / "overlay-workspace.db")
    frontend = build_overlay_browser_frontend(store=store)
    app.processEvents()

    assert frontend.page.objectName() == "OverlayWorkspacePage"
    assert frontend.page.findChild(QWidget, "OverlayWorkspaceSidebar") is not None
    assert frontend.page.findChild(QWidget, "OverlayWorkspacePreview") is not None
    assert frontend.page.findChild(QWidget, "OverlayWorkspaceControls") is not None
    assert frontend.page.findChild(QWidget, "OverlayWorkspaceDock") is not None
    assert frontend.page.findChild(QSplitter, "OverlayWorkspaceSplitter") is not None
    assert frontend.page.findChild(QTabBar, "OverlayDockTabs") is not None
    assert frontend.page.findChild(QToolButton, "OverlayTopNavButton_overlay") is not None
    assert frontend.page.findChild(QPushButton, "OverlayTopMonitorAction") is not None
    assert frontend.page.findChild(QPushButton, "OverlayControlsPrimaryAction") is not None

    frontend.page.deleteLater()


def test_overlay_browser_workspace_shell_callbacks_are_remapped(tmp_path) -> None:
    app = _app()
    store = OverlayStateStore(tmp_path / "overlay-shell-callbacks.db")
    events: list[tuple[str, object]] = []
    frontend = build_overlay_browser_frontend(
        store=store,
        shell_callbacks=OverlayWorkspaceShellCallbacks(
            switch_page=lambda page_id: events.append(("page", page_id)),
            open_settings=lambda: events.append(("settings", None)),
            resume_monitoring=lambda: events.append(("resume", None)),
            pause_monitoring=lambda: events.append(("pause", None)),
        ),
    )
    app.processEvents()

    live_button = frontend.page.findChild(QToolButton, "OverlayTopNavButton_live")
    settings_button = frontend.page.findChild(QToolButton, "OverlayTopIconAction_settings")
    monitor_button = frontend.page.findChild(QPushButton, "OverlayTopMonitorAction")

    assert live_button is not None
    assert settings_button is not None
    assert monitor_button is not None

    live_button.click()
    settings_button.click()
    monitor_button.click()
    frontend.page.set_shell_status(status="Recording", detail="ACC live", monitoring_active=True)
    app.processEvents()
    monitor_button.click()

    assert ("page", "live") in events
    assert ("settings", None) in events
    assert ("resume", None) in events
    assert ("pause", None) in events

    frontend.page.deleteLater()


def test_overlay_settings_form_renderer_tracks_dirty_changes() -> None:
    app = _app()
    renderer = OverlaySettingsFormRenderer()
    renderer.set_sections(
        (
            OverlayBrowserSettingsSectionView(
                section_key="appearance",
                label="Appearance",
                description="",
                fields=(
                    OverlayBrowserSettingFieldView(
                        field_key="show_metadata",
                        label="Show Metadata",
                        description="Toggle metadata rows.",
                        kind="boolean",
                        section_key="appearance",
                        current_value=True,
                        default_value=True,
                        source="default",
                        editable=True,
                    ),
                    OverlayBrowserSettingFieldView(
                        field_key="opacity",
                        label="Opacity",
                        description="Glass opacity.",
                        kind="float",
                        section_key="appearance",
                        current_value=0.85,
                        default_value=0.85,
                        source="default",
                        editable=True,
                        min_value=0.0,
                        max_value=1.0,
                        step=0.05,
                    ),
                ),
            ),
        )
    )
    app.processEvents()

    toggle = renderer.findChild(QCheckBox)
    slider = renderer.findChild(QDoubleSpinBox)
    assert toggle is not None
    assert slider is not None

    toggle.setChecked(False)
    slider.setValue(0.7)
    app.processEvents()

    assert renderer.collect_changes() == {
        "show_metadata": False,
        "opacity": 0.7,
    }

    renderer.reset_to_baseline()
    app.processEvents()
    assert renderer.collect_changes() == {}


def test_overlay_browser_layout_tabs_keep_long_names_readable(tmp_path) -> None:
    app = _app()
    store = OverlayStateStore(tmp_path / "overlay-long-layout.db")
    frontend = build_overlay_browser_frontend(store=store)
    frontend.controller.create_layout("Broadcast Timing And Strategy Workspace")
    app.processEvents()

    tabs = frontend.page.findChild(QTabBar, "OverlayDockTabs")
    assert tabs is not None
    assert any("Broadcast Timing And Strategy Workspace" in tabs.tabText(index) for index in range(tabs.count()))

    frontend.page.deleteLater()


def _app() -> QApplication:
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app
