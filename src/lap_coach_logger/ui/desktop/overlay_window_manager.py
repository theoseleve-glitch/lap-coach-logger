"""Qt adapter layer for mapping overlay runtime instances onto floating windows."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from PySide6.QtCore import QEvent, QObject, QPoint, QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizeGrip,
    QVBoxLayout,
    QWidget,
)

from lap_coach_logger.overlays.layouts import OverlayLayoutPresetService
from lap_coach_logger.overlays.runtime_instances import (
    OverlayInstanceEvent,
    OverlayInstanceLifecycleService,
    OverlayRuntimeInstance,
)
from lap_coach_logger.ui.desktop.overlay import OverlayPanel
from lap_coach_logger.ui.desktop.theme import ASPHALT, CHALK, PIT_ORANGE, STEEL

_TELEMETRY_PANEL_RENDERERS = {
    "session_delta",
    "sector_table",
    "track_map",
    "pedal_trace",
    "fuel_strategy",
    "input_diagnostics",
    "live_coach",
}


@dataclass(slots=True, frozen=True)
class OverlayWindowDescriptor:
    instance_id: str
    overlay_id: str
    layout_id: str
    renderer_key: str
    display_name: str
    visible: bool
    active: bool
    preview_mode: bool
    pinned: bool
    locked: bool
    click_through: bool
    entitlement_blocked: bool
    lifecycle_status: str
    screen_id: str
    error: str = ""


@dataclass(slots=True, frozen=True)
class OverlayWindowManagerEvent:
    kind: str
    descriptor: OverlayWindowDescriptor
    source: str
    message: str = ""


class OverlayWindowStateCommitter(Protocol):
    """Optional write-back hook from Qt window interactions into persisted overlay state."""

    def persist_placement(self, instance: OverlayRuntimeInstance) -> None: ...

    def persist_visibility(self, instance: OverlayRuntimeInstance) -> None: ...

    def persist_settings(self, instance: OverlayRuntimeInstance) -> None: ...


class OverlayLayoutStateCommitter:
    """Persists runtime window changes back into layout state without remounting windows."""

    def __init__(self, layout_service: OverlayLayoutPresetService) -> None:
        self._layouts = layout_service

    def persist_placement(self, instance: OverlayRuntimeInstance) -> None:
        self._layouts.update_overlay_instance_placement(
            instance.instance_id,
            x=instance.placement.x,
            y=instance.placement.y,
            width=instance.placement.width,
            height=instance.placement.height,
            scale=instance.placement.scale,
            opacity=instance.placement.opacity,
            z_index=instance.placement.z_index,
            monitor_id=instance.screen_id,
            pinned=instance.state.pinned,
            locked=instance.state.locked,
            apply_to_runtime=False,
        )

    def persist_visibility(self, instance: OverlayRuntimeInstance) -> None:
        self._layouts.set_overlay_instance_enabled(
            instance.instance_id,
            instance.state.visible and not instance.state.entitlement_blocked,
            apply_to_runtime=False,
        )

    def persist_settings(self, instance: OverlayRuntimeInstance) -> None:
        self._layouts.update_overlay_instance_settings(
            instance.instance_id,
            instance.instance_overrides,
            apply_to_runtime=False,
        )


class OverlayWidgetController(QFrame):
    """Qt-side renderer contract for a single overlay window."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._instance_id = ""

    def apply_runtime_instance(self, instance: OverlayRuntimeInstance) -> None:
        self._instance_id = instance.instance_id

    def apply_live_payload(self, payload: dict[str, object]) -> None:
        del payload

    def shutdown(self) -> None:
        return None


class OverlayPlaceholderController(OverlayWidgetController):
    """Fallback renderer used when no specialized overlay widget has been registered."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("OverlayPlaceholder")
        self.setStyleSheet(
            f"""
            QFrame#OverlayPlaceholder {{
                background-color: rgba(20, 20, 20, 220);
                border: 1px solid rgba(240, 237, 229, 28);
                border-radius: 10px;
            }}
            QLabel#OverlayPlaceholderTitle {{
                color: {CHALK};
                font-size: 14px;
                font-weight: 800;
            }}
            QLabel#OverlayPlaceholderMeta {{
                color: {STEEL};
                font-size: 11px;
                font-weight: 600;
            }}
            QLabel#OverlayPlaceholderValue {{
                color: {PIT_ORANGE};
                font-size: 12px;
                font-weight: 700;
            }}
            """
        )
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(6)

        self._title = QLabel("Overlay")
        self._title.setObjectName("OverlayPlaceholderTitle")
        self._meta = QLabel("Renderer")
        self._meta.setObjectName("OverlayPlaceholderMeta")
        self._state = QLabel("IDLE")
        self._state.setObjectName("OverlayPlaceholderValue")
        self._detail = QLabel("No live data yet.")
        self._detail.setWordWrap(True)
        self._detail.setObjectName("OverlayPlaceholderMeta")

        root.addWidget(self._title)
        root.addWidget(self._meta)
        root.addWidget(self._state)
        root.addStretch(1)
        root.addWidget(self._detail)

    def apply_runtime_instance(self, instance: OverlayRuntimeInstance) -> None:
        super().apply_runtime_instance(instance)
        self._title.setText(instance.definition.display_name)
        self._meta.setText(
            f"{instance.definition.category.upper()}  •  {instance.definition.renderer_key}"
        )
        badge = "PREVIEW" if instance.state.preview_mode else "BLOCKED" if instance.state.entitlement_blocked else "LIVE"
        self._state.setText(badge)
        self._detail.setText(
            f"{instance.definition.short_description}\n"
            f"Layout: {instance.layout_id}  •  Screen: {instance.screen_id}"
        )

    def apply_live_payload(self, payload: dict[str, object]) -> None:
        live = payload.get("live")
        live = live if isinstance(live, dict) else {}
        sim = str(payload.get("sim") or live.get("sim_name") or "-")
        status = str(payload.get("status") or "Idle")
        lap = live.get("lap_number")
        speed = live.get("speed_kph")
        detail = f"Status: {status}  •  Sim: {sim}"
        if isinstance(lap, int):
            detail += f"  •  Lap {lap}"
        if isinstance(speed, (int, float)):
            detail += f"  •  {float(speed):.0f} kph"
        self._detail.setText(detail)


class TelemetryOverlayController(OverlayWidgetController):
    """Example specialized renderer that reuses the existing compact telemetry panel."""

    def __init__(self, *, kicker_text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self._panel = OverlayPanel(show_hide_button=False, kicker_text=kicker_text)
        root.addWidget(self._panel)

    def apply_live_payload(self, payload: dict[str, object]) -> None:
        self._panel.apply_snapshot(payload)


class OverlayWidgetFactoryRegistry:
    """Pluggable mapping from renderer keys to Qt widget factories."""

    def __init__(
        self,
        *,
        fallback_factory: Callable[[OverlayRuntimeInstance], OverlayWidgetController] | None = None,
    ) -> None:
        self._factories: dict[str, Callable[[OverlayRuntimeInstance], OverlayWidgetController]] = {}
        self._fallback_factory = fallback_factory or (lambda instance: OverlayPlaceholderController())

    def register(
        self,
        renderer_key: str,
        factory: Callable[[OverlayRuntimeInstance], OverlayWidgetController],
    ) -> None:
        self._factories[str(renderer_key).strip()] = factory

    def create(self, instance: OverlayRuntimeInstance) -> OverlayWidgetController:
        factory = self._factories.get(instance.definition.renderer_key, self._fallback_factory)
        return factory(instance)


def build_default_overlay_widget_factories() -> OverlayWidgetFactoryRegistry:
    registry = OverlayWidgetFactoryRegistry()
    for renderer_key in _TELEMETRY_PANEL_RENDERERS:
        registry.register(
            renderer_key,
            lambda instance, kicker=renderer_key: TelemetryOverlayController(
                kicker_text=instance.definition.display_name.upper()
            ),
        )
    return registry


class OverlayWindowHost(QWidget):
    """Frameless floating host window for a single overlay controller widget."""

    placement_committed = Signal(str, int, int, int, int, str)
    visibility_requested = Signal(str, bool)
    pin_requested = Signal(str, bool)
    lock_requested = Signal(str, bool)
    click_through_requested = Signal(str, bool)

    def __init__(
        self,
        controller: OverlayWidgetController,
        *,
        show_on_screen: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._instance_id = ""
        self._locked = False
        self._drag_offset: QPoint | None = None
        self._suspend_geometry_events = False

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        if not show_on_screen:
            self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)

        self._geometry_commit_timer = QTimer(self)
        self._geometry_commit_timer.setSingleShot(True)
        self._geometry_commit_timer.setInterval(80)
        self._geometry_commit_timer.timeout.connect(self.commit_current_geometry)

        self._build()

    @property
    def controller(self) -> OverlayWidgetController:
        return self._controller

    def apply_runtime_instance(self, instance: OverlayRuntimeInstance) -> None:
        self._instance_id = instance.instance_id
        self._locked = instance.state.locked
        self._suspend_geometry_events = True
        try:
            self._title.setText(instance.definition.display_name)
            state_text = "PREVIEW" if instance.state.preview_mode else "BLOCKED" if instance.state.entitlement_blocked else instance.state.lifecycle_status.upper()
            self._status.setText(state_text)
            self._pin_button.setText("UNPIN" if instance.state.pinned else "PIN")
            self._lock_button.setText("UNLOCK" if instance.state.locked else "LOCK")
            self._pass_button.setText("INTERACTIVE" if instance.state.click_through else "CLICK-THROUGH")
            self._grip.setVisible(not instance.state.locked)
            self._controller.apply_runtime_instance(instance)
            self._apply_window_flags(instance)
            self.setWindowOpacity(max(0.2, min(1.0, instance.placement.opacity)))
            if (
                self.x() != instance.placement.x
                or self.y() != instance.placement.y
                or self.width() != instance.placement.width
                or self.height() != instance.placement.height
            ):
                self.setGeometry(
                    instance.placement.x,
                    instance.placement.y,
                    instance.placement.width,
                    instance.placement.height,
                )
            if instance.state.visible:
                self.show()
                self.raise_()
            else:
                self.hide()
        finally:
            self._suspend_geometry_events = False

    def request_hide(self) -> None:
        if self._instance_id:
            self.visibility_requested.emit(self._instance_id, False)

    def request_show(self) -> None:
        if self._instance_id:
            self.visibility_requested.emit(self._instance_id, True)

    def toggle_pin(self) -> None:
        self._emit_pin_toggle()

    def toggle_lock(self) -> None:
        self._emit_lock_toggle()

    def toggle_click_through(self) -> None:
        self._emit_click_through_toggle()

    def commit_current_geometry(self) -> None:
        if not self._instance_id:
            return
        screen_id = self._screen_id()
        self.placement_committed.emit(
            self._instance_id,
            self.x(),
            self.y(),
            self.width(),
            self.height(),
            screen_id,
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._instance_id:
            self.visibility_requested.emit(self._instance_id, False)
            event.ignore()
            return
        super().closeEvent(event)

    def moveEvent(self, event) -> None:  # noqa: ANN001
        super().moveEvent(event)
        if not self._suspend_geometry_events and self._instance_id:
            self._geometry_commit_timer.start()

    def resizeEvent(self, event) -> None:  # noqa: ANN001
        super().resizeEvent(event)
        if not self._suspend_geometry_events and self._instance_id:
            self._geometry_commit_timer.start()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        drag_targets = {
            target
            for target in (
                getattr(self, "_header", None),
                getattr(self, "_title", None),
                getattr(self, "_status", None),
            )
            if target is not None
        }
        if watched in drag_targets and isinstance(event, QMouseEvent):
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton and not self._locked:
                self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                event.accept()
                return True
            if event.type() == QEvent.Type.MouseMove and self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
                self.move(event.globalPosition().toPoint() - self._drag_offset)
                event.accept()
                return True
            if event.type() == QEvent.Type.MouseButtonRelease:
                self._drag_offset = None
                self._geometry_commit_timer.start()
                event.accept()
                return True
        return super().eventFilter(watched, event)

    def _build(self) -> None:
        self.setObjectName("OverlayWindowHost")
        self.setStyleSheet(
            f"""
            QWidget#OverlayWindowHost {{
                background-color: rgba(11, 12, 15, 180);
                border: 1px solid rgba(240, 237, 229, 32);
                border-radius: 12px;
            }}
            QFrame#OverlayWindowHeader {{
                background-color: rgba(30, 33, 40, 180);
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }}
            QLabel#OverlayWindowTitle {{
                color: {CHALK};
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 1px;
            }}
            QLabel#OverlayWindowStatus {{
                color: {STEEL};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1px;
            }}
            QPushButton#OverlayWindowButton {{
                background-color: rgba(240, 237, 229, 16);
                border: 1px solid rgba(240, 237, 229, 26);
                border-radius: 7px;
                padding: 4px 8px;
                color: {CHALK};
                font-size: 10px;
                font-weight: 700;
            }}
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._header = QFrame()
        self._header.setObjectName("OverlayWindowHeader")
        self._header.installEventFilter(self)
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(12, 10, 10, 10)
        header_layout.setSpacing(8)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self._title = QLabel("Overlay")
        self._title.setObjectName("OverlayWindowTitle")
        self._title.installEventFilter(self)
        self._status = QLabel("IDLE")
        self._status.setObjectName("OverlayWindowStatus")
        self._status.installEventFilter(self)
        title_col.addWidget(self._title)
        title_col.addWidget(self._status)
        header_layout.addLayout(title_col)
        header_layout.addStretch(1)

        self._pin_button = QPushButton("PIN")
        self._pin_button.setObjectName("OverlayWindowButton")
        self._pin_button.clicked.connect(self._emit_pin_toggle)
        self._lock_button = QPushButton("LOCK")
        self._lock_button.setObjectName("OverlayWindowButton")
        self._lock_button.clicked.connect(self._emit_lock_toggle)
        self._pass_button = QPushButton("CLICK-THROUGH")
        self._pass_button.setObjectName("OverlayWindowButton")
        self._pass_button.clicked.connect(self._emit_click_through_toggle)
        self._hide_button = QPushButton("HIDE")
        self._hide_button.setObjectName("OverlayWindowButton")
        self._hide_button.clicked.connect(self.request_hide)

        for button in (self._pin_button, self._lock_button, self._pass_button, self._hide_button):
            header_layout.addWidget(button)

        root.addWidget(self._header)
        root.addWidget(self._controller, 1)

        footer = QHBoxLayout()
        footer.setContentsMargins(10, 0, 10, 8)
        footer.addStretch(1)
        self._grip = QSizeGrip(self)
        footer.addWidget(self._grip)
        root.addLayout(footer)

    def _apply_window_flags(self, instance: OverlayRuntimeInstance) -> None:
        desired_flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if instance.state.pinned:
            desired_flags |= Qt.WindowType.WindowStaysOnTopHint
        if instance.state.click_through:
            desired_flags |= Qt.WindowType.WindowTransparentForInput
        if self.windowFlags() != desired_flags:
            visible = self.isVisible()
            self.setWindowFlags(desired_flags)
            self.setAttribute(
                Qt.WidgetAttribute.WA_ShowWithoutActivating,
                instance.state.pinned or instance.state.click_through,
            )
            if visible and instance.state.visible:
                self.show()

    def _screen_id(self) -> str:
        screen = self.screen()
        if screen is None:
            return "primary"
        return str(screen.name() or "primary")

    def _emit_pin_toggle(self) -> None:
        if self._instance_id:
            self.pin_requested.emit(self._instance_id, self._pin_button.text() == "PIN")

    def _emit_lock_toggle(self) -> None:
        if self._instance_id:
            self.lock_requested.emit(self._instance_id, self._lock_button.text() == "LOCK")

    def _emit_click_through_toggle(self) -> None:
        if self._instance_id:
            self.click_through_requested.emit(self._instance_id, self._pass_button.text() == "CLICK-THROUGH")


class _OverlayRuntimeEventRelay(QObject):
    runtime_event = Signal(object)


@dataclass(slots=True)
class _OverlayWindowBinding:
    instance: OverlayRuntimeInstance
    host: OverlayWindowHost
    controller: OverlayWidgetController


class OverlayWindowManager(QObject):
    """Qt-side coordinator that maps runtime overlay instances onto floating windows."""

    window_event = Signal(object)
    descriptors_changed = Signal()

    def __init__(
        self,
        *,
        runtime: OverlayInstanceLifecycleService,
        factories: OverlayWidgetFactoryRegistry | None = None,
        state_committer: OverlayWindowStateCommitter | None = None,
        update_rate_hz: int = 60,
        show_on_screen: bool = True,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._runtime = runtime
        self._factories = factories or build_default_overlay_widget_factories()
        self._state_committer = state_committer
        self._show_on_screen = show_on_screen
        self._bindings: dict[str, _OverlayWindowBinding] = {}
        self._latest_live_payload: dict[str, object] | None = None

        self._event_relay = _OverlayRuntimeEventRelay(self)
        self._event_relay.runtime_event.connect(self._handle_runtime_event)
        self._unsubscribe = self._runtime.event_bus.subscribe(
            lambda event: self._event_relay.runtime_event.emit(event)
        )

        self._update_timer = QTimer(self)
        self._update_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._update_timer.timeout.connect(self.flush_live_payloads)
        self.set_update_rate_hz(update_rate_hz)
        self._update_timer.start()
        self.sync_runtime_instances()

    def descriptors(self) -> tuple[OverlayWindowDescriptor, ...]:
        return tuple(
            _descriptor_from_instance(binding.instance)
            for binding in self._bindings.values()
        )

    def window(self, instance_id: str) -> OverlayWindowHost | None:
        binding = self._bindings.get(instance_id)
        return binding.host if binding is not None else None

    def controller(self, instance_id: str) -> OverlayWidgetController | None:
        binding = self._bindings.get(instance_id)
        return binding.controller if binding is not None else None

    def sync_runtime_instances(self) -> None:
        live_instances = {
            instance.instance_id: instance
            for instance in self._runtime.list_instances()
        }
        for instance_id in list(self._bindings):
            if instance_id not in live_instances:
                self._unmount_instance(instance_id, source="sync")
        for instance in live_instances.values():
            self._mount_or_update_instance(instance, source="sync")

    def set_update_rate_hz(self, value: int) -> None:
        hz = max(5, min(120, int(value)))
        self._update_timer.setInterval(max(8, round(1000 / hz)))

    def push_live_payload(self, payload: dict[str, object]) -> None:
        self._latest_live_payload = dict(payload)

    def flush_live_payloads(self) -> None:
        payload = self._latest_live_payload
        if not payload:
            return
        for binding in tuple(self._bindings.values()):
            if binding.instance.state.visible:
                binding.controller.apply_live_payload(payload)

    def open_preview_overlay(
        self,
        overlay_id: str,
        *,
        screen_id: str = "primary",
        settings: dict[str, object] | None = None,
    ) -> OverlayRuntimeInstance:
        return self._runtime.create_instance(
            overlay_id,
            layout_id=f"preview:{overlay_id}",
            screen_id=screen_id,
            visible=True,
            active=True,
            preview_mode=True,
            instance_overrides=dict(settings or {}),
            instance_id=f"preview-{uuid.uuid4().hex[:10]}",
        )

    def close_preview_overlay(self, instance_id: str) -> None:
        instance = self._runtime.instance(instance_id)
        if not instance.state.preview_mode:
            raise ValueError(f"Overlay instance '{instance_id}' is not a preview window")
        self._runtime.destroy(instance_id)

    def shutdown(self, *, destroy_runtime_instances: bool = False) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None
        self._update_timer.stop()
        if destroy_runtime_instances:
            for instance_id in list(self._bindings):
                if instance_id in {instance.instance_id for instance in self._runtime.list_instances()}:
                    self._runtime.destroy(instance_id)
        for instance_id in list(self._bindings):
            self._unmount_instance(instance_id, source="shutdown")

    def _handle_runtime_event(self, event: OverlayInstanceEvent) -> None:
        if event.kind == "destroyed":
            instance = self._runtime.instance(event.instance_id)
            descriptor = _descriptor_from_instance(instance)
            self._unmount_instance(event.instance_id, source="runtime_event")
            self.window_event.emit(
                OverlayWindowManagerEvent(
                    kind="window_destroyed",
                    descriptor=descriptor,
                    source="runtime_event",
                )
            )
            return

        instance = self._runtime.instance(event.instance_id)
        self._mount_or_update_instance(instance, source="runtime_event")
        event_kind = "window_created" if event.kind in {"created", "restored"} else "window_updated"
        self.window_event.emit(
            OverlayWindowManagerEvent(
                kind=event_kind,
                descriptor=_descriptor_from_instance(instance),
                source="runtime_event",
                message=event.kind,
            )
        )

    def _mount_or_update_instance(self, instance: OverlayRuntimeInstance, *, source: str) -> None:
        binding = self._bindings.get(instance.instance_id)
        if binding is None:
            try:
                controller = self._factories.create(instance)
                host = OverlayWindowHost(
                    controller,
                    show_on_screen=self._show_on_screen,
                )
                self._wire_host(host)
                binding = _OverlayWindowBinding(instance=instance, host=host, controller=controller)
                self._bindings[instance.instance_id] = binding
            except Exception as exc:
                self.window_event.emit(
                    OverlayWindowManagerEvent(
                        kind="window_failed",
                        descriptor=_descriptor_from_instance(instance),
                        source=source,
                        message=str(exc),
                    )
                )
                return
        binding.instance = instance
        binding.host.apply_runtime_instance(instance)
        self.descriptors_changed.emit()

    def _unmount_instance(self, instance_id: str, *, source: str) -> None:
        binding = self._bindings.pop(instance_id, None)
        if binding is None:
            return
        binding.controller.shutdown()
        binding.host.hide()
        binding.host.deleteLater()
        self.descriptors_changed.emit()
        self.window_event.emit(
            OverlayWindowManagerEvent(
                kind="window_unmounted",
                descriptor=_descriptor_from_instance(binding.instance),
                source=source,
            )
        )

    def _wire_host(self, host: OverlayWindowHost) -> None:
        host.placement_committed.connect(self._on_placement_committed)
        host.visibility_requested.connect(self._on_visibility_requested)
        host.pin_requested.connect(self._on_pin_requested)
        host.lock_requested.connect(self._on_lock_requested)
        host.click_through_requested.connect(self._on_click_through_requested)

    def _on_placement_committed(
        self,
        instance_id: str,
        x: int,
        y: int,
        width: int,
        height: int,
        screen_id: str,
    ) -> None:
        instance = self._runtime.resize(instance_id, width=width, height=height)
        instance = self._runtime.move(instance_id, x=x, y=y, screen_id=screen_id)
        self._commit_placement(instance, source="user")

    def _on_visibility_requested(self, instance_id: str, visible: bool) -> None:
        instance = self._runtime.show(instance_id) if visible else self._runtime.hide(instance_id)
        if self._state_committer is not None:
            self._state_committer.persist_visibility(instance)
        self.window_event.emit(
            OverlayWindowManagerEvent(
                kind="visibility_committed",
                descriptor=_descriptor_from_instance(instance),
                source="user",
            )
        )

    def _on_pin_requested(self, instance_id: str, pinned: bool) -> None:
        instance = self._runtime.pin(instance_id) if pinned else self._runtime.unpin(instance_id)
        self._commit_placement(instance, source="user")

    def _on_lock_requested(self, instance_id: str, locked: bool) -> None:
        instance = self._runtime.lock(instance_id) if locked else self._runtime.unlock(instance_id)
        self._commit_placement(instance, source="user")

    def _on_click_through_requested(self, instance_id: str, enabled: bool) -> None:
        instance = self._runtime.set_click_through(instance_id, enabled)
        if self._state_committer is not None:
            self._state_committer.persist_settings(instance)
        self.window_event.emit(
            OverlayWindowManagerEvent(
                kind="click_through_committed",
                descriptor=_descriptor_from_instance(instance),
                source="user",
            )
        )

    def _commit_placement(self, instance: OverlayRuntimeInstance, *, source: str) -> None:
        if self._state_committer is not None:
            self._state_committer.persist_placement(instance)
        self.window_event.emit(
            OverlayWindowManagerEvent(
                kind="placement_committed",
                descriptor=_descriptor_from_instance(instance),
                source=source,
            )
        )


def _descriptor_from_instance(instance: OverlayRuntimeInstance) -> OverlayWindowDescriptor:
    return OverlayWindowDescriptor(
        instance_id=instance.instance_id,
        overlay_id=instance.overlay_id,
        layout_id=instance.layout_id,
        renderer_key=instance.definition.renderer_key,
        display_name=instance.definition.display_name,
        visible=instance.state.visible,
        active=instance.state.active,
        preview_mode=instance.state.preview_mode,
        pinned=instance.state.pinned,
        locked=instance.state.locked,
        click_through=instance.state.click_through,
        entitlement_blocked=instance.state.entitlement_blocked,
        lifecycle_status=instance.state.lifecycle_status,
        screen_id=instance.screen_id,
        error=instance.state.error,
    )
