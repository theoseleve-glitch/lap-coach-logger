"""Stdio bridge between the Python backend and the native Qt frontend."""

from __future__ import annotations

import atexit
import json
import logging
import sys
import threading
from dataclasses import dataclass
from queue import Empty, Queue

from PySide6.QtCore import QCoreApplication, QObject, QTimer, Signal

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
from lap_coach_logger.native_bridge.contracts import (
    build_dashboard_state,
    build_history_state,
    build_live_state,
    build_logs_state,
    build_overlay_state,
    build_review_state,
    build_shell_state,
)
from lap_coach_logger.overlays import (
    OverlayBrowserPageService,
    OverlayInstanceLifecycleService,
    OverlayLayoutPresetService,
    OverlayRegistry,
    OverlayStateStore,
    StaticOverlayEntitlementResolver,
    build_example_overlay_settings_service,
    build_example_overlay_telemetry_binding_service,
    builtin_overlay_definitions,
    example_overlay_layout_templates,
)
from lap_coach_logger.ui.desktop.overlay_browser.controller import OverlayBrowserPageController
from lap_coach_logger.ui.desktop.service import DesktopService
from lap_coach_logger.utils.logging_setup import setup_logging

log = logging.getLogger(__name__)


class _CommandInbox(QObject):
    command_received = Signal(dict)


@dataclass(slots=True)
class _RuntimeState:
    latest_snapshot: dict[str, object] = None  # type: ignore[assignment]
    latest_history: list[dict[str, object]] = None  # type: ignore[assignment]
    latest_review: dict[str, object] | None = None
    latest_logs: list[dict[str, object]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.latest_snapshot is None:
            self.latest_snapshot = {}
        if self.latest_history is None:
            self.latest_history = []
        if self.latest_logs is None:
            self.latest_logs = []


class NativeBridgeController(QObject):
    def __init__(self) -> None:
        super().__init__()
        cfg_manager = ConfigManager()
        config: AppConfig = cfg_manager.load()
        setup_logging(debug=config.debug)

        # Debounced save scheduler — mirrors qml_bootstrap wiring.
        # T173: 2.0s window — at most one disk write per 2 seconds.
        cfg_saver = SaveScheduler(
            writer=lambda: cfg_manager.save(config),
            delay_s=2.0,
        )

        health = HealthMonitor()
        coordinator = SessionCoordinator(config, health=health)
        watcher = ProcessWatcher(
            _build_adapters(config),
            poll_interval=config.poll_interval_s,
            on_sim_found=coordinator.on_sim_found,
            on_sim_lost=coordinator.on_sim_lost,
        )

        self._config = config
        self._cfg_saver = cfg_saver
        self._coordinator = coordinator
        self._watcher = watcher
        self._service = DesktopService(
            config=config,
            config_manager=cfg_manager,
            config_saver=cfg_saver,
            coordinator=coordinator,
            watcher=watcher,
        )
        registry = OverlayRegistry(builtin_overlay_definitions())
        store = OverlayStateStore()
        settings_service = build_example_overlay_settings_service()
        telemetry_bindings = build_example_overlay_telemetry_binding_service()
        entitlement_resolver = StaticOverlayEntitlementResolver()
        runtime = OverlayInstanceLifecycleService(
            registry=registry,
            settings_service=settings_service,
        )
        layout_service = OverlayLayoutPresetService(
            registry=registry,
            store=store,
            runtime=runtime,
            entitlement_resolver=entitlement_resolver,
            default_layouts=example_overlay_layout_templates(),
        )
        browser_service = OverlayBrowserPageService(
            registry=registry,
            layout_service=layout_service,
            settings_service=settings_service,
            entitlement_resolver=entitlement_resolver,
        )
        self._overlay_controller = OverlayBrowserPageController(
            registry=registry,
            browser_service=browser_service,
            layout_service=layout_service,
            telemetry_bindings=telemetry_bindings,
        )
        self._state = _RuntimeState()
        self._stdout_lock = threading.Lock()
        self._command_queue: Queue[dict[str, object]] = Queue()
        self._inbox = _CommandInbox()
        self._inbox.command_received.connect(self._handle_request)

        self._service.snapshot_changed.connect(self._on_snapshot)
        self._service.history_changed.connect(self._on_history)
        self._service.review_changed.connect(self._on_review)
        self._service.log_event.connect(self._on_log_event)
        self._service.action_message.connect(lambda message: self._emit_event("ui/message", {"message": message, "tone": "neutral"}))
        self._service.action_failed.connect(lambda message: self._emit_event("ui/message", {"message": message, "tone": "error"}))

        self._overlay_controller.state_changed.connect(lambda _state: self._publish_overlay_state())
        self._overlay_controller.preview_changed.connect(lambda _preview: self._publish_overlay_state())
        self._overlay_controller.message_emitted.connect(lambda message: self._emit_event("ui/message", {"message": message, "tone": "neutral"}))
        self._overlay_controller.error_emitted.connect(lambda message: self._emit_event("ui/message", {"message": message, "tone": "error"}))

        self._drain_timer = QTimer(self)
        self._drain_timer.setInterval(40)
        self._drain_timer.timeout.connect(self._drain_commands)

    def start(self) -> None:
        self._watcher.start()
        self._service.start()
        self._overlay_controller.refresh()
        self._drain_timer.start()
        self._start_stdin_reader()

    def stop(self) -> None:
        self._drain_timer.stop()
        self._service.stop()
        self._watcher.stop()
        self._coordinator.stop()
        # Final flush AFTER service/watcher stop so any trailing config
        # mutations made during teardown are persisted.
        self._cfg_saver.shutdown()

    def _start_stdin_reader(self) -> None:
        def _reader() -> None:
            for raw_line in sys.stdin:
                text = raw_line.strip()
                if not text:
                    continue
                try:
                    payload = json.loads(text)
                except json.JSONDecodeError:
                    continue
                self._command_queue.put(payload)

        thread = threading.Thread(target=_reader, name="native-bridge-stdin", daemon=True)
        thread.start()

    def _drain_commands(self) -> None:
        while True:
            try:
                payload = self._command_queue.get_nowait()
            except Empty:
                return
            self._inbox.command_received.emit(payload)

    def _handle_request(self, payload: dict[str, object]) -> None:
        if payload.get("type") != "request":
            return
        request_id = str(payload.get("id") or "")
        method = str(payload.get("method") or "")
        params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
        try:
            result = self._dispatch(method, params)
            self._emit_response(request_id, ok=True, result=result)
        except Exception as exc:  # noqa: BLE001
            log.exception("Bridge request failed: %s", method)
            self._emit_response(request_id, ok=False, error=str(exc))

    def _dispatch(self, method: str, params: dict[str, object]) -> dict[str, object]:
        if method == "bootstrap":
            self._publish_all()
            return {"bootstrapped": True}
        if method == "service.startMonitoring":
            self._service.start_monitoring()
            return {"ok": True}
        if method == "service.stopMonitoring":
            self._service.stop_monitoring()
            return {"ok": True}
        if method == "overlay.selectCategory":
            self._overlay_controller.select_category(str(params.get("category") or ""))
            return {"ok": True}
        if method == "overlay.selectOverlay":
            self._overlay_controller.select_overlay(str(params.get("overlayId") or ""))
            return {"ok": True}
        if method == "overlay.selectLayout":
            self._overlay_controller.select_layout(str(params.get("layoutId") or ""))
            return {"ok": True}
        if method == "overlay.setSearchQuery":
            self._overlay_controller.set_search_query(str(params.get("query") or ""))
            return {"ok": True}
        if method == "overlay.runAction":
            self._overlay_controller.run_overlay_action(str(params.get("actionId") or ""))
            return {"ok": True}
        if method == "overlay.applySettingChanges":
            changes = params.get("changes") if isinstance(params.get("changes"), dict) else {}
            self._overlay_controller.apply_setting_changes(changes)
            return {"ok": True}
        raise KeyError(f"Unsupported method '{method}'")

    def _publish_all(self) -> None:
        self._emit_event("shell/state", build_shell_state(self._state.latest_snapshot))
        self._emit_event("screen/dashboard", build_dashboard_state(self._state.latest_snapshot))
        self._emit_event("screen/live", build_live_state(self._state.latest_snapshot))
        self._emit_event("screen/logs", build_logs_state(self._state.latest_logs))
        self._emit_event("screen/history", build_history_state(self._state.latest_history))
        self._emit_event("screen/review", build_review_state(self._state.latest_review))
        self._publish_overlay_state()

    def _publish_overlay_state(self) -> None:
        state = self._overlay_controller.page_state
        if state is None:
            return
        preview = self._overlay_controller.preview_model()
        self._emit_event("screen/overlay", build_overlay_state(state, preview))

    def _on_snapshot(self, snapshot: dict[str, object]) -> None:
        self._state.latest_snapshot = dict(snapshot or {})
        self._overlay_controller.set_live_snapshot(self._service.overlay_snapshot())
        self._emit_event("shell/state", build_shell_state(self._state.latest_snapshot))
        self._emit_event("screen/dashboard", build_dashboard_state(self._state.latest_snapshot))
        self._emit_event("screen/live", build_live_state(self._state.latest_snapshot))

    def _on_history(self, rows: list[dict[str, object]]) -> None:
        self._state.latest_history = list(rows or [])
        self._emit_event("screen/history", build_history_state(self._state.latest_history))

    def _on_review(self, review: dict[str, object]) -> None:
        self._state.latest_review = dict(review or {})
        self._emit_event("screen/review", build_review_state(self._state.latest_review))

    def _on_log_event(self, event: dict[str, object]) -> None:
        self._state.latest_logs.append(dict(event or {}))
        self._state.latest_logs = self._state.latest_logs[-400:]
        self._emit_event("screen/logs", build_logs_state(self._state.latest_logs))

    def _emit_event(self, event_name: str, payload: dict[str, object]) -> None:
        self._write_json({"type": "event", "event": event_name, "payload": payload})

    def _emit_response(self, request_id: str, *, ok: bool, result: dict[str, object] | None = None, error: str = "") -> None:
        self._write_json(
            {
                "type": "response",
                "id": request_id,
                "ok": ok,
                "result": result or {},
                "error": error,
            }
        )

    def _write_json(self, payload: dict[str, object]) -> None:
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
        with self._stdout_lock:
            sys.stdout.write(encoded + "\n")
            sys.stdout.flush()


def _build_adapters(config: AppConfig) -> list[object]:
    adapters: list[object] = []
    if config.iracing.enabled:
        adapters.append(IRacingAdapter())
    if config.assetto_corsa.enabled:
        adapters.append(AssettoCorsaAdapter())
    if config.acc.enabled:
        adapters.append(ACCAdapter())
    if config.lmu.enabled:
        adapters.append(LMUAdapter())
    return adapters


def run() -> int:
    q_app = QCoreApplication(sys.argv)
    controller = NativeBridgeController()
    q_app.aboutToQuit.connect(controller.stop)
    # Belt-and-braces: atexit guarantees cfg_saver.shutdown() runs on
    # signal-driven exit, where aboutToQuit is not emitted. shutdown() is
    # idempotent, so overlapping with controller.stop is safe.
    atexit.register(controller._cfg_saver.shutdown)
    QTimer.singleShot(0, controller.start)
    return q_app.exec()
