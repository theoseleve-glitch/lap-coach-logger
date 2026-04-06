"""Application bootstrap – wires all components and runs the main loop.

Startup sequence (order matters):
1. Install signal handlers (main thread only).
2. Configure logging.
3. Load / create config.
4. Validate config.
5. Clean up stale temp session folders.
6. Build adapters, health monitor, coordinator.
7. Start tray icon (background thread).
8. Start process watcher (background thread).
9. Block main thread waiting for shutdown signal.
10. On shutdown: stop watcher → finalize session → stop tray → cleanup.
"""

from __future__ import annotations

import logging

from lap_coach_logger.adapters.acc_adapter import ACCAdapter
from lap_coach_logger.adapters.iracing_adapter import IRacingAdapter
from lap_coach_logger.config.manager import ConfigManager
from lap_coach_logger.config.models import AppConfig
from lap_coach_logger.core.health import HealthMonitor
from lap_coach_logger.core.session_coordinator import SessionCoordinator
from lap_coach_logger.detection.process_watcher import ProcessWatcher
from lap_coach_logger.qml_bootstrap import run_qml_shell
from lap_coach_logger.utils.logging_setup import setup_logging
from lap_coach_logger.utils.single_instance import SingleInstance
from lap_coach_logger.utils.shutdown import (
    install_atexit,
    install_signal_handlers,
    register_cleanup,
    request_shutdown,
    run_cleanup,
    shutdown_requested,
)
from lap_coach_logger.utils.win_autostart import sync_autostart
from lap_coach_logger.writers.finalizer import SessionFinalizer

log = logging.getLogger(__name__)


def run(*, debug_override: bool = False) -> None:
    """Full application lifecycle — call from ``__main__``."""

    instance = SingleInstance()
    if not instance.acquire():
        # Avoid noisy stdout when launched from Start menu / installer.
        return

    # 1. Signal handlers (must be main thread)
    install_signal_handlers()
    install_atexit()

    # 2. Config
    cfg_manager = ConfigManager()
    config: AppConfig = cfg_manager.load()
    if debug_override:
        config.debug = True

    # 3. Logging (after config so we know debug flag)
    setup_logging(debug=config.debug)
    from lap_coach_logger import __version__
    log.info("Lap Coach Logger v%s starting up", __version__)
    log.info("Output dir: %s", config.output_path)

    # 4. Validate config
    errors = config.validate()
    if errors:
        for e in errors:
            log.warning("Config validation: %s", e)

    # 4b. Synchronize autostart setting with actual OS state
    actual_autostart = sync_autostart(config.start_with_windows)
    if actual_autostart != config.start_with_windows:
        config.start_with_windows = actual_autostart
        try:
            cfg_manager.save(config)
        except Exception:
            log.warning("Failed to persist synchronized autostart setting", exc_info=True)

    # 5. Stale temp cleanup
    cleaned = SessionFinalizer.cleanup_stale_temps(config.output_path)
    if cleaned:
        log.info("Cleaned %d stale temp session folder(s)", cleaned)

    # 6. Health monitor, adapters & coordinator
    health = HealthMonitor()
    adapters = _build_adapters(config)
    coordinator = SessionCoordinator(config, health=health)

    # 7. Process watcher
    watcher = ProcessWatcher(
        adapters,
        poll_interval=config.poll_interval_s,
        on_sim_found=coordinator.on_sim_found,
        on_sim_lost=coordinator.on_sim_lost,
    )

    # Register cleanup order (reversed on execution)
    register_cleanup(coordinator.stop)
    register_cleanup(watcher.stop)

    # 8. Start background services
    watcher.start()

    log.info("All backend services running – launching QML shell")

    # 9. Launch QML shell (blocking until app exits)
    try:
        run_qml_shell(
            config=config,
            config_manager=cfg_manager,
            coordinator=coordinator,
            watcher=watcher,
            on_exit=request_shutdown,
        )
    except KeyboardInterrupt:
        pass
    finally:
        if not shutdown_requested():
            request_shutdown()
        log.info("Shutdown initiated")
        run_cleanup()
        instance.release()
        log.info("Lap Coach Logger stopped")


def _build_adapters(config: AppConfig) -> list:
    """Instantiate enabled sim adapters."""
    adapters = []
    if config.iracing.enabled:
        adapters.append(IRacingAdapter())
    if config.acc.enabled:
        adapters.append(ACCAdapter())
    log.info("Enabled adapters: %s", [a.sim_name for a in adapters])
    return adapters
