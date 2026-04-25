"""High-level overlay platform service for the desktop application."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import asdict

from lap_coach_logger.overlays.entitlements import (
    OverlayEntitlementContext,
    OverlayEntitlementResolver,
    StaticOverlayEntitlementResolver,
)
from lap_coach_logger.overlays.models import (
    OverlayBrowserSnapshot,
    OverlayCatalogFilter,
    OverlayEvent,
    OverlayInstance,
    OverlayLayoutSlot,
    OverlayPlacement,
    OverlayPreset,
    OverlayPresetScope,
    OverlayPreviewSession,
    OverlayStateDocument,
    utc_now_iso,
)
from lap_coach_logger.overlays.registry import OverlayRegistry
from lap_coach_logger.overlays.runtime import OverlayRuntimeController
from lap_coach_logger.overlays.store import OverlayStateStore


class OverlayEventBus:
    """Small callback-based event bus that avoids UI-layer signal sprawl."""

    def __init__(self) -> None:
        self._listeners: dict[int, Callable[[OverlayEvent], None]] = {}
        self._next_token = 1

    def subscribe(self, listener: Callable[[OverlayEvent], None]) -> Callable[[], None]:
        token = self._next_token
        self._next_token += 1
        self._listeners[token] = listener

        def unsubscribe() -> None:
            self._listeners.pop(token, None)

        return unsubscribe

    def publish(self, event: OverlayEvent) -> None:
        for listener in tuple(self._listeners.values()):
            listener(event)


class OverlayManagerService:
    """Owns overlay catalog state, persistence, runtime sync, and entitlement checks."""

    def __init__(
        self,
        *,
        registry: OverlayRegistry,
        store: OverlayStateStore,
        entitlement_resolver: OverlayEntitlementResolver | None = None,
        runtime: OverlayRuntimeController | None = None,
        event_bus: OverlayEventBus | None = None,
    ) -> None:
        self._registry = registry
        self._store = store
        self._entitlements = entitlement_resolver or StaticOverlayEntitlementResolver()
        self._runtime = runtime or OverlayRuntimeController()
        self._events = event_bus or OverlayEventBus()
        self._entitlement_context = OverlayEntitlementContext()
        self._document = self._store.load()
        self._ensure_default_preset()
        self._sync_active_flags()
        self._runtime.sync_document(self._document)

    @property
    def event_bus(self) -> OverlayEventBus:
        return self._events

    def set_entitlement_context(self, context: OverlayEntitlementContext) -> None:
        self._entitlement_context = context
        self._events.publish(OverlayEvent(kind="entitlements_changed", message="Overlay entitlements updated"))

    def document(self) -> OverlayStateDocument:
        return self._document

    def catalog(self, *, filter_spec: OverlayCatalogFilter | None = None) -> OverlayBrowserSnapshot:
        entries = self._registry.catalog_entries(
            filter_spec=filter_spec,
            favorites=set(self._document.favorite_overlay_ids),
            entitlement_resolver=self._entitlements,
            entitlement_context=self._entitlement_context,
        )
        categories = tuple(dict.fromkeys(entry.category for entry in entries))
        return OverlayBrowserSnapshot(
            active_preset_id=self._document.active_preset_id,
            categories=categories,
            entries=entries,
        )

    def presets(self) -> tuple[OverlayPreset, ...]:
        return tuple(self._document.presets)

    def runtime_states(self):
        return self._runtime.runtime_states()

    def preview_sessions(self) -> tuple[OverlayPreviewSession, ...]:
        return self._runtime.preview_sessions()

    def toggle_favorite(self, overlay_id: str) -> bool:
        if overlay_id not in {definition.overlay_id for definition in self._registry.list_definitions()}:
            raise KeyError(f"Unknown overlay '{overlay_id}'")
        favorite_ids = set(self._document.favorite_overlay_ids)
        if overlay_id in favorite_ids:
            favorite_ids.remove(overlay_id)
            is_favorite = False
        else:
            favorite_ids.add(overlay_id)
            is_favorite = True
        self._document.favorite_overlay_ids = sorted(favorite_ids)
        self._document.updated_at_utc = utc_now_iso()
        self._persist("catalog_changed", overlay_id=overlay_id, message="Overlay favorite updated")
        return is_favorite

    def create_preset(
        self,
        *,
        name: str,
        description: str = "",
        scope: OverlayPresetScope | None = None,
        slots: list[OverlayLayoutSlot] | None = None,
    ) -> OverlayPreset:
        preset = OverlayPreset(
            preset_id=f"preset-{uuid.uuid4().hex[:10]}",
            name=name.strip() or "Preset",
            description=description.strip(),
            scope=scope or OverlayPresetScope(),
            slots=list(slots or []),
        )
        self._document.presets.append(preset)
        if not self._document.active_preset_id:
            self._document.active_preset_id = preset.preset_id
        self._sync_active_flags()
        self._document.updated_at_utc = utc_now_iso()
        self._persist("preset_changed", preset_id=preset.preset_id, message="Overlay preset created")
        return preset

    def activate_preset(self, preset_id: str) -> None:
        preset = self._preset(preset_id)
        self._document.active_preset_id = preset.preset_id
        self._sync_active_flags()
        self._document.updated_at_utc = utc_now_iso()
        self._runtime.sync_document(self._document)
        self._persist("runtime_changed", preset_id=preset_id, message="Overlay preset activated")

    def add_overlay_instance(
        self,
        overlay_id: str,
        *,
        preset_id: str | None = None,
        slot_id: str = "",
        name: str = "",
        settings: dict[str, object] | None = None,
        placement: OverlayPlacement | None = None,
    ) -> OverlayInstance:
        definition = self._registry.get(overlay_id)
        entitlement = self._entitlements.evaluate(definition, context=self._entitlement_context)
        if not entitlement.can_activate:
            raise PermissionError(entitlement.reason)

        preset = self._preset(preset_id or self._document.active_preset_id)
        normalized_settings, issues = self._registry.validate_settings(overlay_id, settings, include_defaults=True)
        instance_id = f"overlay-{uuid.uuid4().hex[:10]}"
        final_placement = placement or OverlayPlacement(
            width=definition.layout.default_width,
            height=definition.layout.default_height,
            scale=float(normalized_settings.get("scale", 1.0)) if isinstance(normalized_settings.get("scale"), (int, float)) else 1.0,
            opacity=float(normalized_settings.get("opacity", 1.0)) if isinstance(normalized_settings.get("opacity"), (int, float)) else 1.0,
        )
        if slot_id:
            self._assign_slot_record(preset, slot_id=slot_id, instance_id=instance_id, overlay_id=overlay_id)
        instance = OverlayInstance(
            instance_id=instance_id,
            overlay_id=overlay_id,
            preset_id=preset.preset_id,
            name=name.strip() or definition.display_name,
            slot_id=slot_id,
            placement=final_placement,
            settings=normalized_settings,
        )
        self._document.instances.append(instance)
        if instance_id not in preset.instance_ids:
            preset.instance_ids.append(instance_id)
        preset.updated_at_utc = utc_now_iso()
        self._document.updated_at_utc = utc_now_iso()
        self._runtime.sync_document(self._document)
        message = "Overlay instance created"
        if issues:
            message = f"{message} ({'; '.join(issues)})"
        self._persist("instance_changed", overlay_id=overlay_id, instance_id=instance_id, preset_id=preset.preset_id, message=message)
        return instance

    def update_instance_settings(self, instance_id: str, changes: dict[str, object]) -> tuple[OverlayInstance, list[str]]:
        instance = self._instance(instance_id)
        merged = dict(instance.settings)
        merged.update(changes)
        normalized, issues = self._registry.validate_settings(instance.overlay_id, merged, include_defaults=True)
        instance.settings = normalized
        if isinstance(normalized.get("scale"), (int, float)):
            instance.placement.scale = float(normalized["scale"])
        if isinstance(normalized.get("opacity"), (int, float)):
            instance.placement.opacity = float(normalized["opacity"])
        instance.updated_at_utc = utc_now_iso()
        self._document.updated_at_utc = utc_now_iso()
        self._persist("instance_changed", overlay_id=instance.overlay_id, instance_id=instance_id, preset_id=instance.preset_id, message="Overlay settings updated")
        return instance, issues

    def update_instance_placement(
        self,
        instance_id: str,
        *,
        x: int | None = None,
        y: int | None = None,
        width: int | None = None,
        height: int | None = None,
        scale: float | None = None,
        opacity: float | None = None,
        z_index: int | None = None,
        monitor_id: str | None = None,
        pinned: bool | None = None,
        locked: bool | None = None,
    ) -> OverlayInstance:
        instance = self._instance(instance_id)
        if x is not None:
            instance.placement.x = int(x)
        if y is not None:
            instance.placement.y = int(y)
        if width is not None:
            instance.placement.width = int(width)
        if height is not None:
            instance.placement.height = int(height)
        if scale is not None:
            instance.placement.scale = float(scale)
        if opacity is not None:
            instance.placement.opacity = float(opacity)
        if z_index is not None:
            instance.placement.z_index = int(z_index)
        if monitor_id is not None:
            instance.placement.monitor_id = str(monitor_id)
        if pinned is not None:
            instance.placement.pinned = bool(pinned)
        if locked is not None:
            instance.placement.locked = bool(locked)
        instance.updated_at_utc = utc_now_iso()
        self._document.updated_at_utc = utc_now_iso()
        self._persist("instance_changed", overlay_id=instance.overlay_id, instance_id=instance.instance_id, preset_id=instance.preset_id, message="Overlay placement updated")
        return instance

    def set_instance_enabled(self, instance_id: str, enabled: bool) -> OverlayInstance:
        instance = self._instance(instance_id)
        instance.enabled = bool(enabled)
        instance.updated_at_utc = utc_now_iso()
        self._document.updated_at_utc = utc_now_iso()
        self._runtime.set_instance_visibility(instance, visible=instance.enabled)
        self._persist("runtime_changed", overlay_id=instance.overlay_id, instance_id=instance.instance_id, preset_id=instance.preset_id, message="Overlay visibility updated")

        # T062: emit overlay_toggled with the *stable* overlay_id as
        # widget_id; the random instance_id is per-user and useless
        # for cross-user funnels. analytics.track is safe-noop when
        # PostHog isn't wired.
        from lap_coach_logger import analytics
        analytics.track(
            "overlay_toggled",
            widget_id=instance.overlay_id,
            enabled=instance.enabled,
        )

        return instance

    def remove_instance(self, instance_id: str) -> None:
        instance = self._instance(instance_id)
        self._document.instances = [item for item in self._document.instances if item.instance_id != instance_id]
        for preset in self._document.presets:
            preset.instance_ids = [value for value in preset.instance_ids if value != instance_id]
            for slot in preset.slots:
                if slot.instance_id == instance_id:
                    slot.instance_id = ""
            preset.updated_at_utc = utc_now_iso()
        self._document.updated_at_utc = utc_now_iso()
        self._runtime.sync_document(self._document)
        self._persist("instance_changed", overlay_id=instance.overlay_id, instance_id=instance_id, preset_id=instance.preset_id, message="Overlay instance removed")

    def assign_instance_to_slot(self, instance_id: str, slot_id: str) -> OverlayInstance:
        instance = self._instance(instance_id)
        preset = self._preset(instance.preset_id)
        self._assign_slot_record(preset, slot_id=slot_id, instance_id=instance.instance_id, overlay_id=instance.overlay_id)
        instance.slot_id = slot_id
        instance.updated_at_utc = utc_now_iso()
        preset.updated_at_utc = utc_now_iso()
        self._document.updated_at_utc = utc_now_iso()
        self._persist("preset_changed", overlay_id=instance.overlay_id, instance_id=instance.instance_id, preset_id=preset.preset_id, message="Overlay slot assignment updated")
        return instance

    def start_preview(self, overlay_id: str, *, settings: dict[str, object] | None = None) -> OverlayPreviewSession:
        definition = self._registry.get(overlay_id)
        if not definition.capabilities.preview_supported:
            raise ValueError(f"Overlay '{overlay_id}' does not support preview mode")
        normalized, _issues = self._registry.validate_settings(overlay_id, settings, include_defaults=True)
        preview = self._runtime.start_preview(overlay_id, settings=normalized)
        self._events.publish(OverlayEvent(kind="preview_changed", overlay_id=overlay_id, message="Overlay preview started"))
        return preview

    def stop_preview(self, preview_id: str) -> None:
        self._runtime.stop_preview(preview_id)
        self._events.publish(OverlayEvent(kind="preview_changed", message="Overlay preview stopped"))

    def snapshot(self, *, filter_spec: OverlayCatalogFilter | None = None) -> dict[str, object]:
        browser = self.catalog(filter_spec=filter_spec)
        return {
            "active_preset_id": self._document.active_preset_id,
            "browser": {
                "categories": list(browser.categories),
                "entries": [asdict(entry) for entry in browser.entries],
            },
            "presets": [preset.to_dict() for preset in self._document.presets],
            "instances": [instance.to_dict() for instance in self._document.instances],
            "runtime": [state.to_dict() for state in self._runtime.runtime_states()],
            "previews": [session.to_dict() for session in self._runtime.preview_sessions()],
            "favorites": list(self._document.favorite_overlay_ids),
            "schema_version": self._document.schema_version,
        }

    def _persist(self, kind: str, *, overlay_id: str = "", instance_id: str = "", preset_id: str = "", message: str = "") -> None:
        self._store.save(self._document)
        self._runtime.sync_document(self._document)
        self._events.publish(
            OverlayEvent(
                kind=kind,
                overlay_id=overlay_id,
                instance_id=instance_id,
                preset_id=preset_id,
                message=message,
            )
        )

    def _ensure_default_preset(self) -> None:
        if self._document.presets:
            if not self._document.active_preset_id:
                self._document.active_preset_id = self._document.presets[0].preset_id
            self._sync_active_flags()
            return
        default = OverlayPreset(
            preset_id="preset-default",
            name="Default Layout",
            description="Starter preset for built-in overlays.",
        )
        default.active = True
        self._document.presets = [default]
        self._document.active_preset_id = default.preset_id
        self._document.updated_at_utc = utc_now_iso()
        self._store.save(self._document)

    def _sync_active_flags(self) -> None:
        active_id = self._document.active_preset_id
        for preset in self._document.presets:
            preset.active = preset.preset_id == active_id

    def _preset(self, preset_id: str | None) -> OverlayPreset:
        target = str(preset_id or self._document.active_preset_id or "")
        for preset in self._document.presets:
            if preset.preset_id == target:
                return preset
        raise KeyError(f"Unknown overlay preset '{target}'")

    def _instance(self, instance_id: str) -> OverlayInstance:
        for instance in self._document.instances:
            if instance.instance_id == instance_id:
                return instance
        raise KeyError(f"Unknown overlay instance '{instance_id}'")

    def _assign_slot_record(self, preset: OverlayPreset, *, slot_id: str, instance_id: str, overlay_id: str) -> None:
        slot = None
        for item in preset.slots:
            if item.slot_id == slot_id:
                slot = item
                break
        if slot is None:
            raise KeyError(f"Unknown layout slot '{slot_id}' for preset '{preset.preset_id}'")

        definition = self._registry.get(overlay_id)
        if slot.allowed_overlay_ids and overlay_id not in set(slot.allowed_overlay_ids):
            raise ValueError(f"Overlay '{overlay_id}' is not allowed in slot '{slot_id}'")
        if slot.allowed_categories and definition.category not in set(slot.allowed_categories):
            raise ValueError(f"Overlay category '{definition.category}' is not allowed in slot '{slot_id}'")
        if slot.locked and slot.instance_id and slot.instance_id != instance_id:
            raise ValueError(f"Slot '{slot_id}' is locked")

        for existing_slot in preset.slots:
            if existing_slot.slot_id != slot_id and existing_slot.instance_id == instance_id:
                existing_slot.instance_id = ""

        for other_instance in self._document.instances:
            if other_instance.preset_id == preset.preset_id and other_instance.slot_id == slot_id and other_instance.instance_id != instance_id:
                other_instance.slot_id = ""
                other_instance.updated_at_utc = utc_now_iso()

        slot.instance_id = instance_id
