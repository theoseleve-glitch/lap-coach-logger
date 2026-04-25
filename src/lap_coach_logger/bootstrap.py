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

from lap_coach_logger.adapters.assetto_corsa_adapter import AssettoCorsaAdapter
from lap_coach_logger.adapters.acc_adapter import ACCAdapter
from lap_coach_logger.adapters.assetto_corsa_adapter import AssettoCorsaAdapter
from lap_coach_logger.adapters.iracing_adapter import IRacingAdapter
from lap_coach_logger.adapters.lmu_adapter import LMUAdapter
from lap_coach_logger.config.manager import ConfigManager
from lap_coach_logger.config.models import AppConfig
from lap_coach_logger.config.save_scheduler import SaveScheduler
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

    # 2b. Debounced save scheduler. All runtime saves route through it so
    # UI bursts (overlay auto-arrange, slider drags) become one disk write.
    # Captures `config` by closure so the writer always reads latest state.
    cfg_saver = SaveScheduler(
        writer=lambda: cfg_manager.save(config),
        delay_s=0.5,
    )

    # 3. Logging (after config so we know debug flag)
    setup_logging(debug=config.debug)
    from lap_coach_logger.utils.release_build import BUILD_KIND, IS_FROZEN
    from lap_coach_logger.utils.runtime_check import check_runtime
    # Release builds are pinned to Python 3.12 and must refuse to boot
    # on any other interpreter. Dev builds only warn so contributors can
    # experiment. See utils/release_build.py for the rationale.
    check_runtime(strict=IS_FROZEN)
    from lap_coach_logger import __version__
    log.info("Lap Coach Logger v%s (%s) starting up", __version__, BUILD_KIND)
    log.info("Output dir: %s", config.output_path)

    # T056: initialize Sentry early so any failure later in bootstrap
    # (or during the run) is captured. Reads DSN from SENTRY_DSN env
    # var; no DSN -> no-op (so dev builds stay silent). T065 will plug
    # the user opt-out flag here.
    # T058: pass release=lap-coach-logger@<__version__> so Sentry's
    # "Releases" page groups events by build, and the environment tag
    # distinguishes packaged release builds from `python -m` dev runs.
    from lap_coach_logger.utils.sentry_init import init_sentry, sentry_release_tag
    sentry_active = init_sentry(
        release=sentry_release_tag(),
        environment="production" if IS_FROZEN else "development",
    )
    log.info(
        "Error telemetry: %s", "enabled (Sentry)" if sentry_active else "disabled"
    )

    # T057: forward QML / Qt critical+ messages to Sentry. QML throws
    # surface as Qt log messages at QtCriticalMsg severity, never as
    # Python exceptions, so Sentry's default sys.excepthook misses
    # them entirely. Skip the install when Sentry is off — Qt's
    # default stderr handler keeps working unmodified.
    if sentry_active:
        import sentry_sdk
        from lap_coach_logger.utils.sentry_qt import install_qt_message_handler
        install_qt_message_handler(sentry_capture=sentry_sdk.capture_message)

    # T059: initialize PostHog so T060+ events can fire. Reads API key
    # from POSTHOG_API_KEY (and optionally POSTHOG_HOST for self-
    # hosted instances). No key -> no-op so dev runs stay silent.
    # T065 will plug the user opt-out flag here alongside Sentry.
    from lap_coach_logger.utils.posthog_init import init_posthog
    posthog_active = init_posthog()
    log.info(
        "Product analytics: %s",
        "enabled (PostHog)" if posthog_active else "disabled",
    )

    # 4. Validate config
    errors = config.validate()
    if errors:
        for e in errors:
            log.warning("Config validation: %s", e)

    # 4b. Synchronize autostart setting with actual OS state.
    # This runs once at boot before the Qt event loop starts, so there
    # is no racing scheduler write. We intentionally bypass cfg_saver
    # here because the scheduler has not yet been wired to the shutdown
    # hook — a synchronous write is simpler and equivalent.
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

    # Register cleanup order (reversed on execution).
    # cfg_saver.shutdown() is registered first so it runs LAST — after
    # coordinator/watcher stop, any final config mutations still get flushed.
    register_cleanup(cfg_saver.shutdown)
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
            config_saver=cfg_saver,
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
    if config.assetto_corsa.enabled:
        adapters.append(AssettoCorsaAdapter())
    if config.acc.enabled:
        adapters.append(ACCAdapter())
    if config.lmu.enabled:
        adapters.append(LMUAdapter())
    log.info("Enabled adapters: %s", [a.sim_name for a in adapters])
    return adapters
