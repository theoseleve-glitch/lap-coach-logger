"""Domain models for the overlay management platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

OverlaySettingKind = Literal["bool", "int", "float", "string", "enum", "color"]
OverlayRuntimeMode = Literal["live", "preview"]
OverlayRuntimeStatus = Literal["inactive", "mounted", "hidden", "preview", "error"]
OverlayPremiumTier = Literal["free", "premium", "internal"]
OverlayAccessState = Literal["accessible", "preview_only", "locked", "hidden"]
OverlayAvailabilityStatus = Literal["available", "beta", "coming_soon", "internal", "deprecated"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _string_tuple(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(str(value) for value in values if str(value).strip())


def _string_list(values: object) -> list[str]:
    return list(_string_tuple(values))


def _dict_copy(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(k): v for k, v in value.items()}


@dataclass(slots=True, frozen=True)
class OverlaySettingOption:
    value: str
    label: str
    description: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "value": self.value,
            "label": self.label,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlaySettingOption:
        payload = _dict_copy(data)
        return cls(
            value=str(payload.get("value") or ""),
            label=str(payload.get("label") or payload.get("value") or ""),
            description=str(payload.get("description") or ""),
        )


@dataclass(slots=True, frozen=True)
class OverlaySettingField:
    key: str
    label: str
    kind: OverlaySettingKind
    section: str
    default: object
    description: str = ""
    min_value: int | float | None = None
    max_value: int | float | None = None
    step: int | float | None = None
    options: tuple[OverlaySettingOption, ...] = ()
    placeholder: str = ""
    unit: str = ""
    premium: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "key": self.key,
            "label": self.label,
            "kind": self.kind,
            "section": self.section,
            "default": self.default,
            "description": self.description,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "step": self.step,
            "options": [option.to_dict() for option in self.options],
            "placeholder": self.placeholder,
            "unit": self.unit,
            "premium": self.premium,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlaySettingField:
        payload = _dict_copy(data)
        return cls(
            key=str(payload.get("key") or ""),
            label=str(payload.get("label") or payload.get("key") or ""),
            kind=str(payload.get("kind") or "string"),
            section=str(payload.get("section") or "behavior"),
            default=payload.get("default"),
            description=str(payload.get("description") or ""),
            min_value=payload.get("min_value") if isinstance(payload.get("min_value"), (int, float)) else None,
            max_value=payload.get("max_value") if isinstance(payload.get("max_value"), (int, float)) else None,
            step=payload.get("step") if isinstance(payload.get("step"), (int, float)) else None,
            options=tuple(OverlaySettingOption.from_dict(item) for item in payload.get("options", [])),
            placeholder=str(payload.get("placeholder") or ""),
            unit=str(payload.get("unit") or ""),
            premium=bool(payload.get("premium")),
        )


@dataclass(slots=True, frozen=True)
class OverlayCapabilities:
    supports_multiple_instances: bool = True
    resizable: bool = True
    draggable: bool = True
    pinnable: bool = True
    scalable: bool = True
    preview_supported: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "supports_multiple_instances": self.supports_multiple_instances,
            "resizable": self.resizable,
            "draggable": self.draggable,
            "pinnable": self.pinnable,
            "scalable": self.scalable,
            "preview_supported": self.preview_supported,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayCapabilities:
        payload = _dict_copy(data)
        return cls(
            supports_multiple_instances=bool(payload.get("supports_multiple_instances", True)),
            resizable=bool(payload.get("resizable", True)),
            draggable=bool(payload.get("draggable", True)),
            pinnable=bool(payload.get("pinnable", True)),
            scalable=bool(payload.get("scalable", True)),
            preview_supported=bool(payload.get("preview_supported", True)),
        )


@dataclass(slots=True, frozen=True)
class OverlayLayoutHints:
    default_width: int = 420
    default_height: int = 220
    min_width: int = 180
    min_height: int = 120
    default_anchor: str = "top_right"
    supported_slots: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "default_width": self.default_width,
            "default_height": self.default_height,
            "min_width": self.min_width,
            "min_height": self.min_height,
            "default_anchor": self.default_anchor,
            "supported_slots": list(self.supported_slots),
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayLayoutHints:
        payload = _dict_copy(data)
        return cls(
            default_width=int(payload.get("default_width") or 420),
            default_height=int(payload.get("default_height") or 220),
            min_width=int(payload.get("min_width") or 180),
            min_height=int(payload.get("min_height") or 120),
            default_anchor=str(payload.get("default_anchor") or "top_right"),
            supported_slots=_string_tuple(payload.get("supported_slots")),
        )


@dataclass(slots=True, frozen=True)
class OverlayEntitlement:
    tier: OverlayPremiumTier = "free"
    feature_key: str = ""
    allow_preview_without_access: bool = True
    allow_settings_without_access: bool = True

    def to_dict(self) -> dict[str, object]:
        return {
            "tier": self.tier,
            "feature_key": self.feature_key,
            "allow_preview_without_access": self.allow_preview_without_access,
            "allow_settings_without_access": self.allow_settings_without_access,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayEntitlement:
        payload = _dict_copy(data)
        tier = str(payload.get("tier") or "free")
        return cls(
            tier="internal" if tier == "internal" else "premium" if tier == "premium" else "free",
            feature_key=str(payload.get("feature_key") or ""),
            allow_preview_without_access=bool(payload.get("allow_preview_without_access", True)),
            allow_settings_without_access=bool(payload.get("allow_settings_without_access", True)),
        )


@dataclass(slots=True, frozen=True)
class OverlayDefinition:
    overlay_id: str
    renderer_key: str
    display_name: str
    short_description: str
    category: str
    tags: tuple[str, ...] = ()
    search_keywords: tuple[str, ...] = ()
    settings_schema_ref: str = ""
    supported_simulators: tuple[str, ...] = ()
    default_enabled: bool = False
    availability_status: OverlayAvailabilityStatus = "available"
    hidden: bool = False
    internal: bool = False
    display_name_i18n_key: str = ""
    short_description_i18n_key: str = ""
    preview_asset: str = ""
    sort_order: int = 0
    settings_schema: tuple[OverlaySettingField, ...] = ()
    capabilities: OverlayCapabilities = field(default_factory=OverlayCapabilities)
    layout: OverlayLayoutHints = field(default_factory=OverlayLayoutHints)
    entitlement: OverlayEntitlement = field(default_factory=OverlayEntitlement)

    def default_settings(self) -> dict[str, object]:
        return {field.key: field.default for field in self.settings_schema}

    def setting_field(self, key: str) -> OverlaySettingField | None:
        for field in self.settings_schema:
            if field.key == key:
                return field
        return None

    @property
    def description(self) -> str:
        return self.short_description

    @property
    def default_size(self) -> tuple[int, int]:
        return (self.layout.default_width, self.layout.default_height)

    @property
    def default_anchor(self) -> str:
        return self.layout.default_anchor

    @property
    def premium_tier(self) -> OverlayPremiumTier:
        return self.entitlement.tier

    @property
    def preview_asset_ref(self) -> str:
        return self.preview_asset

    def to_dict(self) -> dict[str, object]:
        return {
            "overlay_id": self.overlay_id,
            "renderer_key": self.renderer_key,
            "display_name": self.display_name,
            "short_description": self.short_description,
            "category": self.category,
            "tags": list(self.tags),
            "search_keywords": list(self.search_keywords),
            "settings_schema_ref": self.settings_schema_ref,
            "supported_simulators": list(self.supported_simulators),
            "default_enabled": self.default_enabled,
            "availability_status": self.availability_status,
            "hidden": self.hidden,
            "internal": self.internal,
            "display_name_i18n_key": self.display_name_i18n_key,
            "short_description_i18n_key": self.short_description_i18n_key,
            "default_size": list(self.default_size),
            "default_anchor": self.default_anchor,
            "premium_tier": self.premium_tier,
            "preview_asset": self.preview_asset,
            "preview_asset_ref": self.preview_asset_ref,
            "sort_order": self.sort_order,
            "settings_schema": [field.to_dict() for field in self.settings_schema],
            "capabilities": self.capabilities.to_dict(),
            "layout": self.layout.to_dict(),
            "entitlement": self.entitlement.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayDefinition:
        payload = _dict_copy(data)
        return cls(
            overlay_id=str(payload.get("overlay_id") or ""),
            renderer_key=str(payload.get("renderer_key") or payload.get("overlay_id") or ""),
            display_name=str(payload.get("display_name") or payload.get("overlay_id") or ""),
            short_description=str(payload.get("short_description") or payload.get("description") or ""),
            category=str(payload.get("category") or "General"),
            tags=_string_tuple(payload.get("tags")),
            search_keywords=_string_tuple(payload.get("search_keywords")),
            settings_schema_ref=str(payload.get("settings_schema_ref") or ""),
            supported_simulators=_string_tuple(payload.get("supported_simulators")),
            default_enabled=bool(payload.get("default_enabled")),
            availability_status=str(payload.get("availability_status") or "available"),
            hidden=bool(payload.get("hidden")),
            internal=bool(payload.get("internal")),
            display_name_i18n_key=str(payload.get("display_name_i18n_key") or ""),
            short_description_i18n_key=str(payload.get("short_description_i18n_key") or ""),
            preview_asset=str(payload.get("preview_asset_ref") or payload.get("preview_asset") or ""),
            sort_order=int(payload.get("sort_order") or 0),
            settings_schema=tuple(OverlaySettingField.from_dict(item) for item in payload.get("settings_schema", [])),
            capabilities=OverlayCapabilities.from_dict(payload.get("capabilities")),
            layout=_layout_from_payload(payload),
            entitlement=_entitlement_from_payload(payload),
        )


@dataclass(slots=True)
class OverlayPlacement:
    x: int = 0
    y: int = 0
    width: int = 420
    height: int = 220
    scale: float = 1.0
    opacity: float = 1.0
    z_index: int = 0
    monitor_id: str = "primary"
    pinned: bool = False
    locked: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "scale": self.scale,
            "opacity": self.opacity,
            "z_index": self.z_index,
            "monitor_id": self.monitor_id,
            "pinned": self.pinned,
            "locked": self.locked,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayPlacement:
        payload = _dict_copy(data)
        return cls(
            x=int(payload.get("x") or 0),
            y=int(payload.get("y") or 0),
            width=int(payload.get("width") or 420),
            height=int(payload.get("height") or 220),
            scale=float(payload.get("scale") or 1.0),
            opacity=float(payload.get("opacity") or 1.0),
            z_index=int(payload.get("z_index") or 0),
            monitor_id=str(payload.get("monitor_id") or "primary"),
            pinned=bool(payload.get("pinned")),
            locked=bool(payload.get("locked")),
        )


@dataclass(slots=True)
class OverlayPresetScope:
    sim: str = ""
    car: str = ""
    driver: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "sim": self.sim,
            "car": self.car,
            "driver": self.driver,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayPresetScope:
        payload = _dict_copy(data)
        return cls(
            sim=str(payload.get("sim") or ""),
            car=str(payload.get("car") or ""),
            driver=str(payload.get("driver") or ""),
        )


@dataclass(slots=True)
class OverlayLayoutSlot:
    slot_id: str
    name: str
    instance_id: str = ""
    allowed_categories: tuple[str, ...] = ()
    allowed_overlay_ids: tuple[str, ...] = ()
    locked: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "slot_id": self.slot_id,
            "name": self.name,
            "instance_id": self.instance_id,
            "allowed_categories": list(self.allowed_categories),
            "allowed_overlay_ids": list(self.allowed_overlay_ids),
            "locked": self.locked,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayLayoutSlot:
        payload = _dict_copy(data)
        return cls(
            slot_id=str(payload.get("slot_id") or ""),
            name=str(payload.get("name") or payload.get("slot_id") or ""),
            instance_id=str(payload.get("instance_id") or ""),
            allowed_categories=_string_tuple(payload.get("allowed_categories")),
            allowed_overlay_ids=_string_tuple(payload.get("allowed_overlay_ids")),
            locked=bool(payload.get("locked")),
        )


@dataclass(slots=True)
class OverlayLayoutContext:
    simulator: str = ""
    car: str = ""
    session_type: str = ""
    driver: str = ""
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "simulator": self.simulator,
            "car": self.car,
            "session_type": self.session_type,
            "driver": self.driver,
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayLayoutContext:
        payload = _dict_copy(data)
        return cls(
            simulator=str(payload.get("simulator") or payload.get("sim") or ""),
            car=str(payload.get("car") or ""),
            session_type=str(payload.get("session_type") or payload.get("session") or ""),
            driver=str(payload.get("driver") or ""),
            tags=_string_tuple(payload.get("tags")),
        )


@dataclass(slots=True)
class OverlayAutoApplyRule:
    rule_id: str
    name: str = ""
    enabled: bool = True
    priority: int = 100
    simulators: tuple[str, ...] = ()
    cars: tuple[str, ...] = ()
    session_types: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "enabled": self.enabled,
            "priority": self.priority,
            "simulators": list(self.simulators),
            "cars": list(self.cars),
            "session_types": list(self.session_types),
            "tags": list(self.tags),
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayAutoApplyRule:
        payload = _dict_copy(data)
        return cls(
            rule_id=str(payload.get("rule_id") or payload.get("name") or ""),
            name=str(payload.get("name") or payload.get("rule_id") or ""),
            enabled=bool(payload.get("enabled", True)),
            priority=int(payload.get("priority") or 100),
            simulators=_string_tuple(payload.get("simulators") or payload.get("simulator_filter")),
            cars=_string_tuple(payload.get("cars") or payload.get("car_filter")),
            session_types=_string_tuple(payload.get("session_types") or payload.get("session_type_filter")),
            tags=_string_tuple(payload.get("tags")),
        )


@dataclass(slots=True, frozen=True)
class OverlayLayoutFieldChange:
    field: str
    before: object
    after: object

    def to_dict(self) -> dict[str, object]:
        return {
            "field": self.field,
            "before": self.before,
            "after": self.after,
        }


@dataclass(slots=True, frozen=True)
class OverlayLayoutInstanceChange:
    change_type: str
    overlay_id: str
    signature: str
    changes: tuple[OverlayLayoutFieldChange, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "change_type": self.change_type,
            "overlay_id": self.overlay_id,
            "signature": self.signature,
            "changes": [change.to_dict() for change in self.changes],
        }


@dataclass(slots=True, frozen=True)
class OverlayLayoutDiff:
    layout_a_id: str
    layout_b_id: str
    metadata_changes: tuple[OverlayLayoutFieldChange, ...] = ()
    instance_changes: tuple[OverlayLayoutInstanceChange, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "layout_a_id": self.layout_a_id,
            "layout_b_id": self.layout_b_id,
            "metadata_changes": [change.to_dict() for change in self.metadata_changes],
            "instance_changes": [change.to_dict() for change in self.instance_changes],
        }


@dataclass(slots=True)
class OverlayInstance:
    instance_id: str
    overlay_id: str
    preset_id: str
    name: str
    enabled: bool = True
    slot_id: str = ""
    placement: OverlayPlacement = field(default_factory=OverlayPlacement)
    settings: dict[str, object] = field(default_factory=dict)
    created_at_utc: str = field(default_factory=utc_now_iso)
    updated_at_utc: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, object]:
        return {
            "instance_id": self.instance_id,
            "overlay_id": self.overlay_id,
            "preset_id": self.preset_id,
            "name": self.name,
            "enabled": self.enabled,
            "slot_id": self.slot_id,
            "placement": self.placement.to_dict(),
            "settings": dict(self.settings),
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayInstance:
        payload = _dict_copy(data)
        return cls(
            instance_id=str(payload.get("instance_id") or ""),
            overlay_id=str(payload.get("overlay_id") or ""),
            preset_id=str(payload.get("preset_id") or ""),
            name=str(payload.get("name") or payload.get("overlay_id") or "Overlay"),
            enabled=bool(payload.get("enabled", True)),
            slot_id=str(payload.get("slot_id") or ""),
            placement=OverlayPlacement.from_dict(payload.get("placement")),
            settings=_dict_copy(payload.get("settings")),
            created_at_utc=str(payload.get("created_at_utc") or utc_now_iso()),
            updated_at_utc=str(payload.get("updated_at_utc") or payload.get("created_at_utc") or utc_now_iso()),
        )


@dataclass(slots=True)
class OverlayPreset:
    preset_id: str
    name: str
    description: str = ""
    scope: OverlayPresetScope = field(default_factory=OverlayPresetScope)
    favorite: bool = False
    simulator_filter: tuple[str, ...] = ()
    car_filter: tuple[str, ...] = ()
    session_type_filter: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    slots: list[OverlayLayoutSlot] = field(default_factory=list)
    instance_ids: list[str] = field(default_factory=list)
    active: bool = False
    auto_apply_rules: list[OverlayAutoApplyRule] = field(default_factory=list)
    version: int = 1
    created_at_utc: str = field(default_factory=utc_now_iso)
    updated_at_utc: str = field(default_factory=utc_now_iso)

    @property
    def layout_id(self) -> str:
        return self.preset_id

    @property
    def display_name(self) -> str:
        return self.name

    @property
    def last_modified(self) -> str:
        return self.updated_at_utc

    def to_dict(self) -> dict[str, object]:
        return {
            "preset_id": self.preset_id,
            "layout_id": self.layout_id,
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "scope": self.scope.to_dict(),
            "favorite": self.favorite,
            "simulator_filter": list(self.simulator_filter),
            "car_filter": list(self.car_filter),
            "session_type_filter": list(self.session_type_filter),
            "tags": list(self.tags),
            "slots": [slot.to_dict() for slot in self.slots],
            "instance_ids": list(self.instance_ids),
            "active": self.active,
            "auto_apply_rules": [rule.to_dict() for rule in self.auto_apply_rules],
            "version": self.version,
            "last_modified": self.last_modified,
            "created_at": self.created_at_utc,
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayPreset:
        payload = _dict_copy(data)
        scope = OverlayPresetScope.from_dict(payload.get("scope"))
        simulator_filter = _string_tuple(payload.get("simulator_filter")) or ((scope.sim,) if scope.sim else ())
        car_filter = _string_tuple(payload.get("car_filter")) or ((scope.car,) if scope.car else ())
        return cls(
            preset_id=str(payload.get("layout_id") or payload.get("preset_id") or ""),
            name=str(payload.get("display_name") or payload.get("name") or payload.get("layout_id") or payload.get("preset_id") or "Preset"),
            description=str(payload.get("description") or ""),
            scope=scope,
            favorite=bool(payload.get("favorite")),
            simulator_filter=simulator_filter,
            car_filter=car_filter,
            session_type_filter=_string_tuple(payload.get("session_type_filter")),
            tags=_string_tuple(payload.get("tags")),
            slots=[OverlayLayoutSlot.from_dict(item) for item in payload.get("slots", [])],
            instance_ids=_string_list(payload.get("instance_ids")),
            active=bool(payload.get("active")),
            auto_apply_rules=[OverlayAutoApplyRule.from_dict(item) for item in payload.get("auto_apply_rules", [])],
            version=int(payload.get("version") or 1),
            created_at_utc=str(payload.get("created_at_utc") or payload.get("created_at") or utc_now_iso()),
            updated_at_utc=str(payload.get("updated_at_utc") or payload.get("last_modified") or payload.get("created_at_utc") or utc_now_iso()),
        )


@dataclass(slots=True)
class OverlayBrowserPreferences:
    selected_category: str = ""
    selected_overlay_id: str = ""
    selected_layout_id: str = ""
    search_query: str = ""
    tag_filters: tuple[str, ...] = ()
    simulator_filters: tuple[str, ...] = ()
    availability_filters: tuple[str, ...] = ()
    status_filters: tuple[str, ...] = ()
    entitlement_filter: str = "all"
    favorites_only: bool = False
    include_hidden: bool = False
    updated_at_utc: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, object]:
        return {
            "selected_category": self.selected_category,
            "selected_overlay_id": self.selected_overlay_id,
            "selected_layout_id": self.selected_layout_id,
            "search_query": self.search_query,
            "tag_filters": list(self.tag_filters),
            "simulator_filters": list(self.simulator_filters),
            "availability_filters": list(self.availability_filters),
            "status_filters": list(self.status_filters),
            "entitlement_filter": self.entitlement_filter,
            "favorites_only": self.favorites_only,
            "include_hidden": self.include_hidden,
            "updated_at_utc": self.updated_at_utc,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayBrowserPreferences:
        payload = _dict_copy(data)
        return cls(
            selected_category=str(payload.get("selected_category") or ""),
            selected_overlay_id=str(payload.get("selected_overlay_id") or ""),
            selected_layout_id=str(payload.get("selected_layout_id") or ""),
            search_query=str(payload.get("search_query") or ""),
            tag_filters=_string_tuple(payload.get("tag_filters")),
            simulator_filters=_string_tuple(payload.get("simulator_filters")),
            availability_filters=_string_tuple(payload.get("availability_filters")),
            status_filters=_string_tuple(payload.get("status_filters")),
            entitlement_filter=str(payload.get("entitlement_filter") or "all"),
            favorites_only=bool(payload.get("favorites_only")),
            include_hidden=bool(payload.get("include_hidden")),
            updated_at_utc=str(payload.get("updated_at_utc") or utc_now_iso()),
        )


@dataclass(slots=True)
class OverlayLastUsedSettings:
    overlay_id: str
    settings_schema_ref: str = ""
    settings_schema_version: int = 0
    values: dict[str, object] = field(default_factory=dict)
    updated_at_utc: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, object]:
        return {
            "overlay_id": self.overlay_id,
            "settings_schema_ref": self.settings_schema_ref,
            "settings_schema_version": self.settings_schema_version,
            "values": dict(self.values),
            "updated_at_utc": self.updated_at_utc,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayLastUsedSettings:
        payload = _dict_copy(data)
        return cls(
            overlay_id=str(payload.get("overlay_id") or ""),
            settings_schema_ref=str(payload.get("settings_schema_ref") or ""),
            settings_schema_version=int(payload.get("settings_schema_version") or 0),
            values=_dict_copy(payload.get("values")),
            updated_at_utc=str(payload.get("updated_at_utc") or utc_now_iso()),
        )


@dataclass(slots=True)
class OverlayStateDocument:
    schema_version: int
    active_preset_id: str = ""
    layout_shortcuts: dict[str, str] = field(default_factory=lambda: {"A": "", "B": "", "C": ""})
    favorite_overlay_ids: list[str] = field(default_factory=list)
    browser_preferences: OverlayBrowserPreferences = field(default_factory=OverlayBrowserPreferences)
    last_used_settings: list[OverlayLastUsedSettings] = field(default_factory=list)
    presets: list[OverlayPreset] = field(default_factory=list)
    instances: list[OverlayInstance] = field(default_factory=list)
    created_at_utc: str = field(default_factory=utc_now_iso)
    updated_at_utc: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "active_preset_id": self.active_preset_id,
            "layout_shortcuts": dict(self.layout_shortcuts),
            "favorite_overlay_ids": list(self.favorite_overlay_ids),
            "browser_preferences": self.browser_preferences.to_dict(),
            "last_used_settings": [item.to_dict() for item in self.last_used_settings],
            "presets": [preset.to_dict() for preset in self.presets],
            "instances": [instance.to_dict() for instance in self.instances],
            "created_at_utc": self.created_at_utc,
            "updated_at_utc": self.updated_at_utc,
        }

    @classmethod
    def from_dict(cls, data: object) -> OverlayStateDocument:
        payload = _dict_copy(data)
        return cls(
            schema_version=int(payload.get("schema_version") or 1),
            active_preset_id=str(payload.get("active_preset_id") or ""),
            layout_shortcuts=_layout_shortcuts_from_payload(payload.get("layout_shortcuts")),
            favorite_overlay_ids=_string_list(payload.get("favorite_overlay_ids")),
            browser_preferences=OverlayBrowserPreferences.from_dict(payload.get("browser_preferences")),
            last_used_settings=[OverlayLastUsedSettings.from_dict(item) for item in payload.get("last_used_settings", [])],
            presets=[OverlayPreset.from_dict(item) for item in payload.get("presets", [])],
            instances=[OverlayInstance.from_dict(item) for item in payload.get("instances", [])],
            created_at_utc=str(payload.get("created_at_utc") or utc_now_iso()),
            updated_at_utc=str(payload.get("updated_at_utc") or payload.get("created_at_utc") or utc_now_iso()),
        )

    def preset_map(self) -> dict[str, OverlayPreset]:
        return {preset.preset_id: preset for preset in self.presets}

    def instance_map(self) -> dict[str, OverlayInstance]:
        return {instance.instance_id: instance for instance in self.instances}

    def last_used_settings_map(self) -> dict[str, OverlayLastUsedSettings]:
        return {item.overlay_id: item for item in self.last_used_settings}


@dataclass(slots=True, frozen=True)
class OverlayCatalogFilter:
    query: str = ""
    categories: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    premium_tiers: tuple[str, ...] = ()
    availability_statuses: tuple[str, ...] = ()
    simulators: tuple[str, ...] = ()
    favorites_only: bool = False
    entitled_only: bool = False
    include_locked: bool = True
    include_hidden: bool = False


@dataclass(slots=True, frozen=True)
class OverlayCatalogEntry:
    overlay_id: str
    display_name: str
    short_description: str
    category: str
    tags: tuple[str, ...]
    settings_schema_ref: str
    preview_asset: str
    favorite: bool
    premium_tier: OverlayPremiumTier
    availability_status: OverlayAvailabilityStatus
    hidden: bool
    entitled: bool
    entitlement_reason: str
    preview_supported: bool
    supported_simulators: tuple[str, ...]
    default_enabled: bool
    settings_sections: tuple[str, ...]
    access_state: OverlayAccessState = "accessible"
    can_activate: bool = True
    can_preview: bool = True
    can_view_settings: bool = True
    upsell_message: str = ""
    access_badge: str = ""


@dataclass(slots=True)
class OverlayRuntimeState:
    instance_id: str
    overlay_id: str
    preset_id: str
    mode: OverlayRuntimeMode
    status: OverlayRuntimeStatus = "inactive"
    visible: bool = False
    error: str = ""
    mounted_at_utc: str = field(default_factory=utc_now_iso)
    updated_at_utc: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, object]:
        return {
            "instance_id": self.instance_id,
            "overlay_id": self.overlay_id,
            "preset_id": self.preset_id,
            "mode": self.mode,
            "status": self.status,
            "visible": self.visible,
            "error": self.error,
            "mounted_at_utc": self.mounted_at_utc,
            "updated_at_utc": self.updated_at_utc,
        }


@dataclass(slots=True)
class OverlayPreviewSession:
    preview_id: str
    overlay_id: str
    settings: dict[str, object] = field(default_factory=dict)
    started_at_utc: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, object]:
        return {
            "preview_id": self.preview_id,
            "overlay_id": self.overlay_id,
            "settings": dict(self.settings),
            "started_at_utc": self.started_at_utc,
        }


@dataclass(slots=True, frozen=True)
class OverlayEvent:
    kind: str
    overlay_id: str = ""
    instance_id: str = ""
    preset_id: str = ""
    message: str = ""


@dataclass(slots=True, frozen=True)
class OverlayBrowserSnapshot:
    active_preset_id: str
    categories: tuple[str, ...]
    entries: tuple[OverlayCatalogEntry, ...]


def _layout_from_payload(payload: dict[str, object]) -> OverlayLayoutHints:
    if "layout" in payload:
        return OverlayLayoutHints.from_dict(payload.get("layout"))

    default_size = payload.get("default_size")
    width = 420
    height = 220
    if isinstance(default_size, (list, tuple)) and len(default_size) >= 2:
        if isinstance(default_size[0], (int, float)):
            width = int(default_size[0])
        if isinstance(default_size[1], (int, float)):
            height = int(default_size[1])
    return OverlayLayoutHints(
        default_width=width,
        default_height=height,
        default_anchor=str(payload.get("default_anchor") or "top_right"),
        supported_slots=_string_tuple(payload.get("supported_slots")),
    )


def _entitlement_from_payload(payload: dict[str, object]) -> OverlayEntitlement:
    if "entitlement" in payload:
        return OverlayEntitlement.from_dict(payload.get("entitlement"))
    tier = str(payload.get("premium_tier") or "free")
    return OverlayEntitlement(
        tier="internal" if tier == "internal" else "premium" if tier == "premium" else "free",
        feature_key=str(payload.get("feature_key") or ""),
    )


def _layout_shortcuts_from_payload(data: object) -> dict[str, str]:
    payload = _dict_copy(data)
    shortcuts = {"A": "", "B": "", "C": ""}
    for key in shortcuts:
        shortcuts[key] = str(payload.get(key) or payload.get(key.lower()) or "")
    return shortcuts
