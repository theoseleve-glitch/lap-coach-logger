"""QML application bootstrap -- engine setup replacing the QWidgets shell.

Provides two public entry points:

* ``build_view_models(service)`` -- testable wiring of all ViewModels.
* ``run_qml_shell(...)`` -- full QApplication lifecycle (not unit-tested).
"""

from __future__ import annotations

import ctypes
import logging
import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QUrl
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine

from lap_coach_logger import APP_NAME, __version__
from lap_coach_logger.app_identity import APP_ID, COMPANY_NAME
from lap_coach_logger.assets import app_icon_path, qml_dir
from lap_coach_logger.ui.desktop.service import DesktopService
from lap_coach_logger.viewmodels import (
    HistoryViewModel,
    OnboardingViewModel,
    OverlayViewModel,
    ReviewViewModel,
    ServiceViewModel,
    SessionViewModel,
    SettingsViewModel,
)
from lap_coach_logger.viewmodels.mode_vm import ModeViewModel
from lap_coach_logger.viewmodels.strategy_vm import StrategyViewModel
from lap_coach_logger.viewmodels.tray_vm import TrayViewModel
from lap_coach_logger.core.stint_store import StintStore
from lap_coach_logger.sync.client import SyncClient, build_sync_client
from lap_coach_logger.sync.failure_store import SyncFailureStore
from lap_coach_logger.sync.queue import SyncQueue
from lap_coach_logger.utils.paths import runtime_dir
from lap_coach_logger.viewmodels.sync_status_vm import SyncStatusViewModel

if TYPE_CHECKING:
    from collections.abc import Callable

    from lap_coach_logger.config.manager import ConfigManager
    from lap_coach_logger.config.models import AppConfig
    from lap_coach_logger.core.session_coordinator import SessionCoordinator
    from lap_coach_logger.detection.process_watcher import ProcessWatcher

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Testable core: ViewModel factory + signal wiring
# ---------------------------------------------------------------------------

def build_view_models(service: DesktopService) -> dict:
    """Create all ViewModels, wire service signals, and return a name-keyed dict.

    This is the testable core of the QML bootstrap.  It:
    1. Instantiates all 7 ViewModels.
    2. Connects service signals to child VMs.
    3. Performs an initial settings load.
    4. Returns ``{"service": ..., "session": ..., ...}``.
    """
    svc_vm = ServiceViewModel(service)
    session_vm = SessionViewModel()
    history_vm = HistoryViewModel()
    review_vm = ReviewViewModel()
    settings_vm = SettingsViewModel()
    overlay_vm = OverlayViewModel(
        saved_settings=service.config.overlay.widget_settings or None,
    )
    onboarding_vm = OnboardingViewModel()

    # -- Wire service signals to child VMs ---------------------------------
    service.snapshot_changed.connect(session_vm.update_from_snapshot)
    service.snapshot_changed.connect(overlay_vm.update_from_snapshot)
    service.history_changed.connect(history_vm.update_sessions)
    service.review_changed.connect(review_vm.load)

    # Settings: VM save -> service write, service ack -> VM reload
    settings_vm.saveRequested.connect(service.save_settings)
    service.settings_saved.connect(
        lambda _: settings_vm.load(service.settings_snapshot())
    )

    # -- Initial settings load ---------------------------------------------
    settings_vm.load(service.settings_snapshot())

    # -- Persist overlay widget settings on change -------------------------
    def _save_overlay_settings() -> None:
        service.config.overlay.widget_settings = overlay_vm.export_settings()
        service.config_manager.save(service.config)

    overlay_vm.settingsSaveRequested.connect(_save_overlay_settings)

    # -- Mode VM ---------------------------------------------------------------
    mode_vm = ModeViewModel()
    service._mode_vm = mode_vm

    # -- Strategy VM -----------------------------------------------------------
    stint_store = StintStore(runtime_dir() / "stint_profiles.json")
    strategy_vm = StrategyViewModel(stint_store)
    overlay_vm.set_strategy_vm(strategy_vm)
    service._strategy_vm = strategy_vm
    service.snapshot_changed.connect(
        lambda payload: strategy_vm.update_live(payload.get("live", {}) if isinstance(payload, dict) else {})
    )

    # -- Sync wiring: queue feeds events, client drains them over HTTP ---------
    sync_queue = SyncQueue(runtime_dir())
    sync_failures = SyncFailureStore(runtime_dir())
    strategy_vm.set_sync_queue(sync_queue)

    sync_client: SyncClient | None = None
    sync_cfg = getattr(service.config, "sync", None)
    if (
        sync_cfg is not None
        and getattr(sync_cfg, "enabled", False)
        and getattr(sync_cfg, "api_url", "")
    ):
        sync_client = build_sync_client(
            queue=sync_queue,
            failure_store=sync_failures,
            base_url=sync_cfg.api_url,
            device_token=getattr(sync_cfg, "device_token", ""),
            api_key=getattr(sync_cfg, "api_key", "")
            if hasattr(sync_cfg, "api_key")
            else "",
        )
        sync_client.start()
        service._sync_client = sync_client  # keep alive for lifecycle

    sync_status_vm = SyncStatusViewModel(client=sync_client)

    # -- Wire mode changes to strategy VM and overlay defaults ------------------
    mode_vm.modeChanged.connect(lambda: strategy_vm.set_mode(mode_vm.activeMode))
    mode_vm.modeChanged.connect(lambda: overlay_vm.apply_mode_defaults(mode_vm.activeMode))

    return {
        "service": svc_vm,
        "session": session_vm,
        "history": history_vm,
        "review": review_vm,
        "settings": settings_vm,
        "overlay": overlay_vm,
        "onboarding": onboarding_vm,
        "mode": mode_vm,
        "strategy": strategy_vm,
        "syncStatus": sync_status_vm,
    }


# ---------------------------------------------------------------------------
# Full application launcher (not unit-tested -- requires real Qt event loop)
# ---------------------------------------------------------------------------

def run_qml_shell(
    *,
    config: AppConfig,
    config_manager: ConfigManager,
    coordinator: SessionCoordinator,
    watcher: ProcessWatcher,
    on_exit: Callable[[], None],
) -> None:
    """Launch the QML-based desktop shell.

    This replaces ``run_desktop_shell`` from the QWidgets implementation.
    It blocks until the QApplication event loop exits.
    """
    # 1. Windows taskbar grouping
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)  # type: ignore[attr-defined]
    except Exception:
        pass  # Non-Windows or missing API -- harmless

    # 2. QApplication
    app = QApplication(sys.argv)

    # 3. App identity
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(COMPANY_NAME)
    app.setApplicationVersion(__version__)

    # 4. Window icon
    icon_path = app_icon_path()
    if icon_path:
        app.setWindowIcon(QIcon(str(icon_path)))

    # 5. Create and start DesktopService
    service = DesktopService(
        config=config,
        config_manager=config_manager,
        coordinator=coordinator,
        watcher=watcher,
    )
    service.start()

    # 6. Build ViewModels
    vms = build_view_models(service)

    # 7. QML engine
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(qml_dir()))

    # 8. Register context properties
    ctx = engine.rootContext()
    for name, vm in vms.items():
        ctx.setContextProperty(f"{name}VM", vm)

    # 8b. System tray (register before QML load so trayVM is available)
    tray = TrayViewModel(app.windowIcon())
    ctx.setContextProperty("trayVM", tray)

    # 9. Load main.qml
    main_qml = qml_dir() / "main.qml"
    engine.load(QUrl.fromLocalFile(str(main_qml)))

    # 10. Verify load succeeded
    if not engine.rootObjects():
        log.error("QML engine failed to load %s", main_qml)
        return

    # 10b. Wire tray signals (after QML load so rootObjects exist)
    root_window = engine.rootObjects()[0]

    def _show_window():
        root_window.showNormal()
        root_window.raise_()
        root_window.requestActivate()

    def _force_quit():
        root_window.setProperty("forceClose", True)
        app.quit()

    tray.showRequested.connect(_show_window)
    tray.exitRequested.connect(_force_quit)
    # overlayToggleRequested is wired QML-side via Connections in AppShell.qml
    tray.show()

    # 11. Wire app exit
    app.aboutToQuit.connect(on_exit)

    # 12. Run event loop
    app.exec_()

    # 13. Cleanup after event loop exits
    service.stop()
