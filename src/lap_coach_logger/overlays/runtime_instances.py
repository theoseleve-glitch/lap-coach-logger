"""Runtime overlay instance models and lifecycle service."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

from lap_coach_logger.overlays.models import (
    OverlayDefinition,
    OverlayInstance,
    OverlayPlacement,
    utc_now_iso,
)
from lap_coach_logger.overlays.registry import OverlayRegistry
from lap_coach_logger.overlays.settings_service import OverlaySettingsSchemaService

OverlayInstanceLifecycleStatus = Literal[
    "created",
    "visible",
    "hidden",
    "preview",
    "blocked",
    "destroyed",
    "error",
]


@dataclass(slots=True)
class OverlayInstanceState:
    visible: bool = False
    pinned: bool = False
    locked: bool = False
    click_through: bool = False
    active: bool = False
    preview_mode: bool = False
    entitlement_blocked: bool = False
    lifecycle_status: OverlayInstanceLifecycleStatus = "created"
    error: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "visible": self.visible,
            "pinned": self.pinned,
            "locked": self.locked,
            "click_through": self.click_through,
            "active": self.active,
            "preview_mode": self.preview_mode,
            "entitlement_blocked": self.entitlement_blocked,
            "lifecycle_status": self.lifecycle_status,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayInstanceState:
        payload = _dict_copy(data)
        return cls(
            visible=bool(payload.get("visible")),
            pinned=bool(payload.get("pinned")),
            locked=bool(payload.get("locked")),
            click_through=bool(payload.get("click_through")),
            active=bool(payload.get("active")),
            preview_mode=bool(payload.get("preview_mode")),
            entitlement_blocked=bool(payload.get("entitlement_blocked")),
            lifecycle_status=str(payload.get("lifecycle_status") or "created"),
            error=str(payload.get("error") or ""),
        )


@dataclass(slots=True)
class OverlayRuntimeMetrics:
    created_at_utc: str = field(default_factory=utc_now_iso)
    updated_at_utc: str = field(default_factory=utc_now_iso)
    shown_at_utc: str = ""
    hidden_at_utc: str = ""
    destroyed_at_utc: str = ""
    move_count: int = 0
    resize_count: int = 0
    settings_update_count: int = 0
    show_count: int = 0
    hide_count: int = 0
    transition_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
            "shown_at_utc": self.shown_at_utc,
            "hidden_at_utc": self.hidden_at_utc,
            "destroyed_at_utc": self.destroyed_at_utc,
            "move_count": self.move_count,
            "resize_count": self.resize_count,
            "settings_update_count": self.settings_update_count,
            "show_count": self.show_count,
            "hide_count": self.hide_count,
            "transition_count": self.transition_count,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayRuntimeMetrics:
        payload = _dict_copy(data)
        return cls(
            created_at_utc=str(payload.get("created_at_utc") or utc_now_iso()),
            updated_at_utc=str(payload.get("updated_at_utc") or utc_now_iso()),
            shown_at_utc=str(payload.get("shown_at_utc") or ""),
            hidden_at_utc=str(payload.get("hidden_at_utc") or ""),
            destroyed_at_utc=str(payload.get("destroyed_at_utc") or ""),
            move_count=int(payload.get("move_count") or 0),
            resize_count=int(payload.get("resize_count") or 0),
            settings_update_count=int(payload.get("settings_update_count") or 0),
            show_count=int(payload.get("show_count") or 0),
            hide_count=int(payload.get("hide_count") or 0),
            transition_count=int(payload.get("transition_count") or 0),
        )


@dataclass(slots=True)
class OverlayRuntimeInstance:
    instance_id: str
    overlay_id: str
    layout_id: str
    screen_id: str
    definition: OverlayDefinition
    placement: OverlayPlacement
    state: OverlayInstanceState
    metrics: OverlayRuntimeMetrics
    layout_overrides: dict[str, object] = field(default_factory=dict)
    instance_overrides: dict[str, object] = field(default_factory=dict)
    effective_settings: dict[str, object] = field(default_factory=dict)

    def to_dict(self, *, include_definition: bool = False) -> dict[str, object]:
        payload = {
            "instance_id": self.instance_id,
            "overlay_id": self.overlay_id,
            "layout_id": self.layout_id,
            "screen_id": self.screen_id,
            "placement": self.placement.to_dict(),
            "state": self.state.to_dict(),
            "metrics": self.metrics.to_dict(),
            "layout_overrides": dict(self.layout_overrides),
            "instance_overrides": dict(self.instance_overrides),
            "effective_settings": dict(self.effective_settings),
        }
        if include_definition:
            payload["definition"] = self.definition.to_dict()
        return payload

    @classmethod
    def from_dict(
        cls,
        data: object,
        *,
        definition: OverlayDefinition,
    ) -> OverlayRuntimeInstance:
        payload = _dict_copy(data)
        placement = OverlayPlacement.from_dict(payload.get("placement"))
        screen_id = str(payload.get("screen_id") or placement.monitor_id or "primary")
        return cls(
            instance_id=str(payload.get("instance_id") or ""),
            overlay_id=str(payload.get("overlay_id") or definition.overlay_id),
            layout_id=str(payload.get("layout_id") or ""),
            screen_id=screen_id,
            definition=definition,
            placement=placement,
            state=OverlayInstanceState.from_dict(payload.get("state")),
            metrics=OverlayRuntimeMetrics.from_dict(payload.get("metrics")),
            layout_overrides=_dict_copy(payload.get("layout_overrides")),
            instance_overrides=_dict_copy(payload.get("instance_overrides")),
            effective_settings=_dict_copy(payload.get("effective_settings")),
        )


@dataclass(slots=True, frozen=True)
class OverlayInstanceEvent:
    kind: str
    instance_id: str
    overlay_id: str
    layout_id: str
    timestamp_utc: str
    payload: dict[str, object] = field(default_factory=dict)


class OverlayInstanceEventBus:
    """Small callback event bus for runtime instance changes."""

    def __init__(self) -> None:
        self._listeners: dict[int, Callable[[OverlayInstanceEvent], None]] = {}
        self._next_token = 1

    def subscribe(self, listener: Callable[[OverlayInstanceEvent], None]) -> Callable[[], None]:
        token = self._next_token
        self._next_token += 1
        self._listeners[token] = listener

        def unsubscribe() -> None:
            self._listeners.pop(token, None)

        return unsubscribe

    def publish(self, event: OverlayInstanceEvent) -> None:
        for listener in tuple(self._listeners.values()):
            listener(event)


class OverlayInstanceLifecycleService:
    """Thread-safe runtime lifecycle manager for many simultaneous overlay instances."""

    def __init__(
        self,
        *,
        registry: OverlayRegistry,
        settings_service: OverlaySettingsSchemaService | None = None,
        event_bus: OverlayInstanceEventBus | None = None,
    ) -> None:
        self._registry = registry
        self._settings_service = settings_service
        self._events = event_bus or OverlayInstanceEventBus()
        self._lock = threading.RLock()
        self._instances: dict[str, OverlayRuntimeInstance] = {}
        self._destroyed: dict[str, OverlayRuntimeInstance] = {}

    @property
    def event_bus(self) -> OverlayInstanceEventBus:
        return self._events

    def create_instance(
        self,
        overlay_id: str,
        *,
        layout_id: str,
        screen_id: str = "primary",
        x: int = 0,
        y: int = 0,
        width: int | None = None,
        height: int | None = None,
        z_order: int = 0,
        visible: bool | None = None,
        pinned: bool = False,
        locked: bool = False,
        click_through: bool = False,
        active: bool | None = None,
        preview_mode: bool = False,
        entitlement_blocked: bool = False,
        layout_overrides: dict[str, object] | None = None,
        instance_overrides: dict[str, object] | None = None,
        instance_id: str | None = None,
    ) -> OverlayRuntimeInstance:
        with self._lock:
            definition = self._registry.get(overlay_id)
            runtime_instance_id = str(instance_id or f"rt-{uuid.uuid4().hex[:12]}")
            if runtime_instance_id in self._instances:
                raise ValueError(f"Overlay runtime instance '{runtime_instance_id}' already exists")

            layout_settings = dict(layout_overrides or {})
            instance_settings = dict(instance_overrides or {})
            effective_settings = self._resolve_effective_settings(
                definition,
                layout_overrides=layout_settings,
                instance_overrides=instance_settings,
            )
            resolved_width = int(width) if width is not None else int(effective_settings.get("width") or definition.layout.default_width)
            resolved_height = int(height) if height is not None else int(effective_settings.get("height") or definition.layout.default_height)

            placement = OverlayPlacement(
                x=int(x),
                y=int(y),
                width=resolved_width,
                height=resolved_height,
                scale=float(effective_settings.get("scale", 1.0)) if isinstance(effective_settings.get("scale"), (int, float)) else 1.0,
                opacity=float(effective_settings.get("opacity", 1.0)) if isinstance(effective_settings.get("opacity"), (int, float)) else 1.0,
                z_index=int(z_order),
                monitor_id=screen_id,
                pinned=bool(pinned),
                locked=bool(locked),
            )

            if entitlement_blocked:
                resolved_visible = False
                lifecycle_status: OverlayInstanceLifecycleStatus = "blocked"
            elif preview_mode:
                resolved_visible = True
                lifecycle_status = "preview"
            else:
                resolved_visible = bool(definition.default_enabled if visible is None else visible)
                lifecycle_status = "visible" if resolved_visible else "hidden"

            resolved_active = resolved_visible if active is None else bool(active)
            state = OverlayInstanceState(
                visible=resolved_visible,
                pinned=placement.pinned,
                locked=placement.locked,
                click_through=bool(click_through),
                active=False if entitlement_blocked else resolved_active,
                preview_mode=bool(preview_mode),
                entitlement_blocked=bool(entitlement_blocked),
                lifecycle_status=lifecycle_status,
            )
            metrics = OverlayRuntimeMetrics(
                shown_at_utc=utc_now_iso() if resolved_visible else "",
                show_count=1 if resolved_visible else 0,
                hide_count=0 if resolved_visible else 1,
                transition_count=1,
            )
            instance = OverlayRuntimeInstance(
                instance_id=runtime_instance_id,
                overlay_id=definition.overlay_id,
                layout_id=layout_id,
                screen_id=screen_id,
                definition=definition,
                placement=placement,
                state=state,
                metrics=metrics,
                layout_overrides=layout_settings,
                instance_overrides=instance_settings,
                effective_settings=effective_settings,
            )
            self._instances[runtime_instance_id] = instance
            self._emit("created", instance, payload={"visible": state.visible, "preview_mode": state.preview_mode})
            return instance

    def show(self, instance_id: str) -> OverlayRuntimeInstance:
        with self._lock:
            instance = self._require_active_instance(instance_id)
            self._ensure_not_destroyed(instance)
            if instance.state.entitlement_blocked:
                raise PermissionError(f"Overlay '{instance.overlay_id}' is entitlement-blocked")
            instance.state.visible = True
            instance.state.active = True
            instance.state.lifecycle_status = "preview" if instance.state.preview_mode else "visible"
            instance.metrics.shown_at_utc = utc_now_iso()
            instance.metrics.show_count += 1
            self._touch_metrics(instance)
            self._emit("shown", instance)
            return instance

    def hide(self, instance_id: str) -> OverlayRuntimeInstance:
        with self._lock:
            instance = self._require_active_instance(instance_id)
            self._ensure_not_destroyed(instance)
            instance.state.visible = False
            instance.state.active = False
            instance.state.lifecycle_status = "blocked" if instance.state.entitlement_blocked else "hidden"
            instance.metrics.hidden_at_utc = utc_now_iso()
            instance.metrics.hide_count += 1
            self._touch_metrics(instance)
            self._emit("hidden", instance)
            return instance

    def move(self, instance_id: str, *, x: int, y: int, screen_id: str | None = None) -> OverlayRuntimeInstance:
        with self._lock:
            instance = self._require_active_instance(instance_id)
            self._ensure_mutable(instance)
            instance.placement.x = int(x)
            instance.placement.y = int(y)
            if screen_id is not None:
                instance.screen_id = str(screen_id)
                instance.placement.monitor_id = instance.screen_id
            instance.metrics.move_count += 1
            self._touch_metrics(instance)
            self._emit("moved", instance, payload={"x": instance.placement.x, "y": instance.placement.y, "screen_id": instance.screen_id})
            return instance

    def resize(self, instance_id: str, *, width: int, height: int) -> OverlayRuntimeInstance:
        with self._lock:
            instance = self._require_active_instance(instance_id)
            self._ensure_mutable(instance)
            instance.placement.width = int(width)
            instance.placement.height = int(height)
            instance.metrics.resize_count += 1
            self._touch_metrics(instance)
            self._emit("resized", instance, payload={"width": instance.placement.width, "height": instance.placement.height})
            return instance

    def update_settings(
        self,
        instance_id: str,
        *,
        layout_overrides: dict[str, object] | None = None,
        instance_overrides: dict[str, object] | None = None,
        replace_layout_overrides: bool = False,
        replace_instance_overrides: bool = False,
    ) -> OverlayRuntimeInstance:
        with self._lock:
            instance = self._require_active_instance(instance_id)
            self._ensure_not_destroyed(instance)
            if layout_overrides is not None:
                if replace_layout_overrides:
                    instance.layout_overrides = dict(layout_overrides)
                else:
                    merged = dict(instance.layout_overrides)
                    merged.update(layout_overrides)
                    instance.layout_overrides = merged
            if instance_overrides is not None:
                if replace_instance_overrides:
                    instance.instance_overrides = dict(instance_overrides)
                else:
                    merged = dict(instance.instance_overrides)
                    merged.update(instance_overrides)
                    instance.instance_overrides = merged

            instance.effective_settings = self._resolve_effective_settings(
                instance.definition,
                layout_overrides=instance.layout_overrides,
                instance_overrides=instance.instance_overrides,
            )
            if isinstance(instance.effective_settings.get("width"), (int, float)):
                instance.placement.width = int(instance.effective_settings["width"])
            if isinstance(instance.effective_settings.get("height"), (int, float)):
                instance.placement.height = int(instance.effective_settings["height"])
            if isinstance(instance.effective_settings.get("scale"), (int, float)):
                instance.placement.scale = float(instance.effective_settings["scale"])
            if isinstance(instance.effective_settings.get("opacity"), (int, float)):
                instance.placement.opacity = float(instance.effective_settings["opacity"])
            instance.metrics.settings_update_count += 1
            self._touch_metrics(instance)
            self._emit("settings_updated", instance)
            return instance

    def lock(self, instance_id: str) -> OverlayRuntimeInstance:
        with self._lock:
            instance = self._require_active_instance(instance_id)
            self._ensure_not_destroyed(instance)
            instance.state.locked = True
            instance.placement.locked = True
            self._touch_metrics(instance)
            self._emit("locked", instance)
            return instance

    def unlock(self, instance_id: str) -> OverlayRuntimeInstance:
        with self._lock:
            instance = self._require_active_instance(instance_id)
            self._ensure_not_destroyed(instance)
            instance.state.locked = False
            instance.placement.locked = False
            self._touch_metrics(instance)
            self._emit("unlocked", instance)
            return instance

    def pin(self, instance_id: str) -> OverlayRuntimeInstance:
        with self._lock:
            instance = self._require_active_instance(instance_id)
            self._ensure_not_destroyed(instance)
            instance.state.pinned = True
            instance.placement.pinned = True
            self._touch_metrics(instance)
            self._emit("pinned", instance)
            return instance

    def unpin(self, instance_id: str) -> OverlayRuntimeInstance:
        with self._lock:
            instance = self._require_active_instance(instance_id)
            self._ensure_not_destroyed(instance)
            instance.state.pinned = False
            instance.placement.pinned = False
            self._touch_metrics(instance)
            self._emit("unpinned", instance)
            return instance

    def set_click_through(self, instance_id: str, enabled: bool) -> OverlayRuntimeInstance:
        with self._lock:
            instance = self._require_active_instance(instance_id)
            self._ensure_not_destroyed(instance)
            instance.state.click_through = bool(enabled)
            self._touch_metrics(instance)
            self._emit("click_through_updated", instance, payload={"click_through": instance.state.click_through})
            return instance

    def enter_preview_mode(self, instance_id: str) -> OverlayRuntimeInstance:
        with self._lock:
            instance = self._require_active_instance(instance_id)
            self._ensure_not_destroyed(instance)
            instance.state.preview_mode = True
            instance.state.visible = True
            instance.state.active = True
            instance.state.lifecycle_status = "preview"
            instance.metrics.shown_at_utc = utc_now_iso()
            self._touch_metrics(instance)
            self._emit("preview_entered", instance)
            return instance

    def exit_preview_mode(self, instance_id: str) -> OverlayRuntimeInstance:
        with self._lock:
            instance = self._require_active_instance(instance_id)
            self._ensure_not_destroyed(instance)
            instance.state.preview_mode = False
            if instance.state.entitlement_blocked:
                instance.state.visible = False
                instance.state.active = False
                instance.state.lifecycle_status = "blocked"
            elif instance.state.visible:
                instance.state.lifecycle_status = "visible"
            else:
                instance.state.active = False
                instance.state.lifecycle_status = "hidden"
            self._touch_metrics(instance)
            self._emit("preview_exited", instance)
            return instance

    def destroy(self, instance_id: str) -> OverlayRuntimeInstance:
        with self._lock:
            instance = self._require_active_instance(instance_id)
            instance.state.visible = False
            instance.state.active = False
            instance.state.preview_mode = False
            instance.state.lifecycle_status = "destroyed"
            instance.metrics.destroyed_at_utc = utc_now_iso()
            self._touch_metrics(instance)
            self._instances.pop(instance_id, None)
            self._destroyed[instance_id] = instance
            self._emit("destroyed", instance)
            return instance

    def serialize_state(self, instance_id: str, *, include_definition: bool = False) -> dict[str, object]:
        with self._lock:
            instance = self._get_any_instance(instance_id)
            return instance.to_dict(include_definition=include_definition)

    def restore_state(self, snapshot: dict[str, object]) -> OverlayRuntimeInstance:
        with self._lock:
            overlay_id = str(snapshot.get("overlay_id") or "")
            definition = self._registry.get(overlay_id)
            instance = OverlayRuntimeInstance.from_dict(snapshot, definition=definition)
            instance.effective_settings = self._resolve_effective_settings(
                definition,
                layout_overrides=instance.layout_overrides,
                instance_overrides=instance.instance_overrides,
            )
            instance.screen_id = str(instance.screen_id or instance.placement.monitor_id or "primary")
            instance.placement.monitor_id = instance.screen_id
            instance.state.pinned = instance.placement.pinned or instance.state.pinned
            instance.state.locked = instance.placement.locked or instance.state.locked
            if instance.state.lifecycle_status == "destroyed":
                self._destroyed[instance.instance_id] = instance
            else:
                self._instances[instance.instance_id] = instance
            self._emit("restored", instance)
            return instance

    def to_persisted_instance(self, instance_id: str) -> OverlayInstance:
        with self._lock:
            instance = self._get_any_instance(instance_id)
            return OverlayInstance(
                instance_id=instance.instance_id,
                overlay_id=instance.overlay_id,
                preset_id=instance.layout_id,
                name=instance.definition.display_name,
                enabled=instance.state.visible and not instance.state.entitlement_blocked,
                slot_id="",
                placement=OverlayPlacement(
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
                ),
                settings=dict(instance.instance_overrides),
            )

    def restore_from_persisted_instance(
        self,
        record: OverlayInstance,
        *,
        layout_overrides: dict[str, object] | None = None,
        preview_mode: bool = False,
        entitlement_blocked: bool = False,
        click_through: bool = False,
    ) -> OverlayRuntimeInstance:
        return self.create_instance(
            record.overlay_id,
            layout_id=record.preset_id,
            screen_id=record.placement.monitor_id,
            x=record.placement.x,
            y=record.placement.y,
            width=record.placement.width,
            height=record.placement.height,
            z_order=record.placement.z_index,
            visible=record.enabled,
            pinned=record.placement.pinned,
            locked=record.placement.locked,
            click_through=click_through,
            preview_mode=preview_mode,
            entitlement_blocked=entitlement_blocked,
            layout_overrides=layout_overrides,
            instance_overrides=record.settings,
            instance_id=record.instance_id,
        )

    def list_instances(self, *, include_destroyed: bool = False) -> tuple[OverlayRuntimeInstance, ...]:
        with self._lock:
            live = list(self._instances.values())
            if include_destroyed:
                live.extend(self._destroyed.values())
            return tuple(live)

    def instance(self, instance_id: str) -> OverlayRuntimeInstance:
        with self._lock:
            return self._get_any_instance(instance_id)

    def instances_for_layout(self, layout_id: str) -> tuple[OverlayRuntimeInstance, ...]:
        with self._lock:
            return tuple(instance for instance in self._instances.values() if instance.layout_id == layout_id)

    def _resolve_effective_settings(
        self,
        definition: OverlayDefinition,
        *,
        layout_overrides: dict[str, object],
        instance_overrides: dict[str, object],
    ) -> dict[str, object]:
        merged = dict(layout_overrides)
        merged.update(instance_overrides)
        if self._settings_service is not None and definition.settings_schema_ref:
            return self._settings_service.merge_overrides(definition.settings_schema_ref, merged).values
        return dict(definition.default_settings()) | merged

    def _touch_metrics(self, instance: OverlayRuntimeInstance) -> None:
        instance.metrics.updated_at_utc = utc_now_iso()
        instance.metrics.transition_count += 1

    def _ensure_not_destroyed(self, instance: OverlayRuntimeInstance) -> None:
        if instance.state.lifecycle_status == "destroyed":
            raise RuntimeError(f"Overlay instance '{instance.instance_id}' is destroyed")

    def _ensure_mutable(self, instance: OverlayRuntimeInstance) -> None:
        self._ensure_not_destroyed(instance)
        if instance.state.locked:
            raise RuntimeError(f"Overlay instance '{instance.instance_id}' is locked")

    def _require_active_instance(self, instance_id: str) -> OverlayRuntimeInstance:
        try:
            return self._instances[instance_id]
        except KeyError as exc:
            raise KeyError(f"Unknown active overlay instance '{instance_id}'") from exc

    def _get_any_instance(self, instance_id: str) -> OverlayRuntimeInstance:
        if instance_id in self._instances:
            return self._instances[instance_id]
        if instance_id in self._destroyed:
            return self._destroyed[instance_id]
        raise KeyError(f"Unknown overlay instance '{instance_id}'")

    def _emit(self, kind: str, instance: OverlayRuntimeInstance, *, payload: dict[str, object] | None = None) -> None:
        self._events.publish(
            OverlayInstanceEvent(
                kind=kind,
                instance_id=instance.instance_id,
                overlay_id=instance.overlay_id,
                layout_id=instance.layout_id,
                timestamp_utc=utc_now_iso(),
                payload=dict(payload or {}),
            )
        )


def _dict_copy(data: object) -> dict[str, object]:
    if not isinstance(data, dict):
        return {}
    return {str(key): value for key, value in data.items()}
