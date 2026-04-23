"""Overlay layout preset models and service."""

from __future__ import annotations

import fnmatch
import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from lap_coach_logger.overlays.entitlements import (
    OverlayEntitlementContext,
    OverlayEntitlementResolver,
    StaticOverlayEntitlementResolver,
)
from lap_coach_logger.overlays.models import (
    OverlayAutoApplyRule,
    OverlayBrowserPreferences,
    OverlayInstance,
    OverlayLayoutContext,
    OverlayLayoutDiff,
    OverlayLayoutFieldChange,
    OverlayLayoutInstanceChange,
    OverlayLastUsedSettings,
    OverlayLayoutSlot,
    OverlayPlacement,
    OverlayPreset,
    OverlayPresetScope,
    OverlayStateDocument,
    utc_now_iso,
)
from lap_coach_logger.overlays.registry import OverlayRegistry
from lap_coach_logger.overlays.runtime_instances import (
    OverlayInstanceLifecycleService,
    OverlayRuntimeInstance,
)
from lap_coach_logger.overlays.store import OverlayStateStore

LayoutShortcutKey = Literal["A", "B", "C"]
LAYOUT_EXPORT_SCHEMA_VERSION = 1
_SCHEMA_VERSION_RE = re.compile(r"\.v(?P<version>\d+)$", re.IGNORECASE)


@dataclass(slots=True)
class OverlayLayoutTemplate:
    layout: OverlayPreset
    instances: list[OverlayInstance] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "layout": self.layout.to_dict(),
            "instances": [instance.to_dict() for instance in self.instances],
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayLayoutTemplate:
        payload = _dict_copy(data)
        return cls(
            layout=OverlayPreset.from_dict(payload.get("layout")),
            instances=[OverlayInstance.from_dict(item) for item in payload.get("instances", [])],
        )


@dataclass(slots=True, frozen=True)
class OverlayLayoutMatch:
    layout_id: str
    rule_id: str
    reason: str
    priority: int
    specificity: int

    def to_dict(self) -> dict[str, object]:
        return {
            "layout_id": self.layout_id,
            "rule_id": self.rule_id,
            "reason": self.reason,
            "priority": self.priority,
            "specificity": self.specificity,
        }


@dataclass(slots=True)
class OverlayLayoutExportBundle:
    schema_version: int = LAYOUT_EXPORT_SCHEMA_VERSION
    exported_at_utc: str = field(default_factory=utc_now_iso)
    layouts: list[OverlayPreset] = field(default_factory=list)
    instances: list[OverlayInstance] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "exported_at_utc": self.exported_at_utc,
            "layouts": [layout.to_dict() for layout in self.layouts],
            "instances": [instance.to_dict() for instance in self.instances],
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayLayoutExportBundle:
        payload = _dict_copy(data)
        layouts_payload = payload.get("layouts")
        if not isinstance(layouts_payload, list):
            single = payload.get("layout")
            layouts_payload = [single] if single else []
        instances_payload = payload.get("instances")
        if not isinstance(instances_payload, list):
            instances_payload = []
        return cls(
            schema_version=int(payload.get("schema_version") or LAYOUT_EXPORT_SCHEMA_VERSION),
            exported_at_utc=str(payload.get("exported_at_utc") or utc_now_iso()),
            layouts=[OverlayPreset.from_dict(item) for item in layouts_payload],
            instances=[OverlayInstance.from_dict(item) for item in instances_payload],
        )


class OverlayLayoutPresetService:
    """Persistent layout-preset service built on top of the overlay state document."""

    def __init__(
        self,
        *,
        registry: OverlayRegistry,
        store: OverlayStateStore,
        runtime: OverlayInstanceLifecycleService | None = None,
        entitlement_resolver: OverlayEntitlementResolver | None = None,
        default_layouts: tuple[OverlayLayoutTemplate, ...] | list[OverlayLayoutTemplate] | None = None,
    ) -> None:
        self._registry = registry
        self._store = store
        self._runtime = runtime
        self._entitlements = entitlement_resolver or StaticOverlayEntitlementResolver()
        self._entitlement_context = OverlayEntitlementContext()
        self._document = self._store.load()
        self._default_layouts = {
            template.layout.layout_id: _clone_template(template)
            for template in tuple(default_layouts or ())
        }
        self._ensure_layouts()

    def document(self) -> OverlayStateDocument:
        return self._document

    def layouts(self) -> tuple[OverlayPreset, ...]:
        return tuple(self._document.presets)

    def shortcut_bindings(self) -> dict[str, str]:
        return dict(self._document.layout_shortcuts)

    def set_entitlement_context(self, context: OverlayEntitlementContext) -> None:
        self._entitlement_context = context

    def favorite_overlay_ids(self) -> tuple[str, ...]:
        return tuple(self._document.favorite_overlay_ids)

    def browser_preferences(self) -> OverlayBrowserPreferences:
        return self._document.browser_preferences

    def update_browser_preferences(self, **changes: object) -> OverlayBrowserPreferences:
        current = self._document.browser_preferences
        payload = current.to_dict()
        for key, value in changes.items():
            if key in payload:
                payload[key] = value
        payload["updated_at_utc"] = utc_now_iso()
        self._document.browser_preferences = OverlayBrowserPreferences.from_dict(payload)
        self._persist(save_only=True)
        return self._document.browser_preferences

    def last_used_settings_for(self, overlay_id: str) -> OverlayLastUsedSettings | None:
        return self._document.last_used_settings_map().get(overlay_id)

    def toggle_overlay_favorite(self, overlay_id: str) -> bool:
        self._registry.get(overlay_id)
        favorite_ids = set(self._document.favorite_overlay_ids)
        if overlay_id in favorite_ids:
            favorite_ids.remove(overlay_id)
            is_favorite = False
        else:
            favorite_ids.add(overlay_id)
            is_favorite = True
        self._document.favorite_overlay_ids = sorted(favorite_ids)
        self._persist()
        return is_favorite

    def layout_instances(self, layout_id: str) -> tuple[OverlayInstance, ...]:
        self._layout(layout_id)
        return tuple(instance for instance in self._document.instances if instance.preset_id == layout_id)

    def overlay_instances_for_overlay(self, layout_id: str, overlay_id: str) -> tuple[OverlayInstance, ...]:
        self._layout(layout_id)
        return tuple(
            instance
            for instance in self._document.instances
            if instance.preset_id == layout_id and instance.overlay_id == overlay_id
        )

    def create_layout(
        self,
        *,
        display_name: str,
        description: str = "",
        favorite: bool = False,
        simulator_filter: tuple[str, ...] | list[str] = (),
        car_filter: tuple[str, ...] | list[str] = (),
        session_type_filter: tuple[str, ...] | list[str] = (),
        tags: tuple[str, ...] | list[str] = (),
        auto_apply_rules: tuple[OverlayAutoApplyRule, ...] | list[OverlayAutoApplyRule] = (),
        slots: tuple[OverlayLayoutSlot, ...] | list[OverlayLayoutSlot] = (),
        overlay_instances: tuple[OverlayInstance, ...] | list[OverlayInstance] = (),
        activate: bool = False,
    ) -> OverlayPreset:
        layout_id = f"layout-{uuid.uuid4().hex[:10]}"
        layout = OverlayPreset(
            preset_id=layout_id,
            name=display_name.strip() or "Layout",
            description=description.strip(),
            favorite=bool(favorite),
            simulator_filter=tuple(str(item) for item in simulator_filter if str(item).strip()),
            car_filter=tuple(str(item) for item in car_filter if str(item).strip()),
            session_type_filter=tuple(str(item) for item in session_type_filter if str(item).strip()),
            tags=tuple(str(item) for item in tags if str(item).strip()),
            slots=[_clone_slot(slot) for slot in slots],
            auto_apply_rules=[_clone_rule(rule) for rule in auto_apply_rules],
        )
        cloned_instances, remap = self._clone_instances_for_layout(overlay_instances, layout_id)
        layout.instance_ids = [instance.instance_id for instance in cloned_instances]
        for slot in layout.slots:
            if slot.instance_id in remap:
                slot.instance_id = remap[slot.instance_id]
        self._document.presets.append(layout)
        self._document.instances.extend(cloned_instances)
        if activate:
            self._document.active_preset_id = layout.layout_id
        self._persist()
        if activate:
            self.apply_layout_to_runtime(layout.layout_id)
        return layout

    def install_overlay(
        self,
        layout_id: str,
        overlay_id: str,
        *,
        name: str = "",
        settings: dict[str, object] | None = None,
        placement: OverlayPlacement | None = None,
        enabled: bool | None = None,
    ) -> OverlayInstance:
        layout = self._layout(layout_id)
        definition = self._registry.get(overlay_id)
        entitlement = self._entitlements.evaluate(definition, context=self._entitlement_context)
        if not entitlement.can_activate:
            raise PermissionError(entitlement.reason)

        normalized_settings, _issues = self._registry.validate_settings(overlay_id, settings, include_defaults=True)
        final_placement = placement or OverlayPlacement(
            width=definition.layout.default_width,
            height=definition.layout.default_height,
            scale=float(normalized_settings.get("scale", 1.0)) if isinstance(normalized_settings.get("scale"), (int, float)) else 1.0,
            opacity=float(normalized_settings.get("opacity", 1.0)) if isinstance(normalized_settings.get("opacity"), (int, float)) else 1.0,
        )
        instance = OverlayInstance(
            instance_id=self._unique_instance_id(f"{layout_id}-{overlay_id}"),
            overlay_id=overlay_id,
            preset_id=layout_id,
            name=name.strip() or definition.display_name,
            enabled=definition.default_enabled if enabled is None else bool(enabled),
            placement=final_placement,
            settings=normalized_settings,
        )
        self._document.instances.append(instance)
        if instance.instance_id not in layout.instance_ids:
            layout.instance_ids.append(instance.instance_id)
        self.remember_last_used_settings(
            overlay_id,
            normalized_settings,
            settings_schema_ref=definition.settings_schema_ref,
            settings_schema_version=_schema_version_from_ref(definition.settings_schema_ref),
        )
        self._mark_layout_modified(layout)
        self._persist()
        if self._document.active_preset_id == layout_id and self._runtime is not None:
            self.apply_layout_to_runtime(layout_id)
        return instance

    def clone_layout(self, layout_id: str, *, display_name: str | None = None) -> OverlayPreset:
        source = self._layout(layout_id)
        instances = self.layout_instances(layout_id)
        cloned = self.create_layout(
            display_name=display_name or f"{source.display_name} Copy",
            description=source.description,
            favorite=source.favorite,
            simulator_filter=source.simulator_filter,
            car_filter=source.car_filter,
            session_type_filter=source.session_type_filter,
            tags=source.tags,
            auto_apply_rules=source.auto_apply_rules,
            slots=source.slots,
            overlay_instances=instances,
            activate=False,
        )
        return cloned

    def rename_layout(self, layout_id: str, display_name: str) -> OverlayPreset:
        layout = self._layout(layout_id)
        layout.name = display_name.strip() or layout.name
        self._mark_layout_modified(layout)
        self._persist()
        return layout

    def delete_layout(self, layout_id: str) -> None:
        layout = self._layout(layout_id)
        if self._runtime is not None:
            for runtime_instance in self._runtime.instances_for_layout(layout_id):
                self._runtime.destroy(runtime_instance.instance_id)
        self._document.presets = [item for item in self._document.presets if item.layout_id != layout_id]
        self._document.instances = [item for item in self._document.instances if item.preset_id != layout_id]
        for key, value in list(self._document.layout_shortcuts.items()):
            if value == layout_id:
                self._document.layout_shortcuts[key] = ""
        if self._document.active_preset_id == layout_id:
            self._document.active_preset_id = self._document.presets[0].layout_id if self._document.presets else ""
        self._persist()
        if self._document.active_preset_id and self._runtime is not None:
            self.apply_layout_to_runtime(self._document.active_preset_id)

    def uninstall_overlay(
        self,
        *,
        layout_id: str,
        instance_id: str | None = None,
        overlay_id: str | None = None,
    ) -> int:
        layout = self._layout(layout_id)
        target_instance_ids: set[str] = set()
        if instance_id:
            target_instance_ids.add(self._instance(instance_id).instance_id)
        elif overlay_id:
            target_instance_ids.update(item.instance_id for item in self.overlay_instances_for_overlay(layout_id, overlay_id))
        else:
            raise ValueError("Either instance_id or overlay_id is required")
        if not target_instance_ids:
            return 0

        self._document.instances = [item for item in self._document.instances if item.instance_id not in target_instance_ids]
        layout.instance_ids = [item for item in layout.instance_ids if item not in target_instance_ids]
        for slot in layout.slots:
            if slot.instance_id in target_instance_ids:
                slot.instance_id = ""
        self._mark_layout_modified(layout)
        self._persist()
        if self._document.active_preset_id == layout_id and self._runtime is not None:
            self.apply_layout_to_runtime(layout_id)
        return len(target_instance_ids)

    def export_layout(self, layout_id: str, path: str | Path | None = None) -> OverlayLayoutExportBundle:
        layout = _clone_layout(self._layout(layout_id))
        instances = [_clone_instance(item, layout_id) for item in self.layout_instances(layout_id)]
        bundle = OverlayLayoutExportBundle(layouts=[layout], instances=instances)
        if path is not None:
            target = Path(path)
            target.write_text(json.dumps(bundle.to_dict(), indent=2), encoding="utf-8")
        return bundle

    def import_layout(self, source: str | Path | dict[str, object]) -> tuple[OverlayPreset, ...]:
        payload = _load_payload(source)
        bundle = OverlayLayoutExportBundle.from_dict(payload)
        imported: list[OverlayPreset] = []
        for source_layout in bundle.layouts:
            target_layout_id = self._unique_layout_id(source_layout.layout_id or f"layout-{uuid.uuid4().hex[:10]}")
            layout = _clone_layout(source_layout)
            layout.preset_id = target_layout_id
            layout.name = self._unique_layout_name(layout.display_name)
            layout.active = False
            source_instances = [
                item
                for item in bundle.instances
                if item.preset_id == source_layout.layout_id
            ]
            cloned_instances, remap = self._clone_instances_for_layout(source_instances, target_layout_id)
            layout.instance_ids = [instance.instance_id for instance in cloned_instances]
            for slot in layout.slots:
                if slot.instance_id in remap:
                    slot.instance_id = remap[slot.instance_id]
            self._document.presets.append(layout)
            self._document.instances.extend(cloned_instances)
            imported.append(layout)
        self._persist()
        return tuple(imported)

    def activate_layout(self, layout_id: str, *, apply_to_runtime: bool = True) -> OverlayPreset:
        layout = self._layout(layout_id)
        self._document.active_preset_id = layout.layout_id
        self._persist()
        if apply_to_runtime:
            self.apply_layout_to_runtime(layout.layout_id)
        return layout

    def deactivate_layout(self, layout_id: str | None = None, *, destroy_runtime: bool = True) -> None:
        target_id = str(layout_id or self._document.active_preset_id or "")
        if not target_id:
            return
        self._layout(target_id)
        if self._document.active_preset_id == target_id:
            self._document.active_preset_id = ""
        if destroy_runtime and self._runtime is not None:
            for runtime_instance in self._runtime.instances_for_layout(target_id):
                self._runtime.destroy(runtime_instance.instance_id)
        self._persist()

    def bind_layout_shortcut(self, slot: LayoutShortcutKey, layout_id: str) -> dict[str, str]:
        if slot not in {"A", "B", "C"}:
            raise ValueError("Layout shortcut slot must be one of A, B, or C")
        self._layout(layout_id)
        self._document.layout_shortcuts[slot] = layout_id
        self._persist()
        return dict(self._document.layout_shortcuts)

    def set_overlay_instance_enabled(
        self,
        instance_id: str,
        enabled: bool,
        *,
        apply_to_runtime: bool = True,
    ) -> OverlayInstance:
        instance = self._instance(instance_id)
        instance.enabled = bool(enabled)
        instance.updated_at_utc = utc_now_iso()
        layout = self._layout(instance.preset_id)
        self._mark_layout_modified(layout, increment_version=False)
        self._persist()
        if apply_to_runtime and self._document.active_preset_id == layout.layout_id and self._runtime is not None:
            self.apply_layout_to_runtime(layout.layout_id)
        return instance

    def update_overlay_instance_settings(
        self,
        instance_id: str,
        changes: dict[str, object],
        *,
        apply_to_runtime: bool = True,
    ) -> tuple[OverlayInstance, list[str]]:
        instance = self._instance(instance_id)
        merged = dict(instance.settings)
        merged.update(changes)
        normalized, issues = self._registry.validate_settings(instance.overlay_id, merged, include_defaults=True)
        instance.settings = normalized
        if isinstance(normalized.get("scale"), (int, float)):
            instance.placement.scale = float(normalized["scale"])
        if isinstance(normalized.get("opacity"), (int, float)):
            instance.placement.opacity = float(normalized["opacity"])
        if isinstance(normalized.get("width"), (int, float)):
            instance.placement.width = int(normalized["width"])
        if isinstance(normalized.get("height"), (int, float)):
            instance.placement.height = int(normalized["height"])
        instance.updated_at_utc = utc_now_iso()
        definition = self._registry.get(instance.overlay_id)
        self.remember_last_used_settings(
            instance.overlay_id,
            normalized,
            settings_schema_ref=definition.settings_schema_ref,
            settings_schema_version=_schema_version_from_ref(definition.settings_schema_ref),
        )
        layout = self._layout(instance.preset_id)
        self._mark_layout_modified(layout, increment_version=False)
        self._persist()
        if apply_to_runtime and self._document.active_preset_id == layout.layout_id and self._runtime is not None:
            self.apply_layout_to_runtime(layout.layout_id)
        return instance, issues

    def update_overlay_instance_placement(
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
        apply_to_runtime: bool = True,
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
        layout = self._layout(instance.preset_id)
        self._mark_layout_modified(layout, increment_version=False)
        self._persist()
        if apply_to_runtime and self._document.active_preset_id == layout.layout_id and self._runtime is not None:
            self.apply_layout_to_runtime(layout.layout_id)
        return instance

    def remember_last_used_settings(
        self,
        overlay_id: str,
        values: dict[str, object],
        *,
        settings_schema_ref: str = "",
        settings_schema_version: int = 0,
    ) -> OverlayLastUsedSettings:
        record_map = self._document.last_used_settings_map()
        record = record_map.get(overlay_id)
        if record is None:
            record = OverlayLastUsedSettings(
                overlay_id=overlay_id,
                settings_schema_ref=settings_schema_ref,
                settings_schema_version=settings_schema_version,
                values=dict(values),
            )
            self._document.last_used_settings.append(record)
        else:
            record.settings_schema_ref = settings_schema_ref or record.settings_schema_ref
            record.settings_schema_version = settings_schema_version or record.settings_schema_version
            record.values = dict(values)
            record.updated_at_utc = utc_now_iso()
        return record

    def activate_layout_shortcut(self, slot: LayoutShortcutKey, *, apply_to_runtime: bool = True) -> OverlayPreset:
        layout_id = str(self._document.layout_shortcuts.get(slot) or "")
        if not layout_id:
            raise KeyError(f"No layout bound to shortcut '{slot}'")
        return self.activate_layout(layout_id, apply_to_runtime=apply_to_runtime)

    def match_auto_apply(self, context: OverlayLayoutContext) -> OverlayLayoutMatch | None:
        best: tuple[int, int, OverlayLayoutMatch] | None = None
        for layout in self._document.presets:
            for rule in self._candidate_rules(layout):
                match = self._match_rule(layout, rule, context)
                if match is None:
                    continue
                score = (match.priority, match.specificity)
                if best is None or score > best[:2]:
                    best = (match.priority, match.specificity, match)
        return best[2] if best else None

    def auto_apply_for_context(
        self,
        context: OverlayLayoutContext,
        *,
        apply_to_runtime: bool = True,
    ) -> OverlayPreset | None:
        match = self.match_auto_apply(context)
        if match is None:
            return None
        return self.activate_layout(match.layout_id, apply_to_runtime=apply_to_runtime)

    def apply_layout_to_runtime(self, layout_id: str) -> tuple[OverlayRuntimeInstance, ...]:
        if self._runtime is None:
            return ()
        self._layout(layout_id)
        for runtime_instance in self._runtime.list_instances():
            self._runtime.destroy(runtime_instance.instance_id)

        mounted: list[OverlayRuntimeInstance] = []
        for instance in self.layout_instances(layout_id):
            definition = self._registry.get(instance.overlay_id)
            entitlement = self._entitlements.evaluate(definition, context=self._entitlement_context)
            mounted.append(
                self._runtime.restore_from_persisted_instance(
                    instance,
                    entitlement_blocked=not entitlement.can_activate,
                )
            )
        return tuple(mounted)

    def diff_layouts(self, layout_a_id: str, layout_b_id: str) -> OverlayLayoutDiff:
        layout_a = self._layout(layout_a_id)
        layout_b = self._layout(layout_b_id)
        metadata_changes: list[OverlayLayoutFieldChange] = []
        for field_name in ("display_name", "description", "favorite", "simulator_filter", "car_filter", "session_type_filter", "tags"):
            before = getattr(layout_a, "name" if field_name == "display_name" else field_name)
            after = getattr(layout_b, "name" if field_name == "display_name" else field_name)
            if before != after:
                metadata_changes.append(OverlayLayoutFieldChange(field_name, before, after))

        instance_changes: list[OverlayLayoutInstanceChange] = []
        signatures_a = _signature_index(self.layout_instances(layout_a_id))
        signatures_b = _signature_index(self.layout_instances(layout_b_id))
        for signature in sorted(set(signatures_a) | set(signatures_b)):
            instances_a = signatures_a.get(signature, [])
            instances_b = signatures_b.get(signature, [])
            max_count = max(len(instances_a), len(instances_b))
            for index in range(max_count):
                item_a = instances_a[index] if index < len(instances_a) else None
                item_b = instances_b[index] if index < len(instances_b) else None
                if item_a is None and item_b is not None:
                    instance_changes.append(
                        OverlayLayoutInstanceChange("added", item_b.overlay_id, signature)
                    )
                    continue
                if item_a is not None and item_b is None:
                    instance_changes.append(
                        OverlayLayoutInstanceChange("removed", item_a.overlay_id, signature)
                    )
                    continue
                if item_a is None or item_b is None:
                    continue
                field_changes = _instance_field_changes(item_a, item_b)
                if field_changes:
                    instance_changes.append(
                        OverlayLayoutInstanceChange("modified", item_a.overlay_id, signature, tuple(field_changes))
                    )
        return OverlayLayoutDiff(
            layout_a_id=layout_a_id,
            layout_b_id=layout_b_id,
            metadata_changes=tuple(metadata_changes),
            instance_changes=tuple(instance_changes),
        )

    def reset_layout_to_default(self, layout_id: str) -> OverlayPreset:
        layout = self._layout(layout_id)
        template = self._default_layouts.get(layout.layout_id)
        if template is None:
            raise KeyError(f"Layout '{layout_id}' has no registered default template")
        self._document.instances = [item for item in self._document.instances if item.preset_id != layout_id]
        replacement = _clone_layout(template.layout)
        replacement.active = self._document.active_preset_id == layout_id
        replacement.updated_at_utc = utc_now_iso()
        replacement.created_at_utc = layout.created_at_utc
        replacement.version = layout.version + 1
        cloned_instances, remap = self._clone_instances_for_layout(template.instances, layout_id)
        replacement.instance_ids = [instance.instance_id for instance in cloned_instances]
        for slot in replacement.slots:
            if slot.instance_id in remap:
                slot.instance_id = remap[slot.instance_id]
        for index, existing in enumerate(self._document.presets):
            if existing.layout_id == layout_id:
                self._document.presets[index] = replacement
                break
        self._document.instances.extend(cloned_instances)
        self._persist()
        return replacement

    def _candidate_rules(self, layout: OverlayPreset) -> tuple[OverlayAutoApplyRule, ...]:
        if layout.auto_apply_rules:
            return tuple(layout.auto_apply_rules)
        if layout.simulator_filter or layout.car_filter or layout.session_type_filter:
            return (
                OverlayAutoApplyRule(
                    rule_id=f"{layout.layout_id}:implicit",
                    name="implicit-layout-filter",
                    priority=100,
                    simulators=layout.simulator_filter,
                    cars=layout.car_filter,
                    session_types=layout.session_type_filter,
                ),
            )
        return ()

    def _match_rule(
        self,
        layout: OverlayPreset,
        rule: OverlayAutoApplyRule,
        context: OverlayLayoutContext,
    ) -> OverlayLayoutMatch | None:
        if not rule.enabled:
            return None
        if not _matches_filter(layout.simulator_filter, context.simulator):
            return None
        if not _matches_filter(layout.car_filter, context.car):
            return None
        if not _matches_filter(layout.session_type_filter, context.session_type):
            return None
        if not _matches_filter(rule.simulators, context.simulator):
            return None
        if not _matches_filter(rule.cars, context.car):
            return None
        if not _matches_filter(rule.session_types, context.session_type):
            return None
        if rule.tags and not set(tag.lower() for tag in rule.tags).issubset(set(tag.lower() for tag in context.tags)):
            return None
        specificity = sum(
            1
            for values in (
                layout.simulator_filter,
                layout.car_filter,
                layout.session_type_filter,
                rule.simulators,
                rule.cars,
                rule.session_types,
                rule.tags,
            )
            if values
        )
        reason_parts = []
        if context.simulator:
            reason_parts.append(context.simulator)
        if context.car:
            reason_parts.append(context.car)
        if context.session_type:
            reason_parts.append(context.session_type)
        return OverlayLayoutMatch(
            layout_id=layout.layout_id,
            rule_id=rule.rule_id,
            reason=", ".join(reason_parts) or "rule match",
            priority=rule.priority,
            specificity=specificity,
        )

    def _ensure_layouts(self) -> None:
        if not self._document.presets and self._default_layouts:
            for template in self._default_layouts.values():
                self._seed_template(template)
        if not self._document.presets:
            self._seed_template(
                OverlayLayoutTemplate(
                    layout=OverlayPreset(
                        preset_id="layout-default",
                        name="Default Layout",
                        description="Starter layout for LAP COACH overlays.",
                        active=True,
                    )
                )
            )
        self._sync_active_flags()
        self._persist(save_only=True)

    def _seed_template(self, template: OverlayLayoutTemplate) -> None:
        if any(layout.layout_id == template.layout.layout_id for layout in self._document.presets):
            return
        layout = _clone_layout(template.layout)
        cloned_instances, remap = self._clone_instances_for_layout(template.instances, layout.layout_id)
        layout.instance_ids = [instance.instance_id for instance in cloned_instances]
        for slot in layout.slots:
            if slot.instance_id in remap:
                slot.instance_id = remap[slot.instance_id]
        self._document.presets.append(layout)
        self._document.instances.extend(cloned_instances)
        if layout.active and not self._document.active_preset_id:
            self._document.active_preset_id = layout.layout_id

    def _layout(self, layout_id: str) -> OverlayPreset:
        for layout in self._document.presets:
            if layout.layout_id == layout_id:
                return layout
        raise KeyError(f"Unknown overlay layout '{layout_id}'")

    def _instance(self, instance_id: str) -> OverlayInstance:
        for instance in self._document.instances:
            if instance.instance_id == instance_id:
                return instance
        raise KeyError(f"Unknown overlay instance '{instance_id}'")

    def _mark_layout_modified(self, layout: OverlayPreset, *, increment_version: bool = True) -> None:
        if increment_version:
            layout.version += 1
        layout.updated_at_utc = utc_now_iso()

    def _persist(self, *, save_only: bool = False) -> None:
        self._sync_active_flags()
        self._document.updated_at_utc = utc_now_iso()
        self._store.save(self._document)

    def _sync_active_flags(self) -> None:
        active_layout_id = self._document.active_preset_id
        for layout in self._document.presets:
            layout.active = layout.layout_id == active_layout_id

    def _clone_instances_for_layout(
        self,
        instances: tuple[OverlayInstance, ...] | list[OverlayInstance],
        layout_id: str,
    ) -> tuple[list[OverlayInstance], dict[str, str]]:
        cloned_instances: list[OverlayInstance] = []
        remap: dict[str, str] = {}
        for source in instances:
            cloned = _clone_instance(source, layout_id)
            cloned.instance_id = self._unique_instance_id(cloned.instance_id)
            remap[source.instance_id] = cloned.instance_id
            cloned_instances.append(cloned)
        return cloned_instances, remap

    def _unique_layout_id(self, preferred: str) -> str:
        candidate = preferred or f"layout-{uuid.uuid4().hex[:10]}"
        existing = {layout.layout_id for layout in self._document.presets}
        if candidate not in existing:
            return candidate
        while True:
            candidate = f"{preferred or 'layout'}-{uuid.uuid4().hex[:6]}"
            if candidate not in existing:
                return candidate

    def _unique_layout_name(self, preferred: str) -> str:
        candidate = preferred.strip() or "Imported Layout"
        existing = {layout.display_name.lower() for layout in self._document.presets}
        if candidate.lower() not in existing:
            return candidate
        suffix = 2
        while True:
            next_candidate = f"{candidate} ({suffix})"
            if next_candidate.lower() not in existing:
                return next_candidate
            suffix += 1

    def _unique_instance_id(self, preferred: str) -> str:
        candidate = preferred or f"overlay-{uuid.uuid4().hex[:10]}"
        existing = {instance.instance_id for instance in self._document.instances}
        if candidate not in existing:
            return candidate
        while True:
            candidate = f"overlay-{uuid.uuid4().hex[:10]}"
            if candidate not in existing:
                return candidate


def _signature_index(instances: tuple[OverlayInstance, ...]) -> dict[str, list[OverlayInstance]]:
    grouped: dict[str, list[OverlayInstance]] = {}
    for instance in instances:
        signature = f"{instance.overlay_id}|{instance.slot_id}|{instance.name}"
        grouped.setdefault(signature, []).append(instance)
    return grouped


def _instance_field_changes(instance_a: OverlayInstance, instance_b: OverlayInstance) -> list[OverlayLayoutFieldChange]:
    changes: list[OverlayLayoutFieldChange] = []
    for field_name in ("enabled", "slot_id", "name"):
        before = getattr(instance_a, field_name)
        after = getattr(instance_b, field_name)
        if before != after:
            changes.append(OverlayLayoutFieldChange(field_name, before, after))
    if instance_a.settings != instance_b.settings:
        changes.append(OverlayLayoutFieldChange("settings", dict(instance_a.settings), dict(instance_b.settings)))
    placement_a = instance_a.placement.to_dict()
    placement_b = instance_b.placement.to_dict()
    if placement_a != placement_b:
        changes.append(OverlayLayoutFieldChange("placement", placement_a, placement_b))
    return changes


def _clone_template(template: OverlayLayoutTemplate) -> OverlayLayoutTemplate:
    return OverlayLayoutTemplate(
        layout=_clone_layout(template.layout),
        instances=[_clone_instance(instance, instance.preset_id) for instance in template.instances],
    )


def _clone_layout(layout: OverlayPreset) -> OverlayPreset:
    return OverlayPreset.from_dict(layout.to_dict())


def _clone_rule(rule: OverlayAutoApplyRule) -> OverlayAutoApplyRule:
    return OverlayAutoApplyRule.from_dict(rule.to_dict())


def _clone_slot(slot: OverlayLayoutSlot) -> OverlayLayoutSlot:
    return OverlayLayoutSlot.from_dict(slot.to_dict())


def _clone_instance(instance: OverlayInstance, layout_id: str) -> OverlayInstance:
    cloned = OverlayInstance.from_dict(instance.to_dict())
    cloned.preset_id = layout_id
    cloned.updated_at_utc = utc_now_iso()
    return cloned


def _matches_filter(filters: tuple[str, ...], value: str) -> bool:
    if not filters:
        return True
    target = value.strip().lower()
    if not target:
        return False
    for candidate in filters:
        normalized = str(candidate).strip().lower()
        if not normalized:
            continue
        if "*" in normalized or "?" in normalized:
            if fnmatch.fnmatch(target, normalized):
                return True
        elif normalized == target:
            return True
    return False


def _load_payload(source: str | Path | dict[str, object]) -> dict[str, object]:
    if isinstance(source, dict):
        return source
    path = Path(source)
    return json.loads(path.read_text(encoding="utf-8"))


def _dict_copy(data: object) -> dict[str, object]:
    if not isinstance(data, dict):
        return {}
    return {str(key): value for key, value in data.items()}


def _schema_version_from_ref(schema_ref: str) -> int:
    match = _SCHEMA_VERSION_RE.search(str(schema_ref or "").strip())
    if match is None:
        return 0
    return int(match.group("version"))
